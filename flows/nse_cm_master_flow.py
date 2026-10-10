import os
import click
import pandas as pd
import numpy as np

from typing import Optional

from core.dates import generate_business_dates
from core.prefect_utils import flow, task, deploy_flow, unified_notifier, task_name_gen, task_retries
from core.enums import Exchange, Segment
from core.config import get_storage_config
from parsers.nse_parser import get_merge_cm_security_stream_qty_freeze_bhavcopy

# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

def create_sutra_symbol(exchange: str, symbol: str, segment: str, instrument_type: str = None) -> str:
    """Create SutraSymbol identifier for CM."""
    parts = [exchange, symbol, segment, instrument_type]
    return "_".join(map(str, parts))


def build_sutra_symbol_row(row: pd.Series) -> str:
    """Build SutraSymbol for a single row."""
    return create_sutra_symbol(
        exchange="NSE",
        symbol=row["symbol"],
        segment="EQ",
        instrument_type=row["instrument_type"]
    )


# Backward compatibility aliases
create_mimbol = create_sutra_symbol
build_mimbol_row = build_sutra_symbol_row


# ========================================================================
# TASKS
# ========================================================================

@task(
    task_run_name=task_name_gen,
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")],
    retries=task_retries(6),
    retry_delay_seconds=60*20
)
def fetch_cm_contract_data(bdate: str) -> pd.DataFrame:
    print(f"Fetching CM contract data for {bdate}")
    cm_df = get_merge_cm_security_stream_qty_freeze_bhavcopy(bdate)
    print(f"Fetched {len(cm_df)} records")
    return cm_df


