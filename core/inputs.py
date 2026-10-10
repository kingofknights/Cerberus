"""
Exchange input files: the one place that knows every file name, date format and folder.

Files are downloaded by hand. Parsers resolve paths here, the GUI checklist and the
importer read the same list, so "what the app asks for" and "what the build reads"
can never disagree.

Layout: one flat folder per exchange per business date, e.g. ~/EOD/nse/source/20261009/
"""

import gzip
import io
import os
import re
import shutil
import string
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from core.config import get_storage_config
from core.dates import get_prev_businessday


@dataclass(frozen=True)
class InputFile:
    key: str
    exchange: str  # NSE / BSE / MCX
    pattern: str  # {prev:%d%m%Y} = previous business day, {bdate:...} = business date
    steps: Tuple[str, ...]  # master steps (pipeline.STEPS keys) that read it
    required: bool  # False: the master is still built, those columns stay 0
    label: str
    source: str  # where to download it
    aliases: Tuple[str, ...] = ()  # other names the same content arrives under (e.g. uncompressed .txt)
    about: str = ""  # what the file is (shown in the app's Help)
    feeds: str = ""  # contract-master columns it fills

    def names(self, bdate: str) -> List[str]:
        d = datetime.strptime(bdate, "%Y%m%d")
        prev = get_prev_businessday(d, apply_holidays=self.exchange)
        return [p.format(bdate=d, prev=prev) for p in (self.pattern, *self.aliases)]

    def name(self, bdate: str) -> str:
        return self.names(bdate)[0]

    def path(self, bdate: str) -> Path:
        """The file as present on disk (any accepted name, any letter case), else the canonical path."""
        folder = input_dir(self.exchange, bdate)
        try:
            present = {p.name.lower(): p for p in folder.iterdir() if p.is_file()}
        except FileNotFoundError:
            present = {}
        return next((present[n.lower()] for n in self.names(bdate) if n.lower() in present),
                    folder / self.name(bdate))

    def any_date_regex(self) -> "re.Pattern":
        """Same name with any date: spots a file the user downloaded for the wrong day."""
        parts = [re.escape(lit) + (r"\d{6,8}" if field is not None else "")
                 for lit, field, _, _ in string.Formatter().parse(self.pattern)]
        return re.compile("".join(parts) + "$", re.I)


_NSE_EXT = "NSE extranet (connect2nse) › "
_BSE_EXT = "BSE member extranet › "
_MCX_SFTP = "MCX SFTP (sftp.mcxindia.com) › "

_BHAV_ABOUT = "Previous business day's {ex} {seg} bhavcopy (UDiFF format): open, high, low, close, last and previous close price, volume, turnover and open interest per instrument."
_BHAV_FEEDS = "open / high / low / close / last / previous_close / underlying price, total_traded_volume, total_traded_value, open_interest"

