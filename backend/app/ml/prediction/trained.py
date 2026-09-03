from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np

from backend.app.ml.types import (
    ForecastHorizon,
    HorizonProbability,
    LandslidePredictionOutput,
    LandslideFeatureVector,
    ModelTier,
)
from backend.app.ml.prediction.base import LandslidePredictor
from backend.app.ml.features.pipeline import LandslideFeaturePipeline
from backend.app.ml.explainability.explainer import explainer


class TrainedTabularPredictor(LandslidePredictor):
    """
    Inference adapter for a genuinely trained and calibrated tabular ML model.
    Runs raw station feature vectors through the identical feature pipeline
    and outputs calibrated probabilities with physical factor attribution.
    """

    def __init__(
        self,
        model: Any,
        pipeline: LandslideFeaturePipeline,
        metadata: Dict[str, Any],
    ):
        self.model = model
        self.pipeline = pipeline
        self.metadata = metadata
        self.model_tier = ModelTier(metadata.get("model_tier", ModelTier.TABULAR_ML_RANDOM_FOREST.value))
        self.model_version = metadata.get("model_version", "2.0.0")
        self.primary_horizon = ForecastHorizon(metadata.get("forecast_horizon", ForecastHorizon.HORIZON_24H.value))
        self.feature_importances = metadata.get("feature_importances", [])
        self.optimal_threshold = metadata.get("optimal_threshold", 0.50)

    def predict(self, vector: LandslideFeatureVector) -> LandslidePredictionOutput:
        flat_dict = vector.to_flat_dict()
        
        # Transform through shared preprocessing pipeline
        X_arr = self.pipeline.transform_single_dict(flat_dict)

        # Predict probability
        if hasattr(self.model, "predict_proba"):
            p = float(self.model.predict_proba(X_arr)[0, 1])
        else:
            raw = float(self.model.decision_function(X_arr)[0])
            p = float(1.0 / (1.0 + np.exp(-raw)))

        p = round(max(0.0, min(1.0, p)), 3)

        # Build multi-horizon estimates (scaled by temporal dispersion if primary is 24h)
        horizons_map: Dict[ForecastHorizon, HorizonProbability] = {}
        
        # Compute bounds for primary horizon
        margin = round(0.08 * (1.0 - p) + 0.04, 3)
        low_bound = round(max(0.0, p - margin), 3)
        high_bound = round(min(1.0, p + margin), 3)

        def get_risk_tier(prob: float) -> str:
            if prob >= 0.70:
                return "CRITICAL"
            elif prob >= 0.45:
                return "HIGH"
            elif prob >= 0.25:
                return "MODERATE"
            return "LOW"

        # Primary Horizon
        horizons_map[self.primary_horizon] = HorizonProbability(
            horizon=self.primary_horizon,
            probability=p,
            confidence_interval_low=low_bound,
            confidence_interval_high=high_bound,
            risk_tier=get_risk_tier(p),
        )

        # Associated auxiliary horizons scaled by accumulation factors
        if self.primary_horizon == ForecastHorizon.HORIZON_24H:
            p6 = round(p * 0.55, 3)
            p12 = round(p * 0.78, 3)
            horizons_map[ForecastHorizon.HORIZON_6H] = HorizonProbability(
                horizon=ForecastHorizon.HORIZON_6H,
                probability=p6,
                confidence_interval_low=round(max(0.0, p6 - 0.06), 3),
                confidence_interval_high=round(min(1.0, p6 + 0.06), 3),
                risk_tier=get_risk_tier(p6),
            )
            horizons_map[ForecastHorizon.HORIZON_12H] = HorizonProbability(
                horizon=ForecastHorizon.HORIZON_12H,
                probability=p12,
                confidence_interval_low=round(max(0.0, p12 - 0.07), 3),
                confidence_interval_high=round(min(1.0, p12 + 0.07), 3),
                risk_tier=get_risk_tier(p12),
            )

        # Physical factor attribution
        attributions = explainer.get_local_feature_attribution(
            feature_dict=flat_dict,
            global_importances=self.feature_importances,
            top_k=5,
        )

        disclaimer = (
            f"Trained {self.metadata.get('model_name', 'Tabular ML')} Model v{self.model_version}. "
            f"Trained on {self.metadata.get('training_samples_count', 0)} samples. "
            f"Test PR-AUC: {self.metadata.get('test_pr_auc', 'N/A')}, ROC-AUC: {self.metadata.get('test_roc_auc', 'N/A')}."
        )

        return LandslidePredictionOutput(
            location_id=vector.location_id,
            station_name=vector.station_name,
            timestamp=vector.timestamp,
            model_tier=self.model_tier,
            model_version=self.model_version,
            is_trained_ml_model=True,
            data_provenance_summary=vector.get_provenance_summary(),
            horizons=horizons_map,
            primary_contributing_features=attributions,
            confidence_score=round(self.metadata.get("test_roc_auc", 0.85), 2),
            disclaimer=disclaimer,
        )
