"""Phoenix Contract Masters — native desktop app (Qt 6 / PySide6) over gui/backend.py.

Start with:  python3 -m gui   (or ./run_gui.sh)
"""

import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import (QAbstractTableModel, QDate, QModelIndex, QObject, QRectF, QRunnable, QSize, Qt,
                            QThreadPool, QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QIcon, QIntValidator, QKeySequence, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QShortcut, QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtWidgets import (QAbstractButton, QAbstractItemView, QApplication, QButtonGroup, QCheckBox,
                               QComboBox, QDateEdit, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from shiboken6 import isValid

from . import backend as B

# ---------------------------------------------------------------------------
# look & feel
# ---------------------------------------------------------------------------

PALETTES = {
    "dark": dict(bg="#0b0e15", side="#0e121b", panel="#141925", panel2="#1a2030", border="#232a3b",
                 border2="#30384c", text="#e8ebf3", muted="#8d96aa", faint="#5d667a", accent="#7c7cff",
                 ok="#34d399", okbg="#10382b", err="#fb7185", errbg="#3a1620", warn="#fbbf24", warnbg="#3a2c0c",
                 run="#a5a8ff", runbg="#22234a", hover="#1b2131", sel="#262a4d", logbg="#0a0d13",
                 NSE="#60a5fa", BSE="#fb923c", MCX="#facc15"),
    "light": dict(bg="#f3f5fa", side="#ffffff", panel="#ffffff", panel2="#f5f6fa", border="#e3e6ee",
                  border2="#cfd4df", text="#121826", muted="#5d667a", faint="#9aa2b4", accent="#6366f1",
                  ok="#059669", okbg="#d9f3ea", err="#e11d48", errbg="#fde4ea", warn="#b45309", warnbg="#fbefd5",
                  run="#4f46e5", runbg="#e5e6ff", hover="#f0f2f8", sel="#e5e6ff", logbg="#0f1420",
                  NSE="#2563eb", BSE="#ea580c", MCX="#ca8a04"),
}
GRAD = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:0.55 #8b5cf6, stop:1 #d946ef)"
FONT, MONO = "Segoe UI", "Consolas"
P = dict(PALETTES["dark"])  # current palette (mutated on theme switch)


def qss(p) -> str:
    return f"""
* {{ font-family: "{FONT}"; font-size: 10pt; color: {p['text']}; }}
#root, QDialog {{ background: {p['bg']}; }}
#side {{ background: {p['side']}; border-right: 1px solid {p['border']}; }}
#side QPushButton[nav="1"] {{ text-align: left; padding: 10px 14px; border-radius: 10px; border: none;
    background: transparent; color: {p['muted']}; font-size: 10.5pt; }}
#side QPushButton[nav="1"]:hover {{ background: {p['hover']}; color: {p['text']}; }}
#side QPushButton[nav="1"]:checked {{ background: {p['sel']}; color: {p['text']}; font-weight: 600; }}
QFrame[card="1"] {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QFrame[card="1"]:hover[clickable="1"] {{ border-color: {p['border2']}; }}
QFrame[drop="1"] {{ background: {p['panel']}; border: 2px dashed {p['border2']}; border-radius: 16px; }}
QFrame[drop="over"] {{ background: {p['sel']}; border: 2px dashed {p['accent']}; border-radius: 16px; }}
QFrame[row="1"] {{ background: transparent; border: none; border-top: 1px solid {p['border']}; border-radius: 0; }}
QFrame[row="1"]:hover, QFrame[row="open"] {{ background: {p['hover']}; border-top: 1px solid {p['border']}; }}
QFrame[step="1"] {{ background: {p['panel2']}; border: 1px solid {p['border']}; border-radius: 12px; }}
QFrame[step="ok"] {{ background: {p['panel2']}; border: 1px solid {p['ok']}; border-radius: 12px; }}
QFrame[step="fail"] {{ background: {p['panel2']}; border: 1px solid {p['err']}; border-radius: 12px; }}
QLabel {{ background: transparent; border: none; }}
QLabel[role="h1"] {{ font-size: 20pt; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: 13pt; font-weight: 700; }}
QLabel[role="date"] {{ font-size: 18pt; font-weight: 700; }}
QLabel[role="big"] {{ font-size: 17pt; font-weight: 700; }}
QLabel[role="muted"] {{ color: {p['muted']}; }}
QLabel[role="faint"] {{ color: {p['faint']}; font-size: 9pt; }}
QLabel[role="section"] {{ color: {p['muted']}; font-size: 8.5pt; font-weight: 700; letter-spacing: 1px; }}
QLabel[role="mono"] {{ font-family: "{MONO}"; font-size: 9.5pt; }}
QLabel[role="ok"] {{ color: {p['ok']}; font-weight: 600; }}
QLabel[role="err"] {{ color: {p['err']}; font-weight: 600; }}
QLabel[role="warn"] {{ color: {p['warn']}; font-weight: 600; }}
QLabel[chip] {{ border-radius: 9px; padding: 2px 9px; font-weight: 700; font-size: 8.5pt; }}
QLabel[chip="ok"] {{ background: {p['okbg']}; color: {p['ok']}; }}
QLabel[chip="err"] {{ background: {p['errbg']}; color: {p['err']}; }}
QLabel[chip="warn"] {{ background: {p['warnbg']}; color: {p['warn']}; }}
QLabel[chip="run"] {{ background: {p['runbg']}; color: {p['run']}; }}
QLabel[chip="plain"] {{ background: {p['panel2']}; color: {p['muted']}; }}
QPushButton {{ background: {p['panel2']}; border: 1px solid {p['border2']}; border-radius: 9px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['hover']}; }}
QPushButton:disabled {{ color: {p['faint']}; border-color: {p['border']}; }}
QPushButton[kind="primary"] {{ background: {GRAD}; border: none; color: white; font-weight: 600; }}
QPushButton[kind="primary"]:disabled {{ background: {p['panel2']}; color: {p['faint']}; }}
QPushButton[kind="big"] {{ background: {GRAD}; border: none; color: white; font-weight: 700; font-size: 12pt;
    padding: 12px 28px; border-radius: 12px; }}
QPushButton[kind="big"]:disabled {{ background: {p['panel2']}; color: {p['faint']}; }}
QPushButton[kind="danger"] {{ color: {p['err']}; }}
QPushButton[kind="danger"]:hover {{ border-color: {p['err']}; background: {p['errbg']}; }}
QPushButton[kind="ghost"] {{ background: transparent; border-color: transparent; }}
QPushButton[kind="ghost"]:hover {{ background: {p['hover']}; border-color: {p['border']}; }}
QPushButton[kind="seg"] {{ background: transparent; border: none; color: {p['muted']}; padding: 5px 12px;
    border-radius: 7px; font-weight: 600; }}
QPushButton[kind="seg"]:checked {{ background: {p['panel']}; color: {p['text']}; }}
QFrame[segbox="1"] {{ background: {p['panel2']}; border: 1px solid {p['border']}; border-radius: 10px; }}
QLineEdit, QComboBox, QDateEdit {{ background: {p['panel2']}; border: 1px solid {p['border2']};
    border-radius: 9px; padding: 6px 10px; selection-background-color: {p['accent']}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{ border-color: {p['accent']}; }}
QLineEdit[role="mono"] {{ font-family: "{MONO}"; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p['panel']}; border: 1px solid {p['border2']}; selection-background-color: {p['sel']}; padding: 4px; }}
QPlainTextEdit {{ background: {p['panel2']}; border: 1px solid {p['border2']}; border-radius: 10px; padding: 8px;
    font-family: "{MONO}"; font-size: 9.5pt; selection-background-color: {p['accent']}; }}
QPlainTextEdit[log="1"] {{ background: {p['logbg']}; color: #d5dbea; border: none; border-radius: 0;
    border-bottom-left-radius: 14px; border-bottom-right-radius: 14px; }}
QTableView, QTableWidget {{ background: {p['panel']}; border: none; gridline-color: transparent;
    selection-background-color: {p['sel']}; selection-color: {p['text']}; alternate-background-color: {p['panel2']}; }}
QTableView::item, QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {p['border']}; }}
QHeaderView::section {{ background: {p['panel']}; color: {p['muted']}; border: none; border-bottom: 1px solid {p['border']};
    padding: 8px 8px; font-weight: 700; font-size: 8.5pt; }}
QTableCornerButton::section {{ background: {p['panel']}; border: none; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 2px; border-radius: 10px; }}
QListWidget::item:selected {{ background: {p['sel']}; }}
QListWidget::item:hover:!selected {{ background: {p['hover']}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle {{ background: {p['border2']}; border-radius: 4px; min-height: 30px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {p['faint']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QProgressBar {{ background: {p['border']}; border: none; max-height: 4px; min-height: 4px; }}
QProgressBar::chunk {{ background: {GRAD}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {p['muted']}; padding: 10px 18px; border: none;
    border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {p['text']}; border-bottom: 2px solid {p['accent']}; }}
QToolTip {{ background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['border2']}; padding: 6px 8px; }}
QMenu {{ background: {p['panel']}; border: 1px solid {p['border2']}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p['sel']}; }}
QCalendarWidget QWidget {{ alternate-background-color: {p['panel2']}; }}
QCalendarWidget QAbstractItemView {{ background: {p['panel']}; selection-background-color: {p['accent']}; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; padding: 4px 8px; font-weight: 600; }}
QCalendarWidget #qt_calendar_navigationbar {{ background: {p['panel2']}; }}
"""


ICONS = {
    "build": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "table": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
    "db": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "sliders": '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "left": '<path d="m15 18-6-6 6-6"/>',
    "right": '<path d="m9 18 6-6-6-6"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "alert": '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "terminal": '<path d="m4 17 6-6-6-6M12 19h8"/>',
    "ext": '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "trash": '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
}
_icon_cache = {}


def icon(name: str, color: str = None, size: int = 18) -> QIcon:
    color = color or P["text"]
    key = (name, color, size)
    if key not in _icon_cache:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size * 2}" height="{size * 2}" '
               f'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               f'{ICONS[name]}</svg>')
        pm = QPixmap()
        pm.loadFromData(svg.encode(), "SVG")
        _icon_cache[key] = QIcon(pm)
    return _icon_cache[key]


def pix(name, color=None, size=18) -> QPixmap:
    return icon(name, color, size).pixmap(QSize(size, size))


def logo_pixmap(size=40) -> QPixmap:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size * 2, size * 2)
    g.setColorAt(0, QColor("#6366f1"))
    g.setColorAt(0.55, QColor("#8b5cf6"))
    g.setColorAt(1, QColor("#d946ef"))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size * 2, size * 2), size * 0.6, size * 0.6)
    p.fillPath(path, g)
    inner = pix("build", "#ffffff", size)
    p.drawPixmap(int(size * 0.45), int(size * 0.45), int(size * 1.1), int(size * 1.1), inner)
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


def setp(w: QWidget, **props):
    """Set dynamic QSS properties and re-polish so the style updates."""
    for k, v in props.items():
        w.setProperty(k, v)
    w.style().unpolish(w)
    w.style().polish(w)
    return w


def label(text="", role=None, wrap=False) -> QLabel:
    l = QLabel(text)
    if role:
        l.setProperty("role", role)
    l.setWordWrap(wrap)
    return l


def chip(text, kind="plain") -> QLabel:
    l = QLabel(text)
    l.setProperty("chip", kind)
    return l


def button(text="", icon_name=None, kind=None, tip=None, slot=None, color=None) -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    if icon_name:
        white = kind in ("primary", "big")
        b.setIcon(icon(icon_name, "#ffffff" if white else color or P["text"], 18))
        b.setIconSize(QSize(17, 17))
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    b.setCursor(Qt.PointingHandCursor)
    return b


