from typing import List, Dict, Any, Tuple, Optional
import math


def compute_confusion_matrix(y_true: List[int], y_pred: List[int]) -> Dict[str, int]:
    """
    Computes exact confusion matrix from binary ground-truth (0/1) and predictions (0/1).
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have identical lengths.")

    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "total_evaluations": len(y_true),
    }


def compute_brier_score(y_true: List[int], y_pred_probs: List[float]) -> float:
    """
    Computes Brier probability calibration score:
    Brier = (1/N) * sum((p_i - y_i)^2)
    A lower score (closer to 0.0) indicates superior probabilistic calibration.
    """
    if not y_true:
        return 0.0
    if len(y_true) != len(y_pred_probs):
        raise ValueError("y_true and y_pred_probs must have identical lengths.")

    n = len(y_true)
    squared_errors = [(p - y) ** 2 for y, p in zip(y_true, y_pred_probs)]
    return round(sum(squared_errors) / n, 4)


def compute_roc_auc(y_true: List[int], y_pred_probs: List[float]) -> float:
    """
    Computes Area Under the Receiver Operating Characteristic curve (ROC-AUC)
    using the Wilcoxon-Mann-Whitney U-statistic formulation:
    AUC = (sum(ranks of positive instances) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    Guarantees exact mathematical calculation without external dependencies.
    """
    if not y_true or len(y_true) != len(y_pred_probs):
        return 0.5

    pos_count = sum(1 for y in y_true if y == 1)
    neg_count = sum(1 for y in y_true if y == 0)

    if pos_count == 0 or neg_count == 0:
        return 0.5  # Undefined when only one class is present

    # Pair and sort by predicted probability ascending
    paired = sorted(zip(y_pred_probs, y_true), key=lambda x: x[0])

    # Assign ranks with tie handling
    ranks = [0.0] * len(paired)
    i = 0
    n = len(paired)
    while i < n:
        j = i
        while j < n - 1 and paired[j][0] == paired[j + 1][0]:
            j += 1
        mean_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[k] = mean_rank
        i = j + 1

    pos_rank_sum = sum(rank for rank, (_, yt) in zip(ranks, paired) if yt == 1)
    u_stat = pos_rank_sum - (pos_count * (pos_count + 1)) / 2.0
    auc = u_stat / (pos_count * neg_count)

    return round(float(auc), 4)


def compute_classification_metrics(
    y_true: List[int],
    y_pred_probs: List[float],
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """
    Comprehensive evaluation metrics pipeline computing Precision, Recall, F1,
    ROC-AUC, Brier score, and 2x2 confusion matrix.
    """
    if len(y_true) != len(y_pred_probs):
        raise ValueError("y_true and y_pred_probs must have identical lengths.")

    y_pred = [1 if p >= threshold else 0 for p in y_pred_probs]
    cm = compute_confusion_matrix(y_true, y_pred)

    tp = cm["true_positives"]
    fp = cm["false_positives"]
    fn = cm["false_negatives"]
    tn = cm["true_negatives"]

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    accuracy = round((tp + tn) / len(y_true), 4) if y_true else 0.0
    specificity = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0.0

    roc_auc = compute_roc_auc(y_true, y_pred_probs)
    brier = compute_brier_score(y_true, y_pred_probs)

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy,
        "specificity": specificity,
        "roc_auc": roc_auc,
        "brier_score": brier,
        "threshold_applied": threshold,
        "confusion_matrix": cm,
    }


def compute_lead_time_distribution(lead_times_hours: List[float]) -> Dict[str, Any]:
    """
    Computes statistical summary and histogram binning for early-warning lead times.
    """
    if not lead_times_hours:
        return {
            "mean_lead_time_hours": 0.0,
            "median_lead_time_hours": 0.0,
            "min_lead_time_hours": 0.0,
            "max_lead_time_hours": 0.0,
            "hist_bins": {"<6h": 0, "6-12h": 0, "12-18h": 0, "18-24h": 0, ">24h": 0},
        }

    sorted_lt = sorted(lead_times_hours)
    n = len(sorted_lt)
    mean_val = round(sum(sorted_lt) / n, 1)
    median_val = round(
        (sorted_lt[n // 2] if n % 2 != 0 else (sorted_lt[n // 2 - 1] + sorted_lt[n // 2]) / 2.0),
        1
    )

    hist_bins = {
        "<6h": sum(1 for x in sorted_lt if x < 6.0),
        "6-12h": sum(1 for x in sorted_lt if 6.0 <= x < 12.0),
        "12-18h": sum(1 for x in sorted_lt if 12.0 <= x < 18.0),
        "18-24h": sum(1 for x in sorted_lt if 18.0 <= x < 24.0),
        ">24h": sum(1 for x in sorted_lt if x >= 24.0),
    }

    return {
        "mean_lead_time_hours": mean_val,
        "median_lead_time_hours": median_val,
        "min_lead_time_hours": round(sorted_lt[0], 1),
        "max_lead_time_hours": round(sorted_lt[-1], 1),
        "hist_bins": hist_bins,
    }