@task(
    task_run_name=task_name_gen,
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")],
)
def transform_cm_contract_data(
    cm_df: pd.DataFrame, 
    bdate: str
) -> pd.DataFrame:
    print("Starting CM contract data transformation")
    
    df = pd.DataFrame(index=cm_df.index)
    
    # Basic identifiers
    df["trade_date"] = bdate
    df["sutra_symbol"] = None
    df["sutra_token"] = (f"{Exchange.NSE * 10 + Segment.CM}" + cm_df["Token"].astype(str)).astype(int)
    df["token"] = cm_df["Token"].astype(int)
    df["future_token"] = cm_df["Token"].astype(int)
    df["equity_token"] = cm_df["Token"].astype(int)
    df["exchange"] = "NSE"
    df["contract_name"] = cm_df["Name"]
    df["symbol"] = cm_df["Symbol_security"].str.strip()
    df["segment"] = "CM"
    
    # Instrument details
    df["instrument_type"] = cm_df["Series_security"]
    df["option_type"] = "XX"
    df["strike_price"] = 0
    
    # Expiry information
    df["expiry_epoch"] = -1
    df["expiry_date"] = pd.to_datetime("1970-01-01").strftime("%d %B %Y")
    df["days_to_expiry"] = 0
    df["expiry_cycle"] = 'NA'
    
    # Stream information
    df["stream_id"] = cm_df["StreamID"]
    df["market_segment_id"] = 0
    
    # Trading parameters
    df["freeze_quantity"] = cm_df["FreezeQty"].astype(float).fillna(np.iinfo(np.int64).max).astype(int)
    df["lot_size"] = cm_df["BoardLotQty"].fillna(1).astype(int)
    df["divisor"] = 100
    
    # Price information
    df["tick_size"] = cm_df["TickSize"].astype(int)
    df["open_price"] = (cm_df["OpnPric"].astype(float) * 100).fillna(0).astype(int)
    df["high_price"] = (cm_df["HghPric"].astype(float) * 100).fillna(0).astype(int)
    df["low_price"] = (cm_df["LwPric"].astype(float) * 100).fillna(0).astype(int)
    df["close_price"] = (cm_df["ClsPric"].astype(float) * 100).fillna(0).astype(int)
    df["last_price"] = (cm_df["LastPric"].astype(float) * 100).fillna(0).astype(int)
    df["previous_close_price"] = (cm_df["PrvsClsgPric"].astype(float) * 100).fillna(0).astype(int)
    df["underlying_price"] = (cm_df["UndrlygPric"].astype(float) * 100).fillna(0).astype(int)
    df["total_traded_volume"] = cm_df["TtlTradgVol"].fillna(0).astype(int)
    df["total_traded_value"] = (cm_df["TtlTrfVal"].astype(float) * 100).fillna(0).astype(int)
    df["high_dpr"] = (pd.to_numeric(
        cm_df["CreditRating"].str.split("-", expand=False).str[1], errors="coerce"
    ) * 100).fillna(0).astype(int)
    df["low_dpr"] = (pd.to_numeric(
        cm_df["CreditRating"].str.split("-", expand=False).str[0], errors="coerce"
    ) * 100).fillna(0).astype(int)
    
    # ==========================================================
    # Tradeable Flag
    #
    # security.gz alone has no single "tradable" field, so combine:
    #   DeleteFlag                = N   (security not deleted)
    #   Eligibility (Normal Mkt)  = 1   (eligible for Normal Market)
    #   SecurityStatus (Normal)  != 3   (not Suspended)
    #   PermittedToTrade         in (0, 1)  (Listed or Permitted to Trade)
    #
    # SecurityStatus == 2 (Open) is intentionally not required: this flow
    # runs at 6 AM, before NSE flips securities to Open at market start,
    # so requiring "Open" here would make is_tradeable "N" for everything.
    # ==========================================================
    df["is_tradeable"] = np.where(
        (cm_df["DeleteFlag"].astype(str) == "N") &
        (cm_df["IsNormalMarketEligible"].astype(str) == "1") &
        (cm_df["NormalMarketStatus"].astype(str) != "3") &
        (cm_df["PermittedToTrade"].astype(str).isin(["0", "1"])),
        "Y",
        "N"
    )
    df["is_banned"] = "N"
    df["currency"] = "INR"
    df["timezone"] = "Asia/Kolkata"
    df["trading_schedule"] = "09:15:00-15:30:00"
    df["isin"] = cm_df["ISIN_bhavcopy"]
    df["face_value"] = cm_df["FaceValue"]
    df["asset_code"] = cm_df["Symbol"]
    
    # Populate computed columns
    print("Computing sutra_symbol")
    df["sutra_symbol"] = df.apply(build_sutra_symbol_row, axis=1)
    
    # Adding new columns
    df["open_interest"] = (pd.to_numeric(cm_df["OpnIntrst"], errors="coerce").fillna(0).astype(int))
    
    print(f"Transformation complete: {len(df)} valid contracts")
    return df


@task(
    task_run_name=task_name_gen,
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")]
)
def save_cm_contract_file(
    df: pd.DataFrame, 
    bdate: str
) -> None:
    output_template = get_storage_config("nse")["cm_master_output"]
    output_filepath = output_template.format(bdate=bdate)
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    df.to_csv(output_filepath, index=False)
    print(f"Saved {len(df)} contracts to {output_filepath}")


# ========================================================================
# FLOWS
# ========================================================================

@flow(
    name="nse_cm_contract_master_generation",
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")],
    on_completion=[unified_notifier(notification_type="both")],
    on_crashed=[unified_notifier(notification_type="both")],
    on_cancellation=[unified_notifier(notification_type="both")]
)
def nse_cm_contract_master_generation(business_date_str: str = '') -> None:
    bdates = generate_business_dates(business_date_str=business_date_str, use_holidays='NSE', weekdays_only=True)
    
    for bdate in bdates:
        cm_df = fetch_cm_contract_data(bdate)
        transformed_df = transform_cm_contract_data(cm_df, bdate)
        save_cm_contract_file(transformed_df, bdate)


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
        nse_cm_contract_master_generation(business_date_str=bdate)


if __name__ == "__main__":
    main()