INPUTS: List[InputFile] = [
    InputFile("nse_security", "NSE", "security.gz", ("nse_cm",), True,
              "CM security master", _NSE_EXT + "CM › /ntneat/security.gz", ("security.txt",),
              about="NSE capital-market security master (NEAT CM format, pipe-separated; compressed .gz or the "
                    "uncompressed security.txt). One row per security: token, symbol, series, board lot, tick size, "
                    "price band, trading status and eligibility, face value and issued capital.",
              feeds="token, symbol, instrument_type (series), contract_name, lot_size, tick_size, high_dpr / low_dpr "
                    "(price band), is_tradeable, face_value"),
    InputFile("nse_cm_stream", "NSE", "cm_contract_stream_info.csv", ("nse_cm",), True,
              "CM stream info", _NSE_EXT + "CM › /tbt_masters/cm_contract_stream_info.csv",
              about="Tick-by-tick stream map for the cash market: which market-data stream carries each token. "
                    "Only securities listed here end up in the master.",
              feeds="stream_id — and it decides which securities are included"),
    InputFile("nse_qty_freeze", "NSE", "qty_freeze_{prev:%d%m%Y}.csv", ("nse_cm",), True,
              "CM quantity freeze", _NSE_EXT + "CM › /ntneat/ (previous business day's file)",
              about="Maximum quantity allowed in a single order, per symbol and series, published for the previous "
                    "business day.",
              feeds="freeze_quantity (a symbol not in the file gets its highest freeze quantity, else freeze % × "
                    "issued capital ÷ face value)"),
    InputFile("nse_cm_bhav", "NSE", "BhavCopy_NSE_CM_0_0_0_{prev:%Y%m%d}_F_0000.csv", ("nse_cm",), False,
              "CM bhavcopy (prices)", "nseindia.com › All Reports › Equities › CM UDiFF Common Bhavcopy (.zip is fine)",
              about=_BHAV_ABOUT.format(ex="NSE", seg="equity"), feeds=_BHAV_FEEDS + ", isin"),
    InputFile("nse_contract", "NSE", "contract.gz", ("nse_fo",), True,
              "FO contract master", _NSE_EXT + "FO › /contract.gz", ("contract.txt",),
              about="NSE F&O contract master (NEAT FO format; compressed .gz or the uncompressed contract.txt): every "
                    "future and option with underlying, expiry, lot size, tick size, freeze quantity and price range.",
              feeds="token, equity_token, symbol, instrument_type, contract_name, expiry_epoch / expiry_date / "
                    "days_to_expiry / expiry_cycle, lot_size, tick_size, freeze_quantity, high_dpr / low_dpr"),
    InputFile("nse_fo_stream", "NSE", "fo_contract_stream_info.csv", ("nse_fo",), True,
              "FO stream info", _NSE_EXT + "FO › /tbt_masters/fo_contract_stream_info.csv",
              about="Tick-by-tick stream map for F&O, with each contract's option type and strike. Only contracts "
                    "listed here end up in the master.",
              feeds="stream_id, option_type, strike_price — and it decides which contracts are included"),
    InputFile("nse_fo_bhav", "NSE", "BhavCopy_NSE_FO_0_0_0_{prev:%Y%m%d}_F_0000.csv", ("nse_fo",), False,
              "FO bhavcopy (prices)", "nseindia.com › All Reports › Derivatives › F&O UDiFF Common Bhavcopy (.zip is fine)",
              about=_BHAV_ABOUT.format(ex="NSE", seg="F&O"), feeds=_BHAV_FEEDS),

    InputFile("bse_eq_scrip", "BSE", "BSE_EQ_SCRIP_{prev:%d%m%Y}.csv", ("bse_cm",), True,
              "EQ scrip master", _BSE_EXT + "EQ › COMMON › month › day › Check All › Download (zip is fine)",
              about="BSE equity scrip master for the previous business day: scrip code, ticker, security type, board "
                    "lot, tick size, face value, ISIN and product id.",
              feeds="token, symbol, instrument_type, contract_name, lot_size, tick_size, stream_id / "
                    "market_segment_id, isin, face_value"),
    InputFile("bse_cm_dp", "BSE", "DP{bdate:%d%m%y}", ("bse_cm",), False,
              "EQ price bands (circuits)", _BSE_EXT + "EQ › COMMON (inside SCRIP_BSE.zip)",
              about="Daily price bands (circuit limits) for equities. Unlike the other files it carries the business "
                    "date itself, not the previous day.",
              feeds="high_dpr / low_dpr (upper / lower circuit price)"),
    InputFile("bse_cm_bhav", "BSE", "BhavCopy_BSE_CM_0_0_0_{prev:%Y%m%d}_F_0000.csv", ("bse_cm",), False,
              "EQ bhavcopy (prices)", _BSE_EXT + "EQ › COMMON",
              about=_BHAV_ABOUT.format(ex="BSE", seg="equity"), feeds=_BHAV_FEEDS),
    InputFile("bse_eqd_contract", "BSE", "BSE_EQD_CONTRACT_{prev:%d%m%Y}.csv", ("bse_fo",), True,
              "FO contract master", _BSE_EXT + "FNO › COMMON › month › day › Check All › Download (zip is fine)",
              about="BSE equity-derivatives contract master for the previous business day: every future and option "
                    "with underlying, expiry, strike, lot size, tick size and maximum order quantity.",
              feeds="token, equity_token, symbol, instrument_type, option_type, strike_price, contract_name, expiry_*, "
                    "lot_size, tick_size, freeze_quantity, stream_id, market_segment_id, asset_code"),
    InputFile("bse_eqd_dp", "BSE", "EQD_DP{prev:%d%m%y}", ("bse_fo",), True,
              "FO price bands (circuits)", _BSE_EXT + "FNO › COMMON (inside CO_BSE.zip)",
              about="Daily price bands (circuit limits) for derivatives, previous business day.",
              feeds="high_dpr / low_dpr (upper / lower circuit price)"),
    InputFile("bse_fo_bhav", "BSE", "BhavCopy_BSE_FO_0_0_0_{prev:%Y%m%d}_F_0000.csv", ("bse_fo",), False,
              "FO bhavcopy (prices)", _BSE_EXT + "FNO › COMMON",
              about=_BHAV_ABOUT.format(ex="BSE", seg="derivatives"), feeds=_BHAV_FEEDS),

    InputFile("mcx_scrips", "MCX", "MCXScrips.bcp", ("mcx_fo",), True,
              "Contract master", _MCX_SFTP + "/Common/Contract Master/CTCLContractMaster/MCXScrips.bcp",
              about="MCX CTCL contract master: every commodity future and option with underlying, expiry, strike, lot "
                    "size, tick size, daily price range and maximum order size.",
              feeds="token, equity_token, symbol, instrument_type, option_type, strike_price, contract_name, expiry_*, "
                    "lot_size, tick_size, freeze_quantity, stream_id, market_segment_id, high_dpr / low_dpr"),
    InputFile("mcx_bhav", "MCX", "Bhavcopy_MCX_CO_0_0_0_{prev:%Y%m%d}_F_0000.csv", ("mcx_fo",), False,
              "Bhavcopy (prices)", _MCX_SFTP + "/Common/",
              about=_BHAV_ABOUT.format(ex="MCX", seg="commodity"), feeds=_BHAV_FEEDS),
]
BY_KEY: Dict[str, InputFile] = {f.key: f for f in INPUTS}


