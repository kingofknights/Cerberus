#!/usr/bin/env python3
"""
Phoenix Trading Platform - Contract Master Database Ingestion Utility.

Updates exchange-wise contract master CSV files (NSE CM/FO, BSE CM/FO, MCX FO)
into the PostgreSQL `contracts` table using high-throughput batched upserts
(ON CONFLICT DO UPDATE).
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from prettytable import PrettyTable

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from db.schema import metadata, contracts
from core.config import get_base_path, load_config, get_config, find_default_config_path


def get_default_db_url(cfg: Optional[Dict[str, Any]] = None) -> str:
    """Resolve database URL from environment, loaded configuration, or defaults."""
    env_url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("PG_CONN_STR")
    )
    if env_url:
        return env_url

    if cfg:
        cfg_db_url = cfg.get("database", {}).get("url") or cfg.get("database", {}).get("db_url")
        if cfg_db_url:
            return cfg_db_url

    return "postgresql+psycopg://postgres:postgres@localhost:5432/phoenix"


def find_latest_available_date(base_dir: Path) -> str:
    """Find the most recent available date folder in common storage."""
    found_dates = set()
    for exch in ["nse", "bse", "mcx"]:
        common_p = base_dir / exch / "common"
        if common_p.is_dir():
            for child in common_p.iterdir():
                if child.is_dir() and child.name.isdigit() and len(child.name) == 8:
                    if any(child.glob("*.csv")):
                        found_dates.add(child.name)
    if found_dates:
        return sorted(found_dates)[-1]
    return datetime.now().strftime("%Y%m%d")


def resolve_contract_files(
    exchange: str = "all",
    segment: str = "all",
    bdate: Optional[str] = None,
    custom_file: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Locate contract master CSV files based on exchange, segment, and trade date.
    """
    base_dir = Path(get_base_path())

    if custom_file:
        p = Path(custom_file).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Specified contract file not found: {p}")
        return [{
            "exchange": "CUSTOM",
            "segment": "CUSTOM",
            "bdate": bdate or datetime.now().strftime("%Y%m%d"),
            "filepath": p,
        }]

    if bdate:
        target_bdate = bdate.strip()
    else:
        # Check today's date first, fallback to latest available date in storage
        today_str = datetime.now().strftime("%Y%m%d")
        today_has_files = any((base_dir / exch / "common" / today_str).is_dir() for exch in ["nse", "bse", "mcx"])
        target_bdate = today_str if today_has_files else find_latest_available_date(base_dir)

    exchange = exchange.lower().strip()
    segment = segment.lower().strip()

    targets = []

    # Mapping of (exchange, segment) to expected master file path
    exchange_segment_map = [
        ("NSE", "CM", base_dir / f"nse/common/{target_bdate}/nse_cm_contract_master.csv"),
        ("NSE", "FO", base_dir / f"nse/common/{target_bdate}/nse_fo_contract_master.csv"),
        ("BSE", "CM", base_dir / f"bse/common/{target_bdate}/bse_cm_contract_master.csv"),
        ("BSE", "FO", base_dir / f"bse/common/{target_bdate}/bse_fo_contract_master.csv"),
        ("MCX", "FO", base_dir / f"mcx/common/{target_bdate}/mcx_fo_contract_master.csv"),
    ]

    for exch_code, seg_code, path in exchange_segment_map:
        if exchange not in ("all", exch_code.lower()):
            continue
        if segment not in ("all", seg_code.lower()):
            continue

        targets.append({
            "exchange": exch_code,
            "segment": seg_code,
            "bdate": target_bdate,
            "filepath": path,
        })

    return targets


