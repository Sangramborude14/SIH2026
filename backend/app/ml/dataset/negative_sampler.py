import random
import logging
from datetime import date, timedelta
from typing import List, Dict, Set, Tuple, Any, Optional

from backend.app.ml.dataset.schemas import (
    LandslideInventoryRecord,
    NegativeSamplingConfig,
)

logger = logging.getLogger(__name__)


class ScientificNegativeSampler:
    """
    Constructs representative, scientifically grounded non-landslide negative samples.
    Enforces temporal buffers, spatial matching, and hard-negative rainfall conditioning.
    """

    def __init__(self, config: Optional[NegativeSamplingConfig] = None):
        self.config = config or NegativeSamplingConfig()

    def sample_negatives(
        self,
        positive_records: List[LandslideInventoryRecord],
        available_station_dates: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Samples non-landslide negative instances from available historical station-date telemetry.
        
        available_station_dates: list of dicts with:
          - location_id: str
          - latitude: float
          - longitude: float
          - date: date
          - rainfall_24h: float
          - is_monsoon: bool
          - static_features: dict
          - dynamic_features: dict
        """
        rng = random.Random(self.config.random_seed)
        
        # Build positive exclusion lookup: (location_id, blocked_date)
        positive_exclusions: Set[Tuple[str, date]] = set()
        for pos in positive_records:
            # We associate with station by nearest distance or location_id
            loc_id = getattr(pos, "location_id", None) or pos.district
            for d_offset in range(-self.config.temporal_buffer_days, self.config.temporal_buffer_days + 1):
                blocked = pos.event_date + timedelta(days=d_offset)
                positive_exclusions.add((loc_id, blocked))

        # Filter candidates that are NOT within temporal exclusion buffers
        candidate_pool: List[Dict[str, Any]] = []
        for cand in available_station_dates:
            cand_date = cand["date"]
            loc_id = cand["location_id"]
            if (loc_id, cand_date) not in positive_exclusions:
                candidate_pool.append(cand)

        total_positives = len(positive_records)
        target_negatives = int(total_positives * self.config.negative_to_positive_ratio)

        # Split into hard negative pool (rainy days without failure) and baseline pool
        hard_neg_candidates = [
            c for c in candidate_pool
            if c.get("rainfall_24h", 0.0) >= self.config.min_rainfall_hard_negative_mm
        ]
        baseline_candidates = [
            c for c in candidate_pool
            if c.get("rainfall_24h", 0.0) < self.config.min_rainfall_hard_negative_mm
        ]

        target_hard = int(target_negatives * self.config.hard_negative_pct)
        target_baseline = target_negatives - target_hard

        # Sample hard negatives with fallback
        sampled_hard = rng.sample(hard_neg_candidates, min(len(hard_neg_candidates), target_hard))
        remaining_needed = target_negatives - len(sampled_hard)

        # Sample baseline negatives
        sampled_baseline = rng.sample(baseline_candidates, min(len(baseline_candidates), remaining_needed))

        sampled_negatives: List[Dict[str, Any]] = []
        for item in sampled_hard:
            copy_item = dict(item)
            copy_item["label"] = 0
            copy_item["is_hard_negative"] = True
            sampled_negatives.append(copy_item)

        for item in sampled_baseline:
            copy_item = dict(item)
            copy_item["label"] = 0
            copy_item["is_hard_negative"] = False
            sampled_negatives.append(copy_item)

        stats = {
            "total_positives": total_positives,
            "target_negatives": target_negatives,
            "actual_negatives_sampled": len(sampled_negatives),
            "hard_negatives_count": len(sampled_hard),
            "baseline_negatives_count": len(sampled_baseline),
            "temporal_buffer_days": self.config.temporal_buffer_days,
            "min_rainfall_threshold_mm": self.config.min_rainfall_hard_negative_mm,
        }

        logger.info(
            f"Sampled {len(sampled_negatives)} negative instances "
            f"({len(sampled_hard)} hard-rain negatives, {len(sampled_baseline)} baseline) "
            f"for {total_positives} positive events."
        )
        return sampled_negatives, stats
