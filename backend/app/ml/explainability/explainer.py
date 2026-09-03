from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.inspection import permutation_importance


class LandslideModelExplainer:
    """
    Extracts global and local feature importance interpretations
    from trained models without inventing manufactured per-sample weights.
    """

    @classmethod
    def get_global_importance(
        cls,
        model: Any,
        feature_names: List[str],
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> List[Dict[str, Any]]:
        """
        Computes intrinsic feature importances (or permutation importance if validation data is provided).
        """
        # Unwrap CalibratedClassifierCV if wrapped
        base = model
        if hasattr(model, "estimator"):
            base = model.estimator
        elif hasattr(model, "calibrated_classifiers_") and len(model.calibrated_classifiers_) > 0:
            base = model.calibrated_classifiers_[0].estimator

        importances: List[Dict[str, Any]] = []

        # Tree-based feature_importances_
        if hasattr(base, "feature_importances_"):
            raw_imp = base.feature_importances_
            total = float(np.sum(raw_imp)) if np.sum(raw_imp) > 0 else 1.0
            for name, val in zip(feature_names, raw_imp):
                importances.append({
                    "feature": name,
                    "importance_score": round(float(val) / total, 4),
                    "method": "mean_decrease_impurity",
                })
        # Linear coefficients
        elif hasattr(base, "coef_"):
            coefs = np.abs(base.coef_[0])
            total = float(np.sum(coefs)) if np.sum(coefs) > 0 else 1.0
            for name, val in zip(feature_names, coefs):
                importances.append({
                    "feature": name,
                    "importance_score": round(float(val) / total, 4),
                    "method": "absolute_coefficient",
                })
        # Fallback permutation importance on validation fold
        elif X_val is not None and y_val is not None:
            r = permutation_importance(model, X_val, y_val, n_repeats=5, random_state=42)
            raw_imp = np.maximum(0, r.importances_mean)
            total = float(np.sum(raw_imp)) if np.sum(raw_imp) > 0 else 1.0
            for name, val in zip(feature_names, raw_imp):
                importances.append({
                    "feature": name,
                    "importance_score": round(float(val) / total, 4),
                    "method": "permutation_importance",
                })
        else:
            # Uniform fallback
            uniform = 1.0 / len(feature_names)
            for name in feature_names:
                importances.append({
                    "feature": name,
                    "importance_score": round(uniform, 4),
                    "method": "uniform_fallback",
                })

        # Sort descending
        importances.sort(key=lambda x: x["importance_score"], reverse=True)
        return importances

    @classmethod
    def get_local_feature_attribution(
        cls,
        feature_dict: Dict[str, float],
        global_importances: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Creates an honest physical attribution for an individual sample:
        links the top influential global features with the actual physical sensor measurement.
        """
        top_features = global_importances[:top_k]
        attributions = []

        for item in top_features:
            feat_name = item["feature"]
            val = feature_dict.get(feat_name, 0.0)
            attributions.append({
                "feature": feat_name,
                "measured_value": round(float(val), 2),
                "importance_weight": item["importance_score"],
                "importance_rank": top_features.index(item) + 1,
            })

        return attributions


explainer = LandslideModelExplainer()