def sanitize_dataframe(df: pd.DataFrame, target_bdate: str) -> pd.DataFrame:
    """
    Sanitize and type-cast dataframe records to match the PostgreSQL `contracts` schema.
    """
    clean_df = pd.DataFrame(index=df.index)

    def _col_str(name: str, default: str = "") -> pd.Series:
        if name in df.columns:
            s = df[name].fillna(default).astype(str).str.strip()
            return s.replace({"nan": default, "None": default, "NaN": default, "NAT": default, "NaT": default})
        return pd.Series(default, index=df.index, dtype=str)

    def _col_int(name: str, default: int = 0) -> pd.Series:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").fillna(default).astype("int64")
        return pd.Series(default, index=df.index, dtype="int64")

    # Core Identifiers
    clean_df["trade_date"] = _col_str("trade_date", target_bdate)
    clean_df["trade_date"] = clean_df["trade_date"].replace({"": target_bdate, "nan": target_bdate, "None": target_bdate})
    clean_df["sutra_symbol"] = _col_str("sutra_symbol", "")
    clean_df["sutra_token"] = _col_int("sutra_token", 0)
    clean_df["token"] = _col_int("token", 0)
    clean_df["future_token"] = _col_int("future_token", 0)
    clean_df["equity_token"] = _col_int("equity_token", 0)
    clean_df["exchange"] = _col_str("exchange", "").str.upper()
    clean_df["segment"] = _col_str("segment", "").str.upper()
    clean_df["symbol"] = _col_str("symbol", "")
    clean_df["contract_name"] = _col_str("contract_name", "")

    # Instrument Details
    clean_df["instrument_type"] = _col_str("instrument_type", "")
    clean_df["option_type"] = _col_str("option_type", "XX")
    clean_df["option_type"] = clean_df["option_type"].replace({"": "XX"})
    clean_df["strike_price"] = _col_int("strike_price", 0)

    # Expiry
    clean_df["expiry_epoch"] = _col_int("expiry_epoch", -1)
    clean_df["expiry_date"] = _col_str("expiry_date", "")
    clean_df["days_to_expiry"] = _col_int("days_to_expiry", 0)
    clean_df["expiry_cycle"] = _col_str("expiry_cycle", "NA")
    clean_df["expiry_cycle"] = clean_df["expiry_cycle"].replace({"": "NA"})

    # Stream & Segment
    clean_df["stream_id"] = _col_int("stream_id", 0)
    clean_df["market_segment_id"] = _col_int("market_segment_id", 0)

    # Trading Parameters
    clean_df["freeze_quantity"] = _col_int("freeze_quantity", np.iinfo(np.int64).max)
    clean_df["lot_size"] = _col_int("lot_size", 1)
    clean_df["divisor"] = _col_int("divisor", 100)
    clean_df["tick_size"] = _col_int("tick_size", 5)

    # Prices & DPR
    clean_df["open_price"] = _col_int("open_price", 0)
    clean_df["high_price"] = _col_int("high_price", 0)
    clean_df["low_price"] = _col_int("low_price", 0)
    clean_df["close_price"] = _col_int("close_price", 0)
    clean_df["last_price"] = _col_int("last_price", 0)
    clean_df["previous_close_price"] = _col_int("previous_close_price", 0)
    clean_df["underlying_price"] = _col_int("underlying_price", 0)
    clean_df["total_traded_volume"] = _col_int("total_traded_volume", 0)
    clean_df["total_traded_value"] = _col_int("total_traded_value", 0)
    clean_df["high_dpr"] = _col_int("high_dpr", 0)
    clean_df["low_dpr"] = _col_int("low_dpr", 0)
    clean_df["open_interest"] = _col_int("open_interest", 0)

    # Flags & Identifiers
    clean_df["is_tradeable"] = _col_str("is_tradeable", "Y")
    clean_df["is_tradeable"] = clean_df["is_tradeable"].replace({"": "Y"})
    clean_df["is_banned"] = _col_str("is_banned", "N")
    clean_df["is_banned"] = clean_df["is_banned"].replace({"": "N"})
    clean_df["currency"] = _col_str("currency", "INR")
    clean_df["currency"] = clean_df["currency"].replace({"": "INR"})
    clean_df["timezone"] = _col_str("timezone", "Asia/Kolkata")
    clean_df["timezone"] = clean_df["timezone"].replace({"": "Asia/Kolkata"})
    clean_df["trading_schedule"] = _col_str("trading_schedule", "")
    clean_df["isin"] = _col_str("isin", "")
    clean_df["face_value"] = _col_int("face_value", 0)
    clean_df["asset_code"] = _col_str("asset_code", "")

    # Deduplicate in-memory to prevent PG ON CONFLICT multiple match error
    clean_df.drop_duplicates(
        subset=["trade_date", "exchange", "segment", "token"],
        keep="last",
        inplace=True,
    )

    return clean_df


