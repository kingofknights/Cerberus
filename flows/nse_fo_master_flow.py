import os
import click
import numpy as np
import pandas as pd

from datetime import datetime
from prefect import flow, task
from typing import Dict, Optional

from core.prefect_utils import deploy_flow, unified_notifier, task_name_gen, task_retries
from core.dates import convert_nse_epoch_to_datetime, generate_business_dates
from core.enums import Exchange, Segment
from core.config import get_storage_config
from parsers.nse_parser import get_merge_fo_contract_stream_bhavcopy

# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

def build_expiry_cycle_map(df: pd.DataFrame, expiry_col: str = "expiry_date", bdate: Optional[str] = None) -> Dict:
    """Build mapping of expiry dates to cycle codes (W1, W2, M1, M2, etc.)."""
    dates = pd.to_datetime(df[expiry_col], format="%d %B %Y", errors="coerce")
    unique_dates = sorted(dates.dropna().unique())
    
    bdate_ts = pd.to_datetime(bdate, format="%Y%m%d") if bdate else None
    
    grouped = {}
    for d in unique_dates:
        key = (d.year, d.month)
        grouped.setdefault(key, []).append(d)
    
    cycle_map = {}
    week_counter = 1
    month_counter = 1
    
    for month_dates in grouped.values():
        month_dates = sorted(month_dates)
        last_date = month_dates[-1]
        
        for d in month_dates:
            is_today = bdate_ts is not None and d.date() == bdate_ts.date()
            
            if d == last_date:
                cycle_map[d] = "M0" if is_today else f"M{month_counter}"
                if not is_today:
                    month_counter += 1
            else:
                cycle_map[d] = "W0" if is_today else f"W{week_counter}"
                if not is_today:
                    week_counter += 1
    
    return cycle_map


def create_sutra_symbol(exchange: str, symbol: str, segment: str, expiry: Optional[str] = None, 
                          expiry_cycle: Optional[str] = None, strike_price: Optional[str] = None, 
                          option_type: Optional[str] = None) -> str:
    """Create SutraSymbol identifier."""
    parts = [exchange, symbol, segment]
    if expiry:
        parts.append(expiry)
    if expiry_cycle:
        parts.append(expiry_cycle)
    if strike_price:
        parts.append(strike_price)
    if option_type:
        parts.append(option_type)
    return "_".join(map(str, parts))


def build_sutra_symbol_row(row: pd.Series) -> str:
    """Build SutraSymbol for a single row."""
    expiry = (
        datetime.strptime(row["expiry_date"], "%d %B %Y").strftime("%Y%m%d")
        if isinstance(row["expiry_date"], str) and row["expiry_date"] != "NaT"
        else None
    )

    expiry_cycle = (
        row["expiry_cycle"][0]
        if isinstance(row["expiry_cycle"], str) and row["expiry_cycle"]
        else None
    )

    strike_price = (
        float(row["strike_price"])/100
        if pd.notnull(row["strike_price"]) and str(row["strike_price"]).strip() != ""
        else None
    )

    instrument_type = str(row["instrument_type"]).upper()
    option_type = "" if instrument_type.startswith("FUT") else row["option_type"]

    return create_sutra_symbol(
        exchange="NSE",
        symbol=row["symbol"],
        segment=instrument_type[:3],
        expiry=expiry,
        expiry_cycle=expiry_cycle,
        strike_price=strike_price,
        option_type=option_type,
    )


# Backward compatibility aliases
create_mimbol = create_sutra_symbol
build_mimbol_row = build_sutra_symbol_row


def build_expiry_fields(expiry_epoch: pd.Series, bdate: str) -> Dict[str, pd.Series]:
    """Build expiry-related fields."""
    expiry_datetimes = pd.to_datetime(
        expiry_epoch.astype(int).apply(convert_nse_epoch_to_datetime), errors="coerce"
    ) - pd.Timedelta(hours=14, minutes=30)

    expiry_date = expiry_datetimes.dt.strftime("%d %B %Y")
    bdate_dt = datetime.strptime(bdate, "%Y%m%d")
    days_to_expiry = (pd.to_datetime(expiry_date, format="%d %B %Y") - bdate_dt).dt.days
    cycle_map = build_expiry_cycle_map(pd.DataFrame({"expiry_date": expiry_date}), "expiry_date", bdate=bdate)
    expiry_cycle = pd.to_datetime(expiry_date, format="%d %B %Y", errors="coerce").map(cycle_map)

    return {
        "expiry_date": expiry_date,
        "days_to_expiry": days_to_expiry,
        "expiry_cycle": expiry_cycle,
    }


