"""Persistent GUI settings and run history, stored under ~/.contract_downloader/."""

import json
import os
from datetime import datetime
from pathlib import Path

HOME = Path(os.environ.get("CONTRACT_DOWNLOADER_HOME", "~/.contract_downloader")).expanduser()
LOG_DIR = HOME / "logs"
SETTINGS_FILE = HOME / "settings.json"
HISTORY_FILE = HOME / "history.json"
MAX_HISTORY = 200


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)  # atomic: a crash never leaves half a file


class Settings(dict):
    def __init__(self):
        super().__init__(_read(SETTINGS_FILE, {}))

    def save(self) -> None:
        _write(SETTINGS_FILE, dict(self))


class History:
    def __init__(self):
        self.entries = _read(HISTORY_FILE, [])

    def add(self, kind: str, title: str, cmd: list, exit_code: int, seconds: float,
            log_text: str, details: dict) -> dict:
        ts = datetime.now()
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{ts:%Y%m%d_%H%M%S}_{kind}.log"
        log_file.write_text(log_text, encoding="utf-8")
        entry = {
            "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": kind,
            "title": title,
            "cmd": cmd,
            "exit_code": exit_code,
            "seconds": round(seconds, 2),
            "log_file": str(log_file),
            **details,
        }
        self.entries.insert(0, entry)
        for old in self.entries[MAX_HISTORY:]:
            Path(old.get("log_file", "")).unlink(missing_ok=True)
        del self.entries[MAX_HISTORY:]
        self.save()
        return entry

    def remove(self, index: int) -> None:
        entry = self.entries.pop(index)
        Path(entry.get("log_file", "")).unlink(missing_ok=True)
        self.save()

    def save(self) -> None:
        _write(HISTORY_FILE, self.entries)