def upsert_contracts_to_db(
    engine,
    df: pd.DataFrame,
    target_bdate: str,
    chunk_size: int = 1000,
) -> int:
    """
    Perform high-performance batch upsert into the PostgreSQL `contracts` table.
    Ensures parameter count does not exceed PostgreSQL's 65,535 parameter limit.
    """
    sanitized_df = sanitize_dataframe(df, target_bdate)
    records = sanitized_df.to_dict(orient="records")
    total_records = len(records)
    if total_records == 0:
        return 0

    # Fields to update on conflict (all except the unique constraint keys and synthetic id)
    update_cols = {
        col.name: col
        for col in contracts.columns
        if col.name not in ("id", "trade_date", "exchange", "segment", "token", "created_at")
    }
    update_cols["updated_at"] = func.now()

    # PostgreSQL prepared statement parameter limit is 65535.
    # Calculate safe chunk size based on number of columns per row.
    num_cols = len(records[0]) if records else 1
    max_safe_chunk = max(1, 65535 // max(num_cols, 1))
    batch_size = min(chunk_size, max_safe_chunk) if chunk_size and chunk_size > 0 else max_safe_chunk

    inserted_count = 0
    with engine.begin() as conn:
        for i in range(0, total_records, batch_size):
            batch = records[i : i + batch_size]
            stmt = pg_insert(contracts).values(batch)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["trade_date", "exchange", "segment", "token"],
                set_={col_name: getattr(stmt.excluded, col_name) for col_name in update_cols if col_name != "updated_at"}
                | {"updated_at": func.now()},
            )
            conn.execute(upsert_stmt)
            inserted_count += len(batch)

    return inserted_count


def process_contract_ingestion(
    exchange: Optional[str] = None,
    segment: Optional[str] = None,
    bdate: Optional[str] = None,
    custom_file: Optional[str] = None,
    config_path: Optional[str] = None,
    db_url: Optional[str] = None,
    chunk_size: Optional[int] = None,
    dry_run: bool = False,
    create_tables: Optional[bool] = None,
) -> bool:
    """
    Main entrypoint for reading, validating, and updating contract master files into PostgreSQL.
    """
    cfg = load_config(config_path, reload=True) if config_path else get_config()
    url = db_url or get_default_db_url(cfg)

    effective_exchange = (exchange or cfg.get("ingestion", {}).get("default_exchange", "all")).lower().strip()
    effective_segment = (segment or cfg.get("ingestion", {}).get("default_segment", "all")).lower().strip()
    effective_chunk_size = chunk_size or cfg.get("database", {}).get("chunk_size", 1000)
    effective_create_tables = create_tables if create_tables is not None else cfg.get("database", {}).get("create_tables", True)

    targets = resolve_contract_files(effective_exchange, effective_segment, bdate, custom_file)

    if not targets:
        print("❌ No matching contract master targets found.")
        return False

    print("=" * 80)
    print(" 🦅 Phoenix Trading Platform - Contract Master Database Ingestion")
    print("=" * 80)
    print(f" Target Exchange : {effective_exchange.upper()}")
    print(f" Target Segment  : {effective_segment.upper()}")
    print(f" Business Date   : {bdate or 'Latest / Auto'}")
    print(f" Config Path     : {config_path or find_default_config_path()}")
    print(f" Database URL    : {url.split('@')[-1] if '@' in url else url}")
    print(f" Chunk Size      : {effective_chunk_size}")
    print(f" Dry Run Mode    : {'ENABLED (No DB writes)' if dry_run else 'DISABLED (Live DB write)'}")
    print("=" * 80)

    engine = None
    if not dry_run:
        try:
            engine = create_engine(url, pool_pre_ping=True)
            if effective_create_tables:
                metadata.create_all(engine)
                print("✓ Verified database tables and indexes exist.")
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False

    summary_table = PrettyTable()
    summary_table.field_names = [
        "Exchange",
        "Segment",
        "Trade Date",
        "Records",
        "Status",
        "Duration",
    ]

    all_success = True

    for target in targets:
        exch = target["exchange"]
        seg = target["segment"]
        t_bdate = target["bdate"]
        fpath = target["filepath"]

        start_time = time.time()

        if not fpath.is_file():
            print(f"\n⚠️  Contract file not found: {fpath}")
            summary_table.add_row([exch, seg, t_bdate, 0, "FILE NOT FOUND", "0.00s"])
            all_success = False
            continue

        print(f"\n>>> Processing {exch} {seg} ({t_bdate}) from {fpath.name}...")

        try:
            df = pd.read_csv(fpath)
            record_count = len(df)
            print(f"    Read {record_count:,} contracts from file.")

            if dry_run:
                sanitized = sanitize_dataframe(df, t_bdate)
                duration = time.time() - start_time
                print(f"    ✓ [DRY RUN] Validated {len(sanitized):,} records cleanly.")
                summary_table.add_row([exch, seg, t_bdate, f"{record_count:,}", "VALIDATED", f"{duration:.2f}s"])
            else:
                upserted = upsert_contracts_to_db(engine, df, t_bdate, chunk_size=effective_chunk_size)
                duration = time.time() - start_time
                print(f"    ✓ Successfully upserted {upserted:,} records to DB in {duration:.2f}s.")
                summary_table.add_row([exch, seg, t_bdate, f"{upserted:,}", "UPSERTED", f"{duration:.2f}s"])

        except Exception as e:
            duration = time.time() - start_time
            print(f"    ❌ Ingestion failed: {e}")
            summary_table.add_row([exch, seg, t_bdate, 0, f"FAILED: {e}", f"{duration:.2f}s"])
            all_success = False

    print("\n" + "=" * 80)
    print(" INGESTION SUMMARY")
    print("=" * 80)
    print(summary_table)
    print("=" * 80)

    return all_success


