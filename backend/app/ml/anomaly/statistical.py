from typing import List
from backend.app.ml.types import (
    LandslideFeatureVector,
    EnvironmentalAnomalyOutput,
    AnomalyLevel,
)
from backend.app.ml.anomaly.base import EnvironmentalAnomalyDetector


class StatisticalEnvironmentalAnomalyDetector(EnvironmentalAnomalyDetector):
    """
    Multivariate Statistical Environmental Anomaly Detector.
    Evaluates departures in rainfall burst rates, cumulative precipitation z-scores,
    soil pore saturation surges, and hydrologic loading against expected seasonal baselines.
    """

    def detect_anomaly(self, features: LandslideFeatureVector) -> EnvironmentalAnomalyOutput:
        # 1. Rainfall Anomaly Subscore (0.0 - 1.0)
        z = features.rainfall_z_score_24h.value
        r1 = features.rainfall_1h.value
        r24 = features.rainfall_24h.value

        # Z-score contribution (z >= 3.0 represents 99.7th percentile)
        z_norm = min(1.0, max(0.0, z / 3.5)) if z > 0 else 0.0
        # Instantaneous burst contribution (>30mm/h is extreme in NER)
        burst_norm = min(1.0, r1 / 35.0)
        # Absolute cumulative loading (>150mm/24h)
        load_norm = min(1.0, r24 / 160.0)

        rain_anomaly = round(min(1.0, (z_norm * 0.45) + (burst_norm * 0.30) + (load_norm * 0.25)), 3)

        # 2. Soil Wetness Anomaly Subscore (0.0 - 1.0)
        sm_surf = features.soil_moisture_surface.value
        sm_mid = features.soil_moisture_middle.value
        sm_trend = features.soil_moisture_trend_slope.value

        # Baseline soil moisture saturation departure (>75% indicates heightened pore pressure)
        sm_sat_norm = min(1.0, max(0.0, (sm_surf - 40.0) / 45.0))
        # Rate of rapid infiltration / saturation spike
        sm_rate_norm = min(1.0, max(0.0, sm_trend / 4.0)) if sm_trend > 0 else 0.0

        soil_anomaly = round(min(1.0, (sm_sat_norm * 0.70) + (sm_rate_norm * 0.30)), 3)

        # 3. Hydro-Atmospheric Loading Subscore (0.0 - 1.0)
        id_ratio = features.id_curve_ratio.value
        api = features.antecedent_precipitation_index.value
        wet_hours = features.consecutive_wet_hours.value

        id_norm = min(1.0, max(0.0, id_ratio / 2.0))
        api_norm = min(1.0, max(0.0, api / 120.0))
        wet_norm = min(1.0, max(0.0, wet_hours / 24.0))

        hydro_anomaly = round(min(1.0, (id_norm * 0.40) + (api_norm * 0.35) + (wet_norm * 0.25)), 3)

        # Composite Environmental Anomaly Score (0.0 - 1.0)
        total_anomaly = round(
            min(1.0, (rain_anomaly * 0.45) + (soil_anomaly * 0.35) + (hydro_anomaly * 0.20)),
            3
        )

        # Operational Anomaly Level
        if total_anomaly >= 0.85:
            level = AnomalyLevel.EXTREME
        elif total_anomaly >= 0.60:
            level = AnomalyLevel.SEVERE
        elif total_anomaly >= 0.30:
            level = AnomalyLevel.ELEVATED
        else:
            level = AnomalyLevel.NORMAL

        primary_abnormal_factors: List[str] = []
        if rain_anomaly >= 0.60:
            primary_abnormal_factors.append(f"Precipitation departure (z={z:.1f}, 24h={r24:.1f}mm)")
        if soil_anomaly >= 0.60:
            primary_abnormal_factors.append(f"Pore saturation surge (surface={sm_surf:.1f}%, slope={sm_trend:+.2f}%/step)")
        if hydro_anomaly >= 0.60:
            primary_abnormal_factors.append(f"Hydrologic loading (I-D ratio={id_ratio:.2f}, wet_hours={wet_hours:.0f}h)")

        is_statistically_anomalous = total_anomaly >= 0.60 or z >= 2.5 or sm_surf >= 85.0

        summary = (
            f"Environmental anomaly status: {level.value} (score={total_anomaly:.2f}). "
            f"Rainfall departure={rain_anomaly:.2f}, Soil saturation anomaly={soil_anomaly:.2f}, "
            f"Hydro loading anomaly={hydro_anomaly:.2f}."
        )

        return EnvironmentalAnomalyOutput(
            location_id=features.location_id,
            timestamp=features.timestamp,
            anomaly_score=total_anomaly,
            anomaly_level=level,
            rainfall_anomaly_score=rain_anomaly,
            soil_wetness_anomaly_score=soil_anomaly,
            atmospheric_anomaly_score=hydro_anomaly,
            primary_abnormal_factors=primary_abnormal_factors,
            is_statistically_anomalous=is_statistically_anomalous,
            summary=summary,
        )


statistical_anomaly_detector = StatisticalEnvironmentalAnomalyDetector()
