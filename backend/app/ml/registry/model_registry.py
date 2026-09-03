import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import joblib

from backend.app.ml.types import (
    ModelTier,
    ModelMetadata,
)
from backend.app.ml.prediction.base import LandslidePredictor
from backend.app.ml.prediction.baseline import deterministic_baseline_predictor
from backend.app.ml.prediction.trained import TrainedTabularPredictor
from backend.app.ml.anomaly.base import EnvironmentalAnomalyDetector
from backend.app.ml.anomaly.statistical import statistical_anomaly_detector
from backend.app.ml.anomaly.isolation_forest import (
    IsolationForestAnomalyDetector,
    isolation_forest_anomaly_detector,
)
from backend.app.ml.features.pipeline import LandslideFeaturePipeline, shared_feature_pipeline

logger = logging.getLogger(__name__)


class LandslideModelRegistry:
    """
    Centralized Model Registry managing model versions, manifests,
    data provenance constraints, artifact loading, and active inference instances.
    """

    FEATURE_NAMES = LandslideFeaturePipeline.FEATURE_NAMES
    ARTIFACTS_DIR = Path("backend/models/landslide")

    def __init__(self):
        self._active_predictor: LandslidePredictor = deterministic_baseline_predictor
        self._active_anomaly_detector: EnvironmentalAnomalyDetector = statistical_anomaly_detector
        self._is_trained_model_active: bool = False
        self._active_metrics: Optional[Dict[str, Any]] = None
        self._registered_models: Dict[str, ModelMetadata] = {
            "baseline-deterministic": ModelMetadata(
                model_id="baseline-deterministic",
                model_name="NER Deterministic Landslide Physics Baseline",
                model_tier=ModelTier.BASELINE_DETERMINISTIC,
                version="1.0.0",
                is_trained=False,
                is_active=True,
                training_dataset_name="None (Empirical Physical Formulations)",
                training_samples_count=0,
                positive_events_count=0,
                negative_samples_count=0,
                feature_names=self.FEATURE_NAMES,
                validation_roc_auc=None,
                validation_f1_score=None,
                validation_brier_score=None,
                status_note=(
                    "Operational baseline. Provides physics-grounded probability bounds "
                    "while genuine tabular ML models await curated GSI/IMD regional training data."
                ),
            ),
        }

        # Attempt to discover and load any trained model artifact
        self.reload_artifacts()

    def reload_artifacts(self) -> bool:
        """
        Scans ARTIFACTS_DIR for serialized model artifacts.
        Loads trained model, pipeline, and metrics if present.
        """
        model_file = self.ARTIFACTS_DIR / "model.joblib"
        pipe_file = self.ARTIFACTS_DIR / "pipeline.joblib"
        meta_file = self.ARTIFACTS_DIR / "metadata.json"
        metrics_file = self.ARTIFACTS_DIR / "metrics.json"

        if model_file.exists() and pipe_file.exists() and meta_file.exists():
            try:
                with open(meta_file, "r") as f:
                    meta = json.load(f)

                with open(metrics_file, "r") as f:
                    metrics = json.load(f)

                model = joblib.load(model_file)
                pipeline = joblib.load(pipe_file)

                predictor = TrainedTabularPredictor(
                    model=model,
                    pipeline=pipeline,
                    metadata=meta,
                )

                self._active_predictor = predictor
                self._is_trained_model_active = True
                self._active_metrics = metrics

                trained_meta = ModelMetadata(
                    model_id=meta.get("model_id", "tabular-trained-ner"),
                    model_name=meta.get("model_name", "Trained Tabular Landslide Predictor"),
                    model_tier=ModelTier(meta.get("model_tier", ModelTier.TABULAR_ML_RANDOM_FOREST.value)),
                    version=meta.get("model_version", "2.0.0"),
                    is_trained=True,
                    is_active=True,
                    training_dataset_name="Regional Landslide Inventory & Telemetry Archive",
                    training_samples_count=meta.get("training_samples_count", 0),
                    positive_events_count=meta.get("positive_events_count", 0),
                    negative_samples_count=meta.get("negative_samples_count", 0),
                    feature_names=meta.get("feature_names", self.FEATURE_NAMES),
                    validation_roc_auc=meta.get("test_roc_auc"),
                    validation_f1_score=meta.get("test_f1_score"),
                    validation_brier_score=meta.get("test_brier_score"),
                    status_note="Trained and calibrated machine learning model loaded and operational.",
                )

                self._registered_models[trained_meta.model_id] = trained_meta
                # Demote baseline to inactive
                if "baseline-deterministic" in self._registered_models:
                    self._registered_models["baseline-deterministic"].is_active = False

                logger.info(
                    f"Loaded trained model artifact: {trained_meta.model_name} v{trained_meta.version} "
                    f"(Test ROC-AUC={trained_meta.validation_roc_auc}, Brier={trained_meta.validation_brier_score})"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to load trained model artifacts from {self.ARTIFACTS_DIR}: {e}")
                self._fallback_to_baseline()
                return False
        else:
            self._fallback_to_baseline()
            return False

    def _fallback_to_baseline(self):
        self._active_predictor = deterministic_baseline_predictor
        self._is_trained_model_active = False
        self._active_metrics = None
        if "baseline-deterministic" in self._registered_models:
            self._registered_models["baseline-deterministic"].is_active = True

    def get_active_predictor(self) -> LandslidePredictor:
        return self._active_predictor

    def get_active_anomaly_detector(self) -> EnvironmentalAnomalyDetector:
        return self._active_anomaly_detector

    def get_active_metrics(self) -> Optional[Dict[str, Any]]:
        return self._active_metrics

    def is_trained_model_active(self) -> bool:
        return self._is_trained_model_active

    def get_model_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        return self._registered_models.get(model_id)

    def list_models(self) -> List[ModelMetadata]:
        return list(self._registered_models.values())

    def get_registry_status(self) -> Dict[str, Any]:
        active_id = "baseline-deterministic"
        active_tier = ModelTier.BASELINE_DETERMINISTIC.value
        for m_id, m in self._registered_models.items():
            if m.is_active:
                active_id = m_id
                active_tier = m.model_tier.value
                break

        return {
            "registry_version": "1.0.0",
            "active_model_id": active_id,
            "active_model_tier": active_tier,
            "is_active_model_trained_ml": self._is_trained_model_active,
            "models_count": len(self._registered_models),
            "feature_count": len(self.FEATURE_NAMES),
            "features_monitored": self.FEATURE_NAMES,
            "registered_models": [m.model_dump() for m in self._registered_models.values()],
            "operational_status": "READY" if self._is_trained_model_active else "NOT_TRAINED",
            "model_status": "READY" if self._is_trained_model_active else "NOT_TRAINED",
            "active_model_version": "2.0.0",
            "training_pipeline_status": "MODEL_LOADED" if self._is_trained_model_active else "AWAITING_LABELLED_NER_DATASET",
        }



model_registry = LandslideModelRegistry()
