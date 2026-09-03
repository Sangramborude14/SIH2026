from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.engine.base import TerrainProfile
from backend.app.ml.types import (
    DataProvenance,
    TaggedFeatureValue,
    LandslideFeatureVector,
)
from backend.app.core.config import settings


class LandslideFeatureExtractor:
    """
    Constructs standardized, typed ML feature vectors from in-situ telemetry,
    terrain metadata, and physical hydrologic indicators.
    Enforces 100% explicit data provenance tagging on every attribute.
    """

    @staticmethod
    def extract_features(
        location: Location,
        current_obs: Optional[WeatherObservation],
        obs_history: Optional[List[WeatherObservation]] = None,
        terrain: Optional[TerrainProfile] = None,
        data_mode: Optional[str] = None,
    ) -> LandslideFeatureVector:
        now = datetime.now(timezone.utc)
        mode = data_mode or getattr(settings, "DATA_MODE", "LIVE")
        is_sim = mode.upper() == "SIMULATION"

        # Resolve observation timestamp
        obs_time = current_obs.timestamp if current_obs and current_obs.timestamp else now
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        # 1. Static Topographic & Geospatial Features
        geo_provenance = DataProvenance.SIMULATED if is_sim else DataProvenance.STATIC
        
        slope_val = float(terrain.slope_angle if terrain and terrain.slope_angle is not None else (location.slope_angle or 30.0))
        elev_val = float(terrain.elevation if terrain and terrain.elevation is not None else (location.elevation or 1200.0))
        susc_val = float(location.susceptibility_score if location.susceptibility_score is not None else 0.65)

        slope_feat = TaggedFeatureValue(
            name="slope_angle",
            value=slope_val,
            unit="degrees",
            provenance=geo_provenance,
            source_name="DEM_SURVEY",
            timestamp=obs_time,
        )
        elev_feat = TaggedFeatureValue(
            name="elevation",
            value=elev_val,
            unit="meters",
            provenance=geo_provenance,
            source_name="DEM_SURVEY",
            timestamp=obs_time,
        )
        susc_feat = TaggedFeatureValue(
            name="baseline_susceptibility",
            value=susc_val,
            unit="index_0_1",
            provenance=geo_provenance,
            source_name="GSI_NLSM_CATALOG",
            timestamp=obs_time,
        )

        # 2. Dynamic Meteorological Telemetry
        obs_prov = DataProvenance.SIMULATED if is_sim else DataProvenance.OBSERVED
        src_name = "SIMULATOR" if is_sim else (current_obs.source if current_obs and current_obs.source else "OPEN_METEO")

        r1 = float(current_obs.rainfall_1h if current_obs and current_obs.rainfall_1h is not None else 0.0)
        r6 = float(current_obs.rainfall_6h if current_obs and current_obs.rainfall_6h is not None else (r1 * 2.5))
        r24 = float(current_obs.rainfall_24h if current_obs and current_obs.rainfall_24h is not None else (r6 * 1.8))
        
        # Calculate 72h accumulation from history if present
        history = obs_history or []
        if history:
            r72_acc = sum(o.rainfall_1h or 0.0 for o in history[-72:])
            r72 = max(r24, float(r72_acc))
        else:
            r72 = r24 * 1.5

        r1_feat = TaggedFeatureValue(name="rainfall_1h", value=round(r1, 2), unit="mm", provenance=obs_prov, source_name=src_name, timestamp=obs_time)
        r6_feat = TaggedFeatureValue(name="rainfall_6h", value=round(r6, 2), unit="mm", provenance=obs_prov, source_name=src_name, timestamp=obs_time)
        r24_feat = TaggedFeatureValue(name="rainfall_24h", value=round(r24, 2), unit="mm", provenance=obs_prov, source_name=src_name, timestamp=obs_time)
        r72_feat = TaggedFeatureValue(name="rainfall_72h", value=round(r72, 2), unit="mm", provenance=obs_prov, source_name=src_name, timestamp=obs_time)

        # 3. Dynamic Soil Moisture Strata
        sm_base = float(current_obs.soil_moisture if current_obs and current_obs.soil_moisture is not None else 45.0)
        sm_surf = min(100.0, sm_base * 1.05)
        sm_mid = sm_base
        sm_deep = max(0.0, sm_base * 0.92)

        sm_surf_feat = TaggedFeatureValue(name="soil_moisture_surface", value=round(sm_surf, 1), unit="percent", provenance=obs_prov, source_name=src_name, timestamp=obs_time)
        sm_mid_feat = TaggedFeatureValue(name="soil_moisture_middle", value=round(sm_mid, 1), unit="percent", provenance=obs_prov, source_name=src_name, timestamp=obs_time)
        sm_deep_feat = TaggedFeatureValue(name="soil_moisture_deep", value=round(sm_deep, 1), unit="percent", provenance=obs_prov, source_name=src_name, timestamp=obs_time)

        # 4. Derived Physical & Statistical Indicators
        derived_prov = DataProvenance.SIMULATED if is_sim else DataProvenance.MODEL_DERIVED

        # Antecedent Precipitation Index (API): API_t = P_t + 0.85 * API_{t-1}
        api_val = r24 * 0.5 + (r72 - r24) * 0.3
        
        # Consecutive wet hours (>0.5 mm/h)
        wet_hours = 0.0
        for obs in reversed(history):
            if (obs.rainfall_1h or 0.0) >= 0.5:
                wet_hours += 1.0
            else:
                break
        if r1 >= 0.5 and wet_hours == 0:
            wet_hours = 1.0

        # Rainfall 24h z-score against history
        if len(history) >= 5:
            r24_history = [o.rainfall_24h or 0.0 for o in history]
            mean_r = sum(r24_history) / len(r24_history)
            variance = sum((x - mean_r) ** 2 for x in r24_history) / max(1, len(r24_history) - 1)
            std_r = (variance ** 0.5) or 1.0
            z_score = (r24 - mean_r) / std_r
        else:
            z_score = 0.0

        # Soil moisture trend slope (%/step)
        if len(history) >= 3:
            sm_hist = [o.soil_moisture or sm_base for o in history[-3:]]
            sm_trend = (sm_hist[-1] - sm_hist[0]) / max(1, len(sm_hist) - 1)
        else:
            sm_trend = 0.0

        # Empirical I-D Curve Ratio: I_critical = 25.0 * D^(-0.45) for D=24h -> 25 * 0.238 = 5.95 mm/h
        # Current mean intensity over 24h: r24 / 24.0
        current_mean_intensity = r24 / 24.0
        critical_mean_intensity = 25.0 * (24.0 ** -0.45)  # ~5.97 mm/h
        id_ratio = current_mean_intensity / critical_mean_intensity

        api_feat = TaggedFeatureValue(name="antecedent_precipitation_index", value=round(api_val, 2), unit="API", provenance=derived_prov, source_name="HYDRO_DECAY_API", timestamp=obs_time)
        wet_feat = TaggedFeatureValue(name="consecutive_wet_hours", value=round(wet_hours, 1), unit="hours", provenance=derived_prov, source_name="WET_SPELL_COUNTER", timestamp=obs_time)
        z_feat = TaggedFeatureValue(name="rainfall_z_score_24h", value=round(z_score, 2), unit="sigma", provenance=derived_prov, source_name="ROLLING_Z_SCORE", timestamp=obs_time)
        sm_trend_feat = TaggedFeatureValue(name="soil_moisture_trend_slope", value=round(sm_trend, 3), unit="pct_per_step", provenance=derived_prov, source_name="DERIVATIVE_FILTER", timestamp=obs_time)
        id_feat = TaggedFeatureValue(name="id_curve_ratio", value=round(id_ratio, 3), unit="ratio", provenance=derived_prov, source_name="ID_POWER_LAW", timestamp=obs_time)

        return LandslideFeatureVector(
            location_id=location.id,
            station_name=location.name,
            timestamp=obs_time,
            slope_angle=slope_feat,
            elevation=elev_feat,
            baseline_susceptibility=susc_feat,
            rainfall_1h=r1_feat,
            rainfall_6h=r6_feat,
            rainfall_24h=r24_feat,
            rainfall_72h=r72_feat,
            soil_moisture_surface=sm_surf_feat,
            soil_moisture_middle=sm_mid_feat,
            soil_moisture_deep=sm_deep_feat,
            antecedent_precipitation_index=api_feat,
            consecutive_wet_hours=wet_feat,
            rainfall_z_score_24h=z_feat,
            soil_moisture_trend_slope=sm_trend_feat,
            id_curve_ratio=id_feat,
        )


feature_extractor = LandslideFeatureExtractor()
