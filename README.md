# Phoenix Contract Masters

[![CI](https://github.com/kingofknights/Cerberus/actions/workflows/ci.yml/badge.svg)](https://github.com/kingofknights/Cerberus/actions/workflows/ci.yml)

Builds standardized 52-column contract master CSVs for **NSE**, **BSE** and **MCX** (CM and FO) from the
exchange reference files, ready for the Phoenix trading engines and the PostgreSQL `contracts` table.

The exchange files are **downloaded by hand** (extranet / SFTP / website). The app tells you exactly which
files it needs for a date, files them into the right folder for you, and builds the masters.

```mermaid
flowchart LR
    DL["You download<br/>exchange files"] --> ADD["Add files<br/>(zips OK)"]
    ADD --> IN["data/&lt;exch&gt;/source/&lt;date&gt;/"]
    IN --> BUILD["Build"]
    BUILD --> OUT["data/&lt;exch&gt;/common/&lt;date&gt;/*_contract_master.csv"]
    OUT --> DB[("PostgreSQL")]
```

---

## Install

| Where | How |
| :--- | :--- |
| **Windows** | Python 3.10+ from python.org, then right-click `install\windows.ps1` → *Run with PowerShell*. Creates `.venv` and Desktop + Start-menu shortcuts. |
| **Linux** | `./install/linux.sh` — creates `.venv` and an application-menu entry. |
| **WSL** (app shown on the Windows desktop) | `pip install --user -r requirements.txt`, then `./install/wsl-shortcut.sh` for a Windows Desktop + Start-menu shortcut (no console window). |
| **Anywhere, no install** | `pip install -r requirements.txt && python3 -m gui` (or `./run_gui.sh`). |

Packaged releases (zip for Windows, tar.gz for Linux) are on the GitHub Releases page.

## Quick start

1. **Build** → pick the business date (the day the masters are *for*). The header shows the previous
   business day, which is the date most exchange files carry.
2. Download the files in the checklist as usual. Click a file to see where to get it.
3. Click **Import from Downloads** (`Ctrl+I`): your Windows Downloads folder is searched — subfolders,
   zips, zips inside zips, `.gz`, `security.txt`/`contract.txt`, upper-case `.CSV` — and only the files
   this date needs are copied into place. Files for the wrong date are pointed out.
   Or switch on **Auto-import new downloads**: every needed file you download from then on is filed by
   itself. Choose files / Choose folder / a pasted folder path (`C:\...` works) and dropping files onto the
   window work too, and so does copying into the folder by hand — the page refreshes every 2 seconds.
4. When a master card shows **Ready**, press **Build** (`Ctrl+R`). Masters with missing files are left
   out and listed; the rest are built, with contract counts and plain-language errors.
5. Click a result to open it in **Masters**, then **Upload to database**.

---

## Where files live

Everything is under the **data folder** (`storage.base_path` in `config/common.json`, default `~/EOD/`;
change it from the header of the GUI).

```text
<data folder>/
├── nse/source/20261012/     ← input files for business date 12 Oct 2026 (one flat folder)
├── nse/common/20261012/     ← nse_cm_contract_master.csv, nse_fo_contract_master.csv
├── bse/source/20261012/  bse/common/20261012/
└── mcx/source/20261012/  mcx/common/20261012/
```

## Database credentials

Secrets never go in the committed config. Put machine-local settings in `config/local.json` (git-ignored);
it is merged over `common.json`:

```json
{ "database": { "url": "postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME" } }
```

The `DATABASE_URL` environment variable, or the URL typed on the Database page, takes precedence.

## Input files

`{prev}` = previous business day of the business date (holiday calendar aware). Defined once in
[`core/inputs.py`](core/inputs.py); the parsers, the GUI checklist, the importer and the CLI pre-check all
read that list.

| Exchange | Master | File | Needed |
| :--- | :--- | :--- | :--- |
| NSE | CM | `security.gz` (or `security.txt`) | required |
| NSE | CM | `cm_contract_stream_info.csv` | required |
| NSE | CM | `qty_freeze_{prev:DDMMYYYY}.csv` | required |
| NSE | CM | `BhavCopy_NSE_CM_0_0_0_{prev:YYYYMMDD}_F_0000.csv` | optional (prices) |
| NSE | FO | `contract.gz` (or `contract.txt`) | required |
| NSE | FO | `fo_contract_stream_info.csv` | required |
| NSE | FO | `BhavCopy_NSE_FO_0_0_0_{prev:YYYYMMDD}_F_0000.csv` | optional (prices) |
| BSE | CM | `BSE_EQ_SCRIP_{prev:DDMMYYYY}.csv` | required |
| BSE | CM | `DP{bdate:DDMMYY}` | optional (circuits) |
| BSE | CM | `BhavCopy_BSE_CM_0_0_0_{prev:YYYYMMDD}_F_0000.csv` | optional (prices) |
| BSE | FO | `BSE_EQD_CONTRACT_{prev:DDMMYYYY}.csv` | required |
| BSE | FO | `EQD_DP{prev:DDMMYY}` | required |
| BSE | FO | `BhavCopy_BSE_FO_0_0_0_{prev:YYYYMMDD}_F_0000.csv` | optional (prices) |
| MCX | FO | `MCXScrips.bcp` | required |
| MCX | FO | `Bhavcopy_MCX_CO_0_0_0_{prev:YYYYMMDD}_F_0000.csv` | optional (prices) |

Without an optional file the master is still built; its prices / open interest / circuit columns are 0.

---

## Desktop app

| Page | What it does |
| :--- | :--- |
| **Build** | Business date with ‹ › business-day stepping · 5 master cards with readiness rings · import from Downloads / auto-import / drop / pick · per-exchange file checklist with download hints · live build progress, contract counts, errors and a filterable log. |
| **Masters** | Every generated master in a fast native table (all rows): search, filter by instrument / option / expiry, sort, row details, export the filtered view, hand off to Database. |
| **Database** | Test the PostgreSQL connection, see rows per trade date, upsert (or validate only). The DB URL is passed via environment and never saved. |
| **History** | Every build / upload / registration with its full log; build a past date again. |
| **Settings** | Data folder, holiday calendars, Prefect schedules + registration, raw config editor (keeps `.bak`). |
| **Help** (`F1`) | Getting started, daily routine, a card for every exchange file (what it is, where to get it, which columns it fills, what happens without it, its exact name for the selected date), dates explained, folders, output columns, troubleshooting, shortcuts, About. |

Shortcuts: `Ctrl+1…6` pages · `F1` help · `Ctrl+I` import from Downloads · `Ctrl+O` choose files · `Ctrl+R` build.
Light / dark theme in the sidebar. Code: `gui/app.py` (UI) over `gui/backend.py` (logic, no Qt).

---

## Command line

```bash
./run_all.sh                                  # every master for today
./run_all.sh -s nse -d 20261012               # NSE CM + FO
./run_all.sh -s nse_cm,bse_fo -d 20261012     # any combination (groups: all, nse, bse, mcx, cm, fo)
./run_all.sh -d 20261001:20261012             # date range (weekends/holidays skipped)
./run_all.sh --dry-run -d 20261012            # plan + list of missing input files
./run_all.sh --no-retry                       # fail fast instead of waiting for files
./run_all.sh --register                       # register Prefect deployments
```

The header lists any missing input files before running. Exit code is non-zero if a master failed.

Checks: `python3 -m core.inputs` (file names, importer), `python3 pipeline.py` (step registry) and
`python3 -m pytest tests` (end-to-end MCX build from a zipped download, desktop app smoke test).

## CI / CD

GitHub Actions (`.github/workflows/`):

- **CI** — every push / pull request: Windows + Linux × Python 3.10 / 3.12 run the self-checks, the CLI,
  the end-to-end build and the headless app test; then both installers are run on fresh Windows and Linux
  machines.
- **Release** — push a tag (`git tag v2.0.0 && git push origin v2.0.0`): the full CI runs, then a GitHub
  Release is published with `…-windows.zip` and `…-linux.tar.gz`.

---

## Contract master schema

Every generated contract master CSV adheres strictly to the standardized schema:

| Column Name | Type | Description / Sample |
| :--- | :--- | :--- |
| `trade_date` | `str` | Business Date (`20260827`) |
| `sutra_symbol` | `str` | Normalized Sutra Symbol (e.g., `NSE_BANKNIFTY_OPT_20260929_M_72600.0_CE`) |
| `sutra_token` | `int` | Unique composite token (`Exchange * 10 + Segment + Token`) |
| `token` | `int` | Exchange native Instrument Token |
| `future_token` | `int` | Token of the corresponding near-month future |
| `equity_token` | `int` | Token of the underlying equity/cash asset |
| `exchange` | `str` | Exchange code: `NSE`, `BSE`, `MCX` |
| `contract_name` | `str` | Human-readable contract description |
| `symbol` | `str` | Underlying symbol / Ticker (e.g., `NIFTY`, `RELIANCE`, `CRUDEOIL`) |
| `segment` | `str` | `CM`, `FO` |
| `instrument_type` | `str` | `OPTSTK`, `OPTIDX`, `FUTSTK`, `FUTIDX`, `EQ`, `COM` |
| `option_type` | `str` | `CE`, `PE`, `XX` |
| `strike_price` | `int` | Strike price in integer paise/cents (divided by divisor for display) |
| `expiry_epoch` | `int` | Expiry timestamp in NSE epoch format (seconds since 1980-01-01) |
| `expiry_date` | `str` | Expiry formatted as `DD MMMM YYYY` (e.g. `27 August 2026`) |
| `days_to_expiry` | `int` | Number of calendar days until expiration |
| `expiry_cycle` | `str` | Expiry cycle bucket: `Monthly`, `Weekly1`, `Weekly2`, `NA` |
| `stream_id` | `int` / `str` | Market data feed Partition / Stream ID |
| `market_segment_id` | `int` / `str` | Product ID / Market Segment code |
| `freeze_quantity` | `int` | Maximum allowable single-order quantity |
| `lot_size` | `int` | Minimum lot size for trading |
| `divisor` | `int` | Price scale divisor (usually `100`) |
| `tick_size` | `int` | Minimum price movement (in paise) |
| `open_price`, `high_price`, `low_price`, `close_price`, `last_price` | `int` | OHLC price data scaled by 100 |
| `previous_close_price`, `underlying_price` | `int` | Prior settlement price and underlying spot price |
| `total_traded_volume`, `total_traded_value` | `int` | Traded volume and turnover |
| `high_dpr`, `low_dpr` | `int` | Upper and Lower Daily Price Ranges (Circuits) |
| `open_interest` | `int` | Total open contracts |
| `is_tradeable`, `is_banned` | `str` | Trading permission flags (`Y`/`N`) |
| `currency`, `timezone`, `trading_schedule` | `str` | `INR`, `Asia/Kolkata`, `09:15:00-15:30:00` |
| `isin`, `face_value`, `asset_code` | `str` / `int` | Regulatory identifiers |

---

## Project layout

```text
config/          common.json (data folder, holidays, DB, Prefect) + nse/bse/mcx.json (folders, schedules)
core/inputs.py   the input-file list, path lookup and importer
core/            config loader, business-day calendar, Prefect helpers
parsers/         read + merge the exchange files per master
flows/           Prefect flows that transform and write each master
db/              PostgreSQL schema + uploader (python -m db.uploader -h)
gui/             desktop app: app.py (Qt UI) + backend.py (logic)
pipeline.py      the 5 masters (single source of truth for CLI + GUI)
run_all.py       CLI
```
