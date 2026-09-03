from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    precision_recall_curve,
    auc,
    brier_score_loss,
    confusion_matrix,
)


class LandslideModelEvaluator:
    """
    Evaluates probabilistic landslide classification models on held-out validation/test datasets.
    Computes threshold sweeps, PR-AUC, Brier calibration scores, and operational early-warning metrics.
    """

    OPERATIONAL_THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70]

    @classmethod
    def evaluate_model(
        cls,
        y_true: np.ndarray,
        y_probs: np.ndarray,
        selected_threshold: float = 0.50,
    ) -> Dict[str, Any]:
        """
        Computes comprehensive evaluation metrics on held-out data.
        """
        y_true = np.asarray(y_true, dtype=int)
        y_probs = np.asarray(y_probs, dtype=float)

        # ROC-AUC
        try:
            if len(np.unique(y_true)) > 1:
                roc_auc = float(roc_auc_score(y_true, y_probs))
            else:
                roc_auc = 0.50
        except Exception:
            roc_auc = 0.50

        # PR-AUC
        try:
            precisions, recalls, _ = precision_recall_curve(y_true, y_probs)
            pr_auc = float(auc(recalls, precisions))
        except Exception:
            pr_auc = 0.0

        # Brier Score (mean squared error between prob and binary label)
        brier = float(brier_score_loss(y_true, y_probs))

        # Metrics at selected threshold
        y_pred = (y_probs >= selected_threshold).astype(int)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        precision = float(precision_score(y_true, y_pred, zero_division=0))
        recall = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))

        # False Alarm Ratio: FP / (TP + FP)
        far = float(fp / (tp + fp)) if (tp + fp) > 0 else 0.0
        # Critical Success Index (Threat Score): TP / (TP + FP + FN)
        csi = float(tp / (tp + fp + fn)) if (tp + fp + fn) > 0 else 0.0

        # Threshold sweep
        threshold_results = []
        for thresh in cls.OPERATIONAL_THRESHOLDS:
            p_thresh = (y_probs >= thresh).astype(int)
            t_cm = confusion_matrix(y_true, p_thresh, labels=[0, 1])
            t_tn, t_fp, t_fn, t_tp = t_cm.ravel()
            threshold_results.append({
                "threshold": thresh,
                "precision": round(float(precision_score(y_true, p_thresh, zero_division=0)), 4),
                "recall": round(float(recall_score(y_true, p_thresh, zero_division=0)), 4),
                "f1_score": round(float(f1_score(y_true, p_thresh, zero_division=0)), 4),
                "true_positives": int(t_tp),
                "false_positives": int(t_fp),
                "false_negatives": int(t_fn),
                "true_negatives": int(t_tn),
                "false_alarm_ratio": round(float(t_fp / (t_tp + t_fp)), 4) if (t_tp + t_fp) > 0 else 0.0,
            })

        return {
            "total_samples": len(y_true),
            "positive_events": int(np.sum(y_true)),
            "negative_samples": int(len(y_true) - np.sum(y_true)),
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier, 4),
            "selected_threshold": selected_threshold,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_alarm_ratio": round(far, 4),
            "critical_success_index": round(csi, 4),
            "confusion_matrix": {
                "true_positives": int(tp),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_negatives": int(tn),
            },
            "threshold_sweep": threshold_results,
        }


evaluator = LandslideModelEvaluator()