def pattern_text(f: InputFile) -> str:
    """'qty_freeze_{prev:%d%m%Y}.csv' -> 'qty_freeze_<prev DDMMYYYY>.csv' for people."""
    out = ""
    for lit, field, spec, _ in string.Formatter().parse(f.pattern):
        out += lit
        if field is not None:
            fmt = spec.replace("%d", "DD").replace("%m", "MM").replace("%Y", "YYYY").replace("%y", "YY")
            out += f"<{'prev ' if field == 'prev' else ''}{fmt}>"
    return out


def input_dir(exchange: str, bdate: str) -> Path:
    storage = get_storage_config(exchange)
    template = storage.get("input_dir") or f"{storage.get('base_path', '')}/{exchange.lower()}/source/{{bdate}}/"
    return Path(template.format(bdate=bdate))


def input_path(key: str, bdate: str) -> Path:
    return BY_KEY[key].path(bdate)


def for_step(step_key: str) -> List[InputFile]:
    return [f for f in INPUTS if step_key in f.steps]


def missing(step_key: str, bdate: str, required_only: bool = True) -> List[InputFile]:
    return [f for f in for_step(step_key) if (f.required or not required_only) and not f.path(bdate).is_file()]


# ---------------------------------------------------------------------------
# Importer: files / folders / zips the user downloaded -> the right input folder
# ---------------------------------------------------------------------------