def get_future_token(df: pd.DataFrame) -> pd.Series:
    """
    Vectorized mapping of option tokens to future tokens.

    Handles holiday-shifted expiries:
    Example:
    - Option expiry: 30 April 2025 (1 May holiday)
    - Future expiry: May 2025
    → Correctly maps to May future (nearest >= expiry)
    """

    result = df["token"].copy()

    expiry_date = pd.to_datetime(
        df["expiry_date"], format="%d %B %Y", errors="coerce"
    )

    instrument_map = {"OPTIDX": "FUTIDX", "OPTSTK": "FUTSTK"}

    opt_mask = df["instrument_type"].isin(instrument_map.keys())
    if not opt_mask.any():
        return result.astype(int)

    # Options
    opt_df = df.loc[opt_mask, ["symbol", "instrument_type", "token"]].copy()
    opt_df["expiry_date"] = expiry_date.loc[opt_mask]
    opt_df["target_type"] = opt_df["instrument_type"].map(instrument_map)
    opt_df["orig_index"] = opt_df.index  # ← preserve original index

    fut_df = df.loc[:, ["symbol", "instrument_type", "token"]].copy()
    fut_df["expiry_date"] = expiry_date
    fut_df = fut_df[fut_df["instrument_type"].isin(instrument_map.values())]
    fut_df = fut_df.rename(columns={"token": "future_token"})

    merged = opt_df.merge(
        fut_df,
        left_on=["symbol", "target_type"],
        right_on=["symbol", "instrument_type"],
        how="left",
        suffixes=("_opt", "_fut"),
    )
    # ↑ After merge, index resets to 0,1,2... — group by orig_index instead

    valid = merged[merged["expiry_date_fut"] >= merged["expiry_date_opt"]]
    valid = valid.sort_values("expiry_date_fut")
    nearest = valid.groupby("orig_index").first()  # ← use orig_index

    fallback = (
        merged.sort_values("expiry_date_fut")
        .groupby("orig_index")                     # ← use orig_index
        .first()
    )

    final = nearest["future_token"].combine_first(fallback["future_token"]).fillna(-1)

    result.loc[opt_df["orig_index"]] = final.reindex(opt_df["orig_index"]).astype(int)
    return result.astype(int)


# ========================================================================
# TASKS
# ========================================================================


@task(
    task_run_name=task_name_gen,
    log_prints=True,
    # on_failure=[unified_notifier(notification_type="both")],
    retries=task_retries(6),
    retry_delay_seconds=60*20
)
def fetch_fo_contract_data(bdate: str) -> pd.DataFrame:
    print(f"Fetching FO contract data for {bdate}")
    fo_df = get_merge_fo_contract_stream_bhavcopy(bdate)
    print(f"Fetched {len(fo_df)} records")
    return fo_df