HELP_EPILOG = """
Examples:
  # 1. Ingest all exchanges and segments for today (or latest available date):
  $ contract_uploader

  # 2. Ingest NSE segment files only:
  $ contract_uploader -e nse

  # 3. Ingest NSE FO segment only for a specific trade date:
  $ contract_uploader -e nse -s fo -d 20260828

  # 4. Ingest a specific contract master CSV directly:
  $ contract_uploader -f /path/to/nse_cm_contract_master.csv

  # 5. Ingest using custom config JSON file:
  $ contract_uploader -c /path/to/custom_config.json

  # 6. Dry run validation without writing to database:
  $ contract_uploader --dry-run

  # 7. Specify custom database connection string:
  $ contract_uploader --db-url "postgresql+psycopg://user:password@127.0.0.1:5432/phoenix"

Cron Scheduling Example:
  # Run contract ingestion every weekday at 06:30 AM IST after download finishes:
  30 6 * * 1-5 /path/to/contract_uploader -e all >> /var/log/phoenix/uploader.log 2>&1
"""


def main():
    parser = argparse.ArgumentParser(
        prog="contract_uploader",
        description="🦅 Phoenix Trading Platform - Contract Master Database Ingestion.\n"
                    "Ingests unified Contract Master CSV files into PostgreSQL with high-performance "
                    "batched upserts (ON CONFLICT DO UPDATE) and composite trade date indexing.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-e",
        "--exchange",
        choices=["nse", "bse", "mcx", "all"],
        default=None,
        help="Target exchange to ingest (default: all or from config)",
    )
    parser.add_argument(
        "-s",
        "--segment",
        choices=["cm", "fo", "all"],
        default=None,
        help="Target market segment to ingest (default: all or from config)",
    )
    parser.add_argument(
        "-d",
        "--bdate",
        type=str,
        default=None,
        help="Business trade date in YYYYMMDD format (default: today with auto latest fallback)",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=str,
        default=None,
        help="Direct path to a specific contract master CSV file",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to custom config JSON file or directory",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="PostgreSQL connection string (defaults to DATABASE_URL env or config file)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Batch size for database upserts (default: 1000 records per transaction or from config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CSV structure and record schema without executing database writes",
    )
    parser.add_argument(
        "--no-create-tables",
        action="store_false",
        dest="create_tables",
        default=None,
        help="Skip automatic table and index creation check",
    )

    args = parser.parse_args()

    success = process_contract_ingestion(
        exchange=args.exchange,
        segment=args.segment,
        bdate=args.bdate,
        custom_file=args.file,
        config_path=args.config,
        db_url=args.db_url,
        chunk_size=args.chunk_size,
        dry_run=args.dry_run,
        create_tables=args.create_tables,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
