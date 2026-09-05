import json
import math
import random
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from backend.app.core.logging import logger
from backend.app.ml.features.feature_extractor import feature_extractor
from backend.app.ml.features.pipeline import LandslideFeaturePipeline
from backend.app.ml.features.pipeline_v2 import ResearchFeaturePipelineV2
from backend.app.ml.susceptibility.static_model import StaticGeospatialFactors
from backend.app.models.location import Location
from backend.app.models.weather import WeatherObservation
from backend.app.models.weather_forecast import WeatherForecastSnapshot



class SyntheticLandslideDatasetGenerator:
    """
    High-Volume Synthetic Landslide Dataset Generator for North Eastern Region (NER).
    Extends the multi-signal environmental simulation framework to produce realistic,
    reproducible training datasets without label leakage from the deterministic risk formula.

    Key Features:
    - 18+ varied meteorological & geotechnical scenarios.
    - Explicit hard negatives (high rain on flat terrain, steep dry slopes, saturated flat valleys).
    - Hidden geotechnical limit-equilibrium failure process with stochastic noise.
    - Preserves complete provenance: dataset_source, is_synthetic, scenario_id, seed, generator_version.
    """

    GENERATOR_VERSION = "2.0.0"

    # Diverse NER location profiles across elevation & slope spectra
    STATION_PROFILES = [
        {"id": "NER-SYNTH-SK-01", "name": "Gangtok High Ridge", "state": "Sikkim", "lat": 27.3389, "lon": 88.6065, "elev": 1780.0, "slope": 44.5, "susc": 0.84},
        {"id": "NER-SYNTH-AS-02", "name": "Guwahati Brahmaputra Basin", "state": "Assam", "lat": 26.1445, "lon": 91.7362, "elev": 55.0, "slope": 8.0, "susc": 0.12},
        {"id": "NER-SYNTH-ML-03", "name": "Cherrapunji Escarpment", "state": "Meghalaya", "lat": 25.2702, "lon": 91.7323, "elev": 1430.0, "slope": 38.0, "susc": 0.78},
        {"id": "NER-SYNTH-MZ-04", "name": "Aizawl North Ridge", "state": "Mizoram", "lat": 23.7271, "lon": 92.7176, "elev": 1132.0, "slope": 41.5, "susc": 0.82},
        {"id": "NER-SYNTH-NL-05", "name": "Kohima Valley & Pass", "state": "Nagaland", "lat": 25.6751, "lon": 94.1086, "elev": 1444.0, "slope": 34.0, "susc": 0.70},
        {"id": "NER-SYNTH-MN-06", "name": "Imphal Central Valley", "state": "Manipur", "lat": 24.8170, "lon": 93.9368, "elev": 786.0, "slope": 12.0, "susc": 0.22},
        {"id": "NER-SYNTH-AR-07", "name": "Tawang High Alpine Pass", "state": "Arunachal Pradesh", "lat": 27.5861, "lon": 91.8594, "elev": 3048.0, "slope": 48.0, "susc": 0.88},
        {"id": "NER-SYNTH-TR-08", "name": "Agartala Plains", "state": "Tripura", "lat": 23.8315, "lon": 91.2868, "elev": 15.0, "slope": 6.5, "susc": 0.08},
    ]

    SCENARIO_TYPES = [
        "normal_dry",
        "normal_monsoon",
        "moderate_rain",
        "heavy_rain_low_slope",       # HARD NEGATIVE
        "heavy_rain_high_slope",      # POTENTIAL POSITIVE
        "persistent_rain",
        "saturated_soil_no_failure",  # HARD NEGATIVE
        "steep_dry_slope",            # HARD NEGATIVE
        "antecedent_wetness",
        "rapid_rain_intensification",
        "extreme_rainfall",
        "landslide_buildup",
        "landslide_event",            # POSITIVE
        "post_landslide_recovery",
        "sensor_noise",
        "missing_soil_moisture",
        "stale_sensor",
        "forecast_rain_arriving",
    ]

    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        self.rng = random.Random(random_seed)

    def _generate_scenario_timeseries(
        self,
        station: Dict[str, Any],
        scenario: str,
        start_time: datetime,
        num_hours: int = 72
    ) -> Tuple[List[WeatherObservation], bool, float]:
        """
        Generates realistic multi-hour weather telemetry frames and independently simulates
        whether a slope failure occurs in the subsequent 24 hours via hidden geotechnical physics.
        Returns: (observations, landslide_within_24h, event_delay_hours)
        """
        loc_id = station["id"]
        slope = station["slope"]
        susc = station["susc"]
        base_elev = station["elev"]

        obs_list: List[WeatherObservation] = []
        curr_rain_1h = 0.0
        curr_soil_m = 25.0 + self.rng.uniform(-3.0, 5.0)

        # Baseline climate based on elevation
        base_temp = max(8.0, 26.0 - (base_elev / 250.0))
        base_pressure = 1013.25 * math.exp(-base_elev / 8400.0)

        for h in range(num_hours):
            frame_time = start_time + timedelta(hours=h)
            progress = h / max(1, num_hours - 1)

            # Scenario dynamics
            if scenario == "normal_dry":
                rain = 0.0
                curr_soil_m = max(18.0, curr_soil_m - 0.08 + self.rng.uniform(-0.3, 0.3))
                pressure_dev = self.rng.uniform(-1.0, 1.0)
            elif scenario == "normal_monsoon":
                rain = self.rng.uniform(0.0, 4.0) if self.rng.random() > 0.4 else 0.0
                curr_soil_m = min(70.0, max(45.0, curr_soil_m + (rain * 0.4) - 0.15))
                pressure_dev = self.rng.uniform(-2.0, 2.0)
            elif scenario in ("heavy_rain_low_slope", "heavy_rain_high_slope", "extreme_rainfall"):
                burst = math.sin(progress * math.pi) * 35.0
                rain = max(0.0, burst + self.rng.uniform(2.0, 12.0))
                curr_soil_m = min(98.0, curr_soil_m + (rain * 0.6) + self.rng.uniform(0.2, 0.8))
                pressure_dev = -8.0 * progress
            elif scenario == "persistent_rain":
                rain = self.rng.uniform(6.0, 16.0)
                curr_soil_m = min(96.0, curr_soil_m + 0.35)
                pressure_dev = -5.0 + self.rng.uniform(-1.0, 1.0)
            elif scenario == "saturated_soil_no_failure":
                rain = self.rng.uniform(0.5, 3.0)
                curr_soil_m = min(95.0, max(88.0, curr_soil_m + self.rng.uniform(-0.5, 0.5)))
                pressure_dev = -2.0
            elif scenario == "steep_dry_slope":
                rain = 0.0
                curr_soil_m = max(14.0, 22.0 - (progress * 4.0))
                pressure_dev = self.rng.uniform(-1.0, 1.0)
            elif scenario in ("landslide_buildup", "landslide_event"):
                rain = 15.0 + (progress ** 2) * 38.0 + self.rng.uniform(-2.0, 5.0)
                curr_soil_m = min(99.5, 60.0 + (progress * 38.0))
                pressure_dev = -12.0 * progress
            elif scenario == "rapid_rain_intensification":
                rain = (progress ** 3) * 55.0 + self.rng.uniform(0.0, 5.0)
                curr_soil_m = min(97.0, 35.0 + (progress ** 2) * 58.0)
                pressure_dev = -9.0 * progress
            elif scenario == "post_landslide_recovery":
                rain = max(0.0, 5.0 - (progress * 8.0))
                curr_soil_m = max(30.0, 92.0 - (progress * 45.0))
                pressure_dev = (progress * 6.0) - 3.0
            else:
                rain = self.rng.uniform(0.0, 8.0) if self.rng.random() > 0.5 else 0.0
                curr_soil_m = min(85.0, max(30.0, curr_soil_m + (rain * 0.3) - 0.2))
                pressure_dev = self.rng.uniform(-3.0, 3.0)

            # Rolling window calculations
            recent_rains = [o.rainfall_1h for o in obs_list[-5:]] + [rain]
            rain_6h = sum(recent_rains)
            recent_24 = [o.rainfall_1h for o in obs_list[-23:]] + [rain]
            rain_24h = sum(recent_24)

            obs = WeatherObservation(
                id=f"SYNTH-{loc_id}-{h}",
                location_id=loc_id,
                timestamp=frame_time,
                temperature=round(base_temp - (rain * 0.1) + self.rng.uniform(-0.8, 0.8), 1),
                humidity=round(min(100.0, max(40.0, 75.0 + (rain * 1.5))), 1),
                pressure=round(base_pressure + pressure_dev, 1),
                wind_speed=round(10.0 + (rain * 0.4) + self.rng.uniform(-2.0, 4.0), 1),
                wind_direction=round(self.rng.uniform(180.0, 240.0), 1),
                rainfall_1h=round(max(0.0, rain), 2),
                rainfall_6h=round(max(0.0, rain_6h), 2),
                rainfall_24h=round(max(0.0, rain_24h), 2),
                soil_moisture=round(max(0.0, min(100.0, curr_soil_m)), 1),
                source="SYNTHETIC_SCENARIO_ENGINE",
                source_version=self.GENERATOR_VERSION,
                observation_type="SIMULATED",
                quality_score=0.75 if scenario == "sensor_noise" else 1.0,
                freshness_status="STALE" if scenario == "stale_sensor" and h > num_hours - 6 else "FRESH"
            )
            obs_list.append(obs)

        # -------------------------------------------------------------
        # Hidden Geotechnical Limit-Equilibrium Failure Model (Ground Truth)
        # -------------------------------------------------------------
        latest = obs_list[-1]
        beta_rad = math.radians(slope)

        # Effective cohesion (kPa) and internal friction angle (degrees) based on terrain
        c_prime = 12.0 * (1.0 - susc * 0.4) + self.rng.uniform(-2.0, 2.0)
        phi_prime = math.radians(32.0 - (susc * 8.0) + self.rng.uniform(-1.5, 1.5))
        gamma = 19.5  # kN/m3 unit soil weight
        z = 2.2       # shear failure surface depth in meters

        # Pore water pressure u (kPa) from soil saturation profile
        sat_ratio = latest.soil_moisture / 100.0
        u = max(0.0, (sat_ratio - 0.70) * 45.0) if sat_ratio > 0.70 else 0.0

        # Additional seepage force from 24h antecedent rainfall
        seepage_factor = max(0.0, (latest.rainfall_24h - 90.0) * 0.08)

        # Resisting stress vs driving shear stress
        normal_stress = (gamma * z - u) * (math.cos(beta_rad) ** 2)
        resisting_shear = c_prime + (max(0.0, normal_stress) * math.tan(phi_prime))
        driving_shear = (gamma * z * math.sin(beta_rad) * math.cos(beta_rad)) + seepage_factor

        # Geotechnical Factor of Safety (FoS) with unmodelled geological heterogeneity noise
        noise = self.rng.gauss(0.0, 0.07)
        fos = (resisting_shear / max(0.01, driving_shear)) + noise

        # Hard negative clamps:
        # Low slope (< 18°) NEVER slides, even with 300mm rain (creates flooding, not landslide)
        if slope < 18.0:
            fos = max(1.8, fos)

        # Extremely dry soil (< 35% moisture) and zero recent rain NEVER triggers immediate rain-induced slide
        if latest.soil_moisture < 35.0 and latest.rainfall_24h < 15.0:
            fos = max(1.5, fos)

        # Failure occurs if FoS < 1.0 within target 24h window
        landslide_occurs = (fos < 1.0)
        event_delay = round(self.rng.uniform(4.0, 22.0), 1) if landslide_occurs else 999.0

        return obs_list, landslide_occurs, event_delay

    def generate_dataset(
        self,
        num_samples: int = 25000,
        output_path: Optional[Path] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Generates a balanced-to-realistic multi-signal landslide training dataset.
        Extracts the exact standardized 25-feature vector per sample used in production.
        """
        logger.info(f"Generating synthetic landslide dataset with {num_samples} samples (seed={self.random_seed})...")
        base_time = datetime(2025, 5, 1, 0, 0, tzinfo=timezone.utc)

        rows: List[Dict[str, Any]] = []
        positive_count = 0
        scenario_id_prefix = str(uuid.uuid4())[:8]

        for i in range(num_samples):
            station_info = self.rng.choice(self.STATION_PROFILES)
            scenario = self.rng.choice(self.SCENARIO_TYPES)

            # Reconstruct dummy Location model
            loc = Location(
                id=station_info["id"],
                name=station_info["name"],
                state=station_info["state"],
                district=station_info["name"].split()[0],
                latitude=station_info["lat"],
                longitude=station_info["lon"],
                elevation=station_info["elev"],
                slope_angle=station_info["slope"],
                susceptibility_score=station_info["susc"],
            )

            sample_time = base_time + timedelta(hours=i * 2 + self.rng.randint(0, 12))
            obs_history, label_24h, delay_h = self._generate_scenario_timeseries(
                station=station_info,
                scenario=scenario,
                start_time=sample_time,
                num_hours=72
            )
            current_obs = obs_history[-1]

            # Scenario & event group IDs
            scenario_id = f"SCEN-{scenario_id_prefix}-{(i // 8):05d}"
            event_id = f"EV-SYNTH-{(i // 8):05d}" if label_24h else None

            # 24h Numerical Forecast Simulation (Khan et al. 2022)
            fc_rain = (
                self.rng.uniform(45.0, 140.0)
                if scenario in ("heavy_rain_high_slope", "extreme_rainfall", "forecast_rain_arriving", "landslide_event")
                else self.rng.uniform(0.0, 15.0)
            )
            fc_snap = WeatherForecastSnapshot(
                location_id=loc.id,
                forecast_issued_at=current_obs.timestamp,
                forecast_valid_at=current_obs.timestamp + timedelta(hours=24),
                forecast_horizon_hours=24,
                precipitation_mm=round(fc_rain, 2),
                source="OPEN_METEO_SIMULATED",
            )

            static_factors = StaticGeospatialFactors(
                slope_angle=station_info["slope"],
                elevation=station_info["elev"],
                aspect_degrees=self.rng.uniform(0.0, 360.0),
                curvature=self.rng.uniform(-2.0, 2.0),
                lithology_strength=round(max(0.1, min(0.9, 1.0 - station_info["susc"] * 0.5 + self.rng.uniform(-0.1, 0.1))), 2),
                distance_to_active_fault_km=round(self.rng.uniform(5.0, 50.0), 1),
                lineament_density_km_km2=round(self.rng.uniform(0.5, 4.0), 2),
                distance_to_road_m=round(self.rng.uniform(50.0, 2500.0), 0),
                ndvi=round(self.rng.uniform(0.30, 0.85), 2),
            )

            # Extract research-v2 feature vector (29 features)
            v2_res = feature_extractor.extract_features_v2(
                location=loc,
                current_obs=current_obs,
                obs_history=obs_history,
                forecast_snapshot=fc_snap,
                static_factors=static_factors,
                prediction_time=current_obs.timestamp,
            )
            feature_dict = v2_res["features"]

            # Auxiliary horizons
            label_12h = 1 if (label_24h and delay_h <= 12.0) else 0
            label_6h = 1 if (label_24h and delay_h <= 6.0) else 0

            # Row dictionary with provenance
            row = {
                # Target Labels
                "landslide_within_24h": int(label_24h),
                "landslide_within_12h": int(label_12h),
                "landslide_within_6h": int(label_6h),
                "event_lead_time_hours": delay_h if label_24h else None,

                # Provenance Columns (Section 15)
                "dataset_source": "SYNTHETIC",
                "is_synthetic": True,
                "scenario_id": scenario_id,
                "scenario_type": scenario,
                "event_id": event_id,
                "location_id": loc.id,
                "station_name": loc.name,
                "timestamp": current_obs.timestamp.isoformat(),
                "generator_version": self.GENERATOR_VERSION,
                "seed": self.random_seed,

                # 29-Feature Schema Values & Backward Compatibility Aliases
                "rainfall_24h": feature_dict.get("current_rainfall_24h", 0.0),
                **feature_dict
            }
            rows.append(row)
            if label_24h:
                positive_count += 1

        df = pd.DataFrame(rows)

        # Dataset Manifest
        manifest = {
            "dataset_name": "synthetic_landslide_v2_research",
            "dataset_version": f"v{self.GENERATOR_VERSION}",
            "source": "SYNTHETIC_SCENARIO_ENGINE",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(df),
            "positive_count": positive_count,
            "negative_count": len(df) - positive_count,
            "positive_rate": round(positive_count / max(1, len(df)), 4),
            "date_range": f"{df['timestamp'].min()} to {df['timestamp'].max()}",
            "geographic_scope": "North Eastern Region (NER) Multi-Elevation Corridor",
            "is_synthetic": True,
            "validation_level": "SIMULATION_ONLY",
            "generator_version": self.GENERATOR_VERSION,
            "random_seed": self.random_seed,
            "feature_schema_version": "2.0.0-research",
            "feature_count": len(ResearchFeaturePipelineV2.FEATURE_NAMES),
            "features": ResearchFeaturePipelineV2.FEATURE_NAMES,
        }


        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Save Parquet or CSV based on extension
            if output_path.suffix == ".parquet":
                try:
                    df.to_parquet(output_path, index=False)
                except Exception:
                    # Fallback to CSV if pyarrow/fastparquet not installed
                    csv_fallback = output_path.with_suffix(".csv.gz")
                    df.to_csv(csv_fallback, index=False, compression="gzip")
                    manifest["file_format"] = "csv.gz"
                    output_path = csv_fallback
            else:
                df.to_csv(output_path, index=False)

            manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Saved synthetic dataset to {output_path} and manifest to {manifest_path}")

        return df, manifest