@task(
    task_run_name=task_name_gen,
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")],
)
def transform_fo_contract_data(
    fo_df: pd.DataFrame, 
    bdate: str
) -> pd.DataFrame:
    print("Starting FO contract data transformation")
    
    df = pd.DataFrame(index=fo_df.index)
    
    # Basic identifiers
    df["trade_date"] = bdate
    df["sutra_symbol"] = None
    df["sutra_token"] = (f"{Exchange.NSE * 10 + Segment.FO}" + fo_df["Token"].astype(str)).astype(int)
    df["token"] = fo_df["Token"].astype(int)
    df["future_token"] = None
    df["equity_token"] = fo_df["AssetToken"].astype(int)
    df["exchange"] = "NSE"
    df["contract_name"] = fo_df["Name"]
    df["symbol"] = fo_df["Symbol"]
    df["segment"] = "FO"
    
    # Instrument details
    df["instrument_type"] = fo_df["InstrumentType"].astype(str)
    df["option_type"] = fo_df["OptionType_stream"].astype(str).fillna("XX")
    df["strike_price"] = fo_df["StrikePrice_stream"].astype(int)
    
    # Expiry information
    df["expiry_epoch"] = fo_df["ExpiryDate_contract"]
    expiry_fields = build_expiry_fields(df["expiry_epoch"], bdate)
    df["expiry_date"] = expiry_fields["expiry_date"]
    df["days_to_expiry"] = expiry_fields["days_to_expiry"]
    df["expiry_cycle"] = expiry_fields["expiry_cycle"]
    
    # Stream information
    df["stream_id"] = fo_df["StreamID"]
    df["market_segment_id"] = 0
    
    # Trading parameters
    df["freeze_quantity"] = fo_df["FreezeQuantity"].astype(float).fillna(np.iinfo(np.int64).max).astype(int)
    df["lot_size"] = fo_df["MinimumLotQuantity"].astype(int)
    df["divisor"] = 100
    
    # Price information
    df["tick_size"] = fo_df["TickSize"].astype(int)
    df["open_price"] = (fo_df["OpnPric"].astype(float) * 100).fillna(0).astype(int)
    df["high_price"] = (fo_df["HghPric"].astype(float) * 100).fillna(0).astype(int)
    df["low_price"] = (fo_df["LwPric"].astype(float) * 100).fillna(0).astype(int)
    df["close_price"] = (fo_df["ClsPric"].astype(float) * 100).fillna(0).astype(int)
    df["last_price"] = (fo_df["LastPric"].astype(float) * 100).fillna(0).astype(int)
    df["previous_close_price"] = (fo_df["PrvsClsgPric"].astype(float) * 100).fillna(0).astype(int)
    df["underlying_price"] = (fo_df["UndrlygPric"].astype(float) * 100).fillna(0).astype(int)
    df["total_traded_volume"] = fo_df["TtlTradgVol"].fillna(0).astype(int)
    df["total_traded_value"] = (fo_df["TtlTrfVal"].astype(float) * 100).fillna(0).astype(int)
    df["high_dpr"] = fo_df["HighPriceRange"].fillna(0).astype(int)
    df["low_dpr"] = fo_df["LowPriceRange"].fillna(0).astype(int)
    
    # Metadata
    df["is_tradeable"] = "Y"
    df["is_banned"] = "N"
    df["currency"] = "INR"
    df["timezone"] = "Asia/Kolkata"
    df["trading_schedule"] = "09:15:00-15:40:00"
    df["isin"] = "NA"
    df["face_value"] = 1
    df["asset_code"] = fo_df["Symbol"]
    
    # Populate computed columns
    print("Computing sutra_symbol and future_token")
    df["sutra_symbol"] = df.apply(build_sutra_symbol_row, axis=1)
    df["future_token"] = get_future_token(df)
    
    # Adding new columns
    df["open_interest"] = fo_df["OpnIntrst"].fillna(0).astype(int)
    
    # Filter invalid records
    df = df[df["future_token"] != -1]

    print(f"Transformation complete: {len(df)} valid contracts")
    return df


@task(
    task_run_name=task_name_gen,
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")]
)
def save_fo_contract_file(
    df: pd.DataFrame, 
    bdate: str
) -> None:
    output_template = get_storage_config("nse")["fo_master_output"]
    output_filepath = output_template.format(bdate=bdate)
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    df.to_csv(output_filepath, index=False)
    print(f"Saved {len(df)} contracts to {output_filepath}")
 

# ========================================================================
# FLOWS
# ========================================================================


@flow(
    name="nse_fo_contract_master_generation",
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")],
    on_completion=[unified_notifier(notification_type="both")],
    on_crashed=[unified_notifier(notification_type="both")],
    on_cancellation=[unified_notifier(notification_type="both")]
)
def nse_fo_contract_master_generation(business_date_str: str = '') -> None:
    bdates = generate_business_dates(business_date_str=business_date_str, use_holidays='NSE', weekdays_only=True)
    
    for bdate in bdates:
        fo_df = fetch_fo_contract_data(bdate)
        transformed_df = transform_fo_contract_data(fo_df, bdate)
        save_fo_contract_file(transformed_df, bdate)


# ========================================================================
# Flow Registration
# ========================================================================


@click.command()
@click.option("-d", "--bdate", default="", help="Business date (YYYYMMDD or range)")
@click.option("-r", "--register", is_flag=True, default=False, help="Register flow")
def main(bdate: str, register: bool):
    if register:
        deploy_flow(
            flow_name=os.path.abspath(__file__),
            cron="00 6 * * 1-5",
            parameters={"business_date_str": bdate},
            work_pool="nse_optflows",
            queue_name="prod-queue"
        )
    else:
        nse_fo_contract_master_generation(business_date_str=bdate)


if __name__ == "__main__":
    main()
