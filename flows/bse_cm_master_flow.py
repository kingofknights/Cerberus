import os
import click
import numpy as np
import pandas as pd

from typing import Optional
from prefect import flow, task

from core.dates import generate_business_dates
from core.prefect_utils import deploy_flow, unified_notifier, task_name_gen, task_retries
from core.enums import Exchange, Segment
from core.config import get_storage_config
from parsers.bse_parser import get_merged_cm_scrip_bhavcopy_df

# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

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
    return create_sutra_symbol(
        exchange="BSE",
        symbol=row["symbol"],
        segment="EQ",
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
    print(f"Fetching BSE CM contract data for {bdate}")
    cm_df = get_merged_cm_scrip_bhavcopy_df(bdate)
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
    print("Starting BSE CM contract data transformation")
    
    df = pd.DataFrame(index=cm_df.index)
    
    # Basic identifiers
    df["trade_date"] = bdate
    df["sutra_symbol"] = None
    df["sutra_token"] = (f"{Exchange.BSE * 10 + Segment.CM}" + cm_df["FinInstrmId"].astype(str)).astype(int)
    df["token"] = cm_df["FinInstrmId"].astype(int)
    df["future_token"] = cm_df["FinInstrmId"].astype(int)
    df["equity_token"] = cm_df["FinInstrmId"].astype(int)
    df["exchange"] = "BSE"
    df["contract_name"] = cm_df["FinInstrmNm_scrip"]
    df["symbol"] = cm_df["TckrSymb_scrip"].astype(str)
    df["segment"] = "CM"
    
    # Instrument details
    df["instrument_type"] = cm_df["SctyTpFlg"]
    df["option_type"] = "XX"
    df["strike_price"] = 0
    
    # Expiry information
    df["expiry_epoch"] = -1
    df["expiry_date"] = pd.to_datetime("1980-01-01").strftime("%d %B %Y")
    df["days_to_expiry"] = 0
    df["expiry_cycle"] = "NA"

    # Stream information
    df["stream_id"] = cm_df["UnqPdctIdr"].str.split("-").str[0]
    df["market_segment_id"] = cm_df["UnqPdctIdr"].str.split("-").str[1]

    # Trading parameters
    df["freeze_quantity"] = np.iinfo(np.int64).max
    df["lot_size"] = cm_df["NewBrdLotQty_scrip"].astype(int)
    df["divisor"] = 100
    
    # Price information
    df["tick_size"] = (cm_df["BidIntrvl"].astype(float).round(2) * 100).fillna(0).astype(int)
    df["open_price"] = (cm_df["OpnPric"].astype(float) * 100).fillna(0).astype(int)
    df["high_price"] = (cm_df["HghPric"].astype(float) * 100).fillna(0).astype(int)
    df["low_price"] = (cm_df["LwPric"].astype(float) * 100).fillna(0).astype(int)
    df["close_price"] = (cm_df["ClsPric"].astype(float) * 100).fillna(0).astype(int)
    df["last_price"] = (cm_df["LastPric"].astype(float) * 100).fillna(0).astype(int)
    df["previous_close_price"] = (cm_df["PrvsClsgPric"].astype(float) * 100).fillna(0).astype(int)
    df["underlying_price"] = (cm_df["UndrlygPric"].astype(float) * 100).fillna(0).astype(int)
    df["total_traded_volume"] = cm_df["TtlTradgVol"].fillna(0).astype(int)
    df["total_traded_value"] = (cm_df["TtlTrfVal"].astype(float) * 100).fillna(0).astype(int)

    df["high_dpr"] = cm_df["Upper Circuit Price"].fillna(0).astype(int)
    df["low_dpr"] = cm_df["Lower Circuit Price"].fillna(0).astype(int)
    
    # Metadata
    df["is_tradeable"] = "Y"
    df["is_banned"] = "N"
    df["currency"] = "INR"
    df["timezone"] = "Asia/Kolkata"
    df["trading_schedule"] = "09:15:00-15:30:00"
    df["isin"] = cm_df["ISIN_scrip"]
    df["face_value"] = cm_df["ParVal"]
    df["asset_code"] = cm_df["TckrSymb_scrip"]
    
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
    output_template = get_storage_config("bse")["cm_master_output"]
    output_filepath = output_template.format(bdate=bdate)
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    df.to_csv(output_filepath, index=False)
    print(f"Saved {len(df)} contracts to {output_filepath}")


# ========================================================================
# FLOWS
# ========================================================================

@flow(
    name="bse_cm_contract_master_generation",
    log_prints=True,
    on_failure=[unified_notifier(notification_type="both")],
    on_completion=[unified_notifier(notification_type="both")],
    on_crashed=[unified_notifier(notification_type="both")],
    on_cancellation=[unified_notifier(notification_type="both")]
)
def bse_cm_contract_master_generation(business_date_str: str = '') -> None:
    bdates = generate_business_dates(business_date_str=business_date_str, use_holidays='BSE', weekdays_only=True)
    
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
            cron="10 6 * * 1-5",
            parameters={"business_date_str": bdate},
            work_pool="nse_optflows",
            queue_name="prod-queue"
        )
    else:
        bse_cm_contract_master_generation(business_date_str=bdate)


if __name__ == "__main__":
    main()
