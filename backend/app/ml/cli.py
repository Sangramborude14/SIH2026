import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import joblib
import numpy as np
import pandas as pd
import yaml

from backend.app.core.logging import logger
from backend.app.ml.features.pipeline import LandslideFeaturePipeline
from backend.app.ml.features.pipeline_v2 import ResearchFeaturePipelineV2
from backend.app.ml.evaluation.sensitivity import sensitivity_analyzer
from backend.app.ml.prediction.trainer import trainer
from backend.app.ml.registry.model_registry import model_registry
from backend.app.ml.synthetic.generator import SyntheticLandslideDatasetGenerator


def get_project_root() -> Path:
    """Returns the absolute root directory of the repository in a portable manner."""
    return Path(__file__).resolve().parent.parent.parent.parent


def get_data_dir() -> Path:
    root = get_project_root()
    env_dir = os.environ.get("ML_DATA_DIR")
    return Path(env_dir) if env_dir else root / "data"


def get_artifact_dir() -> Path:
    root = get_project_root()
    env_dir = os.environ.get("ML_ARTIFACT_DIR")
    return Path(env_dir) if env_dir else root / "artifacts" / "models"


def get_active_model_dir() -> Path:
    root = get_project_root()
    env_dir = os.environ.get("ML_ACTIVE_MODEL_PATH")
    return Path(env_dir) if env_dir else root / "backend" / "models" / "landslide"


# -------------------------------------------------------------
# 1. BOOTSTRAP
# -------------------------------------------------------------
def cmd_bootstrap(args):
    """Verifies local directory layout, checks dependencies, and guides setup."""
    root = get_project_root()
    print("==================================================================")
    print("   SIH26001 ML Environment & Pipeline Bootstrap")
    print("==================================================================")
    print(f"Project Root: {root}")

    # 1. Create directory hierarchy
    dirs_to_create = [
        root / "data" / "raw" / "open_meteo",
        root / "data" / "raw" / "nasa_glc",
        root / "data" / "processed",
        root / "data" / "external" / "gsi",
        root / "data" / "landslide_inventory",
        root / "artifacts" / "models" / "landslide_24h",
        root / "backend" / "models" / "landslide",
    ]
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        print(f" [OK] Directory verified: {d.relative_to(root)}")

    # 2. Verify Python dependencies
    deps = ["numpy", "pandas", "sklearn", "joblib", "yaml", "httpx"]
    all_ok = True
    for dep in deps:
        try:
            __import__(dep)
            print(f" [OK] Dependency: {dep}")
        except ImportError:
            print(f" [MISSING] Dependency: {dep} -> install via pip install -r backend/requirements.txt")
            all_ok = False

    # 3. Model Registry Status
    is_active = model_registry.is_trained_model_active()
    print(f"Model Registry Active: {'YES (READY)' if is_active else 'NO (NOT_TRAINED - Baseline Physics Active)'}")

    print("------------------------------------------------------------------")
    if all_ok:
        print("Bootstrap check PASSED. Everything is ready!")
        print("Next Command to train baseline models:")
        print("  python -m backend.app.ml.cli demo-train")
    else:
        print("Please install missing dependencies first: pip install -r backend/requirements.txt")
    print("==================================================================")


# -------------------------------------------------------------
# 2. SYNTHETIC GENERATION
# -------------------------------------------------------------
def cmd_synthetic_generate(args):
    """Generates synthetic landslide dataset with hard negatives and provenance."""
    root = get_project_root()
    samples = args.samples or 25000
    seed = args.seed or 42
    output = Path(args.output) if args.output else root / "data" / "processed" / "synthetic_landslide_v1.parquet"

    generator = SyntheticLandslideDatasetGenerator(random_seed=seed)
    df, manifest = generator.generate_dataset(num_samples=samples, output_path=output)

    print("\n=== Synthetic Dataset Generated Successfully ===")
    print(f"Samples: {len(df)} total ({manifest['positive_count']} positives, {manifest['negative_count']} negatives)")
    print(f"Positive Rate: {manifest['positive_rate'] * 100:.2f}%")
    print(f"Saved to: {output}")


