import json
import logging
from typing import Dict, Any, Tuple, List, Optional
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
import xgboost as xgb

from backend.app.ml.types import ModelTier
from backend.app.ml.evaluation.evaluator import evaluator
from backend.app.ml.prediction.calibrator import calibrator
from backend.app.ml.explainability.explainer import explainer
from backend.app.ml.explainability.shap_explainer import shap_explainer

logger = logging.getLogger(__name__)

# Scientifically documented monotonic physical assumptions (Stanley et al., 2021; Khan et al., 2022)
PHYSICAL_MONOTONIC_ASSUMPTIONS: Dict[str, Tuple[int, str]] = {
    "current_rainfall_24h": (1, "Increasing triggering rainfall increases pore-water pressure and driving weight; cannot directly decrease slope failure probability."),
    "current_rainfall_p99_ratio": (1, "Increasing localized extreme rainfall anomaly increases probability of exceeding physical geotechnical thresholds."),
    "current_rainfall_p95_ratio": (1, "Higher normalized antecedent-to-peak rainfall burst increases failure hazard."),
    "forecast_precipitation_24h": (1, "Incoming forecasted storm deluge adds prospective driving infiltration; cannot decrease upcoming 24h probability."),
    "forecast_rainfall_p99_ratio": (1, "Normalized prospective storm intensity increases upcoming risk monotonically."),
    "antecedent_rainfall_48h": (1, "Prior wetting saturates regolith pore space and reduces matric suction."),
    "rainfall_72h": (1, "Cumulative 3-day rainfall promotes deep seepage and water table elevation."),
    "antecedent_precipitation_index": (1, "Higher API represents greater residual subsurface moisture storage."),
    "consecutive_wet_hours": (1, "Prolonged rainfall duration promotes continuous infiltration without drainage recovery."),
    "soil_moisture_surface": (1, "Near-surface saturation induces positive pore water pressure and reduces shear strength."),
    "wetness_percentile": (1, "Higher saturation ratio relative to field capacity decreases effective normal stress."),
    "dry_to_wet_transition": (1, "Rapid wetting front advancement destabilizes dry cohesive bonds."),
    "rainfall_x_soil_wetness": (1, "Coupled rainfall trigger and soil preconditioning compounds destabilization."),
    "slope_angle": (1, "Steeper slope increases tangential gravitational driving shear stress along prospective failure planes."),
    "susceptibility_prior": (1, "Higher intrinsic geological susceptibility cannot decrease operational failure probability."),
    "baseline_susceptibility": (1, "Baseline physical susceptibility cannot decrease slope failure probability."),
    "lineament_density": (1, "Higher structural fracture density facilitates infiltration and creates shear weakness planes."),
    "lithology_strength": (-1, "Higher intact rock strength resists shear failure and reduces failure probability."),
    "distance_to_active_fault": (-1, "Greater distance from active seismotectonic faults reduces seismic fracture damage."),
    "distance_to_road": (-1, "Greater distance from road cuts reduces destabilizing toe excavation."),
    "ndvi": (-1, "Higher vegetation and root reinforcement enhances slope cohesion and evapotranspiration."),
}


def get_monotonic_constraints_for_features(feature_names: List[str]) -> Tuple[int, ...]:
    """Derives monotonic constraints tuple (+1, -1, 0) aligned to input feature names."""
    return tuple(PHYSICAL_MONOTONIC_ASSUMPTIONS.get(f, (0, ""))[0] for f in feature_names)


def get_interaction_constraints_for_features(feature_names: List[str]) -> Optional[str]:
    """
    Constructs interaction constraints for XGBoost:
    Permits triggers (rainfall variables) to interact with preconditioning variables (slope, soil, geology),
    preventing unphysical interactions between independent static terms.
    """
    triggers = [i for i, f in enumerate(feature_names) if "rain" in f or "precip" in f]
    preconds = [i for i, f in enumerate(feature_names) if i not in triggers]
    if triggers and preconds:
        interaction_groups = [triggers + [p] for p in preconds[:12]]
        return json.dumps(interaction_groups)
    return None


