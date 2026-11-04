import os
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = Path(os.environ.get("FINANZAS_DB_PATH", ROOT / "data" / "finanzas.db"))
LOCAL_CONFIG_PATH = ROOT / "data" / "local_config.json"
DEFAULT_PERIODS = 5


def local_config():
    """Optional machine-local parameters; never part of the repository."""
    if not LOCAL_CONFIG_PATH.exists():
        return {}
    config = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("La configuración local debe ser un objeto JSON.")
    return config


def today():
    return datetime.now(timezone(timedelta(hours=-5))).date()