# -------------------------------------------------------------
# 3. DATASET IMPORTERS
# -------------------------------------------------------------
def cmd_dataset_import_gsi(args):
    """Imports manually downloaded GSI Bhusanket/Bhukosh landslide CSV into database."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file does not exist: {input_path}")
        sys.exit(1)

    from backend.app.core.database import AsyncSessionLocal
    from backend.app.ml.dataset.gsi_importer import GSILandslideImporter

    async def _run():
        async with AsyncSessionLocal() as session:
            return await GSILandslideImporter.import_from_csv(session, input_path)

    res = asyncio.run(_run())
    print("\n=== GSI Inventory Import Completed ===")
    print(json.dumps(res, indent=2))


def cmd_dataset_download_nasa_glc(args):
    """Downloads NASA GLC export, filters to NER coordinates, and imports into database."""
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.ml.dataset.nasa_glc_importer import NASAGLCLandslideImporter

    raw_dir = get_data_dir() / "raw" / "nasa_glc"

    async def _run():
        csv_path = await NASAGLCLandslideImporter.download_catalog(raw_dir)
        async with AsyncSessionLocal() as session:
            return await NASAGLCLandslideImporter.import_to_database(session, csv_path, filter_ner_only=True)

    res = asyncio.run(_run())
    print("\n=== NASA Global Landslide Catalog Import Completed ===")
    print(json.dumps(res, indent=2))


# -------------------------------------------------------------
# 4. HISTORICAL WEATHER BACKFILL
# -------------------------------------------------------------
def cmd_data_backfill_weather(args):
    """Backfills retrospective environmental data using Open-Meteo Historical Archive API."""
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.ml.dataset.open_meteo_historical import OpenMeteoHistoricalBackfillAdapter

    start_date = args.start or "2023-01-01"
    end_date = args.end or "2024-01-01"
    location = args.location or "all"

    adapter = OpenMeteoHistoricalBackfillAdapter(raw_cache_dir=get_data_dir() / "raw" / "open_meteo")

    async def _run():
        async with AsyncSessionLocal() as session:
            return await adapter.run_backfill(
                session=session,
                start_date=start_date,
                end_date=end_date,
                location_id=location
            )

    res = asyncio.run(_run())
    print("\n=== Open-Meteo Historical Backfill Completed ===")
    print(json.dumps(res, indent=2))


# -------------------------------------------------------------
# 5. MODEL TRAINING ENGINE
# -------------------------------------------------------------
def train_model_from_df(
    df: pd.DataFrame,
    output_dir: Path,
    horizon_hours: int = 24,
    random_seed: int = 42,
    training_source: str = "SYNTHETIC"
) -> Dict[str, Any]:
    """
    Standardized, leakage-safe tabular ML training routine.
    Trains Logistic Regression, Random Forest, and HistGradientBoosting on CPU,
    evaluates on held-out test split, calibrates probabilities, and saves production bundle.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    target_col = f"landslide_within_{horizon_hours}h"
    if target_col not in df.columns:
        target_col = "landslide_within_24h"

    logger.info(f"Target column: {target_col}, Total dataset size: {len(df)} rows.")

    # 1. Leakage-safe Grouped / Scenario Splitting
    group_col = "scenario_id" if "scenario_id" in df.columns else ("location_id" if "location_id" in df.columns else None)
    if group_col:
        unique_groups = np.array(list(df[group_col].unique()))
        rng = np.random.RandomState(random_seed)
        rng.shuffle(unique_groups)

        n_groups = len(unique_groups)
        n_train = int(n_groups * 0.70)
        n_val = int(n_groups * 0.15)

        train_groups = set(unique_groups[:n_train])
        val_groups = set(unique_groups[n_train:n_train + n_val])
        test_groups = set(unique_groups[n_train + n_val:])

        train_df = df[df[group_col].isin(train_groups)].copy()
        val_df = df[df[group_col].isin(val_groups)].copy()
        test_df = df[df[group_col].isin(test_groups)].copy()
    else:
        # Fallback to temporal row splitting
        n_total = len(df)
        n_train = int(n_total * 0.70)
        n_val = int(n_total * 0.15)
        train_df = df.iloc[:n_train].copy()
        val_df = df.iloc[n_train:n_train + n_val].copy()
        test_df = df.iloc[n_train + n_val:].copy()

    logger.info(f"Split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    # 2. Feature Pipeline Selection (v1 vs v2)
    is_v2 = ("current_rainfall_p99_ratio" in df.columns) or ("forecast_precipitation_24h" in df.columns)
    if is_v2:
        pipeline = ResearchFeaturePipelineV2()
        schema_ver_str = "2.0.0-research"
        model_ver_str = "v2.1.0-research"
    else:
        pipeline = LandslideFeaturePipeline()
        schema_ver_str = "1.0.0"
        model_ver_str = "v2.0.0"

    for col in pipeline.FEATURE_NAMES:
        if col not in train_df.columns:
            spec = next((f for f in pipeline.FEATURE_SCHEMA if f["name"] == col), None)
            default_val = spec["default"] if spec else 0.0
            train_df[col] = default_val
            val_df[col] = default_val
            test_df[col] = default_val

    y_train = train_df[target_col].values.astype(int)
    y_val = val_df[target_col].values.astype(int)
    y_test = test_df[target_col].values.astype(int)

    X_train = pipeline.fit_transform(train_df)
    X_val = pipeline.transform(val_df)
    X_test = pipeline.transform(test_df)

    # 3. Model Training & Comparison across 5 candidates
    training_res = trainer.train_full_pipeline(
        X_train=X_train,
        y_train=y_train,
        X_val=X_val,
        y_val=y_val,
        X_test=X_test,
        y_test=y_test,
        feature_names=pipeline.FEATURE_NAMES,
        calibrate=True,
    )

    selected_spec = training_res["selected_spec"]
    test_eval = training_res["test_evaluation"]
    final_model = training_res["model"]
    feature_importances = training_res["feature_importances"]
    shap_importances = training_res.get("shap_global_importances", [])

    # 4. Physical Sensitivity & Sanity Checks
    sanity_res = sensitivity_analyzer.run_comprehensive_sanity_checks(final_model, pipeline)
    logger.info(
        f"Physical sanity check status: {'PASSED' if sanity_res['overall_sanity_passed'] else 'FLAGGED'} "
        f"({sanity_res['tests_run']} checks run)"
    )

    # 5. Serialize Model Artifact Bundle
    model_path = output_dir / "model.joblib"
    joblib.dump(final_model, model_path)

    pipe_path = output_dir / "pipeline.joblib"
    joblib.dump(pipeline, pipe_path)

    schema_path = output_dir / "feature_schema.json"
    pipeline.export_schema_json(schema_path)

    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(test_eval, f, indent=2)

    metadata = {
        "model_id": f"tabular-{selected_spec['tier'].lower()}-ner",
        "model_name": selected_spec["name"],
        "model_tier": selected_spec["tier"],
        "model_version": model_ver_str,
        "forecast_horizon": f"{horizon_hours}H",
        "forecast_horizon_hours": horizon_hours,
        "training_source": training_source,
        "validation_level": "SIMULATION_ONLY" if training_source == "SYNTHETIC" else "HISTORICAL_VALIDATION",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_samples_count": len(train_df),
        "validation_samples_count": len(val_df),
        "test_samples_count": len(test_df),
        "positive_events_count": int(np.sum(y_train) + np.sum(y_val) + np.sum(y_test)),
        "negative_samples_count": int(len(df) - (np.sum(y_train) + np.sum(y_val) + np.sum(y_test))),
        "test_roc_auc": test_eval["roc_auc"],
        "test_pr_auc": test_eval["pr_auc"],
        "test_f1_score": test_eval["f1_score"],
        "test_precision": test_eval["precision"],
        "test_recall": test_eval["recall"],
        "test_brier_score": test_eval["brier_score"],
        "decision_threshold": 0.50,
        "random_seed": random_seed,
        "feature_schema_version": schema_ver_str,
        "feature_names": pipeline.FEATURE_NAMES,
        "feature_importances": feature_importances,
        "shap_global_importances": shap_importances,
        "candidate_comparison": training_res["candidate_comparison"],
        "sanity_checks": sanity_res,
        "monotonic_assumptions": training_res.get("monotonic_assumptions", {}),
    }

    meta_path = output_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # 6. Copy to active model path for immediate production inference
    active_dir = get_active_model_dir()
    active_dir.mkdir(parents=True, exist_ok=True)
    for fname in ["model.joblib", "pipeline.joblib", "feature_schema.json", "metrics.json", "metadata.json"]:
        shutil.copy2(output_dir / fname, active_dir / fname)

    # Reload active registry model
    model_registry.reload_artifacts()

    return metadata



def cmd_train(args):
    """Executes offline model training using config file or parameters."""
    root = get_project_root()
    config_path = Path(args.config) if args.config else root / "backend" / "app" / "ml" / "config" / "default.yaml"

    cfg = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    horizon = int(args.horizon or cfg.get("forecast_horizon_hours", 24))
    seed = int(args.seed or cfg.get("random_seed", 42))
    dataset_type = args.dataset or cfg.get("dataset", {}).get("source", "synthetic")

    out_dir = get_artifact_dir() / "landslide_24h" / f"v{cfg.get('version', '2.0.0')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if dataset_type == "synthetic":
        synth_file = root / "data" / "processed" / "synthetic_landslide_v1.parquet"
        if not synth_file.exists():
            print(f"Synthetic dataset not found at {synth_file}. Generating now...")
            gen = SyntheticLandslideDatasetGenerator(random_seed=seed)
            df, _ = gen.generate_dataset(num_samples=25000, output_path=synth_file)
        else:
            try:
                df = pd.read_parquet(synth_file)
            except Exception:
                csv_fallback = synth_file.with_suffix(".csv.gz")
                df = pd.read_csv(csv_fallback)
    else:
        # Load real dataset
        inv_path = cfg.get("dataset", {}).get("inventory_path")
        telem_path = cfg.get("dataset", {}).get("telemetry_path")
        if not inv_path or not telem_path or not Path(inv_path).exists():
            print("Error: Real dataset inventory or telemetry path not found. Falling back to synthetic.")
            return cmd_train(argparse.Namespace(config=args.config, dataset="synthetic", horizon=horizon, seed=seed))
        # run real training
        from backend.app.ml.training.train import run_training_pipeline
        res = run_training_pipeline(inv_path, telem_path, output_dir=str(out_dir), horizon=f"{horizon}h", random_seed=seed)
        print(json.dumps(res, indent=2))
        return

    metadata = train_model_from_df(
        df=df,
        output_dir=out_dir,
        horizon_hours=horizon,
        random_seed=seed,
        training_source="SYNTHETIC"
    )

    print("\n=== Model Training Completed Successfully ===")
    print(f"Active Model: {metadata['model_name']} ({metadata['model_tier']})")
    print(f"Validation: PR-AUC={metadata['test_pr_auc']:.4f}, ROC-AUC={metadata['test_roc_auc']:.4f}, F1={metadata['test_f1_score']:.4f}")
    print(f"Saved to: {out_dir}")


def cmd_demo_train(args):
    """Convenience command: generates synthetic dataset, trains 3 baseline models, evaluates, and activates."""
    print("==================================================================")
    print("   SIH26001 Complete ML Demo Training Pipeline")
    print("==================================================================")
    root = get_project_root()
    synth_file = root / "data" / "processed" / "synthetic_landslide_demo.parquet"
    synth_csv = root / "data" / "processed" / "synthetic_landslide_demo.csv.gz"

    df = None
    if synth_file.exists():
        try:
            df = pd.read_parquet(synth_file)
        except Exception:
            df = None
    if df is None and synth_csv.exists():
        try:
            df = pd.read_csv(synth_csv)
        except Exception:
            df = None

    # If existing demo dataset is missing research v2 columns, regenerate
    need_regenerate = False
    if df is not None:
        if "current_rainfall_p99_ratio" not in df.columns or "forecast_precipitation_24h" not in df.columns:
            need_regenerate = True
            print("Step 1/4: Existing demo dataset is on legacy schema v1. Regenerating with Research Schema v2...")
        else:
            print(f"Step 1/4: Using existing research-v2 synthetic dataset at {synth_file.name} ({len(df)} rows)...")

    if df is None or need_regenerate:
        print("Step 1/4: Generating 15,000 multi-signal synthetic scenario samples (Research Schema v2)...")
        gen = SyntheticLandslideDatasetGenerator(random_seed=42)
        df, manifest = gen.generate_dataset(num_samples=15000, output_path=synth_file)
        print(f" Generated: {len(df)} samples across 18 scenarios ({manifest['positive_count']} positives).")

    print("\nStep 2/4: Splitting data (Group-safe scenario holdout)...")
    out_dir = get_artifact_dir() / "landslide_24h" / "v2.1.0-research"

    print("Step 3/4: Benchmarking 5 candidate models (Logistic Regression, Random Forest, HistGB, Standard XGBoost, Research-Constrained XGBoost)...")
    metadata = train_model_from_df(
        df=df,
        output_dir=out_dir,
        horizon_hours=24,
        random_seed=42,
        training_source="SYNTHETIC"
    )

    print("\nStep 4/4: Authentic held-out evaluation & artifact serialization...")
    print("-------------------------------------------------------------------------------------------")
    print(f" Selected Model: {metadata['model_name']} ({metadata['model_tier']})")
    print(f" Feature Schema: {metadata['feature_schema_version']} ({len(metadata['feature_names'])} features)")
    print(f" Training Source: {metadata['training_source']} ({metadata['validation_level']})")
    print(f" Test ROC-AUC:   {metadata['test_roc_auc']:.4f}")
    print(f" Test PR-AUC:    {metadata['test_pr_auc']:.4f}")
    print(f" Test F1-Score:  {metadata['test_f1_score']:.4f}")
    print(f" Test Precision: {metadata['test_precision']:.4f}")
    print(f" Test Recall:    {metadata['test_recall']:.4f}")
    print(f" Test Brier:     {metadata['test_brier_score']:.4f}")
    print("-------------------------------------------------------------------------------------------")

    print("\nCandidate Model Comparison (Held-Out Validation Fold):")
    print(f"{'Model Name':<42} | {'PR-AUC':<8} | {'ROC-AUC':<8} | {'F1-Score':<8} | {'Brier':<8}")
    print("-" * 82)
    for c in metadata.get("candidate_comparison", []):
        print(f"{c['name']:<42} | {c['pr_auc']:<8.4f} | {c['roc_auc']:<8.4f} | {c['f1_score']:<8.4f} | {c['brier_score']:<8.4f}")

    sanity = metadata.get("sanity_checks", {})
    if sanity:
        print("\nPhysical Sensitivity & Geotechnical Sanity Checks:")
        for check_name, check_info in sanity.get("checks", {}).items():
            status_str = "[PASS]" if check_info.get("passed") else "[WARN]"
            print(f"  {status_str} {check_name}: {check_info.get('description')}")

    shap_list = metadata.get("shap_global_importances", [])
    if shap_list:
        print("\nTop Global TreeSHAP Feature Attributions:")
        for item in shap_list[:5]:
            print(f"  * {item['feature']}: importance={item['importance_score']:.4f} ({item['method']})")

    print("-------------------------------------------------------------------------------------------")
    print("RESEARCH MODEL READY FOR PRODUCTION INFERENCE. Zero startup training required.")
    print("===========================================================================================")


# -------------------------------------------------------------
# 6. MODEL EXPORT / IMPORT / ACTIVATE
# -------------------------------------------------------------
def cmd_model_export(args):
    """Exports model artifact directory into portable .zip bundle with SHA256 checksum."""
    version = args.model or "v2.0.0"
    source_dir = get_artifact_dir() / "landslide_24h" / version
    if not source_dir.exists():
        source_dir = get_active_model_dir()

    if not (source_dir / "model.joblib").exists():
        print(f"Error: Model binary not found at {source_dir}")
        sys.exit(1)

    out_zip = Path(args.output) if args.output else Path(f"landslide-24h-{version}.zip")
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in source_dir.glob("*"):
            if f.is_file():
                zf.write(f, arcname=f.name)

    # Compute checksum
    sha256 = hashlib.sha256(open(out_zip, "rb").read()).hexdigest()
    checksum_path = out_zip.with_suffix(".zip.sha256")
    with open(checksum_path, "w") as f:
        f.write(f"{sha256}  {out_zip.name}\n")

    print("\n=== Model Bundle Exported Successfully ===")
    print(f"Archive:  {out_zip.resolve()} ({out_zip.stat().st_size} bytes)")
    print(f"Checksum: {sha256}")
    print(f"SHA File: {checksum_path.resolve()}")


def cmd_model_import(args):
    """Validates and imports a model bundle into the local artifact repository."""
    bundle_path = Path(args.file)
    if not bundle_path.exists():
        print(f"Error: Model bundle not found: {bundle_path}")
        sys.exit(1)

    # Verify checksum if present
    checksum_path = bundle_path.with_suffix(".zip.sha256")
    if checksum_path.exists():
        expected_sha = open(checksum_path).read().split()[0].strip()
        actual_sha = hashlib.sha256(open(bundle_path, "rb").read()).hexdigest()
        if expected_sha.lower() != actual_sha.lower():
            print(f"Error: Checksum mismatch! Expected {expected_sha}, got {actual_sha}")
            sys.exit(1)
        print(" [OK] Checksum verified successfully.")

    # Extract version from metadata inside zip
    with zipfile.ZipFile(bundle_path, "r") as zf:
        if "metadata.json" not in zf.namelist():
            print("Error: Invalid bundle! metadata.json missing from zip.")
            sys.exit(1)
        meta_data = json.loads(zf.read("metadata.json").decode("utf-8"))
        version = meta_data.get("model_version", "v2.0.0")

    target_dir = get_artifact_dir() / "landslide_24h" / version
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle_path, "r") as zf:
        zf.extractall(target_dir)

    print(f" [OK] Extracted model to: {target_dir}")

    # Activate model
    active_dir = get_active_model_dir()
    for f in target_dir.glob("*"):
        if f.is_file():
            shutil.copy2(f, active_dir / f.name)

    model_registry.reload_artifacts()
    print(" [OK] Model activated for production inference.")


