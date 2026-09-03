from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.ensemble import IsolationForest

from backend.app.ml.types import (
    AnomalyLevel,
    EnvironmentalAnomalyOutput,
    LandslideFeatureVector,
)
from backend.app.ml.anomaly.base import EnvironmentalAnomalyDetector


class IsolationForestAnomalyDetector(EnvironmentalAnomalyDetector):
    """
    Unsupervised multidimensional anomaly detector using Isolation Forest.
    Learns normal joint distributions of rainfall windows, intensity,
    antecedent moisture, and soil saturation.
    
    PURPOSE:
      "Current environmental state is unusual relative to learned normal conditions."
    INVARIANT:
      Its output is NOT a landslide probability.
    """

    ANOMALY_FEATURE_NAMES = [
        "rainfall_1h",
        "rainfall_6h",
        "rainfall_24h",
        "rainfall_72h",
        "soil_moisture_surface",
        "antecedent_precipitation_index",
        "rainfall_z_score_24h",
        "soil_moisture_trend_slope",
    ]

    def __init__(
        self,
        contamination: float = 0.05,
        random_state: int = 42,
        model_version: str = "iforest-v1.0.0"
    ):
        self.contamination = contamination
        self.random_state = random_state
        self.model_version = model_version
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=random_state,
        )
        self.is_fitted = False

    def fit(self, X_baseline: np.ndarray) -> "IsolationForestAnomalyDetector":
        """
        Fits the Isolation Forest on un-anomalous baseline historical environmental data.
        """
        if X_baseline.ndim == 1:
            X_baseline = X_baseline.reshape(1, -1)
        self.model.fit(X_baseline)
        self.is_fitted = True
        return self

    def detect_anomaly(self, vector: LandslideFeatureVector) -> EnvironmentalAnomalyOutput:
        """
        Evaluates current environmental vector against the fitted isolation forest.
        """
        # Extract features for anomaly model
        feat_dict = vector.to_flat_dict()
        row = [feat_dict.get(k, 0.0) for k in self.ANOMALY_FEATURE_NAMES]
        arr = np.array(row, dtype=np.float64).reshape(1, -1)

        if not self.is_fitted:
            # Fall back to heuristic scoring if Isolation Forest not yet trained
            r1 = vector.rainfall_1h.value
            r24 = vector.rainfall_24h.value
            sm = vector.soil_moisture_surface.value
            heuristic_score = min(1.0, (r1 / 40.0) * 0.35 + (r24 / 120.0) * 0.35 + (sm / 100.0) * 0.30)
            score = round(heuristic_score, 3)
            is_anomalous = score >= 0.60
        else:
            # score_samples returns negative anomaly score (lower means more anomalous)
            raw_score = self.model.score_samples(arr)[0]
            # Normalize to [0.0, 1.0] where 1.0 is extremely anomalous
            # Typ standard raw_score is in range [-0.8, -0.2]
            normalized = max(0.0, min(1.0, (-raw_score - 0.35) / 0.40))
            score = round(float(normalized), 3)
            pred = self.model.predict(arr)[0]
            is_anomalous = bool(pred == -1)

        if score < 0.30:
            level = AnomalyLevel.NORMAL
        elif score < 0.60:
            level = AnomalyLevel.ELEVATED
        elif score < 0.85:
            level = AnomalyLevel.SEVERE
        else:
            level = AnomalyLevel.EXTREME

        factors = []
        if vector.rainfall_1h.value >= 20.0:
            factors.append(f"Short burst rainfall: {vector.rainfall_1h.value:.1f} mm/h")
        if vector.rainfall_24h.value >= 75.0:
            factors.append(f"24h heavy accumulation: {vector.rainfall_24h.value:.1f} mm")
        if vector.soil_moisture_surface.value >= 80.0:
            factors.append(f"Surface pore saturation: {vector.soil_moisture_surface.value:.1f}%")

        summary = (
            f"IsolationForest ML anomaly: {level.value} (score={score:.2f}). "
            f"Evaluates multivariable state normality against learned distribution."
        )

        return EnvironmentalAnomalyOutput(
            location_id=vector.location_id,
            timestamp=vector.timestamp,
            anomaly_score=score,
            anomaly_level=level,
            rainfall_anomaly_score=min(1.0, vector.rainfall_24h.value / 120.0),
            soil_wetness_anomaly_score=min(1.0, vector.soil_moisture_surface.value / 100.0),
            atmospheric_anomaly_score=min(1.0, vector.antecedent_precipitation_index.value / 150.0),
            primary_abnormal_factors=factors,
            is_statistically_anomalous=is_anomalous,
            summary=summary,
        )


isolation_forest_anomaly_detector = IsolationForestAnomalyDetector()
