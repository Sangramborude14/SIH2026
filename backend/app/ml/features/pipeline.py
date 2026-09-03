import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler


class IncompatibleFeatureSchemaError(ValueError):
    """Raised when inference input feature vector violates the trained schema specification."""
    pass


class LandslideFeaturePipeline:
    """
    Standardized, shared feature engineering pipeline used for both
    batch training and real-time operational inference.
    """

    FEATURE_SCHEMA = [
        # Topographic & Spatial
        {"name": "slope_angle", "type": "float", "unit": "degrees", "min": 0.0, "max": 90.0, "default": 30.0},
        {"name": "elevation", "type": "float", "unit": "m", "min": 0.0, "max": 8000.0, "default": 1000.0},
        {"name": "aspect_sin", "type": "float", "unit": "rad", "min": -1.0, "max": 1.0, "default": 0.0},
        {"name": "aspect_cos", "type": "float", "unit": "rad", "min": -1.0, "max": 1.0, "default": 1.0},
        {"name": "baseline_susceptibility", "type": "float", "unit": "score", "min": 0.0, "max": 1.0, "default": 0.5},
        
        # Rainfall accumulation windows
        {"name": "rainfall_1h", "type": "float", "unit": "mm", "min": 0.0, "max": 300.0, "default": 0.0},
        {"name": "rainfall_3h", "type": "float", "unit": "mm", "min": 0.0, "max": 500.0, "default": 0.0},
        {"name": "rainfall_6h", "type": "float", "unit": "mm", "min": 0.0, "max": 600.0, "default": 0.0},
        {"name": "rainfall_12h", "type": "float", "unit": "mm", "min": 0.0, "max": 800.0, "default": 0.0},
        {"name": "rainfall_24h", "type": "float", "unit": "mm", "min": 0.0, "max": 1000.0, "default": 0.0},
        {"name": "rainfall_48h", "type": "float", "unit": "mm", "min": 0.0, "max": 1500.0, "default": 0.0},
        {"name": "rainfall_72h", "type": "float", "unit": "mm", "min": 0.0, "max": 2000.0, "default": 0.0},
        {"name": "rainfall_7d", "type": "float", "unit": "mm", "min": 0.0, "max": 3000.0, "default": 0.0},
        
        # Rainfall indicators
        {"name": "consecutive_wet_hours", "type": "float", "unit": "hours", "min": 0.0, "max": 720.0, "default": 0.0},
        {"name": "antecedent_precipitation_index", "type": "float", "unit": "API", "min": 0.0, "max": 500.0, "default": 0.0},
        {"name": "rainfall_z_score_24h", "type": "float", "unit": "sigma", "min": -5.0, "max": 15.0, "default": 0.0},
        {"name": "id_curve_ratio", "type": "float", "unit": "ratio", "min": 0.0, "max": 10.0, "default": 0.0},

        # Soil strata & change
        {"name": "soil_moisture_surface", "type": "float", "unit": "%", "min": 0.0, "max": 100.0, "default": 35.0},
        {"name": "soil_moisture_middle", "type": "float", "unit": "%", "min": 0.0, "max": 100.0, "default": 35.0},
        {"name": "soil_moisture_deep", "type": "float", "unit": "%", "min": 0.0, "max": 100.0, "default": 35.0},
        {"name": "soil_moisture_change_6h", "type": "float", "unit": "%", "min": -50.0, "max": 50.0, "default": 0.0},
        {"name": "soil_moisture_change_24h", "type": "float", "unit": "%", "min": -80.0, "max": 80.0, "default": 0.0},

        # Temporal Context
        {"name": "month_sin", "type": "float", "unit": "rad", "min": -1.0, "max": 1.0, "default": 0.0},
        {"name": "month_cos", "type": "float", "unit": "rad", "min": -1.0, "max": 1.0, "default": 1.0},
        {"name": "is_monsoon_season", "type": "float", "unit": "binary", "min": 0.0, "max": 1.0, "default": 0.0},
    ]

    FEATURE_NAMES = [f["name"] for f in FEATURE_SCHEMA]
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, preprocessor: Optional[Pipeline] = None):
        self.preprocessor = preprocessor or self._create_default_preprocessor()
        self.is_fitted = False

    @classmethod
    def _create_default_preprocessor(cls) -> Pipeline:
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ])

    def validate_features_dict(self, features: Dict[str, Any], allow_missing_with_default: bool = False) -> Dict[str, float]:
        """
        Validates an input dictionary against the exact schema.
        Raises IncompatibleFeatureSchemaError if mandatory features are missing or invalid.
        """
        cleaned: Dict[str, float] = {}
        missing = []

        for spec in self.FEATURE_SCHEMA:
            name = spec["name"]
            if name in features and features[name] is not None:
                val = float(features[name])
                # Bounds check warning/clamping
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
        """
        Transforms a single feature dictionary into the standardized 2D numpy array for inference.
        """
        valid_dict = self.validate_features_dict(features, allow_missing_with_default=True)
        ordered_vals = [valid_dict[col] for col in self.FEATURE_NAMES]
        arr = np.array(ordered_vals, dtype=np.float64).reshape(1, -1)
        if self.is_fitted:
            return self.preprocessor.transform(arr)
        return arr

    def fit(self, X: pd.DataFrame | np.ndarray) -> "LandslideFeaturePipeline":
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
        }
        json_str = json.dumps(schema_dict, indent=2)
        if filepath:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w") as f:
                f.write(json_str)
        return json_str


shared_feature_pipeline = LandslideFeaturePipeline()