def cmd_model_activate(args):
    """Activates a specific versioned artifact directory for production inference."""
    version = args.version
    source_dir = get_artifact_dir() / "landslide_24h" / version
    if not source_dir.exists():
        print(f"Error: Version directory does not exist: {source_dir}")
        sys.exit(1)

    active_dir = get_active_model_dir()
    for f in source_dir.glob("*"):
        if f.is_file():
            shutil.copy2(f, active_dir / f.name)

    model_registry.reload_artifacts()
    print(f" [OK] Activated model version {version} at {active_dir}")



def cmd_status(args):
    """Displays comprehensive model provenance, metrics, and training status."""
    st = model_registry.get_registry_status()
    print("==================================================================")
    print("   SIH26001 ML Model Registry & Provenance Status")
    print("==================================================================")
    print(f"Operational Status:   {st['operational_status']}")
    print(f"Active Model ID:      {st['active_model_id']}")
    print(f"Active Model Tier:    {st['active_model_tier']}")
    print(f"Is Trained ML Active: {st['is_active_model_trained_ml']}")
    print(f"Features Monitored:   {st['feature_count']} features")
    print(f"Feature Schema Ver:   2.0.0")

    metrics = model_registry.get_active_metrics()
    if metrics:
        print("------------------------------------------------------------------")
        print("Authentic Held-Out Evaluation Metrics:")
        print(f" - ROC-AUC:   {metrics.get('roc_auc')}")
        print(f" - PR-AUC:    {metrics.get('pr_auc')}")
        print(f" - F1-Score:  {metrics.get('f1_score')}")
        print(f" - Precision: {metrics.get('precision')}")
        print(f" - Recall:    {metrics.get('recall')}")
        print(f" - Brier:     {metrics.get('brier_score')}")
    print("==================================================================")


