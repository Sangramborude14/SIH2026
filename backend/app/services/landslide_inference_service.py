from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.ml_forecast import LandslideForecastRecord
from backend.app.ml.features.feature_extractor import feature_extractor
from backend.app.ml.registry.model_registry import model_registry
from backend.app.ml.types import ForecastHorizon
from backend.app.schemas.ml_forecast import (
    ForecastHorizonDetail,
    CurrentConditionSummary,
    EnvironmentalAnomalySummary,
    LocationForecastResponse,
    MultiLocationForecastResponse,
    GISHeatmapFeature,
    GISHeatmapResponse,
)
from backend.app.core.logging import logger


class LandslideInferenceService:
    """
    Production Real-Time ML Inference Service.
    Transforms live weather observations, historical sequences, and static terrain features
    into calibrated future landslide probabilities across feasible forecast horizons.
    Ensures absolute semantic separation between deterministic risk, anomaly scores, and ML probabilities.
    """

    @staticmethod
    def evaluate_data_freshness(latest_obs_time: Optional[datetime]) -> str:
        if not latest_obs_time:
            return "STALE"
        now = datetime.now(timezone.utc)
        if latest_obs_time.tzinfo is None:
            latest_obs_time = latest_obs_time.replace(tzinfo=timezone.utc)
        age = now - latest_obs_time
        if age < timedelta(hours=3):
            return "FRESH"
        elif age < timedelta(hours=12):
            return "AGING"
        return "STALE"

    @staticmethod
    def determine_risk_class(prob: float) -> str:
        if prob >= 0.70:
            return "CRITICAL"
        elif prob >= 0.50:
            return "HIGH"
        elif prob >= 0.30:
            return "MODERATE"
        return "LOW"

    async def generate_forecast_for_location(
        self,
        session: Optional[AsyncSession],
        location: Location,
        latest_obs: Optional[WeatherObservation],
        obs_history: List[WeatherObservation],
        deterministic_risk_score: float = 10.0,
        deterministic_risk_level: str = "LOW",
        persist: bool = True,
    ) -> LocationForecastResponse:
        now = datetime.now(timezone.utc)
        data_ts = latest_obs.timestamp if latest_obs else now
        if data_ts.tzinfo is None:
            data_ts = data_ts.replace(tzinfo=timezone.utc)

        data_freshness = self.evaluate_data_freshness(latest_obs.timestamp if latest_obs else None)

        # 1. Build standardized 25-feature vector
        vector = feature_extractor.extract_features(
            location=location,
            current_obs=latest_obs,
            obs_history=obs_history,
        )

        # 2. Task A: Multi-Signal Environmental Anomaly Detection
        detector = model_registry.get_active_anomaly_detector()
        anomaly_output = detector.detect_anomaly(vector)
        anomaly_summary = EnvironmentalAnomalySummary(
            score=round(anomaly_output.anomaly_score, 3),
            status=anomaly_output.anomaly_level.value,
            rainfall_anomaly_score=round(anomaly_output.rainfall_anomaly_score, 3),
            soil_anomaly_score=round(anomaly_output.soil_wetness_anomaly_score, 3),
            is_statistically_anomalous=anomaly_output.is_statistically_anomalous,
        )

        # 3. Task B: ML Landslide Probability Forecasting
        forecast_dict: Dict[str, ForecastHorizonDetail] = {}
        model_contributions: List[Dict[str, Any]] = []
        is_trained = model_registry.is_trained_model_active()
        model_status = "READY" if is_trained else "NOT_TRAINED"
        model_version = "2.0.0"
        disclaimer = ""

        if is_trained:
            predictor = model_registry.get_active_predictor()
            pred_res = predictor.predict(vector)
            model_version = pred_res.model_version
            disclaimer = pred_res.disclaimer

            for horizon_enum, horizon_pred in pred_res.horizons.items():
                h_str = horizon_enum.value.lower()  # "24h", "12h", "6h"
                prob = horizon_pred.probability
                r_class = self.determine_risk_class(prob)

                hours = 24 if "24" in h_str else (12 if "12" in h_str else 6)
                w_start = now
                w_end = now + timedelta(hours=hours)

                forecast_dict[h_str] = ForecastHorizonDetail(
                    landslide_probability=round(prob, 4),
                    risk_class=r_class,
                    target_window_start=w_start,
                    target_window_end=w_end,
                    decision_threshold=0.50,
                    threshold_exceeded=(prob >= 0.50),
                )

            for feat_c in pred_res.primary_contributing_features:
                if isinstance(feat_c, dict):
                    f_name = feat_c.get("feature", "unknown")
                    f_imp = feat_c.get("importance_score", 0.0)
                    f_meth = feat_c.get("method", "LOCAL_FEATURE_ATTRIBUTION")
                else:
                    f_name = getattr(feat_c, "feature", "unknown")
                    f_imp = getattr(feat_c, "importance_score", 0.0)
                    f_meth = getattr(feat_c, "method", "LOCAL_FEATURE_ATTRIBUTION")

                model_contributions.append({
                    "feature": f_name,
                    "importance_score": round(float(f_imp), 4),
                    "method": f_meth,
                })

        else:
            disclaimer = (
                "ML FORECAST UNAVAILABLE: Model is in NOT_TRAINED status. "
                "Forecasts rely strictly on the deterministic baseline physics engine."
            )

        # 4. Generate transparent Observed Risk Indicators (physical ground-truth observations)
        observed_drivers: List[str] = []
        rain_24h = vector.rainfall_24h.value
        rain_72h = vector.rainfall_72h.value
        slope = vector.slope_angle.value
        soil_m = vector.soil_moisture_surface.value
        elev = vector.elevation.value

        if rain_24h >= 100:
            observed_drivers.append(f"24h Rainfall: {rain_24h:.1f} mm (Extreme monsoonal deluge - threshold exceeded)")
        elif rain_24h >= 50:
            observed_drivers.append(f"24h Rainfall: {rain_24h:.1f} mm (Substantial precipitation)")

        if rain_72h >= 150:
            observed_drivers.append(f"72h Antecedent Rain: {rain_72h:.1f} mm (High regolith pre-saturation)")

        if slope >= 35:
            observed_drivers.append(f"Topography: {slope:.1f}° slope gradient (Steep mountain failure corridor)")

        if soil_m >= 80:
            observed_drivers.append(f"Soil Saturation: {soil_m:.1f}% (Critically saturated pore-water pressure)")
        elif soil_m >= 65:
            observed_drivers.append(f"Soil Saturation: {soil_m:.1f}% (Elevated moisture content)")

        if not observed_drivers:
            observed_drivers.append("All observed environmental indicators currently within stable baseline tolerances.")

        # 5. Database Persistence
        if persist and session and is_trained:
            for h_str, h_detail in forecast_dict.items():
                rec = LandslideForecastRecord(
                    location_id=location.id,
                    prediction_timestamp=now,
                    forecast_horizon=h_str.upper(),
                    target_window_start=h_detail.target_window_start,
                    target_window_end=h_detail.target_window_end,
                    probability=h_detail.landslide_probability,
                    model_version=model_version,
                    feature_schema_version="2.0.0",
                    data_timestamp=data_ts,
                    data_freshness=data_freshness,
                    model_status=model_status,
                    decision_threshold=h_detail.decision_threshold,
                    warning_status=h_detail.risk_class,
                    primary_features_compact={
                        "slope_angle": slope,
                        "rainfall_24h": rain_24h,
                        "rainfall_72h": rain_72h,
                        "soil_moisture": soil_m,
                    },
                )
                session.add(rec)

        return LocationForecastResponse(
            location_id=location.id,
            station_name=location.name,
            district=location.district,
            state=location.state,
            latitude=location.latitude,
            longitude=location.longitude,
            elevation=location.elevation,
            slope_angle=location.slope_angle,
            baseline_susceptibility=location.susceptibility_score,
            generated_at=now,
            data_timestamp=data_ts,
            data_freshness=data_freshness,
            model_version=model_version,
            model_status=model_status,
            forecast_available=is_trained,
            current_condition=CurrentConditionSummary(
                deterministic_risk_score=deterministic_risk_score,
                risk_level=deterministic_risk_level,
            ),
            environmental_anomaly=anomaly_summary,
            forecast=forecast_dict,
            observed_drivers=observed_drivers,
            model_contributions=model_contributions,
            disclaimer=disclaimer,
        )

    async def generate_forecast_for_all_locations(
        self,
        session: AsyncSession,
        locations: List[Location],
        persist: bool = True,
    ) -> MultiLocationForecastResponse:
        now = datetime.now(timezone.utc)
        forecasts: List[LocationForecastResponse] = []
        highest_prob = 0.0
        highest_loc_name: Optional[str] = None

        for loc in locations:
            # Fetch latest observations for location
            stmt = (
                select(WeatherObservation)
                .where(WeatherObservation.location_id == loc.id)
                .order_by(WeatherObservation.timestamp.asc())
            )
            result = await session.execute(stmt)
            observations = list(result.scalars().all())
            latest_obs = observations[-1] if observations else None

            # Fetch latest risk assessment if present
            from backend.app.models.risk import RiskAssessment
            r_stmt = (
                select(RiskAssessment)
                .where(RiskAssessment.location_id == loc.id)
                .order_by(RiskAssessment.timestamp.desc())
                .limit(1)
            )
            r_res = await session.execute(r_stmt)
            latest_risk = r_res.scalars().first()
            det_score = latest_risk.risk_score if latest_risk else 10.0
            det_level = latest_risk.risk_level if latest_risk else "LOW"

            fc = await self.generate_forecast_for_location(
                session=session,
                location=loc,
                latest_obs=latest_obs,
                obs_history=observations,
                deterministic_risk_score=det_score,
                deterministic_risk_level=det_level,
                persist=persist,
            )
            forecasts.append(fc)

            # Check 24h probability for highest rank
            p24 = fc.forecast.get("24h", ForecastHorizonDetail(
                target_window_start=now,
                target_window_end=now,
            )).landslide_probability or 0.0

            if p24 > highest_prob:
                highest_prob = p24
                highest_loc_name = loc.name

        is_trained = model_registry.is_trained_model_active()
        return MultiLocationForecastResponse(
            generated_at=now,
            model_status="READY" if is_trained else "NOT_TRAINED",
            model_version="2.0.0",
            locations_count=len(locations),
            highest_forecast_probability=highest_prob if is_trained else None,
            highest_risk_location=highest_loc_name,
            forecasts=forecasts,
        )

    def generate_gis_heatmap(
        self,
        multi_forecast: MultiLocationForecastResponse,
    ) -> GISHeatmapResponse:
        features: List[GISHeatmapFeature] = []

        for fc in multi_forecast.forecasts:
            p24_detail = fc.forecast.get("24h")
            p24_val = p24_detail.landslide_probability if p24_detail else None
            r_class = p24_detail.risk_class if p24_detail else "LOW"

            feat = GISHeatmapFeature(
                type="Feature",
                geometry={
                    "type": "Point",
                    "coordinates": [fc.longitude, fc.latitude],
                },
                properties={
                    "location_id": fc.location_id,
                    "station_name": fc.station_name,
                    "district": fc.district,
                    "state": fc.state,
                    "latitude": fc.latitude,
                    "longitude": fc.longitude,
                    "elevation": fc.elevation,
                    "slope_angle": fc.slope_angle,
                    "baseline_susceptibility": fc.baseline_susceptibility,
                    "deterministic_risk_score": fc.current_condition.deterministic_risk_score,
                    "deterministic_risk_level": fc.current_condition.risk_level,
                    "anomaly_score": fc.environmental_anomaly.score,
                    "anomaly_level": fc.environmental_anomaly.status,
                    "landslide_probability_24h": p24_val,
                    "risk_class_24h": r_class,
                    "forecast_horizon": "24H",
                    "data_freshness": fc.data_freshness,
                    "model_version": fc.model_version,
                    "model_status": fc.model_status,
                    "observation_timestamp": fc.data_timestamp.isoformat(),
                    "prediction_timestamp": fc.generated_at.isoformat(),
                    "observed_drivers": fc.observed_drivers,
                },
            )
            features.append(feat)

        return GISHeatmapResponse(
            type="FeatureCollection",
            generated_at=multi_forecast.generated_at,
            forecast_horizon="24H",
            features=features,
        )


landslide_inference_service = LandslideInferenceService()