class LandslideModelTrainer:
    """
    Trains and benchmarks explainable tabular classifiers for landslide probability forecasting.
    Compares 5 candidate algorithms:
    1. Logistic Regression Baseline
    2. Random Forest Classifier
    3. HistGradientBoosting Classifier
    4. XGBoost Classifier (Standard Regularized)
    5. XGBoost Classifier (Research-Constrained: max_depth 2-3, monotonic & interaction constraints)
    
    Selects the winning model based on held-out validation PR-AUC and F1-score.
    """

    CANDIDATE_MODELS = [
        {
            "name": "Logistic Regression Baseline",
            "tier": ModelTier.TABULAR_ML_LOGISTIC,
            "constructor": lambda seed, feat_names: LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=seed,
            ),
        },
        {
            "name": "Random Forest Classifier",
            "tier": ModelTier.TABULAR_ML_RANDOM_FOREST,
            "constructor": lambda seed, feat_names: RandomForestClassifier(
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
            "constructor": lambda seed, feat_names: HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=6,
                class_weight="balanced",
                random_state=seed,
            ),
        },
        {
            "name": "XGBoost Classifier (Standard Regularized)",
            "tier": ModelTier.TABULAR_ML_XGBOOST,
            "constructor": lambda seed, feat_names: xgb.XGBClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.08,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_lambda=1.0,
                random_state=seed,
                eval_metric="logloss",
                n_jobs=1,
            ),
        },
        {
            "name": "XGBoost Classifier (Research-Constrained)",
            "tier": ModelTier.TABULAR_ML_XGBOOST_CONSTRAINED,
            "constructor": lambda seed, feat_names: xgb.XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                monotone_constraints=get_monotonic_constraints_for_features(feat_names),
                interaction_constraints=get_interaction_constraints_for_features(feat_names),
                random_state=seed,
                eval_metric="logloss",
                n_jobs=1,
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
        Trains all 5 candidate models, evaluates on validation set,
        and selects the best candidate based on PR-AUC and F1-score.
        Returns (best_uncalibrated_model, best_candidate_metadata, candidate_comparison_table).
        """
        comparison_table = []
        trained_candidates = []

        for spec in self.CANDIDATE_MODELS:
            name = spec["name"]
            tier = spec["tier"]
            logger.info(f"Training candidate classifier: {name}...")

            try:
                model = spec["constructor"](self.random_seed, feature_names)
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
            except Exception as e:
                logger.error(f"Candidate {name} failed during training: {e}")

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
        1. Benchmark all 5 candidates on validation set.
        2. Calibrate winning candidate probabilities.
        3. Evaluate final model on held-out test set.
        4. Compute global feature importances and TreeSHAP attributions.
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

        # Global feature importance via permutation / tree weights
        importances = explainer.get_global_importance(
            model=best_raw_model,
            feature_names=feature_names,
            X_val=X_val,
            y_val=y_val,
        )

        # Global TreeSHAP mean absolute attributions
        shap_importances = shap_explainer.compute_global_shap(
            model=best_raw_model,
            X_val=X_val,
            feature_names=feature_names,
        )

        return {
            "model": final_model,
            "uncalibrated_model": best_raw_model,
            "selected_spec": best_spec,
            "candidate_comparison": candidates_summary,
            "calibration_report": calibration_report,
            "test_evaluation": test_metrics,
            "feature_importances": importances,
            "shap_global_importances": shap_importances,
            "feature_names": feature_names,
            "monotonic_assumptions": {
                f: {"constraint": c, "rationale": r}
                for f, (c, r) in PHYSICAL_MONOTONIC_ASSUMPTIONS.items()
                if f in feature_names
            },
        }


trainer = LandslideModelTrainer()