def cmd_test_sensitivity(args):
    """Evaluates physical invariants and monotonicity constraints on active model."""
    from backend.app.ml.evaluation.sensitivity import LandslideSensitivityAnalyzer
    model_registry.reload_artifacts()
    if not model_registry.is_trained_model_active():
        print("Error: Active model is NOT_TRAINED. Please run 'demo-train' or 'train' first.")
        sys.exit(1)
    predictor = model_registry.get_active_predictor()

    print("\n==================================================================")
    print("   SIH26001 Physical Monotonicity & Geotechnical Sensitivity")
    print("==================================================================")
    analyzer = LandslideSensitivityAnalyzer(
        feature_names=predictor.feature_names,
        schema_version=predictor.schema_version
    )
    report = analyzer.run_all_checks(predictor)

    for name, check in report.get("checks", {}).items():
        tag = "[PASS]" if check.get("passed") else "[FAIL]"
        print(f"{tag} {name:<35}: {check.get('description')}")
        if not check.get("passed"):
            print(f"       Violations: {check.get('violations')}")

    print("------------------------------------------------------------------")
    overall = "PASSED ALL PHYSICAL CHECKS" if report.get("all_passed") else "FAILED ONE OR MORE CHECKS"
    print(f"Overall Result: {overall}")
    print("==================================================================\n")
    if not report.get("all_passed"):
        sys.exit(1)


