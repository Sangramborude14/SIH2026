import logging
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

from backend.app.ml.types import ModelTier
from backend.app.ml.evaluation.evaluator import evaluator
from backend.app.ml.prediction.calibrator import calibrator
from backend.app.ml.explainability.explainer import explainer

logger = logging.getLogger(__name__)


class LandslideModelTrainer:
    """
    Trains and benchmarks explainable tabular classifiers for landslide probability forecasting.
    Handles class imbalance, performs probability calibration, and selects the optimal model.
    """

    CANDIDATE_MODELS = [
        {
            "name": "Logistic Regression Baseline",
            "tier": ModelTier.TABULAR_ML_LOGISTIC,
            "constructor": lambda seed: LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=seed,
            ),
        },
        {
            "name": "Random Forest Classifier",
            "tier": ModelTier.TABULAR_ML_RANDOM_FOREST,
            "constructor": lambda seed: RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_leaf=2,
                class_weight="balanced_subsample",
                random_state=seed,
            ),
        },
        {
            "name": "HistGradientBoosting Classifier",
            "tier": ModelTier.TABULAR_ML_GRADIENT_BOOST,
            "constructor": lambda seed: HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=6,
                class_weight="balanced",
                random_state=seed,
            ),
        },
    ]

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed

    def train_and_compare_candidates(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        feature_names: List[str],
    ) -> Tuple[Any, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Trains all candidate models, evaluates on validation set,
        and selects the best candidate based on PR-AUC and F1-score.
        Returns (best_uncalibrated_model, best_candidate_metadata, candidate_comparison_table).
        """
        comparison_table = []
        trained_candidates = []

        for spec in self.CANDIDATE_MODELS:
            name = spec["name"]
            tier = spec["tier"]
            logger.info(f"Training candidate classifier: {name}...")

            model = spec["constructor"](self.random_seed)
            model.fit(X_train, y_train)

            # Predict probabilities on validation fold
            if hasattr(model, "predict_proba"):
                val_probs = model.predict_proba(X_val)[:, 1]
            else:
                raw = model.decision_function(X_val)
                val_probs = 1.0 / (1.0 + np.exp(-raw))

            val_metrics = evaluator.evaluate_model(y_val, val_probs, selected_threshold=0.50)

            record = {
                "name": name,
                "tier": tier.value,
                "pr_auc": val_metrics["pr_auc"],
                "roc_auc": val_metrics["roc_auc"],
                "f1_score": val_metrics["f1_score"],
                "recall": val_metrics["recall"],
                "precision": val_metrics["precision"],
                "brier_score": val_metrics["brier_score"],
            }
            comparison_table.append(record)
            trained_candidates.append((model, spec, val_metrics))

        # Select best model: prioritize PR-AUC, then F1-score
        trained_candidates.sort(
            key=lambda item: (item[2]["pr_auc"], item[2]["f1_score"]),
            reverse=True,
        )
        best_model, best_spec, best_val_metrics = trained_candidates[0]
        logger.info(
            f"Selected best candidate: {best_spec['name']} "
            f"(Val PR-AUC={best_val_metrics['pr_auc']:.4f}, F1={best_val_metrics['f1_score']:.4f})"
        )

        return best_model, best_spec, comparison_table

    def train_full_pipeline(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
        calibrate: bool = True,
    ) -> Dict[str, Any]:
        """
        Full workflow:
        1. Benchmark candidates on validation set.
        2. Calibrate winning candidate probabilities.
        3. Evaluate final model on held-out test set.
        4. Compute global feature importances.
        """
        best_raw_model, best_spec, candidates_summary = self.train_and_compare_candidates(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=feature_names,
        )

        # Calibrate
        calibration_report = {}
        if calibrate and len(y_val) >= 20:
            final_model, calibration_report = calibrator.calibrate_classifier(
                base_estimator=best_raw_model,
                X_val=X_val,
                y_val=y_val,
                method="sigmoid",
            )
        else:
            final_model = best_raw_model
            calibration_report = {"status": "uncalibrated_small_val_set"}

        # Final evaluation on held-out test set
        if hasattr(final_model, "predict_proba"):
            test_probs = final_model.predict_proba(X_test)[:, 1]
        else:
            raw = final_model.decision_function(X_test)
            test_probs = 1.0 / (1.0 + np.exp(-raw))

        test_metrics = evaluator.evaluate_model(y_test, test_probs, selected_threshold=0.50)

        # Global feature importance
        importances = explainer.get_global_importance(
            model=best_raw_model,
            feature_names=feature_names,
            X_val=X_val,
            y_val=y_val,
        )

        return {
            "model": final_model,
            "uncalibrated_model": best_raw_model,
            "selected_spec": best_spec,
            "candidate_comparison": candidates_summary,
            "calibration_report": calibration_report,
            "test_evaluation": test_metrics,
            "feature_importances": importances,
            "feature_names": feature_names,
        }


trainer = LandslideModelTrainer()
