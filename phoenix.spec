# PyInstaller recipe for the one-file client app:   pyinstaller --noconfirm phoenix.spec   ->  dist/
# Prefect is left out on purpose (see core/prefect_utils.py); builds run as plain function calls.
import sys

from PyInstaller.utils.hooks import collect_submodules

datas = [(f"config/{n}.json", "config") for n in ("common", "nse", "bse", "mcx", "uploader_example")]
datas += [("gui/assets/app.png", "gui/assets"), ("gui/assets/app.ico", "gui/assets")]  # never config/local.json
hidden = (collect_submodules("flows") + collect_submodules("parsers")  # loaded by name in pipeline.py
          + ["run_all", "db.uploader", "db.schema", "gui.help_page",
             "sqlalchemy.dialects.postgresql.psycopg", "psycopg"])

a = Analysis(["phoenix.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["prefect", "tkinter", "matplotlib", "IPython", "pytest", "PIL"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="PhoenixContractMasters",
          console=False, upx=False, icon="gui/assets/app.ico" if sys.platform == "win32" else None)
