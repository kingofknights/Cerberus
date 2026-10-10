import numpy as np
import pandas as pd
from typing import Tuple, List
from pathlib import Path
from datetime import datetime

from core.inputs import input_path

# ===============================
# Helpers
# ===============================

def _validate_file_exists(file_path: Path, file_description: str = None) -> None:
    if not file_path.exists():
        desc = f" ({file_description})" if file_description else ""
        raise FileNotFoundError(f"{file_path}{desc}")


def _combine_contract_structure(row: pd.Series) -> Tuple:
    return (
        (row[14], row[15], row[16]),
        (row[17], row[18], row[19]),
        (row[20], row[21], row[22]),
        (row[23], row[24], row[25]),
    )


def _combine_security_structure(row: pd.Series) -> Tuple:
    return (
        (row[6], row[8], row[9]),
        (row[10], row[11], row[12]),
        (row[13], row[14], row[15]),
        (row[16], row[17], row[18]),
    )


# ===============================
# FO CONTRACT (FINAL DB DF)
# ===============================

def get_fo_contract_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_contract", bdate)
    
    _validate_file_exists(file_path, "NSE FO Contract file")

    df = pd.read_csv(file_path, sep="|", compression="infer", skiprows=1, header=None)

    df["ST_SEC_ELIGIBILITY_MARKET"] = df.apply(_combine_contract_structure, axis=1)

    df.drop(df.columns[[5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]], axis=1, inplace=True)

    df.columns = [
        "Token", "AssetToken", "InstrumentName", "Symbol", "Series", "ExpiryDate",
        "StrikePrice", "OptionType", "Category", "CALevel", "ReservedIdentifier",
        "PermittedToTrade", "IssueRate", "IssueStartDate", "InterestPaymentDate",
        "IssueMaturityDate", "MarginPercentage", "MinimumLotQuantity",
        "BoardLotQuantity", "TickSize", "IssuedCapital", "FreezeQuantity",
        "WarningQuantity", "ListingDate", "ExpulsionDate", "ReadmissionDate",
        "RecordDate", "NoDeliveryStartDate", "NoDeliveryEndDate",
        "LowPriceRange", "HighPriceRange", "ExDate",
        "BookClosureStartDate", "BookClosureEndDate", "LocalLDBUpdateDateTime",
        "ExerciseStartDate", "ExerciseEndDate", "TickerSelection",
        "OldTokenNumber", "CreditRating", "Name", "EGMAGM",
        "InterestDividend", "RightsBonus", "MFAON", "Remarks",
        "ExStyle", "ExAllowed", "ExRejectionAllowed", "PlAllowed",
        "SettlementIndicator", "IsCorporateAdjusted", "SymbolForAsset",
        "InstrumentOfAsset", "BasePrice", "DeleteFlag",
        "ST_SEC_ELIGIBILITY_MARKET",
    ]

    df = df.astype(str)
    return df


# ===============================
# FO STREAM (FINAL DB DF)
# ===============================

def get_fo_stream_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_fo_stream", bdate)
    
    _validate_file_exists(file_path, "NSE FO Stream file")

    df = pd.read_csv(file_path, skiprows=1, header=None)
    df.columns = [
        "RecordType", "StreamID", "TokenNumber", "InstrumentType",
        "UnderlyingSymbol", "ExpiryDate", "StrikePrice", "OptionType",
    ]

    df = df.astype(str)
    return df


# ===============================
# FO BHAVCOPY (FINAL DB DF)
# ===============================

def get_fo_bhavcopy_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_fo_bhav", bdate)
    
    _validate_file_exists(file_path, "NSE FO Bhavcopy file")

    df = pd.read_csv(file_path, skiprows=1, header=None)
    df.columns = [
        "TradDt","BizDt","Sgmt","Src","FinInstrmTp",
        "FinInstrmId","ISIN","TckrSymb","SctySrs","XpryDt",
        "FininstrmActlXpryDt","StrkPric","OptnTp","FinInstrmNm","OpnPric",
        "HghPric","LwPric","ClsPric","LastPric","PrvsClsgPric",
        "UndrlygPric","SttlmPric","OpnIntrst","ChngInOpnIntrst","TtlTradgVol",
        "TtlTrfVal","TtlNbOfTxsExctd","SsnId","NewBrdLotQty","Rmks",
        "Rsvd1","Rsvd2","Rsvd3","Rsvd4"
    ]

    df = df.astype(str)
    return df


