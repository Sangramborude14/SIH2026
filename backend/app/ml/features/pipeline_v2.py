import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from backend.app.ml.features.pipeline import IncompatibleFeatureSchemaError


class ResearchFeaturePipelineV2:
    """
    Standardized Research Feature Engineering Pipeline (v2).
    Implements concepts from Stanley et al. (2021), Khan et al. (2022), and Mihu et al. (2026):
    - Triggers: Local Climatology Ratios (P/P99, P/P95) & Forecast Precipitation (P_fc / P99)
    - Preconditions: Multi-window antecedent rain (48h, 72h, API)
    - Dynamic Soil Wetness: Transitions, deltas (6h, 24h, 48h), and saturation interaction
    - Intrinsic Topography & Decoupled Susceptibility Priors
    - Optional Static Geospatial Layers (lithology, fault, lineament, road, NDVI)
    """

    FEATURE_SCHEMA = [
        # --- TRIGGER VARIABLES (Instantaneous & Forecast Forcing) ---
        {
            "name": "current_rainfall_24h",
            "role": "TRIGGER",
            "type": "float",
            "unit": "mm",
            "min": 0.0,
            "max": 1000.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Observed cumulative rainfall in the last 24h leading up to prediction time T."
        },
        {
            "name": "current_rainfall_p99_ratio",
            "role": "TRIGGER",
            "type": "float",
            "unit": "ratio",
            "min": 0.0,
            "max": 15.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Current 24h rainfall divided by location-specific historical 99th percentile (LHASA)."
        },
        {
            "name": "current_rainfall_p95_ratio",
            "role": "TRIGGER",
            "type": "float",
            "unit": "ratio",
            "min": 0.0,
            "max": 20.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Current 24h rainfall divided by location-specific historical 95th percentile."
        },
        {
            "name": "forecast_precipitation_24h",
            "role": "TRIGGER",
            "type": "float",
            "unit": "mm",
            "min": 0.0,
            "max": 1000.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Numerical weather forecast rainfall for upcoming 24h window (T to T+24h)."
        },
        {
            "name": "forecast_rainfall_p99_ratio",
            "role": "TRIGGER",
            "type": "float",
            "unit": "ratio",
            "min": 0.0,
            "max": 15.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Forecast 24h rainfall divided by location-specific historical 99th percentile."
        },

        # --- PRECONDITIONING HYDROLOGICAL VARIABLES ---
        {
            "name": "antecedent_rainfall_48h",
            "role": "PRECONDITION",
            "type": "float",
            "unit": "mm",
            "min": 0.0,
            "max": 1500.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Precipitation accumulated between T-48h and T-24h (prior regolith wetting)."
        },
        {
            "name": "rainfall_72h",
            "role": "PRECONDITION",
            "type": "float",
            "unit": "mm",
            "min": 0.0,
            "max": 2000.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Total cumulative 72-hour rainfall."
        },
        {
            "name": "antecedent_precipitation_index",
            "role": "PRECONDITION",
            "type": "float",
            "unit": "API",
            "min": 0.0,
            "max": 500.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Exponential decay antecedent precipitation index."
        },
        {
            "name": "consecutive_wet_hours",
            "role": "PRECONDITION",
            "type": "float",
            "unit": "hours",
            "min": 0.0,
            "max": 720.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Hours with continuous rainfall >= 0.5 mm/h."
        },

        # --- SOIL MOISTURE DYNAMICS (Dibang Valley Mihu et al. 2026) ---
        {
            "name": "soil_moisture_surface",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "%",
            "min": 0.0,
            "max": 100.0,
            "default": 35.0,
            "monotone_constraint": 1,
            "description": "Current surface layer volumetric soil moisture (0-7 cm)."
        },
        {
            "name": "soil_moisture_middle",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "%",
            "min": 0.0,
            "max": 100.0,
            "default": 35.0,
            "monotone_constraint": 0,
            "description": "Subsurface root-zone soil moisture (7-28 cm)."
        },
        {
            "name": "soil_moisture_deep",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "%",
            "min": 0.0,
            "max": 100.0,
            "default": 35.0,
            "monotone_constraint": 0,
            "description": "Deep regolith pore water stratum (28-100 cm)."
        },
        {
            "name": "soil_moisture_delta_6h",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "%",
            "min": -50.0,
            "max": 50.0,
            "default": 0.0,
            "monotone_constraint": 0,
            "description": "Rate of wetting transition: SM(T) - SM(T-6h)."
        },
        {
            "name": "soil_moisture_delta_24h",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "%",
            "min": -80.0,
            "max": 80.0,
            "default": 0.0,
            "monotone_constraint": 0,
            "description": "24h soil moisture trajectory: SM(T) - SM(T-24h)."
        },
        {
            "name": "soil_moisture_delta_48h",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "%",
            "min": -80.0,
            "max": 80.0,
            "default": 0.0,
            "monotone_constraint": 0,
            "description": "48h cumulative saturation transition: SM(T) - SM(T-48h)."
        },
        {
            "name": "wetness_percentile",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "ratio",
            "min": 0.0,
            "max": 1.0,
            "default": 0.40,
            "monotone_constraint": 1,
            "description": "Current surface wetness relative to field capacity (SM / 100.0)."
        },
        {
            "name": "dry_to_wet_transition",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "indicator",
            "min": 0.0,
            "max": 1.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Binary flag indicating rapid saturation of previously dry soil (<40% to >70%)."
        },
        {
            "name": "rainfall_x_soil_wetness",
            "role": "SOIL_DYNAMICS",
            "type": "float",
            "unit": "interaction",
            "min": 0.0,
            "max": 15.0,
            "default": 0.0,
            "monotone_constraint": 1,
            "description": "Cross-product interaction: (current_rainfall_p99_ratio) * (soil_moisture_surface / 100)."
        },

        # --- TOPOGRAPHIC & STATIC PRIORS ---
        {
            "name": "slope_angle",
            "role": "TOPOGRAPHY",
            "type": "float",
            "unit": "degrees",
            "min": 0.0,
            "max": 90.0,
            "default": 30.0,
            "monotone_constraint": 1,
            "description": "Terrain slope angle (DEM)."
        },
        {
            "name": "elevation",
            "role": "TOPOGRAPHY",
            "type": "float",
            "unit": "m",
            "min": 0.0,
            "max": 8000.0,
            "default": 1000.0,
            "monotone_constraint": 0,
            "description": "Terrain elevation above sea level."
        },
        {
            "name": "aspect_sin",
            "role": "TOPOGRAPHY",
            "type": "float",
            "unit": "rad",
            "min": -1.0,
            "max": 1.0,
            "default": 0.0,
            "monotone_constraint": 0,
            "description": "Sine of terrain aspect angle."
        },
        {
            "name": "aspect_cos",
            "role": "TOPOGRAPHY",
            "type": "float",
            "unit": "rad",
            "min": -1.0,
            "max": 1.0,
            "default": 1.0,
            "monotone_constraint": 0,
            "description": "Cosine of terrain aspect angle."
        },
        {
            "name": "susceptibility_prior",
            "role": "TOPOGRAPHY",
            "type": "float",
            "unit": "score",
            "min": 0.0,
            "max": 1.0,
            "default": 0.50,
            "monotone_constraint": 1,
            "description": "Decoupled static terrain susceptibility score."
        },
        {
            "name": "is_monsoon_season",
            "role": "TEMPORAL",
            "type": "float",
            "unit": "binary",
            "min": 0.0,
            "max": 1.0,
            "default": 0.0,
            "monotone_constraint": 0,
            "description": "Binary indicator for Indian monsoon months (June-September)."
        },

        # --- OPTIONAL GEOSPATIAL CONDITION FACTORS (Dibang Valley, Mihu et al. 2026) ---
        # When unmeasured, these default to physically neutral values or median imputed
        {
            "name": "lithology_strength",
            "role": "STATIC_GIS",
            "type": "float",
            "unit": "index",
            "min": 0.0,
            "max": 1.0,
            "default": 0.50,
            "monotone_constraint": -1,
            "description": "Rock mass strength index (0=weak/sheared, 1=massive crystalline)."
        },
        {
            "name": "distance_to_active_fault",
            "role": "STATIC_GIS",
            "type": "float",
            "unit": "km",
            "min": 0.0,
            "max": 100.0,
            "default": 25.0,
            "monotone_constraint": -1,
            "description": "Distance to mapped regional thrust/fault line."
        },
        {
            "name": "lineament_density",
            "role": "STATIC_GIS",
            "type": "float",
            "unit": "km_per_km2",
            "min": 0.0,
            "max": 10.0,
            "default": 1.5,
            "monotone_constraint": 1,
            "description": "Structural lineament fracture density."
        },
        {
            "name": "distance_to_road",
            "role": "STATIC_GIS",
            "type": "float",
            "unit": "m",
            "min": 0.0,
            "max": 10000.0,
            "default": 1000.0,
            "monotone_constraint": -1,
            "description": "Distance to cut slope / road infrastructure."
        },
        {
            "name": "ndvi",
            "role": "STATIC_GIS",
            "type": "float",
            "unit": "index",
            "min": -1.0,
            "max": 1.0,
            "default": 0.55,
            "monotone_constraint": -1,
            "description": "Normalized Difference Vegetation Index."
        },
    ]

    FEATURE_NAMES = [f["name"] for f in FEATURE_SCHEMA]
    SCHEMA_VERSION = "2.0.0-research"

    def __init__(self, preprocessor: Optional[Pipeline] = None):
        self.preprocessor = preprocessor or self._create_default_preprocessor()
        self.is_fitted = False

    @classmethod
    def _create_default_preprocessor(cls) -> Pipeline:
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])

    @classmethod
    def get_monotonic_constraints_tuple(cls) -> Tuple[int, ...]:
        """
        Returns a tuple of monotonic constraints for gradient boosted trees.
        +1: monotonically non-decreasing
        -1: monotonically non-increasing
         0: unconstrained
        """
        return tuple(spec.get("monotone_constraint", 0) for spec in cls.FEATURE_SCHEMA)

    @classmethod
    def get_trigger_feature_indices(cls) -> List[int]:
        return [i for i, spec in enumerate(cls.FEATURE_SCHEMA) if spec["role"] == "TRIGGER"]

    @classmethod
    def get_precondition_feature_indices(cls) -> List[int]:
        return [
            i for i, spec in enumerate(cls.FEATURE_SCHEMA)
            if spec["role"] in ("PRECONDITION", "SOIL_DYNAMICS", "TOPOGRAPHY", "STATIC_GIS")
        ]

    def validate_features_dict(
        self,
        features: Dict[str, Any],
        allow_missing_with_default: bool = False
    ) -> Dict[str, float]:
        cleaned: Dict[str, float] = {}
        missing = []

        for spec in self.FEATURE_SCHEMA:
            name = spec["name"]
            if name in features and features[name] is not None:
                val = float(features[name])
                val = max(spec["min"], min(spec["max"], val))
                cleaned[name] = val
            elif allow_missing_with_default:
                cleaned[name] = spec["default"]
            else:
                missing.append(name)

        if missing:
            raise IncompatibleFeatureSchemaError(
                f"Input features missing required schema variables: {missing}. "
                f"Expected {len(self.FEATURE_NAMES)} features under Schema v{self.SCHEMA_VERSION}."
            )

        return cleaned

    def transform_single_dict(self, features: Dict[str, Any]) -> np.ndarray:
        valid_dict = self.validate_features_dict(features, allow_missing_with_default=True)
        ordered_vals = [valid_dict[col] for col in self.FEATURE_NAMES]
        arr = np.array(ordered_vals, dtype=np.float64).reshape(1, -1)
        if self.is_fitted:
            return self.preprocessor.transform(arr)
        return arr

    def fit(self, X: pd.DataFrame | np.ndarray) -> "ResearchFeaturePipelineV2":
        if isinstance(X, pd.DataFrame):
            missing_cols = [c for c in self.FEATURE_NAMES if c not in X.columns]
            if missing_cols:
                raise IncompatibleFeatureSchemaError(f"DataFrame missing required feature columns: {missing_cols}")
            X_arr = X[self.FEATURE_NAMES].values
        else:
            X_arr = X

        self.preprocessor.fit(X_arr)
        self.is_fitted = True
        return self

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, pd.DataFrame):
            missing_cols = [c for c in self.FEATURE_NAMES if c not in X.columns]
            if missing_cols:
                raise IncompatibleFeatureSchemaError(f"DataFrame missing required feature columns: {missing_cols}")
            X_arr = X[self.FEATURE_NAMES].values
        else:
            X_arr = X

        if self.is_fitted:
            return self.preprocessor.transform(X_arr)
        return X_arr

    def fit_transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def export_schema_json(self, filepath: Optional[str | Path] = None) -> str:
        schema_dict = {
            "schema_version": self.SCHEMA_VERSION,
            "feature_count": len(self.FEATURE_NAMES),
            "features": self.FEATURE_SCHEMA,
            "trigger_features": [f["name"] for f in self.FEATURE_SCHEMA if f["role"] == "TRIGGER"],
            "precondition_features": [f["name"] for f in self.FEATURE_SCHEMA if f["role"] != "TRIGGER"],
        }
        json_str = json.dumps(schema_dict, indent=2)
        if filepath:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str


shared_research_pipeline_v2 = ResearchFeaturePipelineV2()
RESEARCH_FEATURE_NAMES = ResearchFeaturePipelineV2.FEATURE_NAMES
RESEARCH_FEATURE_SCHEMA_VERSION = ResearchFeaturePipelineV2.SCHEMA_VERSION
