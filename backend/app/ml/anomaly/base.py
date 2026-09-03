from abc import ABC, abstractmethod
from backend.app.ml.types import LandslideFeatureVector, EnvironmentalAnomalyOutput


class EnvironmentalAnomalyDetector(ABC):
    """
    Abstract contract for Task A: Environmental Anomaly Detection.
    Evaluates whether current environmental conditions are statistically abnormal
    compared with local normal / seasonal baselines.
    IMPORTANT: An anomaly score evaluates environmental unorthodoxy;
    it DOES NOT calculate slope failure probability.
    """

    @abstractmethod
    def detect_anomaly(self, features: LandslideFeatureVector) -> EnvironmentalAnomalyOutput:
        """
        Calculates multivariate environmental anomaly score (0.0 to 1.0) and anomaly tier.
        """
        pass
