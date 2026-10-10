"""Single entry point for the packaged app (PyInstaller exe) — also works from source.

    PhoenixContractMasters                     desktop app
    PhoenixContractMasters --run-all ...       command-line builder (same options as run_all.py)
    PhoenixContractMasters --uploader ...      database uploader (same options as db/uploader.py)
    PhoenixContractMasters --import DATE PATH… file downloaded exchange files (folders / zips) for DATE
    PhoenixContractMasters --selftest          start the app headless, open every page, exit (CI);
                                               with PHOENIX_SELFTEST_BUILD=YYYYMMDD it also builds every
                                               ready master from the app, as the Build button does

The app runs builds and uploads by starting itself with --run-all / --uploader, exactly like the source
version starts run_all.py / db.uploader, so one file is all a client needs.
"""

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def frozen_setup() -> None:
    """Packaged app: Prefect isn't bundled, and config must live somewhere writable (not the unpack folder)."""
    if not getattr(sys, "frozen", False):
        return
    os.environ["CONTRACT_DOWNLOADER_NO_PREFECT"] = "1"
    home = Path(os.environ.get("CONTRACT_DOWNLOADER_HOME", "~/.contract_downloader")).expanduser()
    cfg = home / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    for src in (Path(sys._MEIPASS) / "config").glob("*.json"):  # first run / new defaults; never overwrite edits
        if not (cfg / src.name).exists():
            shutil.copy2(src, cfg / src.name)
    os.environ.setdefault("CONTRACT_DOWNLOADER_CONFIG", str(cfg))


def selftest() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gui import app as A
    from gui import backend as B

    B.load_config(reload=True)
    qapp = QApplication([])
    A.load_fonts()
    qapp.setStyleSheet(A.qss(A.P))
    A.Dialog.auto = lambda title, body: None
    w = A.Window()
    w.show()
    for key, _, _ in A.NAV:
        w.go(key)
        qapp.processEvents()
        assert not w.grab().isNull(), key
    bd = os.environ.get("PHOENIX_SELFTEST_BUILD")
    if bd:
        ready = [m["key"] for m in B.api_state(dict(date=bd))["masters"] if m["ready"]]
        assert ready, f"nothing ready to build for {bd}"
        B.api_build(dict(date=bd, steps=ready))
        end = time.time() + 600
        while B.Job.current.code is None and time.time() < end:
            qapp.processEvents()
            time.sleep(0.1)
        states = {s["key"]: s["state"] for s in B.Job.current.snapshot()["steps"]}
        print("selftest build:", states, flush=True)
        if B.Job.current.code != 0 or any(v != "ok" for v in states.values()):
            print("\n".join(B.Job.current.lines[-60:]), flush=True)
            return 1
    print(f"selftest OK: {len(A.NAV)} pages, config {B.config_dir()}, data {B.get_base_path()}", flush=True)
    w.close()
    return 0


def main() -> None:
    frozen_setup()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "--run-all":
        for stream in (sys.stdout, sys.stderr):
            if stream:
                stream.reconfigure(errors="replace")
        sys.argv = ["run_all", *sys.argv[2:]]
        import run_all
        run_all.main()
    elif cmd == "--uploader":
        sys.argv = ["uploader", *sys.argv[2:]]
        from db.uploader import main as upload
        upload()
    elif cmd == "--import":
        from core.inputs import import_files
        r = import_files(sys.argv[3:], sys.argv[2])
        for f, origin in r["imported"]:
            print(f"added {f.exchange} {f.key}: {origin}")
        for name, f in r["wrong_date"]:
            print(f"wrong date: {name} (this date needs {f.name(sys.argv[2])})")
        print(f"{len(r['imported'])} added, {len(r['ignored'])} not needed")
    elif cmd == "--selftest":
        sys.exit(selftest())
    else:
        from gui.app import main as app
        app()


if __name__ == "__main__":
    main()
