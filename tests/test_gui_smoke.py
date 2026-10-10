"""The desktop app starts, every page renders, the theme switch and Help work — headless, on any OS."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_app_pages(tmp_path):
    os.environ.update(QT_QPA_PLATFORM="offscreen", BASE_PATH=str(tmp_path / "data"),
                      CONTRACT_DOWNLOADER_HOME=str(tmp_path / "home"))
    from PySide6.QtWidgets import QApplication

    from gui import app as A
    from gui import backend as B

    B.settings.clear()
    B.load_config(reload=True)
    qapp = QApplication.instance() or QApplication([])
    A.load_fonts()
    qapp.setStyleSheet(A.qss(A.P))
    A.Dialog.auto = lambda title, body: None
    w = A.Window()
    w.resize(1400, 900)
    w.show()
    for key, _, _ in A.NAV:
        w.go(key)
        qapp.processEvents()
        assert not w.grab().isNull()
    build = w.pages["build"]
    build.set_date("20261010")  # Saturday
    assert not build.build_btn.isEnabled()
    build.shift(-1)
    assert build.date == "20261009"
    assert len(w.pages["help"].anchors) == 9
    w.toggle_theme()
    w2 = A.Window.current_window
    assert w2 is not w and w2.pages["build"].date == "20261009"
    w2.close()
    qapp.processEvents()
