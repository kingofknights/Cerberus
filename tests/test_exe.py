"""The packaged app (PyInstaller exe) behaves like the source: import, CLI build, and a build started from
the GUI (the app runs itself as the build child). Runs only when PHOENIX_EXE points at the built file."""

import os
import subprocess
from pathlib import Path

import pytest

from test_e2e_mcx import BDATE, check_master, make_download

EXE = os.environ.get("PHOENIX_EXE")
pytestmark = pytest.mark.skipif(not EXE, reason="set PHOENIX_EXE to the built app to run")


def run(args, env, timeout=600):
    r = subprocess.run([EXE, *args], env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    assert r.returncode == 0, (r.stdout + r.stderr)[-4000:]
    return r.stdout


def test_exe_import_build_and_gui_build(tmp_path):
    env = {**os.environ, "BASE_PATH": str(tmp_path / "data"), "CONTRACT_DOWNLOADER_HOME": str(tmp_path / "home"),
           "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"}
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    make_download(downloads)

    out = run(["--import", BDATE, str(downloads)], env)
    assert "mcx_scrips" in out and "mcx_bhav" in out, out
    assert (tmp_path / "home" / "config" / "common.json").is_file(), "default config copied for the user"
    assert not (tmp_path / "home" / "config" / "local.json").exists(), "secrets are never bundled"

    run(["--run-all", "-s", "mcx_fo", "-d", BDATE, "--no-retry"], env)
    check_master(tmp_path / "data")

    master = tmp_path / "data" / "mcx" / "common" / BDATE / "mcx_fo_contract_master.csv"
    master.unlink()
    out = run(["--selftest"], {**env, "PHOENIX_SELFTEST_BUILD": BDATE})
    assert "'mcx_fo': 'ok'" in out and "selftest OK" in out, out
    check_master(tmp_path / "data")
