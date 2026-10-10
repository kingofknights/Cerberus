"""End to end on any OS: synthetic MCX exchange files, delivered inside a zip, go through the importer,
then the real CLI builds the master through the Prefect flow, and the output is checked."""

import csv
import io
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parsers.mcx_parser import MCXSCRIPS_COLUMNS  # noqa: E402

BDATE, PREV = "20261012", "20261009"  # Monday; files carry Friday's date
BHAV_COLS = ["TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "XpryDt",
             "FininstrmActlXpryDt", "StrkPric", "OptnTp", "FinInstrmNm", "OpnPric", "HghPric", "LwPric", "ClsPric",
             "LastPric", "PrvsClsgPric", "UndrlygPric", "SttlmPric", "OpnIntrst", "ChngInOpnIntrst", "TtlTradgVol",
             "TtlTrfVal", "TtlNbOfTxsExctd", "SsnId", "NewBrdLotQty", "Rmks", "Rsvd1", "Rsvd2", "Rsvd3", "Rsvd4"]


def noon(y, m, d):  # noon UTC: the same calendar date in every runner time zone
    return int(datetime(y, m, d, 12, tzinfo=timezone.utc).timestamp())


def scrip(token, name, opt, strike, expiry, desc):
    row = dict.fromkeys(MCXSCRIPS_COLUMNS, "0")
    row.update(InstrumentIdentifier=token, Symbol="GOLD", InstrumentName=name, OptionType=opt, StrikePrice=strike,
               OriginalExpiryDate=expiry, InstrumentPartitionID=1, ProductID=1114, MaxSingleTransactionQty=100,
               LotSize=1, TickSize=100, UnderlyingIdentifier=559933, UpperDailyPriceRange=1300000,
               LowerDailyPriceRange=1100000, InstrumentDescription=desc)
    return [row[c] for c in MCXSCRIPS_COLUMNS]


def make_download(folder: Path) -> Path:
    scrips = io.StringIO()
    w = csv.writer(scrips)
    w.writerow(scrip(1001, "FUTCOM", "XX", 0, noon(2026, 12, 31), "GOLD FUT DEC"))
    w.writerow(scrip(1002, "OPTFUT", "CE", 15500000, noon(2026, 12, 28), "GOLD 155000 CE"))
    w.writerow(scrip(1003, "OPTFUT", "PE", 15500000, noon(2026, 12, 28), "GOLD 155000 PE"))
    bhav = io.StringIO()
    w = csv.writer(bhav)
    w.writerow(BHAV_COLS)
    w.writerow({**dict.fromkeys(BHAV_COLS, ""), "FinInstrmId": "1001", "OpnPric": "120000", "HghPric": "121000",
                "LwPric": "119000", "ClsPric": "120500.5", "LastPric": "120500", "OpnIntrst": "42",
                "TtlTradgVol": "7", "TtlTrfVal": "843500"}.values())
    z = folder / "mcx_download.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Common/MCXScrips.bcp", scrips.getvalue())
        zf.writestr(f"Common/Bhavcopy_MCX_CO_0_0_0_{PREV}_F_0000.csv", bhav.getvalue())
    return z


def test_import_and_build(tmp_path):
    env = {**os.environ, "BASE_PATH": str(tmp_path / "data"), "PREFECT_HOME": str(tmp_path / "prefect"),
           "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT)}
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    make_download(downloads)

    # importer (in a child so BASE_PATH is picked up fresh)
    out = subprocess.run([sys.executable, "-c", (
        "from core.inputs import import_files; r = import_files([r'%s'], '%s'); "
        "print(sorted(f.key for f, _ in r['imported']))") % (downloads, BDATE)],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    assert "['mcx_bhav', 'mcx_scrips']" in out.stdout, out.stdout

    run = subprocess.run([sys.executable, str(ROOT / "run_all.py"), "-s", "mcx_fo", "-d", BDATE, "--no-retry"],
                         cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=600)
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]

    master = tmp_path / "data" / "mcx" / "common" / BDATE / "mcx_fo_contract_master.csv"
    rows = {r["token"]: r for r in csv.DictReader(master.open(encoding="utf-8"))}
    assert set(rows) == {"1001", "1002", "1003"}
    fut, ce, pe = rows["1001"], rows["1002"], rows["1003"]
    assert fut["instrument_type"] == "FUTCOM" and fut["expiry_date"] == "31 December 2026"
    assert ce["option_type"] == "CE" and pe["option_type"] == "PE" and ce["strike_price"] == "15500000"
    assert ce["future_token"] == pe["future_token"] == "1001", "options must map to their future"
    assert ce["expiry_date"] == "28 December 2026" and int(ce["days_to_expiry"]) == 77
    assert fut["close_price"] == "12050050" and fut["open_interest"] == "42", "bhavcopy prices merged (x100)"
    assert ce["close_price"] == "0", "no bhavcopy row -> 0"
    assert fut["high_dpr"] == "1300000" and fut["sutra_token"] == "321001"
    assert all(r["trade_date"] == BDATE and r["exchange"] == "MCX" for r in rows.values())
