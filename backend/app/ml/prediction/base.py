from abc import ABC, abstractmethod
from typing import Dict
from backend.app.ml.types import (
    LandslideFeatureVector,
    LandslidePredictionOutput,
    ForecastHorizon,
    HorizonProbability,
)


class LandslidePredictor(ABC):
    """
    Abstract contract for Task B: Landslide Prediction Model.
    Calculates P(landslide within forecast horizon | features up to time T).
    """

    @abstractmethod
    def predict(self, features: LandslideFeatureVector) -> LandslidePredictionOutput:
        """
        Executes inference across all standard forecast horizons (6h, 12h, 24h).
        Returns typed predictions, uncertainty bounds, and explicit model disclaimers.
        """
        pass