def card(clickable=False) -> QFrame:
    f = QFrame()
    f.setProperty("card", "1")
    if clickable:
        f.setProperty("clickable", "1")
        f.setCursor(Qt.PointingHandCursor)
    return f


def hbox(*items, spacing=10, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(spacing)
    h.setContentsMargins(*margins)
    for it in items:
        if it is None:
            h.addStretch(1)
        elif isinstance(it, int):
            h.addSpacing(it)
        elif isinstance(it, QWidget):
            h.addWidget(it)
        else:
            h.addLayout(it)
    return h


def vbox(*items, spacing=10, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    v = QVBoxLayout()
    v.setSpacing(spacing)
    v.setContentsMargins(*margins)
    for it in items:
        if it is None:
            v.addStretch(1)
        elif isinstance(it, int):
            v.addSpacing(it)
        elif isinstance(it, QWidget):
            v.addWidget(it)
        else:
            v.addLayout(it)
    return v


def style_badge(l: QLabel, ex: str) -> QLabel:
    c = QColor(P.get(ex, P["muted"]))
    l.setText(ex)
    l.setStyleSheet(f"background: rgba({c.red()},{c.green()},{c.blue()},40); color: {c.name()}; border-radius: 6px;"
                    f"padding: 2px 7px; font-weight: 800; font-size: 8.5pt;")
    l.setAlignment(Qt.AlignCenter)
    l.setFixedSize(46, 22)
    return l


def exbadge(ex: str) -> QLabel:
    return style_badge(QLabel(), ex)


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
        elif it.layout():
            clear_layout(it.layout())


def fmt_ymd(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y%m%d").strftime("%a %d %b %Y")
    except (TypeError, ValueError):
        return s or "—"


def fmt_size(n: int) -> str:
    return f"{n / 1e6:.1f} MB" if n > 1e6 else f"{n / 1e3:.0f} KB" if n > 1e3 else f"{n} B"


def fmt_when(t: float) -> str:
    d = datetime.fromtimestamp(t)
    return f"today {d:%H:%M}" if d.date() == date.today() else f"{d:%d %b %H:%M}"


def fmt_dur(s) -> str:
    if s is None:
        return ""
    return f"{s:.1f}s" if s < 60 else f"{int(s // 60)}m {int(s % 60)}s"


def plural(n, w):
    return f"{n} {w}{'' if n == 1 else 's'}"


# ---------------------------------------------------------------------------
# background work
# ---------------------------------------------------------------------------

class _Signals(QObject):
    done = Signal(object, object)


class Task(QRunnable):
    """Run fn() on the thread pool, then done(result, error) on the UI thread."""
    alive = set()

    def __init__(self, fn, done):
        super().__init__()
        self.fn, self.sig = fn, _Signals()
        self.sig.done.connect(done)
        self.sig.done.connect(lambda *_: Task.alive.discard(self))
        Task.alive.add(self)

    def run(self):
        try:
            res, err = self.fn(), None
        except Exception as exc:  # shown to the user, never crashes the app
            res, err = None, exc
        self.sig.done.emit(res, err)


def run_bg(fn, done):
    QThreadPool.globalInstance().start(Task(fn, done))


# ---------------------------------------------------------------------------
# custom widgets
# ---------------------------------------------------------------------------

class Ring(QWidget):
    def __init__(self, size=48):
        super().__init__()
        self.setFixedSize(size, size)
        self.have, self.need, self.color = 0, 0, P["accent"]

    def set(self, have, need, color):
        self.have, self.need, self.color = have, need, color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(4, 4, self.width() - 8, self.height() - 8)
        p.setPen(QPen(QColor(P["border2"]), 5))
        p.drawEllipse(r)
        if self.need:
            pen = QPen(QColor(self.color), 5)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(360 * 16 * self.have / self.need))
        p.setPen(QColor(P["text"]))
        f = QFont(FONT, 9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, f"{self.have}/{self.need}")
        p.end()


class Switch(QCheckBox):
    """iOS-style toggle; label text sits to the right."""

    def sizeHint(self):
        w = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(46 + w, 24)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        track = QRectF(1, 3, 36, 20)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(P["accent"] if on else P["border2"]))
        p.drawRoundedRect(track, 10, 10)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(19 if on else 4, 6, 14, 14))
        p.setPen(QColor(P["text"] if self.underMouse() else P["muted"]))
        p.drawText(QRectF(46, 0, self.width() - 46, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()


class Seg(QFrame):
    """Segmented control. changed(value)."""
    changed = Signal(str)

    def __init__(self, options, value=None):
        super().__init__()
        self.setProperty("segbox", "1")
        lay = hbox(spacing=2, margins=(3, 3, 3, 3))
        self.setLayout(lay)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for v, text in options:
            b = button(text, kind="seg")
            b.setCheckable(True)
            b.setChecked(v == (value if value is not None else options[0][0]))
            b.clicked.connect(lambda _=False, v=v: self.changed.emit(v))
            self.group.addButton(b)
            lay.addWidget(b)
            self.buttons[v] = b

    def value(self):
        return next(v for v, b in self.buttons.items() if b.isChecked())


class ElideLabel(QLabel):
    """Single-line label that shortens itself with … to whatever width it gets."""

    def __init__(self, text="", mode=Qt.ElideRight):
        super().__init__()
        self.full, self.mode = text, mode
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(20)

    def setText(self, text):
        self.full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, e):
        self._elide()
        super().resizeEvent(e)

    def _elide(self):
        QLabel.setText(self, self.fontMetrics().elidedText(self.full, self.mode, max(self.width(), 20)))


class Clickable(QFrame):
    clicked = Signal()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class LogHighlighter(QSyntaxHighlighter):
    RULES = [("h", "#a5b4fc", re.compile(r"^(>>>|={10,}|PIPELINE SUMMARY|\$ |\|\s+Step\s+\|)"), True),
             ("e", "#fb7185", re.compile(r"traceback|\berror\b|\w+Error\b|exception|failed", re.I), False),
             ("w", "#fbbf24", re.compile(r"warn|not found|skipp", re.I), False),
             ("o", "#34d399", re.compile(r"success|completed|saved \d+|upserted|registered", re.I), False)]

    def highlightBlock(self, text):
        for _, color, rx, bold in self.RULES:
            if rx.search(text):
                f = QTextCharFormat()
                f.setForeground(QColor(color))
                if bold:
                    f.setFontWeight(QFont.Bold)
                self.setFormat(0, len(text), f)
                return


def line_level(l: str) -> str:
    return next((lvl for lvl, _, rx, _ in LogHighlighter.RULES if rx.search(l)), "")


class LogView(QFrame):
    """Dark console with All / Warnings / Errors filter, grep-style search, copy."""

    def __init__(self, height=320):
        super().__init__()
        self.lines, self.filter, self.term = [], "all", ""
        top = QFrame()
        self.count = label("", "faint")
        self.seg = Seg([("all", "All"), ("warn", "Warnings"), ("err", "Errors")])
        self.seg.changed.connect(self.set_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter lines…")
        self.search.setFixedWidth(200)
        self.search.textChanged.connect(self.set_term)
        t = QLabel()
        t.setPixmap(pix("terminal", P["muted"], 16))
        top.setLayout(hbox(t, label("<b>Log</b>"), self.count, None, self.seg, self.search,
                           button("", "copy", "ghost", "Copy log", self.copy), margins=(14, 8, 10, 8)))
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setProperty("log", "1")
        self.text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text.setMinimumHeight(height)
        self.text.setMaximumBlockCount(200_000)
        self.hl = LogHighlighter(self.text.document())
        self.setLayout(vbox(top, self.text, spacing=0))

    def keep(self, l):
        lvl = line_level(l)
        if self.filter == "warn" and lvl not in ("w", "e"):
            return False
        if self.filter == "err" and lvl != "e":
            return False
        return not self.term or self.term in l.lower()

    def set_filter(self, v):
        self.filter = v
        self.render()

    def set_term(self, t):
        self.term = t.lower()
        self.render()

    def set_lines(self, lines):
        self.lines = list(lines)
        self.render()

    def add(self, lines):
        if not lines:
            return
        self.lines += lines
        sb = self.text.verticalScrollBar()
        stick = sb.value() >= sb.maximum() - 4
        keep = [l for l in lines if self.keep(l)]
        if keep:
            self.text.appendPlainText("\n".join(keep))
        if stick:
            sb.setValue(sb.maximum())
        self._count()

    def render(self):
        self.text.setPlainText("\n".join(l for l in self.lines if self.keep(l)))
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        self._count()

    def _count(self):
        e = sum(1 for l in self.lines if line_level(l) == "e")
        self.count.setText(f"{len(self.lines):,} lines" + (f" · {e} error lines" if e else ""))

    def copy(self):
        QApplication.clipboard().setText("\n".join(self.lines))
        toast("Log copied")


# ---------------------------------------------------------------------------
# dialogs + toasts
# ---------------------------------------------------------------------------

class Dialog(QDialog):
    auto = None  # tests: callable(title, body) -> value, replaces showing the dialog
    shown = []

    @staticmethod
    def ask(parent, title, body="", kind="ok", actions=(("OK", "ok", "primary"),)):
        Dialog.shown.append((title, body))
        if Dialog.auto:
            return Dialog.auto(title, body)
        d = Dialog(parent, title, body, kind, actions)
        d.exec()
        return d.result_value

    def __init__(self, parent, title, body, kind, actions):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.result_value = None
        self.setMinimumWidth(520)
        colors = {"ok": (P["ok"], P["okbg"], "check"), "warn": (P["warn"], P["warnbg"], "alert"),
                  "err": (P["err"], P["errbg"], "x"), "info": (P["run"], P["runbg"], "info")}
        fg, bg, ic = colors[kind]
        badge = QLabel()
        badge.setPixmap(pix(ic, fg, 22))
        badge.setFixedSize(42, 42)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background: {bg}; border-radius: 12px;")
        t = label(title, "h2")
        b = QLabel(body)
        b.setWordWrap(True)
        b.setTextFormat(Qt.RichText)
        b.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(b)
        scroll.setMaximumHeight(460)
        scroll.setMinimumHeight(min(460, b.sizeHint().height() + 12))
        btns = []
        for text, value, kind_ in actions:
            bt = button(text, kind=kind_)
            bt.clicked.connect(lambda _=False, v=value: self._done(v))
            btns.append(bt)
            if kind_ == "primary":
                bt.setDefault(True)
        self.setLayout(vbox(hbox(badge, t, None), scroll, hbox(None, *btns), margins=(24, 22, 24, 20), spacing=14))

    def _done(self, v):
        self.result_value = v
        self.accept()


class Toasts(QWidget):
    instance = None

    def __init__(self, parent):
        super().__init__(parent)
        Toasts.instance = self
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.lay = vbox(spacing=8)
        self.setLayout(self.lay)

    def show_toast(self, text, kind="ok"):
        f = QFrame()
        colors = {"ok": (P["ok"], "check"), "err": (P["err"], "x"), "warn": (P["warn"], "alert")}
        c, ic = colors.get(kind, colors["ok"])
        f.setStyleSheet(f"background: {P['panel2']}; border: 1px solid {P['border2']}; border-radius: 12px;")
        i = QLabel()
        i.setPixmap(pix(ic, c, 18))
        i.setStyleSheet("border: none;")
        t = QLabel(text)
        t.setStyleSheet("border: none;")
        t.setWordWrap(True)
        f.setLayout(hbox(i, t, margins=(14, 10, 16, 10)))
        f.setMinimumWidth(300)
        f.setMaximumWidth(440)
        self.lay.addWidget(f)
        self.place()
        self.show()
        self.raise_()
        # context-bound timers die with their widget (the window is rebuilt on a theme switch)
        QTimer.singleShot(4200, f, f.deleteLater)
        f.destroyed.connect(lambda *_: isValid(self) and QTimer.singleShot(50, self, self.place))

    def place(self):
        p = self.parentWidget()
        self.adjustSize()
        self.move(p.width() - self.width() - 24, p.height() - self.height() - 104)


def toast(text, kind="ok"):
    if Toasts.instance:
        Toasts.instance.show_toast(text, kind)


# ---------------------------------------------------------------------------
# shared job polling
# ---------------------------------------------------------------------------

class JobWatch(QObject):
    """Polls backend.Job.current; pages subscribe to lines/updates."""
    update = Signal(dict, list, bool)  # snapshot, new lines, finished-now

    def __init__(self):
        super().__init__()
        self.since, self.job_id, self.was_running = 0, None, False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(400)

    def poll(self):
        j = B.Job.current
        if not j:
            return
        if j.id != self.job_id:
            self.job_id, self.since, self.was_running = j.id, 0, True
        if not j.running and not self.was_running:
            return
        snap = j.snapshot(self.since)
        self.since += len(snap["lines"])
        finished = not snap["running"] and snap["total"] <= self.since
        self.update.emit(snap, snap["lines"], finished)
        if finished:
            self.was_running = False

    def lines(self):
        j = B.Job.current
        return list(j.lines[:self.since]) if j else []


# ---------------------------------------------------------------------------
# BUILD page
# ---------------------------------------------------------------------------

class MasterCard(Clickable):
    def __init__(self, key):
        super().__init__()
        self.key = key
        self.setProperty("card", "1")
        self.setProperty("clickable", "1")
        self.setCursor(Qt.PointingHandCursor)
        self.ring = Ring(50)
        self.check = QLabel()
        self.check.setFixedSize(22, 22)
        self.check.setAlignment(Qt.AlignCenter)
        self.name = QLabel()
        self.name.setTextFormat(Qt.RichText)
        self.state = QLabel()
        self.meta = label("", "faint")
        self.selected = True
        self.setLayout(vbox(hbox(self.ring, None, self.check), 4, self.name, self.state, self.meta,
                            margins=(16, 14, 16, 14), spacing=4))
        self.setMinimumWidth(170)

    def set(self, m, selected):
        self.selected = selected
        color = P[m["exchange"]]
        seg = "Cash" if m["segment"] == "CM" else "Derivatives"
        self.name.setText(f'<span style="font-size:13pt;font-weight:800;color:{color}">{m["exchange"]}</span>'
                          f'<span style="font-size:13pt;font-weight:800"> {m["segment"]}</span>'
                          f'<span style="color:{P["muted"]};font-weight:600"> &nbsp;{seg}</span>')
        self.ring.set(m["have"], m["need"], P["ok"] if m["ready"] else P["err"])
        if m["ready"]:
            extra = " · no bhavcopy" if m["optional_missing"] else ""
            self.state.setText(f"✓ Ready{extra}")
            setp(self.state, role="ok")
            tip = (f"Builds without {', '.join(m['optional_missing'])}: prices / OI / circuits will be 0"
                   if m["optional_missing"] else "All files present")
        else:
            self.state.setText(f"✕ {plural(len(m['missing']), 'file')} missing")
            setp(self.state, role="err")
            tip = "Missing: " + ", ".join(m["missing"])
        self.meta.setText(f"Built {fmt_when(m['built']['mtime'])} · {fmt_size(m['built']['size'])}"
                          if m["built"] else "Not built yet")
        self.setToolTip(tip + "\nClick to include / exclude from the build")
        self.check.setStyleSheet(f"background: {P['accent'] if selected else 'transparent'}; border-radius: 6px;"
                                 f"border: 2px solid {P['accent'] if selected else P['border2']};")
        self.check.setPixmap(pix("check", "#ffffff", 14) if selected else QPixmap())
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.selected:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            g = QLinearGradient(0, 0, self.width(), 0)
            g.setColorAt(0, QColor("#6366f1"))
            g.setColorAt(1, QColor("#d946ef"))
            path = QPainterPath()
            path.addRoundedRect(QRectF(14, self.height() - 4, self.width() - 28, 3), 1.5, 1.5)
            p.fillPath(path, g)
            p.end()


class FileRow(Clickable):
    def __init__(self, page, f):
        super().__init__()
        self.page, self.key = page, f["key"]
        self.setProperty("row", "1")
        self.setCursor(Qt.PointingHandCursor)
        self.st = QLabel()
        self.st.setFixedSize(22, 22)
        self.st.setAlignment(Qt.AlignCenter)
        self.name = ElideLabel("", Qt.ElideMiddle)
        self.name.setProperty("role", "mono")
        self.desc = label("", "faint")
        self.tag = label("", "faint")
        self.detail = label("", "muted", wrap=True)
        self.detail.setTextFormat(Qt.RichText)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.copy = button("Copy name", "copy", slot=self.copy_name)
        self.extra = QWidget()
        self.extra.setLayout(vbox(self.detail, hbox(self.copy, None), margins=(32, 2, 0, 4), spacing=6))
        self.extra.hide()
        self.setLayout(vbox(hbox(self.st, vbox(self.name, self.desc, spacing=0), self.tag),
                            self.extra, margins=(14, 8, 14, 8), spacing=4))
        self.clicked.connect(lambda: page.toggle_file(self.key))

    def set(self, f, open_):
        self.f = f
        self.name.setText(f["name"])
        self.desc.setText(f["label"])
        self.tag.setText(f"{'/'.join(f['segments'])} · {'req' if f['required'] else 'opt'}")
        if f["present"]:
            self.st.setPixmap(pix("check", P["ok"], 13))
            self.st.setStyleSheet(f"background: {P['okbg']}; border-radius: 11px;")
        elif f["required"]:
            self.st.setPixmap(pix("x", P["err"], 13))
            self.st.setStyleSheet(f"background: {P['errbg']}; border-radius: 11px;")
        else:
            self.st.setPixmap(QPixmap())
            self.st.setStyleSheet(f"border: 2px dashed {P['border2']}; border-radius: 11px;")
        here = f"<b>Here</b> · {fmt_size(f['size'])} · added {fmt_when(f['mtime'])}<br>" if f["present"] else ""
        also = f"<br><b>Also accepted:</b> {', '.join(f['also'])}" if f.get("also") else ""
        opt = "" if f["required"] else "<br>Optional — without it prices, open interest and circuit limits are 0."
        self.detail.setText(f"{here}{f['about']}<br><b>Get it from:</b> {f['source']}{also}{opt}"
                            f"<br><span style='color:{P['faint']}'>Press F1 for the full file guide.</span>")
        self.extra.setVisible(open_)
        setp(self, row="open" if open_ else "1")

    def copy_name(self):
        QApplication.clipboard().setText(self.f["name"])
        toast("File name copied")


class ExchangeCard(QFrame):
    def __init__(self, page, ex):
        super().__init__()
        self.page, self.ex, self.rows, self.sig = page, ex, {}, None
        self.setProperty("card", "1")
        self.title = label("", wrap=False)
        self.count = label("", "faint")
        head = hbox(exbadge(ex), vbox(self.title, self.count, spacing=0), None,
                    button("Folder", "folder", "ghost", f"Open the {ex} input folder",
                           lambda: B.api_open(dict(what="input", exchange=ex, date=page.date))),
                    margins=(16, 12, 12, 10))
        self.list = vbox(spacing=0)
        self.setLayout(vbox(head, self.list, margins=(0, 0, 0, 6), spacing=0))

    def set(self, exd, open_key):
        files = exd["files"]
        req = [f for f in files if f["required"]]
        have = sum(f["present"] for f in req)
        self.title.setText(f"<b>{'All required files here' if have == len(req) else f'{len(req) - have} required missing'}</b>")
        self.count.setText(f"{sum(f['present'] for f in files)} of {len(files)} files")
        keys = [f["key"] for f in files]
        if keys != list(self.rows):
            clear_layout(self.list)
            self.rows = {f["key"]: FileRow(self.page, f) for f in files}
            for r in self.rows.values():
                self.list.addWidget(r)
        for f in files:
            self.rows[f["key"]].set(f, open_key == f["key"])


class StepCard(QFrame):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setProperty("step", "1")
        self.setCursor(Qt.PointingHandCursor)
        self.name = QLabel()
        self.name.setStyleSheet("font-weight: 800;")
        self.chip = chip("")
        self.sec = label("", "faint")
        self.big = label("", "big")
        self.desc = label("", "muted", wrap=True)
        self.path = label("", "faint")
        self.setLayout(vbox(hbox(self.name, self.chip, None, self.sec), self.big, self.desc, self.path,
                            margins=(14, 12, 14, 12), spacing=2))
        self.setMinimumWidth(220)

    def set(self, s):
        self.s = s
        self.name.setText(s["label"])
        text, kind = {"pending": ("Waiting", "plain"), "running": ("Building", "run"), "ok": ("Done", "ok"),
                      "fail": ("Failed", "err"), "stopped": ("Stopped", "warn"),
                      "skipped": ("Not run", "warn")}[s["state"]]
        self.chip.setText(text)
        setp(self.chip, chip=kind)
        self.sec.setText(fmt_dur(s.get("seconds")))
        self.big.setVisible(s["state"] == "ok")
        self.path.setVisible(s["state"] == "ok")
        if s["state"] == "ok":
            self.big.setText(f"{s['count']:,}" if s.get("count") is not None else "—")
            self.desc.setText("contracts")
            self.path.setText(self.path.fontMetrics().elidedText(s.get("output", ""), Qt.ElideMiddle, 230))
            self.path.setToolTip(s.get("output", ""))
        elif s["state"] == "fail":
            self.desc.setText(s.get("error") or "See the log below")
        elif s["state"] == "running":
            self.desc.setText("Reading files and transforming…")
        else:
            self.desc.setText(s.get("info") or ("Queued" if s["state"] == "pending" else ""))
        setp(self, step={"ok": "ok", "fail": "fail"}.get(s["state"], "1"))
        setp(self.desc, role="err" if s["state"] == "fail" else "muted")

    def mouseReleaseEvent(self, e):
        if self.s.get("path"):
            self.page.win.open_master(self.s["path"])
        elif self.s["state"] == "fail":
            self.page.log.seg.buttons["err"].click()
            self.page.log.set_filter("err")


class DropZone(QFrame):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setAcceptDrops(True)
        self.setProperty("drop", "1")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            setp(self, drop="over")

    def dragLeaveEvent(self, _):
        setp(self, drop="1")

    def dropEvent(self, e):
        setp(self, drop="1")
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.page.import_paths(paths)


class BuildPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        st = B.api_state({})
        prefs = st.get("prefs", {})
        self.date = st["date"]
        self.sel = set(prefs.get("steps") or [m["key"] for m in st["masters"]] or list(B.STEPS))
        self.open_file = None
        self.st = None
        self.downloads = B.windows_downloads()
        self.watch_seen, self.watch_pending = {}, {}
        self.watch_since = time.time()

        # --- date card
        self.date_lbl = label("", "date")
        self.date_sub = label("", "muted")
        self.date_sub.setTextFormat(Qt.RichText)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd MMM yyyy")
        self.date_edit.setFixedWidth(150)
        self.date_edit.dateChanged.connect(self.on_date_edit)
        self.latest_btn = button("Latest", tip="Most recent business day",
                                 slot=lambda: self.set_date(B.ymd(B.latest_business_day())))
        date_card = card()
        date_card.setLayout(hbox(button("", "left", tip="Previous business day", slot=lambda: self.shift(-1)),
                                 button("", "right", tip="Next business day", slot=lambda: self.shift(1)), 8,
                                 vbox(self.date_lbl, self.date_sub, spacing=2), None, self.date_edit,
                                 self.latest_btn, margins=(18, 16, 18, 16)))

        # --- master cards
        self.cards = {k: MasterCard(k) for k in B.STEPS}
        for k, c in self.cards.items():
            c.clicked.connect(lambda k=k: self.toggle(k))
        masters_row = hbox(*self.cards.values(), spacing=14)

        # --- run panel
        self.run = card()
        self.run_title = label("", "h2")
        self.run_title.setTextFormat(Qt.RichText)
        self.run_elapsed = label("", "muted")
        self.results_btn = button("Open results", "table", slot=self.open_results)
        self.log_btn = button("Log", "terminal", "ghost", slot=lambda: self.log.setVisible(not self.log.isVisible()))
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.steps_grid = QGridLayout()
        self.steps_grid.setSpacing(10)
        self.step_cards = {}
        self.log = LogView(300)
        self.run.setLayout(vbox(hbox(self.run_title, None, self.run_elapsed, self.results_btn, self.log_btn,
                                     margins=(20, 14, 16, 12)), self.progress,
                                vbox(self.steps_grid, margins=(18, 14, 18, 14)), self.log, spacing=0))
        self.run.hide()

        # --- drop zone
        self.drop = DropZone(self)
        ico = QLabel()
        ico.setPixmap(pix("inbox", P["accent"], 30))
        ico.setFixedSize(58, 58)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet(f"background: {P['sel']}; border-radius: 16px;")
        self.auto = Switch("Auto-import new downloads")
        self.auto.setChecked(bool(B.settings.get("auto_import", False)))
        self.auto.toggled.connect(self.on_auto)
        self.auto.setToolTip(f"Watches {self.downloads}\nEvery file you download from now on that this date needs "
                             "is added automatically (zips too).")
        self.scan_edit = QLineEdit(prefs.get("last_scan_path", ""))
        self.scan_edit.setPlaceholderText(r"…or a folder path, e.g. C:\Users\you\Downloads\EOD")
        self.scan_edit.setProperty("role", "mono")
        self.scan_edit.returnPressed.connect(self.scan)
        self.import_btn = button("Import from Downloads", "download", "primary",
                                 f"Look through {self.downloads} (subfolders and zips too)", self.import_downloads)
        drop_text = label("Get the exchange files in", "h2")
        drop_text.setAlignment(Qt.AlignCenter)
        drop_sub = label(f"Download them as usual, then click Import — only the files this date needs are "
                         f"picked out (zips too) and filed. Or drop files here, or choose them.", "muted", wrap=True)
        drop_sub.setAlignment(Qt.AlignCenter)
        self.drop.setLayout(vbox(hbox(None, ico, None), drop_text, drop_sub, 4,
                                 hbox(None, self.import_btn, button("Choose files…", "file", slot=self.choose_files),
                                      button("Choose folder…", "folder", slot=self.choose_folder), None),
                                 hbox(None, self.auto, None),
                                 hbox(None, self.scan_edit, button("Scan", "search", slot=self.scan), None),
                                 margins=(28, 24, 28, 24), spacing=10))
        self.scan_edit.setMinimumWidth(460)

        # --- exchange cards
        self.ex_cards = {ex: ExchangeCard(self, ex) for ex in B.EXCHANGES}
        ex_row = hbox(spacing=16)
        for c in self.ex_cards.values():
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            ex_row.addWidget(c, 1, Qt.AlignTop)

        content = QWidget()
        content.setLayout(vbox(vbox(label("Build contract masters", "h1"),
                                    label("Pick the business date, bring in the exchange files, build.", "muted"),
                                    spacing=2),
                               date_card, masters_row, self.run, self.drop, ex_row, None,
                               margins=(34, 26, 34, 26), spacing=16))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(content)

        # --- action bar
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.RichText)
        self.retry = Switch("Wait & retry")
        self.retry.setToolTip("Off: fail at once so you see the problem now.\n"
                              "On: wait and retry like the scheduled jobs (up to 6 × 20 min).")
        self.retry.setChecked(bool(prefs.get("retry")))
        self.retry.setVisible(B.HAS_PREFECT)  # retries come from Prefect; the packaged app has none
        self.stop_err = Switch("Stop at first error")
        self.stop_err.setChecked(bool(prefs.get("stop_on_error")))
        self.build_btn = button("Build", "zap", "big", "Ctrl+R", self.start)
        self.stop_btn = button("Stop", "stop", "danger", slot=self.win.stop_job)
        self.stop_btn.setStyleSheet("padding: 12px 22px; font-size: 12pt; border-radius: 12px;")
        bar = card()
        bar.setLayout(hbox(self.summary, None, self.retry, 12, self.stop_err, 16, self.stop_btn, self.build_btn,
                           margins=(20, 12, 14, 12)))
        self.setLayout(vbox(self.scroll, vbox(bar, margins=(34, 0, 34, 16)), spacing=8))

        win.jobs.update.connect(self.on_job)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.isVisible() and not (B.Job.current and B.Job.current.running) and self.refresh())
        self.timer.start(2000)
        self.watch = QTimer(self)
        self.watch.timeout.connect(self.watch_tick)
        self.watch.start(3000)
        self.refresh()

    # ----- state
    def set_date(self, ymd):
        self.date = ymd
        self.open_file = None
        self.refresh()

    def shift(self, d):
        self.refresh(shift=d)

    def on_date_edit(self, qd):
        ymd = qd.toString("yyyyMMdd")
        if ymd != self.date:
            self.set_date(ymd)

    def refresh(self, shift=0):
        try:
            st = B.api_state(dict(date=self.date, shift=str(shift)))
        except Exception as exc:
            toast(str(exc), "err")
            return
        self.st, self.date = st, st["date"]
        d = datetime.strptime(st["date"], "%Y%m%d")
        self.date_lbl.setText(st["label"] + ("   ·  today" if st["is_today"] else ""))
        if st["problem"]:
            self.date_sub.setText(f'<span style="color:{P["warn"]};font-weight:600">⚠ {st["problem"]} '
                                  f'Use the arrows to move to one.</span>')
        else:
            self.date_sub.setText(f'Exchange files are dated <b>{st["prev_label"]}</b> — the previous business day')
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(QDate(d.year, d.month, d.day))
        self.date_edit.blockSignals(False)
        self.latest_btn.setEnabled(st["date"] != st["latest"])
        for w in (*self.cards.values(), *self.ex_cards.values()):
            w.setVisible(not st["problem"])
        if not st["problem"]:
            for m in st["masters"]:
                self.cards[m["key"]].set(m, m["key"] in self.sel)
            for exd in st["exchanges"]:
                self.ex_cards[exd["name"]].set(exd, self.open_file)
        self.render_action()
        j = B.Job.current
        if j and j.kind == "pipeline" and not j.running and j.meta.get("bdate") != self.date:
            self.run.hide()
        elif j and j.kind == "pipeline" and self.run.isHidden() and self.step_cards:
            self.run.show()

    def toggle(self, k):
        self.sel.symmetric_difference_update({k})
        self.refresh()

    def toggle_file(self, key):
        self.open_file = None if self.open_file == key else key
        self.refresh()

    def plan(self):
        ms = [m for m in self.st["masters"] if m["key"] in self.sel] if self.st and not self.st["problem"] else []
        return ms, [m for m in ms if m["ready"]], [m for m in ms if not m["ready"]]

    def render_action(self):
        st = self.st
        running = bool(B.Job.current and B.Job.current.running)
        sel, ready, blocked = self.plan()
        if st["problem"]:
            s = "<b>Not a business day</b><br><span style='color:%s'>Use the arrows to move to one</span>" % P["muted"]
        elif not sel:
            s = "<b>Nothing selected</b><br><span style='color:%s'>Click the master cards to choose</span>" % P["muted"]
        else:
            missing = sum(len(m["missing"]) for m in st["masters"])
            s = (f"<b>{len(ready)} of {len(sel)} selected ready"
                 + (f" · {len(blocked)} waiting for files" if blocked else "") + "</b><br>"
                 + f"<span style='color:{P['muted']}'>"
                 + (f"{plural(missing, 'required file')} still missing for {fmt_ymd(self.date)}" if missing
                    else f"All files present for {fmt_ymd(self.date)}") + "</span>")
        self.summary.setText(s)
        self.build_btn.setText(f"Build {plural(len(ready), 'master')}" if ready else "Build")
        self.build_btn.setEnabled(bool(ready) and not running)
        self.build_btn.setVisible(not running)
        self.stop_btn.setVisible(running)

    # ----- importing
    def import_paths(self, paths, quiet_if_empty=False, auto=False):
        if self.st is None or self.st["problem"]:
            toast("Pick a business day first", "warn")
            return
        bd = self.date
        self.win.busy(f"Looking through {plural(len(paths), 'item')}…")

        def done(r, exc):
            self.win.busy(None)
            self.refresh()
            if exc:
                toast(f"Import failed: {exc}", "err")
            elif auto:
                if r["imported"]:
                    toast("Auto-added " + ", ".join(x["name"] for x in r["imported"]))
                for x in r["wrong_date"]:
                    toast(f"{x['name']} is for another date (this one needs {x['expected']})", "warn")
            elif r["imported"] or r["wrong_date"] or not quiet_if_empty:
                self.report(r)
        run_bg(lambda: B.report_json(B.import_files(paths, bd), bd), done)

    def import_downloads(self):
        if not self.downloads.is_dir():
            toast(f"Downloads folder not found: {self.downloads}", "err")
            return
        self.import_paths([self.downloads])

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, f"Exchange files for {fmt_ymd(self.date)}",
                                                str(self.downloads))
        if paths:
            self.import_paths(paths)

    def choose_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Folder with exchange files", str(self.downloads))
        if p:
            self.import_paths([p])

    def scan(self):
        path = self.scan_edit.text().strip()
        if not path:
            self.scan_edit.setFocus()
            return
        p = B.to_linux_path(path)
        if not p.exists():
            toast(f"Not found: {path}", "err")
            return
        B.settings["last_scan_path"] = path
        B.settings.save()
        self.import_paths([p])

    def report(self, r):
        seen, imported = set(), []
        for x in r["imported"]:
            if x["name"] not in seen:
                seen.add(x["name"])
                imported.append(x)
        still = sorted({n for m in self.st["masters"] for n in m["missing"]})
        rows = "".join(f'<tr><td style="color:{P["ok"]};padding-right:8px">✓</td>'
                       f'<td style="color:{P[x["exchange"]]};font-weight:800;padding-right:10px">{x["exchange"]}</td>'
                       f'<td style="font-family:{MONO}">{x["name"]}</td></tr>' for x in imported)
        body = f"<table cellspacing=3>{rows}</table>" if rows else ""
        if r["wrong_date"]:
            body += (f'<p><b style="color:{P["warn"]}">{plural(len(r["wrong_date"]), "file")} for a different date'
                     f'</b> — not added:<br>' + "<br>".join(
                         f'<span style="font-family:{MONO}">{x["name"]}</span> → this date needs '
                         f'<span style="font-family:{MONO}">{x["expected"]}</span>' for x in r["wrong_date"][:10]) + "</p>")
        if r["ignored"]:
            body += f'<p style="color:{P["muted"]}">{plural(len(r["ignored"]), "other file")} not needed — skipped.</p>'
        body += (f'<p style="color:{P["muted"]}">Still missing for {fmt_ymd(self.date)}: '
                 f'<span style="font-family:{MONO}">{", ".join(still)}</span></p>' if still else
                 f'<p style="color:{P["ok"]};font-weight:600">Every required file for {fmt_ymd(self.date)} is here — '
                 f'ready to build.</p>')
        if imported:
            toast(f"Added {plural(len(imported), 'file')}")
        actions = (("OK", "ok", "primary"),) if still or not imported else (("Later", None, None),
                                                                              ("Build now", "build", "primary"))
        v = Dialog.ask(self.win, f"Added {plural(len(imported), 'file')}" if imported else "Nothing needed in there",
                       body, "ok" if imported else "warn", actions)
        if v == "build":
            self.start()

    def on_auto(self, on):
        B.settings["auto_import"] = on
        B.settings.save()
        self.watch_since, self.watch_seen, self.watch_pending = time.time(), {}, {}
        toast(f"Watching {self.downloads} for new exchange files" if on else "Auto-import off", "ok")

    def watch_tick(self):
        """New files in Downloads (since the switch went on) are imported once their size stops changing."""
        if not self.auto.isChecked() or not self.downloads.is_dir() or not self.st or self.st["problem"]:
            return
        ready = []
        try:
            entries = list(os.scandir(self.downloads))
        except OSError:
            return
        for e in entries:
            if not e.is_file() or e.name.endswith((".crdownload", ".part", ".tmp")):
                continue
            st = e.stat()
            if st.st_mtime < self.watch_since or self.watch_seen.get(e.path) == (st.st_size, st.st_mtime):
                continue
            if self.watch_pending.get(e.path) == (st.st_size, st.st_mtime):  # unchanged for one tick: complete
                self.watch_seen[e.path] = (st.st_size, st.st_mtime)
                ready.append(e.path)
            else:
                self.watch_pending[e.path] = (st.st_size, st.st_mtime)
        if ready:
            self.import_paths(ready, auto=True)

    # ----- build
    def start(self):
        if not self.st or self.st["problem"] or (B.Job.current and B.Job.current.running):
            return
        sel, ready, blocked = self.plan()
        if not ready:
            return
        if blocked:
            body = "These can't be built yet:<br><br>" + "<br>".join(
                f'<b style="color:{P[m["exchange"]]}">{m["exchange"]}</b> <b>{m["segment"]}</b> — '
                f'<span style="font-family:{MONO};color:{P["muted"]}">{", ".join(m["missing"])}</span>' for m in blocked) \
                + f"<br><br>Build the other {plural(len(ready), 'master')} now?"
            if Dialog.ask(self.win, "Some files are missing", body, "warn",
                          (("Cancel", None, None), (f"Build {len(ready)}", "go", "primary"))) != "go":
                return
        try:
            snap = B.api_build(dict(date=self.date, steps=[m["key"] for m in sel], retry=self.retry.isChecked(),
                                    stop_on_error=self.stop_err.isChecked()))
        except Exception as exc:
            toast(str(exc), "err")
            return
        self.log.set_lines([])
        self.show_run(snap)
        self.render_action()
        QTimer.singleShot(100, lambda: self.scroll.ensureWidgetVisible(self.run, 0, 0))

    def show_run(self, snap):
        self.run.show()
        steps = snap["steps"]
        if [s["key"] for s in steps] != list(self.step_cards):
            clear_layout(self.steps_grid)
            self.step_cards = {}
            for i, s in enumerate(steps):
                c = StepCard(self)
                self.step_cards[s["key"]] = c
                self.steps_grid.addWidget(c, i // 4, i % 4)
        for s in steps:
            self.step_cards[s["key"]].set(s)
        ok = [s for s in steps if s["state"] == "ok"]
        fail = [s for s in steps if s["state"] == "fail"]
        skipped = [s for s in steps if s["state"] == "skipped" and s.get("info")]
        ran = [s for s in steps if s not in skipped]
        done = sum(s["state"] in ("ok", "fail", "stopped", "skipped") for s in ran)
        if snap["running"]:
            t = f"Building {plural(len(ran), 'master')}…"
        elif snap["code"] == 0:
            t = f'<span style="color:{P["ok"]}">✓</span> {plural(len(ok), "master")} built' + (
                f' &nbsp;<span style="color:{P["warn"]};font-size:10pt">{len(skipped)} waiting for files</span>'
                if skipped else "")
        elif snap["code"] < 0:
            t = "■ Stopped"
        else:
            t = f'<span style="color:{P["err"]}">✕</span> {len(fail)} failed' + (f", {len(ok)} built" if ok else "")
        self.run_title.setText(t)
        self.run_elapsed.setText(("" if snap["running"] else "took ") + fmt_dur(snap["elapsed"]))
        self.progress.setMaximum(max(len(ran), 1))
        self.progress.setValue(done if snap["running"] else max(len(ran), 1))
        self.results_btn.setVisible(bool(ok))

    def on_job(self, snap, lines, finished):
        if snap["kind"] != "pipeline":
            return
        self.log.add(lines)
        self.show_run(snap)
        if finished:
            self.render_action()
            self.refresh()
            ok = sum(s["state"] == "ok" for s in snap["steps"])
            bad = sum(s["state"] == "fail" for s in snap["steps"])
            toast(f"{plural(ok, 'master')} built" if snap["code"] == 0 else
                  "Build stopped" if snap["code"] < 0 else f"{bad} failed, {ok} built",
                  "ok" if snap["code"] == 0 else "err")
            QApplication.alert(self.win)

    def open_results(self):
        j = B.Job.current
        p = next((s["path"] for s in j.snapshot(10 ** 9)["steps"] if s.get("path")), None) if j else None
        if p:
            self.win.open_master(p)


# ---------------------------------------------------------------------------
# MASTERS page
# ---------------------------------------------------------------------------

KEY_COLS = ["sutra_symbol", "token", "symbol", "instrument_type", "option_type", "strike_price", "expiry_date",
            "lot_size", "tick_size", "freeze_quantity", "close_price", "open_interest", "stream_id", "is_tradeable"]


class FrameModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.df, self.cols = None, []

    def set(self, df, cols):
        self.beginResetModel()
        self.df, self.cols = df, cols
        self._vals = df[cols].to_numpy() if df is not None else None
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if self.df is None else len(self.df)

    def columnCount(self, parent=QModelIndex()):
        return len(self.cols)

    def data(self, idx, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self._vals[idx.row(), idx.column()]
        if role == Qt.ForegroundRole and self.cols[idx.column()] == "option_type":
            v = self._vals[idx.row(), idx.column()]
            return QColor(P["ok"] if v == "CE" else P["err"] if v == "PE" else P["muted"])
        if role == Qt.FontRole and self.cols[idx.column()] == "sutra_symbol":
            return QFont(MONO, 9)
        return None

    def headerData(self, s, orient, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orient == Qt.Horizontal:
            return self.cols[s].replace("_", " ").upper()
        return None


class StatCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setProperty("card", "1")
        self.v = label("", "big")
        self.v.setTextFormat(Qt.RichText)
        self.setLayout(vbox(label(title.upper(), "section"), self.v, margins=(16, 12, 16, 12), spacing=2))

    def set(self, html):
        self.v.setText(html)


class MastersPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.files, self.path, self.df, self.view = [], None, None, None
        self.sort, self.desc, self.all_cols = "", False, False

        self.flist = QListWidget()
        self.flist.setFixedWidth(270)
        self.flist.currentItemChanged.connect(self.on_pick)
        left = card()
        left.setLayout(vbox(self.flist, margins=(8, 8, 8, 8)))
        left.setFixedWidth(286)

        self.title = label("", "h2")
        self.badge = exbadge("NSE")
        self.stats = [StatCard(t) for t in ("Contracts", "Futures / Options", "Expiries", "Banned")]
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search symbol, sutra symbol, name, token or ISIN")
        self.search.addAction(icon("search", P["muted"]), QLineEdit.LeadingPosition)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.timeout.connect(self.apply)
        self.search.textChanged.connect(lambda: self.debounce.start(250))
        self.combos = {}
        for col, ph in (("instrument_type", "Instrument"), ("option_type", "Option"), ("expiry_date", "Expiry")):
            c = QComboBox()
            c.setMinimumWidth({"expiry_date": 190, "instrument_type": 170, "option_type": 130}[col])
            c.currentIndexChanged.connect(self.apply)
            c.setProperty("ph", ph)
            self.combos[col] = c
        self.allsw = Switch("All columns")
        self.allsw.toggled.connect(lambda on: (setattr(self, "all_cols", on), self.apply()))
        self.model = FrameModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(self.on_sort)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self.show_row)
        self.table.setToolTip("Double-click a row for every field")
        self.foot = label("", "faint")
        filt = card()
        filt.setLayout(vbox(hbox(self.search, *self.combos.values(), self.allsw,
                                 button("", "refresh", "ghost", "Reset filters", self.reset), margins=(14, 12, 14, 12)),
                            self.table, hbox(self.foot, margins=(14, 8, 14, 10)), spacing=0))
        self.export_btn = button("Export view", "download", slot=self.export)
        self.upload_btn = button("Upload to database", "db", "primary", slot=self.to_db)
        self.right = QWidget()
        self.right.setLayout(vbox(hbox(self.badge, self.title, None, button("Folder", "folder", slot=self.open_folder),
                                       self.export_btn, self.upload_btn),
                                  hbox(*self.stats, spacing=12), filt, spacing=14))
        self.empty = card()
        self.empty.setLayout(vbox(None, label("No contract masters yet", "h2"),
                                  label("Build them on the Build page first.", "muted"), None, margins=(30, 30, 30, 30)))
        self.stack = QStackedWidget()
        self.stack.addWidget(self.right)
        self.stack.addWidget(self.empty)
        self.setLayout(vbox(hbox(vbox(label("Contract masters", "h1"),
                                      label("Browse, filter and export every generated master.", "muted"), spacing=2),
                                 None, button("Refresh", "refresh", slot=self.load_list)),
                            hbox(left, self.stack, spacing=16), margins=(34, 26, 34, 26), spacing=16))

    def showEvent(self, e):
        self.load_list()
        super().showEvent(e)

    def load_list(self, want=None):
        want = want or self.path
        self.files = B.api_masters({})
        self.flist.blockSignals(True)
        self.flist.clear()
        last, pick = None, None
        for f in self.files:
            if f["bdate"] != last:
                it = QListWidgetItem(fmt_ymd(f["bdate"]).upper())
                it.setFlags(Qt.NoItemFlags)
                it.setForeground(QColor(P["faint"]))
                ft = QFont(FONT, 8)
                ft.setBold(True)
                it.setFont(ft)
                self.flist.addItem(it)
                last = f["bdate"]
            it = QListWidgetItem(f"  {f['exchange']}  {f['segment']}        {fmt_size(f['size'])}")
            it.setData(Qt.UserRole, f["path"])
            it.setForeground(QColor(P[f["exchange"]]))
            it.setSizeHint(QSize(240, 36))
            self.flist.addItem(it)
            if f["path"] == want or (pick is None and want is None):
                pick = it
        self.flist.blockSignals(False)
        self.stack.setCurrentWidget(self.right if self.files else self.empty)
        if pick is None and self.files:
            pick = next(self.flist.item(i) for i in range(self.flist.count()) if self.flist.item(i).data(Qt.UserRole))
        if pick:
            self.flist.setCurrentItem(pick)
            if pick.data(Qt.UserRole) != self.path or self.df is None:
                self.on_pick(pick)

    def on_pick(self, it, _prev=None):
        if not it or not it.data(Qt.UserRole):
            return
        self.path = it.data(Qt.UserRole)
        f = next(x for x in self.files if x["path"] == self.path)
        style_badge(self.badge, f["exchange"])
        self.title.setText(f"{f['segment']} master · {fmt_ymd(f['bdate'])}")
        self.foot.setText("Loading…")
        path = self.path

        def done(df, exc):
            if exc:
                toast(str(exc), "err")
                return
            if path != self.path:
                return
            self.df = df
            for col, c in self.combos.items():
                c.blockSignals(True)
                c.clear()
                c.addItem(f"{c.property('ph')}: all", "")
                vals = sorted(df[col].unique(), key=B.expiry_key if col == "expiry_date" else str) if col in df else []
                for v in vals:
                    c.addItem(v, v)
                c.blockSignals(False)
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self.sort, self.desc = "", False
            self.apply()
        p = Path(path)
        run_bg(lambda: B.load_master(str(p), p.stat().st_mtime), done)

    def query(self):
        q = dict(path=self.path, q=self.search.text(), sort=self.sort, desc="1" if self.desc else "")
        for col, c in self.combos.items():
            q[col] = c.currentData() or ""
        return q

    def apply(self):
        if self.df is None:
            return
        df, view = B.filtered(self.query())
        self.view = view
        cols = list(df.columns) if self.all_cols else [c for c in KEY_COLS if c in df]
        self.model.set(view, cols)
        hh = self.table.horizontalHeader()
        for i, c in enumerate(cols):
            hh.resizeSection(i, 270 if c == "sutra_symbol" else 220 if c == "contract_name" else 110)
        if self.sort in cols:
            hh.setSortIndicatorShown(True)
            hh.setSortIndicator(cols.index(self.sort), Qt.DescendingOrder if self.desc else Qt.AscendingOrder)
        else:
            hh.setSortIndicatorShown(False)
        by = view["instrument_type"].value_counts().to_dict() if "instrument_type" in view else {}
        fut = sum(v for k, v in by.items() if k.startswith("FUT"))
        opt = sum(v for k, v in by.items() if k.startswith("OPT"))
        m = P["muted"]
        self.stats[0].set(f"{len(view):,}" + (f"<span style='font-size:10pt;color:{m}'> of {len(df):,}</span>"
                                              if len(view) != len(df) else ""))
        self.stats[1].set(f"{fut:,}<span style='font-size:10pt;color:{m}'> / {opt:,}</span>")
        self.stats[2].set(f"{view['expiry_date'].nunique():,}" if "expiry_date" in view else "—")
        banned = int((view["is_banned"] == "Y").sum()) if "is_banned" in view else 0
        self.stats[3].set(f"<span style='color:{P['err'] if banned else P['text']}'>{banned:,}</span>")
        self.foot.setText(f"{len(view):,} of {len(df):,} contracts · click a column to sort · double-click a row "
                          f"for details")

    def reset(self):
        for c in self.combos.values():
            c.blockSignals(True)
            c.setCurrentIndex(0)
            c.blockSignals(False)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.sort, self.desc = "", False
        self.apply()

    def on_sort(self, i):
        c = self.model.cols[i]
        self.desc = not self.desc if self.sort == c else False
        self.sort = c
        self.apply()

    def show_row(self, idx):
        row = self.view.iloc[idx.row()]
        d = QDialog(self)
        d.setWindowTitle(str(row.get("sutra_symbol", "Contract")))
        d.resize(560, 720)
        t = QTableWidget(len(row), 2)
        t.setHorizontalHeaderLabels(["FIELD", "VALUE"])
        t.verticalHeader().hide()
        t.horizontalHeader().setStretchLastSection(True)
        t.setColumnWidth(0, 190)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for i, (k, v) in enumerate(row.items()):
            a, b = QTableWidgetItem(k), QTableWidgetItem(str(v))
            a.setForeground(QColor(P["muted"]))
            b.setFont(QFont(MONO, 9))
            t.setItem(i, 0, a)
            t.setItem(i, 1, b)
        title = label(str(row.get("sutra_symbol", "")), "h2")
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        d.setLayout(vbox(title, t, hbox(None, button("Close", kind="primary", slot=d.accept)),
                         margins=(20, 18, 20, 16), spacing=12))
        d.exec() if not Dialog.auto else d.show()
        self.detail_dialog = d

    def export(self):
        if self.view is None:
            return
        f = next(x for x in self.files if x["path"] == self.path)
        name = f"{f['exchange'].lower()}_{f['segment'].lower()}_{f['bdate']}_filtered.csv"
        p, _ = QFileDialog.getSaveFileName(self, "Export view", str(B.windows_downloads() / name), "CSV (*.csv)")
        if p:
            self.view.to_csv(p, index=False)
            toast(f"Exported {len(self.view):,} rows")

    def open_folder(self):
        if self.path:
            B.api_open(dict(what="file", path=self.path))

    def to_db(self):
        f = next(x for x in self.files if x["path"] == self.path)
        self.win.go("database")
        self.win.pages["database"].prefill(f)


# ---------------------------------------------------------------------------
# DATABASE page
# ---------------------------------------------------------------------------

class DatabasePage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.url = QLineEdit()
        self.url.setEchoMode(QLineEdit.Password)
        self.url.setPlaceholderText("Leave empty to use the configured database")
        show = button("", "search", "ghost", "Show / hide")
        show.clicked.connect(lambda: self.url.setEchoMode(
            QLineEdit.Normal if self.url.echoMode() == QLineEdit.Password else QLineEdit.Password))
        self.effective = label("", "faint", wrap=True)
        self.status = chip("Not tested")
        self.ex = Seg([(v, v.upper()) for v in ("all", "nse", "bse", "mcx")])
        self.seg = Seg([(v, v.upper()) for v in ("all", "cm", "fo")])
        self.date = QLineEdit()
        self.date.setPlaceholderText("YYYYMMDD — empty = today, else latest with masters")
        self.chunk = QLineEdit("1000")
        self.chunk.setValidator(QIntValidator(100, 100000))
        self.chunk.setFixedWidth(120)
        self.dry = Switch("Validate only (no writes)")
        self.create = Switch("Create tables if missing")
        self.create.setChecked(True)
        self.go_btn = button("Upload", "upload", "big", slot=self.upload)
        conn = card()
        conn.setLayout(vbox(label("CONNECTION", "section"), label("Database URL", "muted"),
                            hbox(self.url, show), self.effective,
                            hbox(button("Test connection", "zap", slot=self.test), self.status, None),
                            margins=(20, 18, 20, 18), spacing=8))
        up = card()
        up.setLayout(vbox(label("UPLOAD MASTERS", "section"), label("Exchange", "muted"), hbox(self.ex, None),
                          label("Segment", "muted"), hbox(self.seg, None), label("Trade date", "muted"), self.date,
                          label("Batch size", "muted"), hbox(self.chunk, None), self.dry, self.create, 6,
                          self.go_btn, margins=(20, 18, 20, 18), spacing=8))
        self.rows = QTableWidget(0, 4)
        self.rows.setHorizontalHeaderLabels(["TRADE DATE", "EXCHANGE", "SEGMENT", "ROWS"])
        self.rows.verticalHeader().hide()
        self.rows.horizontalHeader().setStretchLastSection(True)
        self.rows.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rows.setMinimumHeight(220)
        loaded = card()
        loaded.setLayout(vbox(label("ALREADY IN THE DATABASE", "section"), self.rows, margins=(20, 18, 20, 18)))
        self.job_title = label("Upload output appears here.", "muted")
        self.job_title.setTextFormat(Qt.RichText)
        self.log = LogView(260)
        jobc = card()
        jobc.setLayout(vbox(hbox(self.job_title, None, margins=(20, 14, 20, 8)), self.log, spacing=0))
        left = vbox(conn, up, None, spacing=16)
        right = vbox(loaded, jobc, spacing=16)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(430)
        self.setLayout(vbox(hbox(vbox(label("Database", "h1"), label("Load contract masters into PostgreSQL.", "muted"),
                                      spacing=2), None, button("Schema DDL", "file", slot=self.ddl)),
                            hbox(lw, right, spacing=16), margins=(34, 26, 34, 26), spacing=16))
        win.jobs.update.connect(self.on_job)

    def showEvent(self, e):
        info = B.api_db_info({})
        self.effective.setText(f"Using: {info['effective']} ({info['source']}). The URL is never written to disk "
                               "or put on a command line.")
        super().showEvent(e)

    def prefill(self, f):
        self.ex.buttons[f["exchange"].lower()].setChecked(True)
        self.seg.buttons[f["segment"].lower()].setChecked(True)
        self.date.setText(f["bdate"])
        toast("Upload form filled in — review and press Upload")

    def test(self):
        setp(self.status, chip="run")
        self.status.setText("Connecting…")

        def done(r, exc):
            if exc:
                setp(self.status, chip="err")
                self.status.setText(str(exc).splitlines()[0][:90])
                self.status.setToolTip(str(exc))
                return
            setp(self.status, chip="ok")
            self.status.setText("Connected")
            self.status.setToolTip(r["version"])
            self.rows.setRowCount(len(r["rows"]))
            for i, row in enumerate(r["rows"]):
                for j, v in enumerate(row):
                    self.rows.setItem(i, j, QTableWidgetItem(f"{v:,}" if j == 3 else str(v)))
        url = self.url.text().strip()
        run_bg(lambda: B.api_db_test(dict(url=url)), done)

    def upload(self):
        if B.Job.current and B.Job.current.running:
            toast("Another job is running", "warn")
            return
        if not self.dry.isChecked() and Dialog.ask(
                self.win, "Upsert into the database?", "Rows with the same trade date / exchange / segment / token "
                "are overwritten.", "warn", (("Cancel", None, None), ("Upload", "go", "primary"))) != "go":
            return
        try:
            B.api_db_upload(dict(url=self.url.text().strip(), exchange=self.ex.value(), segment=self.seg.value(),
                                 date=self.date.text().strip(), chunk=self.chunk.text().strip(),
                                 dry_run=self.dry.isChecked(), create_tables=self.create.isChecked()))
            self.log.set_lines([])
            self.job_title.setText("<b>Uploading…</b>")
        except Exception as exc:
            toast(str(exc), "err")

    def on_job(self, snap, lines, finished):
        if snap["kind"] != "upload":
            return
        self.log.add(lines)
        if finished:
            ok = snap["code"] == 0
            msg = ("Validation passed" if snap["meta"].get("dry_run") else "Upload complete") if ok \
                else f"Upload failed (exit {snap['code']})"
            self.job_title.setText(f"<b style='color:{P['ok'] if ok else P['err']}'>{msg}</b> · {fmt_dur(snap['elapsed'])}")
            toast(msg, "ok" if ok else "err")
            if ok:
                self.test()

    def ddl(self):
        Dialog.ask(self.win, "contracts table", f"<pre style='font-family:{MONO}'>{B.schema_ddl()}</pre>", "info")


# ---------------------------------------------------------------------------
# HISTORY page
# ---------------------------------------------------------------------------

class HistoryPage(QWidget):
    KIND = {"pipeline": "Build", "upload": "DB upload", "register": "Prefect"}

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.entries, self.cur = [], None
        self.filter = Seg([("all", "All"), ("pipeline", "Builds"), ("upload", "Uploads"), ("fail", "Failures")])
        self.filter.changed.connect(lambda _: self.fill())
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.on_pick)
        lc = card()
        lc.setLayout(vbox(self.list, margins=(8, 8, 8, 8)))
        lc.setFixedWidth(430)
        self.when = label("", "h2")
        self.again = button("Build this again", "refresh", "primary", slot=self.build_again)
        self.log = LogView(400)
        rc = card()
        rc.setLayout(vbox(hbox(self.when, None, self.again, button("Command", "copy", slot=self.copy_cmd),
                               button("Delete", "trash", "danger", slot=self.delete), margins=(18, 14, 14, 10)),
                          self.log, spacing=0))
        self.setLayout(vbox(hbox(vbox(label("History", "h1"), label("Every build, upload and registration with its "
                                                                     "full log.", "muted"), spacing=2), None,
                                 self.filter, button("Clear all", "trash", "danger", slot=self.clear)),
                            hbox(lc, rc, spacing=16), margins=(34, 26, 34, 26), spacing=16))

    def showEvent(self, e):
        self.fill()
        super().showEvent(e)

    def status(self, e):
        bad = sum(1 for s in (e.get("results") or {}).values() if s == "fail")
        if e["code"] == 0:
            return P["ok"], "✓", {"upload": "Uploaded", "register": "Registered"}.get(e["kind"], "Success")
        if (e["code"] or 0) < 0:
            return P["warn"], "■", "Stopped"
        return P["err"], "✕", f"{bad} failed" if bad else f"Exit {e['code']}"

    def fill(self):
        self.entries = B.api_history({})
        f = self.filter.value()
        self.list.blockSignals(True)
        self.list.clear()
        for e in self.entries:
            if f != "all" and (f == "fail" and e["code"] == 0 or f not in ("fail",) and e["kind"] != f):
                continue
            color, mark, text = self.status(e)
            w = QWidget()
            ic = QLabel(mark)
            ic.setFixedSize(34, 34)
            ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(f"color: {color}; font-weight: 800; font-size: 13pt; background: {P['panel2']}; "
                             f"border-radius: 10px;")
            bd = (e.get("bdate") or "").split(":")[0]
            t = QLabel(f"<b>{self.KIND.get(e['kind'], e['kind'])} · {fmt_ymd(bd) if bd else 'today'}</b><br>"
                       f"<span style='color:{P['muted']}'>{e['title'][:48]}</span><br>"
                       f"<span style='color:{P['faint']};font-size:8.5pt'>{e['time']} · {fmt_dur(e['seconds'])}</span>")
            c = chip(text, "ok" if e["code"] == 0 else "warn" if (e["code"] or 0) < 0 else "err")
            w.setLayout(hbox(ic, t, None, c, margins=(8, 6, 8, 6)))
            it = QListWidgetItem()
            it.setData(Qt.UserRole, e["i"])
            it.setSizeHint(QSize(380, 74))
            self.list.addItem(it)
            self.list.setItemWidget(it, w)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.when.setText("Nothing here yet")
            self.log.set_lines([])

    def on_pick(self, it, _=None):
        if not it:
            return
        i = it.data(Qt.UserRole)
        self.cur = next(e for e in self.entries if e["i"] == i)
        d = B.api_history_log(dict(i=i))
        self.cmd = d["cmd"]
        self.when.setText(self.cur["time"])
        self.again.setVisible(self.cur["kind"] == "pipeline")
        self.log.set_lines(d["text"].split("\n"))

    def copy_cmd(self):
        if self.cur:
            QApplication.clipboard().setText(self.cmd)
            toast("Command copied")

    def delete(self):
        if self.cur:
            B.api_history_delete(dict(i=self.cur["i"]))
            self.fill()

    def clear(self):
        if Dialog.ask(self.win, "Delete all history?", "All entries and their saved logs are removed.", "warn",
                      (("Cancel", None, None), ("Delete all", "y", "primary"))) == "y":
            B.api_history_delete(dict(all=True))
            self.fill()

    def build_again(self):
        if not self.cur:
            return
        b = self.win.pages["build"]
        bd = (self.cur.get("bdate") or "").split(":")[0]
        if bd:
            b.date = bd
        if self.cur.get("steps"):
            b.sel = set(self.cur["steps"])
        self.win.go("build")
        b.refresh()


# ---------------------------------------------------------------------------
# SETTINGS page
# ---------------------------------------------------------------------------

class SettingsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.tabs = QTabWidget()
        self.general, self.holidays, self.schedules, self.files = QWidget(), QWidget(), QWidget(), QWidget()
        for w, t in ((self.general, "General"), (self.holidays, "Holidays"), (self.schedules, "Schedules"),
                     (self.files, "Config files")):
            w.setLayout(QVBoxLayout())
            w.layout().setContentsMargins(0, 16, 0, 0)
            self.tabs.addTab(w, t)
        self.setLayout(vbox(vbox(label("Settings", "h1"), label("Folders, holiday calendars, schedules and raw "
                                                                "configuration.", "muted"), spacing=2),
                            self.tabs, margins=(34, 26, 34, 26), spacing=12))
        self.hol_ex = "NSE"
        self.hol = {}
        self.cur_file = None
        self.reg_log = LogView(220)
        win.jobs.update.connect(self.on_job)

    def showEvent(self, e):
        self.d = B.api_settings({})
        self.hol = {k: list(v) for k, v in self.d["holidays"].items()}
        self.build_general()
        self.build_holidays()
        self.build_schedules()
        self.build_files()
        super().showEvent(e)

    def _reset(self, w):
        clear_layout(w.layout())
        return w.layout()

    def build_general(self):
        lay = self._reset(self.general)
        d = self.d
        self.df_edit = QLineEdit(d["data_folder"])
        self.df_edit.setProperty("role", "mono")
        self.df_edit.setEnabled(not d["env_override"])
        c = card()
        rows = [label("DATA FOLDER", "section"),
                label("Exchange files go to  <data folder>/<exchange>/source/<date>/,  masters to  …/common/<date>/.",
                      "muted", wrap=True)]
        if d["env_override"]:
            rows.append(label("⚠ BASE_PATH is set in the environment and decides the folder.", "warn"))
        rows += [hbox(self.df_edit, button("Browse…", "folder", slot=self.browse_df),
                      button("Save", "save", "primary", slot=self.save_df),
                      button("Open", "ext", slot=lambda: B.api_open(dict(what="data")))),
                 label("Windows paths like D:\\EOD work too." + ("" if d["data_folder_exists"] else
                                                                 "   This folder does not exist yet."), "faint")]
        c.setLayout(vbox(*rows, margins=(20, 18, 20, 18), spacing=8))
        c2 = card()
        c2.setLayout(vbox(label("CONFIGURATION FOLDER", "section"),
                          hbox(label(d["config_folder"], "mono"), None,
                               button("Open", "ext", slot=lambda: B.api_open(dict(what="config")))),
                          margins=(20, 18, 20, 18), spacing=8))
        c3 = card()
        c3.setLayout(vbox(label("DOWNLOADS FOLDER (IMPORT / AUTO-IMPORT)", "section"),
                          hbox(label(str(self.win.pages["build"].downloads), "mono"), None,
                               button("Open", "ext", slot=lambda: B.open_path(self.win.pages["build"].downloads))),
                          margins=(20, 18, 20, 18), spacing=8))
        for w in (c, c2, c3):
            w.setMaximumWidth(900)
            lay.addWidget(w)
        lay.addStretch(1)

    def browse_df(self):
        p = QFileDialog.getExistingDirectory(self, "Data folder", self.df_edit.text())
        if p:
            self.df_edit.setText(p)

    def save_df(self):
        path = self.df_edit.text().strip()
        try:
            B.api_set_data_folder(dict(path=path))
        except ValueError as exc:
            if "does not exist" not in str(exc):
                return toast(str(exc), "err")
            if Dialog.ask(self.win, "Create this folder?", path, "info",
                          (("Cancel", None, None), ("Create", "y", "primary"))) != "y":
                return
            B.api_set_data_folder(dict(path=path, create=True))
        toast("Data folder saved")
        self.win.refresh_side()
        self.d = B.api_settings({})
        self.build_general()
        self.win.pages["build"].refresh()

    def build_holidays(self):
        lay = self._reset(self.holidays)
        ex = self.hol_ex
        lst = sorted(self.hol.get(ex, []))
        today = date.today().isoformat()
        nxt = next((d for d in lst if d >= today), None)
        seg = Seg([(x, x) for x in B.EXCHANGES], ex)
        seg.changed.connect(lambda v: (setattr(self, "hol_ex", v), self.build_holidays()))
        self.hol_new = QDateEdit(QDate.currentDate())
        self.hol_new.setCalendarPopup(True)
        self.hol_new.setDisplayFormat("dd MMM yyyy")
        c = card()
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, d in enumerate(lst):
            dt = datetime.strptime(d, "%Y-%m-%d")
            f = QFrame()
            f.setStyleSheet(f"background: {P['panel2']}; border: 1px solid {P['border']}; border-radius: 10px;")
            t = QLabel(f"<b>{dt:%d %b %Y}</b><br><span style='color:{P['muted']}'>{dt:%A}"
                       f"{' · weekend' if dt.weekday() >= 5 else ''}</span>")
            t.setStyleSheet("border: none;" + ("color: " + P["faint"] if d < today else ""))
            rm = button("", "x", "ghost", "Remove", lambda _=False, d=d: self.rm_hol(d))
            f.setLayout(hbox(t, None, rm, margins=(10, 6, 6, 6)))
            grid.addWidget(f, i // 5, i % 5)
        c.setLayout(vbox(hbox(seg, label(f"{plural(len(lst), 'holiday')} · next: "
                                         f"<b>{fmt_ymd(nxt.replace('-', '')) if nxt else '—'}</b>", "muted"), None,
                              self.hol_new, button("Add", "plus", slot=self.add_hol),
                              button("Copy to all exchanges", "copy", slot=self.copy_hol),
                              button("Save", "save", "primary", slot=self.save_hol)),
                         grid, None, margins=(20, 18, 20, 18), spacing=14))
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(c)
        lay.addWidget(sc)

    def add_hol(self):
        d = self.hol_new.date().toString("yyyy-MM-dd")
        self.hol[self.hol_ex] = sorted(set(self.hol.get(self.hol_ex, [])) | {d})
        self.build_holidays()

    def rm_hol(self, d):
        self.hol[self.hol_ex] = [x for x in self.hol.get(self.hol_ex, []) if x != d]
        self.build_holidays()

    def copy_hol(self):
        for x in B.EXCHANGES:
            self.hol[x] = list(self.hol.get(self.hol_ex, []))
        toast(f"Copied {self.hol_ex} holidays to all exchanges — press Save", "warn")

    def save_hol(self):
        B.api_set_holidays(self.hol)
        toast("Holidays saved")
        self.win.pages["build"].refresh()

    def build_schedules(self):
        lay = self._reset(self.schedules)
        d = self.d
        t = QTableWidget(len(d["schedules"]), 4)
        t.setHorizontalHeaderLabels(["REGISTER", "MASTER", "CRON (minute hour day month weekday)", "RUNS"])
        t.verticalHeader().hide()
        t.verticalHeader().setDefaultSectionSize(40)
        t.horizontalHeader().setStretchLastSection(True)
        t.setColumnWidth(0, 90)
        t.setColumnWidth(1, 120)
        t.setColumnWidth(2, 300)
        self.reg_checks, self.cron_edits, self.human = {}, {}, {}
        for i, s in enumerate(d["schedules"]):
            cb = QCheckBox()
            cb.setChecked(True)
            self.reg_checks[s["key"]] = cb
            w = QWidget()
            w.setLayout(hbox(None, cb, None))
            t.setCellWidget(i, 0, w)
            t.setItem(i, 1, QTableWidgetItem(s["label"]))
            e = QLineEdit(s["cron"])
            e.setProperty("role", "mono")
            e.editingFinished.connect(lambda k=s["key"], e=e: self.save_cron(k, e))
            self.cron_edits[s["key"]] = e
            t.setCellWidget(i, 2, e)
            it = QTableWidgetItem(s["human"])
            it.setForeground(QColor(P["muted"]))
            t.setItem(i, 3, it)
            self.human[s["key"]] = it
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setFixedHeight(40 * len(d["schedules"]) + 40)
        o = d["orchestration"]
        self.pool, self.queue, self.src = QLineEdit(o["work_pool_name"]), QLineEdit(o["work_queue_name"]), QLineEdit(o["source"])
        self.src.setPlaceholderText("empty = /home/$USER/devopts/")
        c1 = card()
        c1.setLayout(vbox(label("PREFECT SCHEDULES", "section"),
                          label("Optional. A Prefect worker builds “today” on this timetable (Asia/Kolkata), waiting "
                                "up to 2 hours for the files to appear in the data folder. Edit a cron and press Enter "
                                "to save it.", "muted", wrap=True), t, margins=(20, 18, 20, 18), spacing=10))
        c2 = card()
        c2.setLayout(vbox(label("DEPLOYMENT TARGET", "section"),
                          hbox(vbox(label("Work pool", "muted"), self.pool, spacing=4),
                               vbox(label("Work queue", "muted"), self.queue, spacing=4),
                               vbox(label("Source folder", "muted"), self.src, spacing=4)),
                          hbox(None, button("Save", "save", slot=self.save_orch),
                               button("Register selected", "play", "primary", slot=self.register)),
                          margins=(20, 18, 20, 18), spacing=10))
        if not B.HAS_PREFECT:
            note = card()
            note.setLayout(vbox(label("PREFECT SCHEDULES", "section"),
                                label("Scheduled runs need Prefect, which is not part of this packaged app. Install "
                                      "from source on the server that should run on a timetable.", "muted", wrap=True),
                                margins=(20, 18, 20, 18), spacing=8))
            lay.addWidget(note)
            lay.addStretch(1)
            return
        self.reg_card = card()
        self.reg_card.setLayout(vbox(self.reg_log, spacing=0))
        self.reg_card.setVisible(bool(B.Job.current and B.Job.current.kind == "register"))
        for w in (c1, c2, self.reg_card):
            lay.addWidget(w)
        lay.addStretch(1)

    def save_cron(self, key, e):
        try:
            r = B.api_set_schedule(dict(key=key, cron=e.text()))
            self.human[key].setText(r["human"])
            toast("Schedule saved — register to apply")
        except ValueError as exc:
            toast(str(exc), "err")

    def save_orch(self):
        B.api_set_orchestration(dict(work_pool_name=self.pool.text(), work_queue_name=self.queue.text(),
                                     source=self.src.text()))
        toast("Deployment target saved")

    def register(self):
        keys = [k for k, c in self.reg_checks.items() if c.isChecked()]
        if not keys:
            return toast("Select at least one master", "warn")
        if Dialog.ask(self.win, f"Register {plural(len(keys), 'deployment')}?",
                      f"Pool <b>{self.pool.text()}</b>, queue <b>{self.queue.text()}</b>.", "info",
                      (("Cancel", None, None), ("Register", "y", "primary"))) != "y":
            return
        try:
            B.api_register(dict(keys=keys))
            self.reg_log.set_lines([])
            self.reg_card.show()
        except ValueError as exc:
            toast(str(exc), "err")

    def on_job(self, snap, lines, finished):
        if snap["kind"] == "register":
            self.reg_log.add(lines)
            if finished:
                toast("Deployments registered" if snap["code"] == 0 else "Registration had errors",
                      "ok" if snap["code"] == 0 else "err")

    def build_files(self):
        lay = self._reset(self.files)
        names = self.d["config_files"]
        self.cur_file = self.cur_file if self.cur_file in names else names[0]
        self.cf_combo = QComboBox()
        self.cf_combo.addItems(names)
        self.cf_combo.setCurrentText(self.cur_file)
        self.cf_combo.currentTextChanged.connect(self.load_cf)
        self.cf_valid = chip("")
        self.cf_text = QPlainTextEdit()
        self.cf_text.textChanged.connect(self.validate_cf)
        c = card()
        c.setLayout(vbox(hbox(self.cf_combo, self.cf_valid, None, button("Format", slot=self.format_cf),
                              button("Save", "save", "primary", slot=self.save_cf)),
                         self.cf_text,
                         label("⚠ May contain credentials (database URL). The previous version is kept as .bak.",
                               "faint"), margins=(20, 18, 20, 18), spacing=10))
        lay.addWidget(c)
        self.load_cf(self.cur_file)

    def load_cf(self, name):
        self.cur_file = name
        self.cf_text.setPlainText(B.config_file(name).read_text(encoding="utf-8"))

    def validate_cf(self):
        import json
        try:
            json.loads(self.cf_text.toPlainText())
            self.cf_valid.setText("✓ Valid JSON")
            setp(self.cf_valid, chip="ok")
            return True
        except json.JSONDecodeError as e:
            self.cf_valid.setText(f"✕ Line {e.lineno}, column {e.colno}: {e.msg}")
            setp(self.cf_valid, chip="err")
            return False

    def format_cf(self):
        import json
        if self.validate_cf():
            self.cf_text.setPlainText(json.dumps(json.loads(self.cf_text.toPlainText()), indent=2) + "\n")

    def save_cf(self):
        if not self.validate_cf():
            return toast("Fix the JSON first", "err")
        try:
            B.api_save_config(dict(name=self.cur_file, text=self.cf_text.toPlainText()))
            toast(f"{self.cur_file} saved")
            self.win.pages["build"].refresh()
        except ValueError as exc:
            toast(str(exc), "err")


# ---------------------------------------------------------------------------
# main window
# ---------------------------------------------------------------------------

NAV = [("build", "Build", "build"), ("masters", "Masters", "table"), ("database", "Database", "db"),
       ("history", "History", "clock"), ("settings", "Settings", "sliders"), ("help", "Help", "info")]


class Window(QMainWindow):
    current_window = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phoenix Contract Masters")
        self.setWindowIcon(QIcon(logo_pixmap(64)))
        self.resize(*B.settings.get("window", [1500, 960]))
        self.setMinimumSize(1180, 720)
        self.jobs = JobWatch()

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(232)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(40))
        brand = QLabel("<b style='font-size:12pt'>Phoenix</b><br><span style='color:%s'>Contract Masters</span>"
                       % P["muted"])
        self.navs = {}
        group = QButtonGroup(self)
        nav_box = vbox(spacing=4)
        for i, (key, text, ic) in enumerate(NAV):
            b = QPushButton(f"  {text}")
            b.setProperty("nav", "1")
            b.setCheckable(True)
            b.setIcon(icon(ic, P["muted"]))
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(f"Ctrl+{i + 1}")
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            group.addButton(b)
            nav_box.addWidget(b)
            self.navs[key] = b
        self.folder_btn = QPushButton()
        self.folder_btn.setStyleSheet(f"text-align: left; padding: 10px 12px; border-radius: 12px;")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(lambda: B.api_open(dict(what="data")))
        self.theme_btn = button("", kind="ghost", slot=self.toggle_theme)
        self.busy_lbl = label("", "faint", wrap=True)
        side.setLayout(vbox(hbox(logo, brand, None, margins=(6, 0, 0, 0)), 18, nav_box, None, self.busy_lbl,
                            self.folder_btn, self.theme_btn, margins=(14, 20, 14, 16), spacing=6))

        self.stack = QStackedWidget()
        self.pages = {}
        self.pages["build"] = BuildPage(self)
        self.pages["masters"] = MastersPage(self)
        self.pages["database"] = DatabasePage(self)
        self.pages["history"] = HistoryPage(self)
        self.pages["settings"] = SettingsPage(self)
        from .help_page import HelpPage  # imports this module's helpers, so it is loaded late
        self.pages["help"] = HelpPage(self)
        for p in self.pages.values():
            self.stack.addWidget(p)
        root.setLayout(hbox(side, self.stack, spacing=0))
        Toasts(root)

        for i, (key, _, _) in enumerate(NAV):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, lambda k=key: self.go(k))
        QShortcut(QKeySequence("F1"), self, lambda: self.go("help"))
        QShortcut(QKeySequence("Ctrl+R"), self, lambda: self.current == "build" and self.pages["build"].start())
        QShortcut(QKeySequence("Ctrl+O"), self, lambda: (self.go("build"), self.pages["build"].choose_files()))
        QShortcut(QKeySequence("Ctrl+I"), self, lambda: (self.go("build"), self.pages["build"].import_downloads()))
        self.jobs.update.connect(self.on_job_nav)
        self.refresh_side()
        self.go("build")

    def go(self, key):
        self.current = key
        self.navs[key].setChecked(True)
        for k, b in self.navs.items():
            b.setIcon(icon(dict((n[0], n[2]) for n in NAV)[k], P["text"] if k == key else P["muted"]))
        self.stack.setCurrentWidget(self.pages[key])

    def refresh_side(self):
        path = self.folder_btn.fontMetrics().elidedText(B.get_base_path(), Qt.ElideMiddle, 150)
        self.folder_btn.setText(f"  Data folder\n  {path}")
        self.folder_btn.setIcon(icon("folder", P["muted"]))
        self.folder_btn.setToolTip(f"Open the data folder\n{B.get_base_path()}")
        dark = theme_name() == "dark"
        self.theme_btn.setText("  Light mode" if dark else "  Dark mode")
        self.theme_btn.setIcon(icon("sun" if dark else "moon", P["text"]))

    def busy(self, text):
        self.busy_lbl.setText(f"⏳ {text}" if text else "")
        QApplication.setOverrideCursor(Qt.BusyCursor) if text else QApplication.restoreOverrideCursor()

    def on_job_nav(self, snap, _lines, finished):
        key = {"pipeline": "build", "upload": "database", "register": "settings"}.get(snap["kind"])
        for k, b in self.navs.items():
            text = dict((n[0], n[1]) for n in NAV)[k]
            b.setText(f"  {text}  ●" if k == key and snap["running"] else f"  {text}")

    def stop_job(self):
        if B.Job.current and B.Job.current.running and Dialog.ask(
                self, "Stop the running job?", "Masters already written stay; the one being built is abandoned.",
                "warn", (("Keep running", None, None), ("Stop", "stop", "primary"))) == "stop":
            B.api_job_stop({})
            toast("Stopping…", "warn")

    def open_master(self, path):
        self.go("masters")
        self.pages["masters"].load_list(want=path)

    def toggle_theme(self):
        """Icons and painted widgets carry colours, so the simplest correct switch is a fresh window."""
        apply_theme("light" if theme_name() == "dark" else "dark")
        _icon_cache.clear()
        b = self.pages["build"]
        new = Window()
        new.setGeometry(self.geometry())
        new.pages["build"].sel = b.sel
        new.pages["build"].set_date(b.date)
        new.go(self.current)
        new.show()
        Window.current_window = new
        self.replaced = True
        self.close()

    def closeEvent(self, e):
        if getattr(self, "replaced", False):
            self.jobs.timer.stop()
            super().closeEvent(e)
            self.deleteLater()
            return
        if B.Job.current and B.Job.current.running:
            if Dialog.ask(self, "A job is still running", "Stop it and quit?", "warn",
                          (("Keep running", None, None), ("Stop and quit", "q", "primary"))) != "q":
                e.ignore()
                return
            B.Job.current.stop()
        B.settings["window"] = [self.width(), self.height()]
        B.settings["build"] = dict(steps=sorted(self.pages["build"].sel), retry=self.pages["build"].retry.isChecked(),
                                   stop_on_error=self.pages["build"].stop_err.isChecked())
        B.settings.save()
        super().closeEvent(e)


