"""Help page: getting started, a reference card for every exchange file, dates, folders, output columns,
troubleshooting, shortcuts and About. File facts come from core/inputs.py, so they never drift from the build."""

import platform
import sys
from html import escape

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QSize, Qt, qVersion
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout, QLabel, QListWidget,
                               QListWidgetItem, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QWidget)

from core.inputs import INPUTS, pattern_text
from pipeline import PROJECT_ROOT, STEPS

from . import __version__
from . import backend as B
from .app import MONO, P, button, card, chip, exbadge, fmt_ymd, hbox, label, plural, toast, vbox
from .state import HOME

STEPS_GUIDE = [
    ("Pick the business date", "On <b>Build</b>, choose the day the masters are <i>for</i> (normally today). "
     "The header tells you the date the exchange files carry — usually the previous business day."),
    ("Download the exchange files", "Download them from the NSE / BSE / MCX extranets as usual. The checklist on "
     "Build lists exactly which files are needed; click a file to see where it lives. The full list is below."),
    ("Bring them in", "Click <b>Import from Downloads</b> (Ctrl+I). Your Windows Downloads folder is searched — "
     "subfolders and zips too — and only the needed files are copied into place. With <b>Auto-import new "
     "downloads</b> on, files are filed the moment a download finishes."),
    ("Build", "When a master card shows <b>Ready</b>, press <b>Build</b> (Ctrl+R). Masters still missing files are "
     "left out and listed; the others are built. Each result shows its contract count."),
    ("Check and load", "Click a result to open it on <b>Masters</b> — search, filter, export. Then <b>Upload to "
     "database</b> loads it into PostgreSQL."),
]

DAILY = [
    "Open the app — it starts on the latest business day.",
    "Download the files for every exchange you trade (the red ✕ items).",
    "Import from Downloads (or leave Auto-import on while you download).",
    "All cards green → Build. Glance at the contract counts.",
    "Upload to the database.",
]

COLUMNS = [
    ("trade_date", "Business date the master is for (YYYYMMDD)"),
    ("sutra_symbol", "Normalised symbol, e.g. NSE_BANKNIFTY_OPT_20261229_M_69400.0_CE"),
    ("sutra_token", "Unique token: exchange × 10 + segment, followed by the exchange token"),
    ("token", "Exchange instrument token"),
    ("future_token", "Token of the matching future (options) / itself"),
    ("equity_token", "Token of the underlying"),
    ("exchange, segment", "NSE / BSE / MCX and CM / FO"),
    ("contract_name, symbol", "Exchange description and ticker"),
    ("instrument_type", "EQ series, FUTIDX, FUTSTK, OPTIDX, OPTSTK, FUTCOM…"),
    ("option_type", "CE, PE, or XX for non-options"),
    ("strike_price", "Strike × 100 (paise)"),
    ("expiry_epoch / expiry_date", "Expiry as seconds since 1980-01-01 and as '27 October 2026'"),
    ("days_to_expiry, expiry_cycle", "Calendar days left; W1, W2… weekly or M1, M2… monthly"),
    ("stream_id, market_segment_id", "Market-data stream / partition and product id"),
    ("freeze_quantity, lot_size", "Max quantity per order; minimum lot"),
    ("divisor, tick_size", "Price scale (100) and minimum price step in paise"),
    ("open … last_price", "Previous day's prices × 100 (0 without a bhavcopy)"),
    ("previous_close_price, underlying_price", "Prices × 100"),
    ("total_traded_volume / _value", "Previous day's volume and turnover"),
    ("high_dpr, low_dpr", "Upper / lower circuit (daily price range) × 100"),
    ("open_interest", "Open contracts at previous close"),
    ("is_tradeable, is_banned", "Y / N flags"),
    ("currency, timezone, trading_schedule", "INR, Asia/Kolkata, session hours"),
    ("isin, face_value, asset_code", "Regulatory identifiers"),
]

