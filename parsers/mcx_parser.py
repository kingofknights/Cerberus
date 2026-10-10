import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Tuple, List

from core.inputs import input_path

# ===============================
# Helpers
# ===============================

def _validate_file_exists(file_path: Path, file_description: str = None) -> None:
    if not file_path.exists():
        desc = f" ({file_description})" if file_description else ""
        raise FileNotFoundError(f"{file_path}{desc}")


# ===============================================
# FO CONTRACT MCX SCRIPS.BCP
# ===============================================

def get_mcx_scrips_df(bdate: str) -> pd.DataFrame:
    file_path = input_path("mcx_scrips", bdate)

    _validate_file_exists(file_path, "MCX Scrips file")

    df = pd.read_csv(file_path, header=None)

    df.columns = [
        "Filler2", "Filler4", "InstrumentPartitionID", "Filler8", "Filler2_2",
        "InstrumentIdentifier", "Symbol", "InstrumentSeries", "InstrumentType", "PermitTrading",
        "Filler4_2", "ProductID", "BandhaniRange", "Filler1", "Filler1_2",
        "Filler1_3", "Filler1_4", "InstrumentStartDate", "Filler4_3", "LastTradingDate",
        "LotSize", "TickSize", "InstrumentDescription", "CapacityGroupID", "Filler4_4", "Filler4_5",
        "DeliveryStartDate", "DeliveryEndDate", "Filler1_5", "Trade2TradeIndicator", "IndexFlag",
        "DefaultIndex", "IndexInstrument", "FeedFlag", "Filler1_6", "Filler1_7",
        "Filler1_8", "LastModifiedDate", "InstrumentStatusFlag", "InstrumentInfo", "MinimumLot",
        "TenderPeriodStartDate", "TenderPeriodEndDate", "ULAssetGroup", "UnderlyingName", "UnderlyingIdentifier",
        "Filler4_6", "Filler4_7", "Filler1_9", "Filler1_10", "Filler1_11",
        "Filler1_12", "Filler1_13", "InstrumentName", "OriginalExpiryDate", "StrikePrice",
        "OptionType", "CALevel", "SegmentID", "AdditionalLeanPeriodMargin", "Filler2_3",
        "PriceQuoteUnit", "PriceQuoteQuantity", "TermsOfDailyPriceRange", "UpperDailyPriceRange", "LowerDailyPriceRange",
        "TenderPeriodIndicator", "SettlementMethod", "TermsOfInitialMargin", "BuyInitialMarginRate", "BasePrice",
        "MaxSingleTransactionQty", "MaxSingleTransactionValue", "InstrumentClass", "NearMonthInstrumentIdentifier", "FarMonthInstrumentIdentifier",
        "TradingUnit", "TradingUnitFactor", "DeliveryUnit", "DeliveryUnitFactor", "PriceNumerator",
        "Specification", "PriceDenominator", "GeneralNumerator", "GeneralDenominator", "LotNumerator",
        "LotDenominator", "DecimalLocator", "Filler2_4", "Filler15", "Filler4_8",
        "Filler50", "AdditionalLeanPeriodMarginSell", "SpreadBenefitOnALPM", "SellInitialMarginRate", "ProductName",
        "Filler2_5", "TermsOfSpecialMargin", "BuySpecialMarginRate", "SellSpecialMarginRate", "InitialMarginSpreadBenefitFlag",
        "InstrumentEndDateTime", "TradingCurrency", "Filler3", "ProductMonth", "PreOpenAllowed",
        "GroupID", "MatchingType", "SpreadType", "Filler16", "ValueMethod",
        "AdditionalLeanPeriodMarginBuy", "SLBMEligibility", "TermsOfExtremeLossMargin", "BuyExtremeLossMarginRate", "SellExtremeLossMarginRate",
        "OptionsPricingModel", "DeliveryMode",
    ]

    df = df.astype(str)
    return df


# ===============================================
# FO MCX BHAVCOPY
# ===============================================

def get_mcx_bhavcopy_df(bdate: str) -> pd.DataFrame:
    '''
    Load MCX FO bhavcopy reference file.
    
    "TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp",
    "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "XpryDt",
    "FininstrmActlXpryDt", "StrkPric", "OptnTp", "FinInstrmNm", "OpnPric",
    "HghPric", "LwPric", "ClsPric", "LastPric", "PrvsClsgPric",
    "UndrlygPric", "SttlmPric", "OpnIntrst", "ChngInOpnIntrst", "TtlTradgVol",
    "TtlTrfVal", "TtlNbOfTxsExctd", "SsnId", "NewBrdLotQty", "Rmks",
    "Rsvd1", "Rsvd2", "Rsvd3", "Rsvd4",
    '''
    file_path = input_path("mcx_bhav", bdate)
    _validate_file_exists(file_path, "MCX Bhavcopy file")

    df = pd.read_csv(file_path)
    df = df.astype(str)
    return df


# ===============================================
# Merge FO Contract and Bhavcopy
# ===============================================

def get_merge_mcx_scrips_bhavcopy_df(bdate: str) -> pd.DataFrame:
    missing_files: List[str] = []
    scrips_df = bhavcopy_df = None

    # Collect required missing files before raising error
    try:
        scrips_df = get_mcx_scrips_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))

    try:
        bhavcopy_df = get_mcx_bhavcopy_df(bdate)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Proceeding without MCX Bhavcopy data.")
        bhavcopy_df = pd.DataFrame(columns=[
            "FinInstrmId", "ISIN", "OpnPric", "HghPric", "LwPric", "ClsPric",
            "LastPric", "PrvsClsgPric", "UndrlygPric", "OpnIntrst", "TtlTradgVol", "TtlTrfVal"
        ])

    # Raise error if core scrips file is missing
    if missing_files:
        error_message = "\n".join(missing_files)
        raise FileNotFoundError(error_message)

    df = pd.merge(
        scrips_df,
        bhavcopy_df,
        left_on="InstrumentIdentifier",
        right_on="FinInstrmId",
        how="left",
        suffixes=("_scrips", "_bhavcopy")
    )

    return df