def _copy(opener, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    with opener() as src, open(tmp, "wb") as dst:
        shutil.copyfileobj(src, dst)
    os.replace(tmp, target)  # a build running right now never sees half a file


def import_files(sources: Iterable, bdate: str) -> dict:
    """Copy every recognised input for bdate found in sources (files, folders, .zip incl. nested, .gz).

    Returns {"imported": [(InputFile, origin)], "wrong_date": [(name, InputFile)], "ignored": [name]}.
    """
    wanted = {n.lower(): (f, n) for f in INPUTS for n in f.names(bdate)}
    report = {"imported": [], "wrong_date": [], "ignored": []}
    seen = set()

    def take(name: str, origin: str, opener, depth: int = 0) -> None:
        """opener() returns a fresh binary file object (zip members stream, nothing is loaded whole)."""
        base = name.replace("\\", "/").rsplit("/", 1)[-1]
        low = base.lower()
        if low in wanted:
            f, spec_name = wanted[low]
            if f.key not in seen:
                while f.path(bdate).is_file():  # replace, never keep two versions under different names
                    f.path(bdate).unlink()
                _copy(opener, input_dir(f.exchange, bdate) / spec_name)
                seen.add(f.key)
                report["imported"].append((f, origin))
        elif low.endswith(".zip") and depth < 4:
            try:
                with opener() as fh, zipfile.ZipFile(fh) as z:
                    for m in z.infolist():
                        if not m.is_dir():
                            take(m.filename, f"{origin} › {m.filename}", lambda m=m: z.open(m), depth + 1)
            except zipfile.BadZipFile:
                report["ignored"].append(f"{base} (damaged or incomplete zip)")
        elif low.endswith(".gz") and low[:-3] in wanted:
            take(base[:-3], origin, lambda: gzip.GzipFile(fileobj=opener()), depth + 1)
        else:
            other = next((f for f in INPUTS if f.any_date_regex().match(base)), None)
            if other and "{" in other.pattern:
                report["wrong_date"].append((base, other))
            elif depth == 0:
                report["ignored"].append(base)

    files = []
    for src in map(Path, sources):
        files += sorted(p for p in src.rglob("*") if p.is_file()) if src.is_dir() else [src]
    # Loose files first: a file the user extracted beats an (often older) copy inside an archive.
    for p in sorted(files, key=lambda p: p.suffix.lower() in (".zip", ".gz")):
        if p.suffix in (".part", ".crdownload", ".tmp"):
            report["ignored"].append(f"{p.name} (download not finished)")
            continue
        take(p.name, p.name, lambda p=p: open(p, "rb"))
    return report


if __name__ == "__main__":
    import tempfile

    from core.config import load_config

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["BASE_PATH"] = tmp
        load_config(reload=True)
        bd = "20261005"  # Monday; Fri 02 Oct is a holiday, so prev business day = Thu 01 Oct
        assert BY_KEY["nse_qty_freeze"].name(bd) == "qty_freeze_01102026.csv"
        assert BY_KEY["bse_eqd_dp"].name(bd) == "EQD_DP011026"
        assert BY_KEY["bse_cm_dp"].name(bd) == "DP051026"
        assert input_path("mcx_scrips", bd) == Path(tmp) / "mcx/source/20261005/MCXScrips.bcp"
        assert pattern_text(BY_KEY["nse_qty_freeze"]) == "qty_freeze_<prev DDMMYYYY>.csv"
        assert pattern_text(BY_KEY["bse_cm_dp"]) == "DP<DDMMYY>"
        assert all(f.about and f.feeds for f in INPUTS)

        drop = Path(tmp) / "Downloads"
        drop.mkdir()
        (drop / "security.gz").write_bytes(b"sec")
        (drop / "notes.txt").write_text("x")
        (drop / "qty_freeze_30092026.csv").write_text("old")  # wrong date
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("EQD_DP011026", "dp")
        with zipfile.ZipFile(drop / "rename.zip", "w") as z:  # BSE style: zip inside zip
            z.writestr("CO_BSE.zip", inner.getvalue())
            z.writestr("junk.csv", "j")
        (drop / "MCXScrips.bcp.gz").write_bytes(gzip.compress(b"mcx"))
        (drop / "half.zip.crdownload").write_bytes(b"")
        (drop / "sub").mkdir()
        (drop / "sub" / "EQD_DP011026").write_text("loose")  # sorts after rename.zip, must still win

        (drop / "contract.txt").write_text("NEATFO")  # uncompressed alias of contract.gz
        (drop / "BhavCopy_NSE_FO_0_0_0_20261001_F_0000.CSV").write_text("bhav")  # upper-case extension
        r = import_files([drop], bd)
        got = sorted(f.key for f, _ in r["imported"])
        assert got == ["bse_eqd_dp", "mcx_scrips", "nse_contract", "nse_fo_bhav", "nse_security"], got
        assert input_path("nse_contract", bd).name == "contract.txt"
        assert input_path("nse_fo_bhav", bd).name == "BhavCopy_NSE_FO_0_0_0_20261001_F_0000.csv"
        input_path("nse_fo_bhav", bd).rename(input_path("nse_fo_bhav", bd).with_suffix(".CSV"))  # manual copy
        assert input_path("nse_fo_bhav", bd).suffix == ".CSV", "lookup must ignore letter case"
        assert input_path("bse_eqd_dp", bd).read_text() == "loose"
        assert input_path("mcx_scrips", bd).read_text() == "mcx"
        assert [n for n, _ in r["wrong_date"]] == ["qty_freeze_30092026.csv"]
        assert "notes.txt" in r["ignored"] and any("crdownload" in i for i in r["ignored"])
        assert [f.key for f in missing("nse_cm", bd)] == ["nse_cm_stream", "nse_qty_freeze"]
        assert missing("bse_fo", bd)[0].key == "bse_eqd_contract"
    print("inputs self-check OK")