# ===============================
# CM SECURITY (FINAL DB DF)
# ===============================

def get_cm_security_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_security", bdate)
    
    _validate_file_exists(file_path, "NSE CM Security file")

    df = pd.read_csv(file_path, sep="|", compression="infer", skiprows=1, header=None)

    df["ST_SEC_ELIGIBILITY_MARKET"] = df.apply(_combine_security_structure, axis=1)
    # Field 8 (col index 7): SecurityStatus - Normal Market (1=Preopen, 2=Open, 3=Suspended, ...)
    df["NormalMarketStatus"] = df[7]
    # Field 9 (col index 8): Eligibility - Normal Market. 0 = Not Eligible, 1 = Eligible.
    df["IsNormalMarketEligible"] = df[8]

    df.drop(df.columns[[7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]], axis=1, inplace=True)

    df.columns = [
        "Token", "Symbol", "Series", "InstrumentType", "IssuedCapital",
        "PermittedToTrade", "CreditRating", "BoardLotQty", "TickSize",
        "Name", "IssueRate", "IssueStartDate", "IssueIPDate",
        "IssueMaturityDate", "FreezePercent", "ListingDate",
        "ExpulsionDate", "ReAdmissionDate", "ExDate", "RecordDate",
        "NoDeliveryStartDate", "NoDeliveryEndDate", "ParticipateInIndex",
        "AON", "MinFill", "WarningPercent", "BookClosureStartDate",
        "BookClosureEndDate", "Dividend", "Rights", "Bonus",
        "Interest", "AGM", "EGM", "UnknownColumn1", "UnknownColumn2",
        "UnknownColumn3", "Remark", "LocalDBUpdateDateTime",
        "DeleteFlag", "FaceValue", "ISIN",
        "ST_SEC_ELIGIBILITY_MARKET", "NormalMarketStatus", "IsNormalMarketEligible",
    ]

    # df = df[df["Series"].str.contains("EQ", na=False)]
    
    df = df.astype(str)
    return df


# ===============================
# CM STREAM (FINAL DB DF)
# ===============================

def get_cm_stream_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_cm_stream", bdate)
    
    _validate_file_exists(file_path, "NSE CM Stream file")

    df = pd.read_csv(file_path, skiprows=1, header=None)
    df.columns = [
        "RecordType", "StreamID", "TokenNumber", "InstrumentType",
        "Symbol", "ExpiryDate", "StrikePrice", "Series",
    ]

    df = df.astype(str)
    return df


# ===============================
# CM QTY FREEZE (FINAL DB DF)
# ===============================

def get_cm_qty_freeze_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_qty_freeze", bdate)
    
    _validate_file_exists(file_path, "NSE CM Quantity Freeze file")

    df = pd.read_csv(file_path, skiprows=1, header=None)
    df.columns = ["Symbol", "Series", "FreezeQty"]

    # df = df[df["Series"].str.contains("EQ", na=False)]
    df = df.astype(str)
    return df


# =====================================================
# CM Bhavcopy (FINAL DB DF)
# =====================================================

def get_cm_bhavcopy_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("nse_cm_bhav", bdate)
    
    _validate_file_exists(file_path, "NSE CM Bhavcopy file")

    df = pd.read_csv(file_path, skiprows=1, header=None)
    df.columns = [
        "TradDt","BizDt","Sgmt","Src","FinInstrmTp",
        "FinInstrmId","ISIN","TckrSymb","SctySrs","XpryDt",
        "FininstrmActlXpryDt","StrkPric","OptnTp","FinInstrmNm","OpnPric",
        "HghPric","LwPric","ClsPric","LastPric","PrvsClsgPric",
        "UndrlygPric","SttlmPric","OpnIntrst","ChngInOpnIntrst","TtlTradgVol",
        "TtlTrfVal","TtlNbOfTxsExctd","SsnId","NewBrdLotQty","Rmks",
        "Rsvd1","Rsvd2","Rsvd3","Rsvd4"
    ]

    df = df.astype(str)
    return df


# =====================================================
# 7. Merge FO
# =====================================================