def theme_name():
    return B.settings.get("theme", "dark")


def apply_theme(name):
    P.clear()
    P.update(PALETTES[name])
    B.settings["theme"] = name
    B.settings.save()
    QApplication.instance().setStyleSheet(qss(P))


def load_fonts():
    """Use the Windows UI fonts when running under WSL; otherwise fall back to whatever is installed."""
    global FONT, MONO
    fonts = Path("/mnt/c/Windows/Fonts")
    for f in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf", "consolab.ttf"):
        if (fonts / f).is_file():
            QFontDatabase.addApplicationFont(str(fonts / f))
    fams = set(QFontDatabase.families())
    FONT = next((f for f in ("Segoe UI", "Inter", "Ubuntu", "Noto Sans", "DejaVu Sans") if f in fams), FONT)
    MONO = next((f for f in ("Consolas", "Cascadia Mono", "JetBrains Mono", "DejaVu Sans Mono") if f in fams), MONO)


def main():
    B.load_config(reload=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Phoenix Contract Masters")
    app.setDesktopFileName("phoenix-contract-masters")
    load_fonts()
    app.setFont(QFont(FONT, 10))
    P.update(PALETTES[theme_name()])
    app.setStyleSheet(qss(P))
    w = Window()
    Window.current_window = w
    w.show()
    code = app.exec()
    if B.Job.current and B.Job.current.running:
        B.Job.current.stop()
    sys.exit(code)
