"""Deployment checks: settings from environment variables and model download from the Hub.

Run from the project root:   python -m pytest tests -q
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_secret_falls_back_to_environment(monkeypatch):
    # On Azure App Service there is no secrets.toml; App settings arrive as environment variables.
    monkeypatch.setenv("LEGAL_AI_TEST_SETTING", "from-env")
    assert app._get_secret("LEGAL_AI_TEST_SETTING") == "from-env"
    monkeypatch.delenv("LEGAL_AI_TEST_SETTING")
    assert app._get_secret("LEGAL_AI_TEST_SETTING") is None


def test_hub_download_requests_only_safe_files(monkeypatch, tmp_path):
    calls = {}

    def fake_snapshot_download(**kwargs):
        calls.update(kwargs)
        return str(tmp_path)

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    folder = app._download_module("C")
    assert folder == os.path.join(str(tmp_path), "Module_C")
    assert calls["repo_id"] == app.HF_MODEL_REPO == "vaishnavi1011/legal-case-outcome-predictor"
    patterns = calls["allow_patterns"]
    assert all(p.startswith("Module_C/") for p in patterns)
    assert not any(p.endswith((".bin", ".pt", ".pkl")) for p in patterns)   # never pickle files


def test_requirements_use_cpu_torch_and_no_test_tools():
    req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in req
    lines = [ln.split("#")[0].strip() for ln in req.splitlines()]
    assert not any(ln.startswith(("pytest", "spacy")) for ln in lines)
    assert not os.path.exists(os.path.join(ROOT, "requirement.txt"))