TROUBLE = [
    ("A file shows ✕ although I downloaded it",
     "The name must match the date: most files carry the <i>previous</i> business day (see the name shown for "
     "the selected date). If Import says a file is “for a different date”, change the date on Build or download "
     "the right day. Files still downloading (.crdownload) are skipped until they finish."),
    ("Import found nothing", "Check the file is in Downloads (or the folder you scanned) and not still "
     "downloading. Zips are opened automatically. Use Choose files… to pick it directly."),
    ("Auto-import didn't pick a file up", "Only files that finish downloading <i>after</i> the switch is turned on "
     "are watched. For files already there, click Import from Downloads."),
    ("A build failed", "The result card says why in plain words — usually a missing or damaged file. Click the "
     "card to see the errors in the log. History keeps every log."),
    ("Fewer contracts than expected", "NSE keeps only contracts listed in the stream-info file; download the latest "
     "one. FO masters drop options whose future cannot be found."),
    ("Prices / OI are 0", "The optional bhavcopy for that master was missing. Add it and build again — rebuilding "
     "replaces the previous output."),
    ("Build is greyed out", "The date is a weekend or holiday, or no selected master is ready. Use ‹ › to move to "
     "a business day; holidays are edited in Settings → Holidays."),
]

SHORTCUTS = [("Ctrl+1 … Ctrl+6", "Switch page"), ("F1", "This help"), ("Ctrl+I", "Import from Downloads"),
             ("Ctrl+O", "Choose files"), ("Ctrl+R", "Build"), ("Esc", "Close a dialog")]


def h(title, sub=""):
    return vbox(label(title, "h2"), *([label(sub, "muted", wrap=True)] if sub else []), spacing=2)


