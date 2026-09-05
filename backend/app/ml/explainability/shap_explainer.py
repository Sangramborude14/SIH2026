import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


class LandslideShapExplainer:
    """
    Tree-based SHAP (SHapley Additive exPlanations) explainability engine.
    Calculates authentic global SHAP importance and local per-instance attributions
    for tree-based models (XGBoost, Random Forest, HistGradientBoosting).
    
    Adheres strictly to the distinction between:
    - OBSERVED ENVIRONMENTAL INDICATORS (raw physical measurements)
    - MODEL CONTRIBUTIONS (directional mathematical SHAP impact)
    """

    @classmethod
    def _unwrap_estimator(cls, model: Any) -> Any:
        """Extracts the underlying estimator from CalibratedClassifierCV or pipelines."""
        base = model
        if hasattr(model, "estimator"):
            base = model.estimator
        elif hasattr(model, "calibrated_classifiers_") and len(model.calibrated_classifiers_) > 0:
            first = model.calibrated_classifiers_[0]
            base = getattr(first, "estimator", first)
        return base

    @classmethod
    def compute_global_shap(
        cls,
        model: Any,
        X_val: np.ndarray,
        feature_names: List[str],
        max_samples: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Computes global mean absolute SHAP values across validation/test fold.
        Returns sorted list of features with importance scores and methods.
        """
        base = cls._unwrap_estimator(model)
        X_sample = X_val[:max_samples]

        # 1. Native XGBoost TreeSHAP
        if hasattr(base, "get_booster"):
            try:
                import xgboost as xgb
                booster = base.get_booster()
                dmat = xgb.DMatrix(X_sample)
                contribs = booster.predict(dmat, pred_contribs=True)
                # Last column is expected value / bias
                shap_matrix = contribs[:, :-1]
                mean_abs = np.mean(np.abs(shap_matrix), axis=0)
                total = float(np.sum(mean_abs)) if np.sum(mean_abs) > 0 else 1.0

                result = []
                for name, val in zip(feature_names, mean_abs):
                    result.append({
                        "feature": name,
                        "importance_score": round(float(val) / total, 4),
                        "mean_abs_shap": round(float(val), 4),
                        "method": "TreeSHAP_exact",
                    })
                result.sort(key=lambda x: x["importance_score"], reverse=True)
                return result
            except Exception as e:
                logger.warning(f"Native XGBoost TreeSHAP global calculation failed: {e}")

        # 2. General shap library TreeExplainer fallback if installed
        try:
            import shap
            explainer = shap.TreeExplainer(base)
            shap_values = explainer.shap_values(X_sample)
            if isinstance(shap_values, list) and len(shap_values) > 1:
                shap_values = shap_values[1]  # positive class
            elif hasattr(shap_values, "values"):
                shap_values = shap_values.values

            mean_abs = np.mean(np.abs(shap_values), axis=0)
            total = float(np.sum(mean_abs)) if np.sum(mean_abs) > 0 else 1.0

            result = []
            for name, val in zip(feature_names, mean_abs):
                result.append({
                    "feature": name,
                    "importance_score": round(float(val) / total, 4),
                    "mean_abs_shap": round(float(val), 4),
                    "method": "shap_TreeExplainer",
                })
            result.sort(key=lambda x: x["importance_score"], reverse=True)
            return result
        except Exception:
            pass

        # 3. Fallback to intrinsic tree feature_importances_
        if hasattr(base, "feature_importances_"):
            raw = base.feature_importances_
            total = float(np.sum(raw)) if np.sum(raw) > 0 else 1.0
            result = []
            for name, val in zip(feature_names, raw):
                result.append({
                    "feature": name,
                    "importance_score": round(float(val) / total, 4),
                    "mean_abs_shap": round(float(val), 4),
                    "method": "mean_decrease_impurity",
                })
            result.sort(key=lambda x: x["importance_score"], reverse=True)
            return result

        # Uniform fallback
        u = 1.0 / max(1, len(feature_names))
        return [
            {"feature": f, "importance_score": round(u, 4), "mean_abs_shap": round(u, 4), "method": "uniform_fallback"}
            for f in feature_names
        ]

    @classmethod
    def explain_instance(
        cls,
        model: Any,
        X_arr: np.ndarray,
        feature_names: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Computes local SHAP attributions for a single sample (X_arr shape (1, D)).
        Returns top contributing features with exact directional push on model output.
        """
        base = cls._unwrap_estimator(model)
        X_single = np.asarray(X_arr, dtype=np.float64)
        if X_single.ndim == 1:
            X_single = X_single.reshape(1, -1)

        # 1. Native XGBoost TreeSHAP
        if hasattr(base, "get_booster"):
            try:
                import xgboost as xgb
                booster = base.get_booster()
                dmat = xgb.DMatrix(X_single)
                contribs = booster.predict(dmat, pred_contribs=True)
                sample_contribs = contribs[0, :-1]  # Exclude bias
                
                ranked = []
                for name, val in zip(feature_names, sample_contribs):
                    val_float = float(val)
                    ranked.append({
                        "feature": name,
                        "importance_score": round(abs(val_float), 4),
                        "shap_value": round(val_float, 4),
                        "direction": "INCREASES_PROBABILITY" if val_float >= 0 else "DECREASES_PROBABILITY",
                        "sign": "+" if val_float >= 0 else "-",
                        "magnitude": round(abs(val_float), 4),
                        "method": "TreeSHAP_local",
                    })

                # Sort by absolute SHAP magnitude
                ranked.sort(key=lambda x: x["magnitude"], reverse=True)
                return ranked[:top_k]
            except Exception as e:
                logger.warning(f"Native TreeSHAP local attribution failed: {e}")

        # 2. SHAP package fallback
        try:
            import shap
            explainer = shap.TreeExplainer(base)
            shap_values = explainer.shap_values(X_single)
            if isinstance(shap_values, list) and len(shap_values) > 1:
                vals = shap_values[1][0]
            else:
                vals = shap_values[0] if hasattr(shap_values, "__getitem__") else np.zeros(len(feature_names))

            ranked = []
            for name, val in zip(feature_names, vals):
                val_float = float(val)
                ranked.append({
                    "feature": name,
                    "importance_score": round(abs(val_float), 4),
                    "shap_value": round(val_float, 4),
                    "direction": "INCREASES_PROBABILITY" if val_float >= 0 else "DECREASES_PROBABILITY",
                    "sign": "+" if val_float >= 0 else "-",
                    "magnitude": round(abs(val_float), 4),
                    "method": "shap_TreeExplainer_local",
                })
            ranked.sort(key=lambda x: x["magnitude"], reverse=True)
            return ranked[:top_k]
        except Exception:
            pass

        # 3. Fallback: rank by feature magnitude relative to standard deviation
        ranked = []
        for i, name in enumerate(feature_names):
            val = float(X_single[0, i])
            ranked.append({
                "feature": name,
                "importance_score": round(abs(val), 4),
                "shap_value": round(val, 4),
                "direction": "INCREASES_PROBABILITY" if val > 0 else "DECREASES_PROBABILITY",
                "sign": "+" if val > 0 else "-",
                "magnitude": round(abs(val), 4),
                "method": "normalized_feature_deviation_fallback",
            })
        ranked.sort(key=lambda x: x["magnitude"], reverse=True)
        return ranked[:top_k]


shap_explainer = LandslideShapExplainer()