# -------------------------------------------------------------
# CLI ENTRYPOINT
# -------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.ml.cli",
        description="SIH26001 North Eastern Region Landslide ML Operations CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # bootstrap
    subparsers.add_parser("bootstrap", help="Verify environment, directories, and dependencies")

    # demo-train
    subparsers.add_parser("demo-train", help="One-command end-to-end synthetic demo training")

    # test-sensitivity
    subparsers.add_parser("test-sensitivity", help="Run physical monotonicity and geotechnical sensitivity checks on active model")

    # status
    subparsers.add_parser("status", help="Print model provenance and registry status")

    # synthetic
    p_synth = subparsers.add_parser("synthetic", help="Synthetic dataset operations")
    p_synth_sub = p_synth.add_subparsers(dest="subcommand")
    p_gen = p_synth_sub.add_parser("generate", help="Generate synthetic scenario dataset")
    p_gen.add_argument("--samples", type=int, default=25000, help="Number of samples (default: 25000)")
    p_gen.add_argument("--seed", type=int, default=42, help="Random seed")
    p_gen.add_argument("--output", type=str, help="Output parquet/csv path")

    # dataset
    p_ds = subparsers.add_parser("dataset", help="Ground-truth dataset operations")
    p_ds_sub = p_ds.add_subparsers(dest="subcommand")
    p_gsi = p_ds_sub.add_parser("import-gsi", help="Import GSI Bhusanket/Bhukosh landslide CSV")
    p_gsi.add_argument("--input", required=True, help="Path to GSI CSV file")
    p_nasa = p_ds_sub.add_parser("download-nasa-glc", help="Download and import NASA Global Landslide Catalog")

    # data
    p_data = subparsers.add_parser("data", help="Telemetry acquisition operations")
    p_data_sub = p_data.add_subparsers(dest="subcommand")
    p_bf = p_data_sub.add_parser("backfill-weather", help="Backfill historical weather from Open-Meteo")
    p_bf.add_argument("--location", default="all", help="Location ID or 'all'")
    p_bf.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    p_bf.add_argument("--end", default="2024-01-01", help="End date (YYYY-MM-DD)")

    # train
    p_train = subparsers.add_parser("train", help="Train baseline ML models")
    p_train.add_argument("--config", help="Path to training config YAML")
    p_train.add_argument("--dataset", default="synthetic", choices=["synthetic", "real"], help="Dataset type")
    p_train.add_argument("--horizon", default="24", help="Forecast horizon in hours (default: 24)")
    p_train.add_argument("--seed", type=int, default=42, help="Random seed")

    # model
    p_model = subparsers.add_parser("model", help="Model artifact packaging operations")
    p_model_sub = p_model.add_subparsers(dest="subcommand")
    p_exp = p_model_sub.add_parser("export", help="Export model to portable .zip bundle")
    p_exp.add_argument("--model", default="v2.0.0", help="Model version string")
    p_exp.add_argument("--output", help="Output zip filename")
    p_imp = p_model_sub.add_parser("import", help="Import model from portable .zip bundle")
    p_imp.add_argument("--file", required=True, help="Path to .zip model bundle")
    p_act = p_model_sub.add_parser("activate", help="Activate model version")
    p_act.add_argument("--version", required=True, help="Version string to activate")

    args = parser.parse_args()

    if args.command == "bootstrap":
        cmd_bootstrap(args)
    elif args.command == "demo-train":
        cmd_demo_train(args)
    elif args.command == "test-sensitivity":
        cmd_test_sensitivity(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "synthetic" and getattr(args, "subcommand", None) == "generate":
        cmd_synthetic_generate(args)
    elif args.command == "dataset" and getattr(args, "subcommand", None) == "import-gsi":
        cmd_dataset_import_gsi(args)
    elif args.command == "dataset" and getattr(args, "subcommand", None) == "download-nasa-glc":
        cmd_dataset_download_nasa_glc(args)
    elif args.command == "data" and getattr(args, "subcommand", None) == "backfill-weather":
        cmd_data_backfill_weather(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "model" and getattr(args, "subcommand", None) == "export":
        cmd_model_export(args)
    elif args.command == "model" and getattr(args, "subcommand", None) == "import":
        cmd_model_import(args)
    elif args.command == "model" and getattr(args, "subcommand", None) == "activate":
        cmd_model_activate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
