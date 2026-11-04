"""Project paths and a small helper for writing step logs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
RESULTS = ROOT / "results"
LOGS = RESULTS / "logs"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
RUNS = RESULTS / "runs"
CONFIGS = ROOT / "configs"


def write_log(name: str, payload: dict) -> Path:
    """Write a step log as JSON to results/logs/<name>.json.

    Input: step name and a JSON-serialisable dict. Output: path written.
    """
    LOGS.mkdir(parents=True, exist_ok=True)
    path = LOGS / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