def get_merge_fo_contract_stream_bhavcopy(bdate: str) -> pd.DataFrame:
    missing_files: List[str] = []
    df_contract = df_stream = df_bhavcopy = None
    
    # Collect required missing files before raising error
    try:
        df_contract = get_fo_contract_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))
    
    try:
        df_stream = get_fo_stream_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))
    
    try:
        df_bhavcopy = get_fo_bhavcopy_df(bdate)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Proceeding without Bhavcopy price data.")
        df_bhavcopy = pd.DataFrame(columns=[
            "FinInstrmId", "ISIN", "OpnPric", "HghPric", "LwPric", "ClsPric",
            "LastPric", "PrvsClsgPric", "UndrlygPric", "OpnIntrst", "TtlTradgVol", "TtlTrfVal"
        ])
    
    # Raise error if core contract/stream files are missing
    if missing_files:
        error_message = "\n".join(missing_files)
        raise FileNotFoundError(error_message)

    # Perform merges
    df = pd.merge(
        df_contract,
        df_stream,
        left_on="Token",
        right_on="TokenNumber",
        how="inner",
        suffixes=("_contract", "_stream")
    )
    
    df = pd.merge(
        df,
        df_bhavcopy,
        left_on=["Token"],
        right_on=["FinInstrmId"],
        how="left",
    )
    
    return df


# =====================================================
# 8. Merge CM
# =====================================================

def get_merge_cm_security_stream_qty_freeze_bhavcopy(
    bdate: str
) -> pd.DataFrame:

    missing_files: List[str] = []

    df_security = (
        df_stream
    ) = (
        df_qty_freeze
    ) = (
        df_bhavcopy
    ) = None

    # Collect required missing files before raising error
    try:
        df_security = get_cm_security_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))

    try:
        df_stream = get_cm_stream_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))

    try:
        df_qty_freeze = get_cm_qty_freeze_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))

    try:
        df_bhavcopy = get_cm_bhavcopy_df(bdate)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Proceeding without Bhavcopy price data.")
        df_bhavcopy = pd.DataFrame(columns=[
            "FinInstrmId", "ISIN", "OpnPric", "HghPric", "LwPric", "ClsPric",
            "LastPric", "PrvsClsgPric", "UndrlygPric", "OpnIntrst", "TtlTradgVol", "TtlTrfVal"
        ])

    # Raise error if core security/stream/qty_freeze files are missing
    if missing_files:
        error_message = "\n".join(missing_files)
        raise FileNotFoundError(error_message)

    # ==========================================================
    # Merge Security + Stream
    # ==========================================================

    df = pd.merge(
        df_security,
        df_stream,
        left_on="Token",
        right_on="TokenNumber",
        how="inner",
        suffixes=(
            "_security",
            "_stream"
        )
    )

    # ==========================================================
    # Merge Qty Freeze
    # ==========================================================

    df = pd.merge(
        df,
        df_qty_freeze,
        left_on=[
            "Symbol_security",
            "Series_security"
        ],
        right_on=[
            "Symbol",
            "Series"
        ],
        how="left",
    )

    # ==========================================================
    # Merge Bhavcopy
    # ==========================================================

    df = pd.merge(
        df,
        df_bhavcopy,
        left_on=["Token"],
        right_on=["FinInstrmId"],
        how="left",
        suffixes=(
            "",
            "_bhavcopy"
        )
    )

    # ==========================================================
    # Fill missing FreezeQty
    #
    # Priority:
    # 1. Exact Symbol + Series match
    # 2. Max FreezeQty for same Symbol
    # 3. Computed: (FreezePercent / 100) * (IssuedCapital / FaceValue)
    # ==========================================================

    symbol_max_freeze = (
        df_qty_freeze.groupby("Symbol")["FreezeQty"]
        .max()
        .to_dict()
    )

    def _computed_freeze_qty(row: pd.Series) -> float:
        try:
            return (float(row["FreezePercent"]) / 100) * (float(row["IssuedCapital"]) / float(row["FaceValue"]))
        except (TypeError, ValueError, ZeroDivisionError):
            return np.nan

    df["FreezeQty"] = df.apply(
        lambda row: (
            symbol_max_freeze.get(row["Symbol_security"], np.nan)
            if pd.isna(row["FreezeQty"])
            else row["FreezeQty"]
        ),
        axis=1
    )

    # Final fallback
    df["FreezeQty"] = df["FreezeQty"].fillna(df.apply(_computed_freeze_qty, axis=1))

    return df
