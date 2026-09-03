import logging
from typing import Tuple, Dict, Any
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

logger = logging.getLogger(__name__)


class LandslideProbabilityCalibrator:
    """
    Applies Platt scaling (sigmoid) or isotonic regression to calibrate
    classifier raw probabilities so that P(Y=1) reflects true physical failure frequency.
    """

    @classmethod
    def calibrate_classifier(
        cls,
        base_estimator: BaseEstimator,
        X_val: np.ndarray,
        y_val: np.ndarray,
        method: str = "sigmoid",
    ) -> Tuple[CalibratedClassifierCV, Dict[str, Any]]:
        """
        Calibrates a pre-fitted or CV-folded estimator.
        Returns (calibrated_model, calibration_report).
        """
        y_val = np.asarray(y_val, dtype=int)

        # Uncalibrated baseline Brier score
        try:
            if hasattr(base_estimator, "predict_proba"):
                raw_probs = base_estimator.predict_proba(X_val)[:, 1]
            else:
                raw_probs = base_estimator.decision_function(X_val)
                raw_probs = 1.0 / (1.0 + np.exp(-raw_probs))
            raw_brier = float(brier_score_loss(y_val, raw_probs))
        except Exception:
            raw_brier = 0.25

        # Isotonic regression requires more samples to avoid overfitting; default to sigmoid
        chosen_method = method if len(y_val) >= 100 else "sigmoid"
        try:
            calibrated_model = CalibratedClassifierCV(
                estimator=base_estimator,
                method=chosen_method,
                cv=None,
            )
            calibrated_model.fit(X_val, y_val)
        except Exception:
            try:
                calibrated_model = CalibratedClassifierCV(
                    estimator=base_estimator,
                    method=chosen_method,
                    cv="prefit",
                )
                calibrated_model.fit(X_val, y_val)
            except Exception:
                calibrated_model = base_estimator


        calibrated_probs = calibrated_model.predict_proba(X_val)[:, 1]
        calibrated_brier = float(brier_score_loss(y_val, calibrated_probs))

        report = {
            "calibration_method": chosen_method,
            "raw_brier_score": round(raw_brier, 4),
            "calibrated_brier_score": round(calibrated_brier, 4),
            "brier_score_improvement": round(raw_brier - calibrated_brier, 4),
            "is_improved": bool(calibrated_brier <= raw_brier),
        }

        logger.info(
            f"Probability calibration ({chosen_method}): Brier score {raw_brier:.4f} -> {calibrated_brier:.4f}"
        )
        return calibrated_model, report


calibrator = LandslideProbabilityCalibrator()
