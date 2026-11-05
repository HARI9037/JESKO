from __future__ import annotations
import os
from pathlib import Path

def config_dir() -> Path:
    return Path(os.environ.get("JESKO_CONFIG_DIR", Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "JESKO"))

def data_dir() -> Path:
    return Path(os.environ.get("JESKO_DATA_DIR", Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "JESKO"))

def ensure_dirs() -> None:
    config_dir().mkdir(parents=True, exist_ok=True)
    data_dir().mkdir(parents=True, exist_ok=True)

def db_path() -> Path:
    return data_dir() / "events.sqlite3"
