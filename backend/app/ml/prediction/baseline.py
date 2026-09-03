import math
from typing import Dict, Any, List
from datetime import datetime, timezone

from backend.app.ml.types import (
    LandslideFeatureVector,
    LandslidePredictionOutput,
    ForecastHorizon,
    HorizonProbability,
    ModelTier,
)
from backend.app.ml.prediction.base import LandslidePredictor


class DeterministicBaselinePredictor(LandslidePredictor):
    """
    Transparent, uncalibrated deterministic baseline predictor.
    Serves as an architectural placeholder implementing the LandslidePredictor protocol.
    DOES NOT claim to be a trained numerical ML model.
    Provides estimated occurrence probabilities across 6h, 12h, and 24h horizons based on
    physical slope geometry, Antecedent Precipitation Index, and pore saturation profiles.
    """

    VERSION = "baseline-deterministic-v1.0"

    def _calculate_base_failure_affinity(self, features: LandslideFeatureVector) -> float:
        """
        Computes static-dynamic physical susceptibility affinity in [0.0, 1.0].
        """
        slope = features.slope_angle.value
        susc = features.baseline_susceptibility.value
        sm = features.soil_moisture_surface.value
        id_ratio = features.id_curve_ratio.value
        api = features.antecedent_precipitation_index.value

        # Slope factor (critical beyond 35 degrees)
        slope_factor = min(1.0, max(0.0, (slope - 15.0) / 30.0))
        # Soil moisture saturation factor (critical beyond 75%)
        soil_factor = min(1.0, max(0.0, (sm - 35.0) / 50.0))
        # Precipitation loading factor
        rain_factor = min(1.0, (id_ratio * 0.5) + min(0.5, api / 100.0))

        # Composite logit
        z = -3.5 + (slope_factor * 2.2) + (soil_factor * 2.5) + (rain_factor * 2.8) + (susc * 1.5)
        # Sigmoidal mapping to probability
        prob = 1.0 / (1.0 + math.exp(-max(-8.0, min(8.0, z))))
        return prob

    def predict(self, features: LandslideFeatureVector) -> LandslidePredictionOutput:
        base_prob = self._calculate_base_failure_affinity(features)

        # Scale probability across forecast horizons:
        # Near-term (6h) requires acute burst; Longer-term (24h) incorporates accumulation
        r1 = features.rainfall_1h.value
        r24 = features.rainfall_24h.value

        # 6-Hour Horizon: heavily influenced by immediate burst rate and slope
        p6_factor = 0.85 if r1 > 20.0 else 0.65
        p6 = min(0.95, max(0.02, round(base_prob * p6_factor, 3)))

        # 12-Hour Horizon: standard outlook
        p12 = min(0.96, max(0.03, round(base_prob * 0.90, 3)))

        # 24-Hour Horizon: full antecedent saturation impact
        p24_factor = 1.10 if r24 > 90.0 else 1.0
        p24 = min(0.98, max(0.04, round(base_prob * p24_factor, 3)))

        def map_tier(p: float) -> str:
            if p >= 0.75:
                return "CRITICAL"
            elif p >= 0.50:
                return "HIGH"
            elif p >= 0.25:
                return "MODERATE"
            return "LOW"

        horizons: Dict[ForecastHorizon, HorizonProbability] = {
            ForecastHorizon.HORIZON_6H: HorizonProbability(
                horizon=ForecastHorizon.HORIZON_6H,
                probability=p6,
                confidence_interval_low=max(0.0, round(p6 - 0.12, 3)),
                confidence_interval_high=min(1.0, round(p6 + 0.12, 3)),
                risk_tier=map_tier(p6),
            ),
            ForecastHorizon.HORIZON_12H: HorizonProbability(
                horizon=ForecastHorizon.HORIZON_12H,
                probability=p12,
                confidence_interval_low=max(0.0, round(p12 - 0.10, 3)),
                confidence_interval_high=min(1.0, round(p12 + 0.10, 3)),
                risk_tier=map_tier(p12),
            ),
            ForecastHorizon.HORIZON_24H: HorizonProbability(
                horizon=ForecastHorizon.HORIZON_24H,
                probability=p24,
                confidence_interval_low=max(0.0, round(p24 - 0.14, 3)),
                confidence_interval_high=min(1.0, round(p24 + 0.14, 3)),
                risk_tier=map_tier(p24),
            ),
        }

        # Contributing features ranking
        contributions = [
            {"feature": "soil_moisture_surface", "value": features.soil_moisture_surface.value, "unit": "%", "weight": 0.30},
            {"feature": "slope_angle", "value": features.slope_angle.value, "unit": "°", "weight": 0.25},
            {"feature": "rainfall_24h", "value": features.rainfall_24h.value, "unit": "mm", "weight": 0.25},
            {"feature": "id_curve_ratio", "value": features.id_curve_ratio.value, "unit": "ratio", "weight": 0.10},
            {"feature": "baseline_susceptibility", "value": features.baseline_susceptibility.value, "unit": "index", "weight": 0.10},
        ]
        contributions.sort(key=lambda x: x["weight"], reverse=True)

        disclaimer = (
            "Model-estimated probabilities are derived from an uncalibrated deterministic baseline. "
            "A genuinely trained ML classifier is awaiting curated GSI/IMD regional training data. "
            "Do NOT interpret probabilities as scientifically certified until model training completes."
        )

        return LandslidePredictionOutput(
            location_id=features.location_id,
            station_name=features.station_name,
            timestamp=features.timestamp,
            model_tier=ModelTier.BASELINE_DETERMINISTIC,
            model_version=self.VERSION,
            is_trained_ml_model=False,
            data_provenance_summary=features.get_provenance_summary(),
            horizons=horizons,
            primary_contributing_features=contributions,
            confidence_score=0.72,
            disclaimer=disclaimer,
        )


deterministic_baseline_predictor = DeterministicBaselinePredictor()
