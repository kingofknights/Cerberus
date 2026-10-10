"""
Centralized Configuration Loader for the contract master generation flows.
Supports modular exchange configs (config/common.json, config/nse.json, config/bse.json, config/mcx.json)
or root config.json, with dynamic base path resolution and BASE_PATH env override.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_EXCHANGE_CONFIGS_CACHE: Dict[str, Dict[str, Any]] = {}


def find_default_config_path() -> Path:
    """
    Find default config/ directory or config.json with external-first priority:
      1. CONTRACT_DOWNLOADER_CONFIG or PHOENIX_CONFIG_DIR env var
      2. <binary_directory>/config/ (adjacent to compiled binary)
      3. ./config/ (current working directory)
      4. script/contractDownloader/config/ (source tree)
      5. sys._MEIPASS/config (fallback embedded bundled configs)
    """
    # 1. Environment variable
    env_path = os.environ.get("CONTRACT_DOWNLOADER_CONFIG") or os.environ.get("PHOENIX_CONFIG_DIR")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    # 2. Directory adjacent to the executable or launcher script (e.g. build/Release/config/)
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        exe_dir = Path(sys.executable).resolve().parent
        exe_cfg_dir = exe_dir / "config"
        if exe_cfg_dir.is_dir() and any(exe_cfg_dir.glob("*.json")):
            return exe_cfg_dir
        if (exe_dir / "config.json").is_file():
            return exe_dir / "config.json"
    elif sys.argv and sys.argv[0]:
        launcher_dir = Path(sys.argv[0]).resolve().parent
        launcher_cfg_dir = launcher_dir / "config"
        if launcher_cfg_dir.is_dir() and any(launcher_cfg_dir.glob("*.json")):
            return launcher_cfg_dir
        if (launcher_dir / "config.json").is_file():
            return launcher_dir / "config.json"

    # 3. Current working directory config/
    cwd_cfg_dir = Path.cwd() / "config"
    if cwd_cfg_dir.is_dir() and any(cwd_cfg_dir.glob("*.json")):
        return cwd_cfg_dir
    if (Path.cwd() / "config.json").is_file():
        return Path.cwd() / "config.json"

    # 4. Source tree config/
    source_dir = Path(__file__).resolve().parent.parent
    source_cfg_dir = source_dir / "config"
    if source_cfg_dir.is_dir() and any(source_cfg_dir.glob("*.json")):
        return source_cfg_dir

    # 5. Embedded fallback inside PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        meipass_cfg = Path(sys._MEIPASS) / "config"
        if meipass_cfg.is_dir():
            return meipass_cfg

    return source_cfg_dir


def find_default_config_dir() -> Path:
    """Find config/ directory location with external-first priority."""
    p = find_default_config_path()
    if p.is_dir():
        return p
    if p.is_file():
        return p.parent
    return Path.cwd() / "config"


def load_modular_exchange_configs(config_dir: Path) -> Dict[str, Any]:
    """
    Load and merge modular JSON configuration files from a config directory:
      - common.json
      - nse.json
      - bse.json
      - mcx.json
    """
    merged: Dict[str, Any] = {
        "storage": {"base_path": os.path.expanduser("~/Downloads/test")},
        "holidays": {},
        "orchestration": {},
    }

    # 1. Load common.json if present
    common_path = config_dir / "common.json"
    if common_path.is_file():
        with open(common_path, "r", encoding="utf-8") as f:
            c_data = json.load(f)
            for k, v in c_data.items():
                if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                    merged[k].update(v)
                else:
                    merged[k] = v

    # 2. Load exchange specific files: nse.json, bse.json, mcx.json
    for exch in ("nse", "bse", "mcx"):
        exch_file = config_dir / f"{exch}.json"
        if not exch_file.is_file():
            continue

        with open(exch_file, "r", encoding="utf-8") as f:
            e_data = json.load(f)
            _EXCHANGE_CONFIGS_CACHE[exch] = e_data

            # Merge storage
            if "storage" in e_data:
                merged.setdefault("storage", {})[exch] = e_data["storage"]

            # Merge schedules
            if "schedules" in e_data:
                merged.setdefault("orchestration", {}).setdefault("schedules", {}).update(e_data["schedules"])

    # 3. Machine-local secrets (git-ignored), e.g. {"database": {"url": "postgresql+psycopg://user:pass@host/db"}}
    local_path = config_dir / "local.json"
    if local_path.is_file():
        with open(local_path, "r", encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v

    return merged


def load_config(config_path: Optional[str] = None, reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration from modular config directory or unified JSON file.
    """
    global _CONFIG_CACHE, _EXCHANGE_CONFIGS_CACHE
    if _CONFIG_CACHE is not None and not reload and config_path is None:
        return _CONFIG_CACHE

    target_path = Path(config_path) if config_path else find_default_config_path()

    if target_path.is_dir():
        cfg = load_modular_exchange_configs(target_path)
    elif target_path.is_file():
        with open(target_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # Check if this config.json points to modular config files
        if "configs" in cfg:
            parent_dir = target_path.parent
            for exch, rel_path in cfg["configs"].items():
                full_p = parent_dir / rel_path
                if full_p.is_file():
                    with open(full_p, "r", encoding="utf-8") as ef:
                        e_data = json.load(ef)
                        _EXCHANGE_CONFIGS_CACHE[exch.lower()] = e_data
                        if "storage" in e_data:
                            cfg.setdefault("storage", {})[exch.lower()] = e_data["storage"]
        else:
            # Check if config/ subdirectory exists alongside config.json
            cfg_dir = target_path.parent / "config"
            if cfg_dir.is_dir():
                mod_cfg = load_modular_exchange_configs(cfg_dir)
                for k, v in mod_cfg.items():
                    if k not in cfg:
                        cfg[k] = v
                    elif isinstance(v, dict) and isinstance(cfg[k], dict):
                        for sub_k, sub_v in v.items():
                            if sub_k not in cfg[k]:
                                cfg[k][sub_k] = sub_v
    else:
        # Fallback default
        cfg_dir = Path(__file__).resolve().parent.parent / "config"
        if cfg_dir.is_dir():
            cfg = load_modular_exchange_configs(cfg_dir)
        else:
            cfg = {
                "storage": {"base_path": os.path.expanduser("~/Downloads/test")},
                "holidays": {},
                "orchestration": {},
            }

    # Environment variable overrides
    storage = cfg.setdefault("storage", {})
    if "BASE_PATH" in os.environ:
        storage["base_path"] = os.environ["BASE_PATH"]
    elif "REFDATA_BASE_PATH" in os.environ:
        storage["base_path"] = os.environ["REFDATA_BASE_PATH"]
    elif "REFDATA_DIR" in os.environ:
        storage["base_path"] = os.environ["REFDATA_DIR"]

    raw_base = storage.get("base_path", "~/Downloads/test")
    base_path = os.path.expanduser(raw_base).rstrip("/")
    storage["base_path"] = base_path

    # Register holidays from config into the shared calendar
    from core.dates import set_holidays
    for exch, h_list in cfg.get("holidays", {}).items():
        if h_list:
            set_holidays(exch, h_list)

    _CONFIG_CACHE = cfg
    return cfg


def get_config() -> Dict[str, Any]:
    """Retrieve cached configuration or load default."""
    return load_config()


def get_exchange_config(exchange: str) -> Dict[str, Any]:
    """
    Get full exchange-specific configuration dictionary (from config/{exchange}.json or root).
    """
    exch = exchange.lower().strip()
    if exch in _EXCHANGE_CONFIGS_CACHE:
        return _EXCHANGE_CONFIGS_CACHE[exch]

    cfg_dir = find_default_config_dir()
    exch_file = cfg_dir / f"{exch}.json"
    if exch_file.is_file():
        with open(exch_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            _EXCHANGE_CONFIGS_CACHE[exch] = data
            return data

    cfg = get_config()
    res = {}
    if "storage" in cfg and exch in cfg["storage"]:
        res["storage"] = cfg["storage"][exch]
    return res



def get_base_path() -> str:
    """Get common base storage path."""
    raw = get_config().get("storage", {}).get("base_path", "~/Downloads/test")
    return os.path.expanduser(raw).rstrip("/")


def get_exchange_path(exchange: str) -> str:
    """Get root directory for a specific exchange under common base path (e.g. PATH:nse/)."""
    base = get_base_path()
    exch_key = exchange.lower().strip()
    return f"{base}/{exch_key}"


def get_storage_config(exchange: Optional[str] = None) -> Dict[str, Any]:
    """
    Get storage and path configuration with base_path resolved for a specific exchange or root.
    """
    cfg = get_config()
    storage = cfg.get("storage", {})
    raw_base = storage.get("base_path", "~/Downloads/test")
    base_path = os.path.expanduser(raw_base).rstrip("/")

    def _resolve_val(val: str) -> str:
        res = val.replace("{base_path}", base_path)
        if res.startswith("~"):
            res = os.path.expanduser(res)
        return res

    if exchange:
        exch_key = exchange.lower().strip()
        exch_sec = storage.get(exch_key, {})
        if not exch_sec:
            exch_cfg = get_exchange_config(exch_key)
            exch_sec = exch_cfg.get("storage", {})

        resolved = {}
        for k, v in exch_sec.items():
            if isinstance(v, str):
                resolved[k] = _resolve_val(v)
            else:
                resolved[k] = v
        return resolved

    # Root storage resolved
    resolved_root = {"base_path": base_path}
    for k, v in storage.items():
        if isinstance(v, str):
            resolved_root[k] = _resolve_val(v)
        elif isinstance(v, dict):
            resolved_root[k] = {
                sub_k: (_resolve_val(sub_v) if isinstance(sub_v, str) else sub_v)
                for sub_k, sub_v in v.items()
            }
        else:
            resolved_root[k] = v
    return resolved_root