class HelpPage(QWidget):
    SECTIONS = ["Getting started", "Daily routine", "Exchange files", "Dates explained", "Where files are saved",
                "Output columns", "Troubleshooting", "Keyboard shortcuts", "About"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.nav = QListWidget()
        self.nav.setFixedWidth(210)
        for s in self.SECTIONS:
            it = QListWidgetItem(s)
            it.setSizeHint(QSize(190, 34))
            self.nav.addItem(it)
        self.nav.currentRowChanged.connect(self.jump)
        navc = card()
        navc.setLayout(vbox(self.nav, None, margins=(8, 8, 8, 8)))
        navc.setFixedWidth(226)
        self.body = QWidget()
        self.body_lay = vbox(spacing=16, margins=(0, 0, 12, 20))
        self.body.setLayout(self.body_lay)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # everything wraps instead
        self.scroll.setWidget(self.body)
        self.setLayout(vbox(vbox(label("Help", "h1"), label("How to use the app, and everything about the exchange "
                                                            "files it needs.", "muted"), spacing=2),
                            hbox(navc, self.scroll, spacing=16), margins=(34, 26, 34, 26), spacing=16))
        self.anchors = {}

    def showEvent(self, e):
        self.build()
        super().showEvent(e)

    def jump(self, row):
        w = self.anchors.get(self.SECTIONS[row]) if row >= 0 else None
        if w:
            self.scroll.verticalScrollBar().setValue(w.y())

    def section(self, title, *widgets_or_layouts, sub=""):
        c = card()
        c.setLayout(vbox(h(title, sub), *widgets_or_layouts, margins=(22, 18, 22, 20), spacing=12))
        self.anchors[title] = c
        self.body_lay.addWidget(c)
        return c

    def build(self):
        while self.body_lay.count():
            it = self.body_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.anchors = {}
        bd = self.win.pages["build"].date
        st = B.api_state(dict(date=bd))
        present = {f["key"]: f for ex in st["exchanges"] for f in ex["files"]}

        # getting started
        rows = []
        for i, (title, text) in enumerate(STEPS_GUIDE, 1):
            n = QLabel(str(i))
            n.setFixedSize(30, 30)
            n.setAlignment(Qt.AlignCenter)
            n.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6366f1, stop:1 #d946ef);"
                            "color: white; border-radius: 15px; font-weight: 800;")
            t = label(f"<b>{title}</b><br><span style='color:{P['muted']}'>{text}</span>", wrap=True)
            t.setTextFormat(Qt.RichText)
            rows.append(hbox(vbox(n, None), t, spacing=14))
        self.section("Getting started", *rows,
                     hbox(button("Go to Build", "build", "primary", slot=lambda: self.win.go("build")), None))

        self.section("Daily routine", label("<ol style='margin:0'>" + "".join(f"<li style='margin:4px'>{d}</li>"
                                                                               for d in DAILY) + "</ol>", wrap=True))

        # exchange files
        blocks = [label(f"Files shown for <b>{fmt_ymd(st['date'])}</b> (the date selected on Build). "
                        "<b>Required</b> files must be there to build that master; <b>optional</b> ones only add "
                        "prices, open interest or circuit limits. File names are case-insensitive; zips and "
                        ".gz are unpacked automatically.", "muted", wrap=True)]
        for ex in B.EXCHANGES:
            files = [f for f in INPUTS if f.exchange == ex]
            req = sum(f.required for f in files)
            masters = ", ".join(f"{s.exchange} {s.segment}" for s in STEPS.values() if s.exchange == ex)
            blocks.append(hbox(exbadge(ex), label(f"<b>{len(files)} files</b> · {req} required · builds {masters}",
                                                  "muted"), None))
            for f in files:
                blocks.append(self.file_block(f, present.get(f.key), bd, st["problem"]))
        self.section("Exchange files", *blocks)

        self.section("Dates explained", label(
            "<b>Business date</b> — the trading day the masters are for. Weekends and the exchange holidays in "
            "Settings → Holidays are skipped.<br><br>"
            "<b>Previous business day</b> — exchanges publish their reference files the evening before, so most "
            "file names carry that date: for Monday 12 Oct the files are dated Friday 09 Oct "
            "(<span style='font-family:%s'>qty_freeze_09102026.csv</span>).<br><br>"
            "<b>Exception</b> — the BSE equity price-band file <span style='font-family:%s'>DP&lt;DDMMYY&gt;</span> "
            "carries the business date itself." % (MONO, MONO), wrap=True))

        base = B.get_base_path()
        paths = QGridLayout()
        paths.setHorizontalSpacing(14)
        paths.setVerticalSpacing(8)
        for i, (what, path, opener) in enumerate([
                ("Exchange files", f"{base}/<exchange>/source/<YYYYMMDD>/", lambda: B.api_open(dict(what="data"))),
                ("Contract masters", f"{base}/<exchange>/common/<YYYYMMDD>/*_contract_master.csv",
                 lambda: B.api_open(dict(what="data"))),
                ("Configuration", str(B.config_dir()), lambda: B.api_open(dict(what="config"))),
                ("Run history & logs", str(HOME), lambda: B.open_path(HOME)),
                ("Downloads watched", str(self.win.pages["build"].downloads),
                 lambda: B.open_path(self.win.pages["build"].downloads))]):
            paths.addWidget(label(f"<b>{what}</b>"), i, 0)
            pl = label(path, "mono", wrap=True)
            pl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            pl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            paths.addWidget(pl, i, 1)
            paths.addWidget(button("Open", "ext", "ghost", slot=opener), i, 2)
        paths.setColumnStretch(1, 1)
        self.section("Where files are saved", paths,
                     label("Change the data folder in Settings → General.", "faint"))

        t = QTableWidget(len(COLUMNS), 2)
        t.setHorizontalHeaderLabels(["COLUMN", "MEANING"])
        t.verticalHeader().hide()
        t.horizontalHeader().setStretchLastSection(True)
        t.setColumnWidth(0, 300)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.verticalHeader().setDefaultSectionSize(30)
        for i, (c, m) in enumerate(COLUMNS):
            a = QTableWidgetItem(c)
            a.setFont(QFont(MONO, 9))
            t.setItem(i, 0, a)
            t.setItem(i, 1, QTableWidgetItem(m))
        t.setFixedHeight(30 * len(COLUMNS) + 40)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.section("Output columns", t, sub="Every contract master CSV has the same 52 columns, ready for "
                                              "the trading engines and the database.")

        self.section("Troubleshooting", *[label(f"<b>{q}</b><br><span style='color:{P['muted']}'>{a}</span>",
                                                wrap=True) for q, a in TROUBLE])

        sc = QGridLayout()
        sc.setHorizontalSpacing(18)
        sc.setVerticalSpacing(8)
        for i, (k, v) in enumerate(SHORTCUTS):
            kl = QLabel(k)
            kl.setStyleSheet(f"background: {P['panel2']}; border: 1px solid {P['border2']}; border-radius: 6px;"
                             f"padding: 3px 9px; font-family: {MONO}; font-weight: 700;")
            sc.addWidget(kl, i // 2, (i % 2) * 2, Qt.AlignLeft)
            sc.addWidget(label(v, "muted"), i // 2, (i % 2) * 2 + 1)
        sc.setColumnStretch(1, 1)
        sc.setColumnStretch(3, 1)
        self.section("Keyboard shortcuts", sc)

        about = QGridLayout()
        about.setHorizontalSpacing(14)
        about.setVerticalSpacing(6)
        for i, (k, v) in enumerate([
                ("Version", __version__), ("Builds", "NSE CM, NSE FO, BSE CM, BSE FO, MCX FO contract masters"),
                ("Program folder", str(PROJECT_ROOT)), ("Data folder", base), ("Python", platform.python_version()),
                ("Qt / PySide6", f"{qVersion()} / {PYSIDE_VERSION}"),
                ("System", f"{platform.system()} {platform.release()}" + ("  (WSL)" if B.IS_WSL else ""))]):
            about.addWidget(label(k, "muted"), i, 0)
            v_ = label(v, "mono" if "folder" in k.lower() else None, wrap=True)
            v_.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v_.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            about.addWidget(v_, i, 1)
        about.setColumnStretch(1, 1)
        info = "\n".join(f"{k}: {v}" for k, v in [("Phoenix Contract Masters", __version__),
                                                   ("Python", sys.version.split()[0]), ("Qt", qVersion()),
                                                   ("Program", PROJECT_ROOT), ("Data", base)])
        self.section("About", label("<b style='font-size:13pt'>Phoenix Contract Masters</b><br>"
                                    f"<span style='color:{P['muted']}'>Builds standard contract masters from the "
                                    "exchange reference files you download.</span>", wrap=True),
                     about, hbox(button("Copy details", "copy", slot=lambda: (QApplication.clipboard().setText(info),
                                                                              toast("Details copied"))), None))
        self.body_lay.addStretch(1)

    def file_block(self, f, info, bd, problem):
        box = QFrame()
        box.setStyleSheet(f"QFrame#fb {{ background: {P['panel2']}; border: 1px solid {P['border']}; "
                          f"border-radius: 12px; }}")
        box.setObjectName("fb")
        segs = "/".join(STEPS[k].segment for k in f.steps)
        here = info and info["present"]
        dot = QLabel("✓" if here else "✕" if f.required else "○")
        dot.setFixedSize(26, 26)
        dot.setAlignment(Qt.AlignCenter)
        color = P["ok"] if here else P["err"] if f.required else P["faint"]
        dot.setStyleSheet(f"color: {color}; font-weight: 800; border: none;")
        title = label(f"<span style='font-family:{MONO};font-size:10.5pt'><b>{escape(pattern_text(f))}</b></span>"
                      f"&nbsp;&nbsp;<span style='color:{P['muted']}'>{f.label}</span>")
        title.setTextFormat(Qt.RichText)
        need = chip("REQUIRED" if f.required else "optional", "err" if f.required and not here else
                    "ok" if f.required else "plain")
        seg = chip(segs, "plain")
        today = "" if problem else info["name"] if here else f.name(bd)  # the file actually on disk, if any
        copy = button("", "copy", "ghost", f"Copy {today}", lambda: (QApplication.clipboard().setText(today),
                                                                    toast("File name copied")))
        masters = " and ".join(f"{STEPS[k].exchange} {STEPS[k].segment}" for k in f.steps)
        missing = (f"<span style='color:{P['err']}'>{masters} cannot be built.</span>" if f.required else
                   f"{masters} is still built; these columns stay 0.")
        rows = [("What it is", f.about), ("Get it from", f.source), ("Fills columns", f.feeds),
                ("If it is missing", missing)]
        if len(f.names(bd)) > 1:
            rows.append(("Also accepted", ", ".join(f"<span style='font-family:{MONO}'>{n}</span>"
                                                    for n in f.names(bd)[1:])))
        if today:
            state = (f"<span style='color:{P['ok']}'>here</span>" if here else
                     f"<span style='color:{P['err' if f.required else 'faint']}'>not added yet</span>")
            rows.append((f"Name for {fmt_ymd(bd)}", f"<span style='font-family:{MONO}'>{today}</span> — {state}"))
        table = "".join(f"<tr><td style='color:{P['muted']};padding:3px 16px 3px 0;white-space:nowrap' valign=top>"
                        f"{k}</td><td style='padding:3px 0'>{v}</td></tr>" for k, v in rows)
        body = label(f"<table cellspacing=0 width='100%'>{table}</table>", wrap=True)
        body.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        body.setTextFormat(Qt.RichText)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box.setLayout(vbox(hbox(dot, title, None, seg, need, *([copy] if today else [])), body,
                           margins=(14, 12, 14, 12), spacing=6))
        return box
