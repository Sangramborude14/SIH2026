import hashlib
import json
import zipfile
import pytest
from pathlib import Path
from backend.app.ml.cli import cmd_model_export, cmd_model_import
from backend.app.ml.registry.model_registry import model_registry
import argparse


def test_model_export_and_import(tmp_path):
    """Verifies that a model artifact bundle can be exported to zip and imported with SHA256 integrity."""
    # Ensure active model files exist
    active_dir = Path("backend/models/landslide")
    assert (active_dir / "model.joblib").exists(), "Active model binary required for export test"

    export_zip = tmp_path / "test_bundle.zip"
    args_export = argparse.Namespace(model="v2.0.0", output=str(export_zip))
    cmd_model_export(args_export)

    assert export_zip.exists()
    checksum_file = export_zip.with_suffix(".zip.sha256")
    assert checksum_file.exists()

    # Validate zip contents
    with zipfile.ZipFile(export_zip, "r") as zf:
        names = zf.namelist()
        assert "model.joblib" in names
        assert "metadata.json" in names
        assert "feature_schema.json" in names
        assert "metrics.json" in names

    # Import bundle
    args_import = argparse.Namespace(file=str(export_zip))
    cmd_model_import(args_import)

    # Verify model registry is loaded
    status = model_registry.get_registry_status()
    assert status["is_active_model_trained_ml"] is True
    assert status["operational_status"] == "READY"
