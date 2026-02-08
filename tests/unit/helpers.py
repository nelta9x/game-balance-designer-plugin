"""Shared helpers for unit tests around balance math scripts."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "game-balance-math" / "scripts"


def script_path(name: str) -> Path:
    return SCRIPTS_DIR / name


def load_script_module(name: str) -> ModuleType:
    path = script_path(name)
    if not path.exists():
        raise FileNotFoundError(path)

    module_name = f"tests_unit_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to create module spec for {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script_json(name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    path = script_path(name)
    cmd = [sys.executable, str(path), "--format", "json"]

    with tempfile.TemporaryDirectory(prefix="gbd-test-") as td:
        if payload is not None:
            input_path = Path(td) / "input.json"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            cmd.extend(["--input", str(input_path)])

        run = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
        if run.returncode != 0:
            raise RuntimeError(f"{name} failed with exit={run.returncode}: {run.stderr.strip()}")
        return json.loads(run.stdout)
