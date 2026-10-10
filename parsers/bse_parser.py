import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Tuple, List

from core.inputs import input_path

# ===============================
# Helpers
# ===============================

def _validate_file_exists(file_path: Path, file_description: str = None) -> None:
    """
    Validate if file exists and raise FileNotFoundError with descriptive message.
    
    Args:
        file_path: Path to the file
        file_description: Optional description of the file for better error messages
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not file_path.exists():
        desc = f" ({file_description})" if file_description else ""
        raise FileNotFoundError(f"{file_path}{desc}")


# ===============================================
# FO CONTRACT BSE_EQD_CONTRACT_28112025.csv
# ===============================================

def get_bse_eqd_contract_df(bdate: str) -> pd.DataFrame:
    """
    Load BSE EQD contract reference file for the given business date.

    Columns:
        FinInstrmId, UndrlygFinInstrmId, FinInstrmNm, TckrSymb, XpryDt,
        StrkPric, OptnTp, PrtdToTrad, MinLot, NewBrdLotQty,
        BidIntrvl, StartDt, EndDt, MtrtyDt, PdctStartDt,
        SrsId, AsstCd, UndrlygInstrmAsstClss, StockNm, SttlmMtd,
        BasePric, DelFlg, ExrcStartDt, ExrcEndDt, IssdCptl,
        MinPric, MaxPric, MktTpAndId, OffclCorpActnEvtId, AdmssnTp,
        IssePric, TradgStsNrmlMkt, ElgbltyNrmlMkt, TradgStsOddLotMkt, ElgbltyOddLotMkt,
        TradgStsSpotMkt, ElgbltySpotMkt, TradgStsAuctnMkt, ElgbltyAuctnMkt, MrgnPctg,
        MaxTradQty, WrngQty, AdmssnDt, RmvlDt, RadmssnDt,
        RcrdDt, NoDlvryStartDt, NoDlvryEndDt, SpclExDt, BookClsrStartDt,
        BookClsrEndDt, StockRcrdDt, TckrSelctn, OdOffclCorpActnEvtId, CdtRatg,
        Mtg, IntrstOrDvdd, RghtsOrBns, MinFillAllOrNn, AddtlInf,
        OptnExrcStyle, ExrcAllwd, ExrcRjctAllwd, PLAllwd, CorpAdjstmnt,
        UndrlygInstrm, DcmlstnPric, PartnIdr, UnqPdctIdr, CpctyGrpId,
        SctyId, Mltplr, SctyLngNm, UndrlygMkt, CtrctTp,
        FinInstrmPdctTpCd, FinInstrmTp, TradToTradInd, IndxFlg, Indx,
        IndxPrtcptnInd, ExtrnlDataSrcFlg, LastUpd, FinInstrmGnlAttrbts, AddtlUndrlygAttrbts,
        UndrlygAsst, OrgnlXpryDt, SgmtId, UnitOfMeasr, PricQtQty,
        PricRgTp, InitlMrgnTp, BuyInitlMrgnRate, MaxSnglTxnQty, MaxSnglTxnVal,
        AsstClss, NearMnthInstrmIdr, FarMnthInstrmIdr, PricNmrtr, Spcfctn,
        PricDnmtr, GnlNmrtr, GnlDnmtr, LotNmrtr, LotDnmtr,
        DcmlLctr, SttlmTp, ParVal, CorpActnRsn, FreeFltCptl,
        ISIN, SellInitlMrgnRate, RatgDtls, FinInstrmClssfctn, SpclMrgnTp,
        BuySpclMrgnRat, SellSpclMrgnRat, InitlMrgnSprdBnftFlg, InstrmEndDtTm, Ccy,
        PdctMnth, GrpId, MtchgCrit, SprdTp, ValMtd,
        SLBMElgblty, PricMtd, InstrmId, XpryPrcDt, MrgnInd,
        RglrBuyMrgn, RglrSellMrgn, SprdBnftAllwd, DlvryWght, DlvryUnit,
        Rsvd01, Rsvd02, Rsvd03, Rsvd04, Rsvd05,
        Rsvd06, Rsvd07, Rsvd08, Rsvd09, Rsvd10,
        Rsvd11, Rsvd12, Rsvd13, Rsvd14, Rsvd15
    """

    file_path = input_path("bse_eqd_contract", bdate)
    
    _validate_file_exists(file_path, "BSE EQD Contract file")

    df = pd.read_csv(file_path, header=0)
    df = df.astype(str)

    return df


# ===============================================
# FO EQD_DP281125
# ===============================================

def get_bse_eqd_dp_contract_df(bdate: str) -> pd.DataFrame:
    '''
    Load BSE EQD DP contract reference file for the given business date.
    
    SeriesId,Precision,Previous Close Price,Lower Circuit(%),Upper Circuit (%),
    Lower Circuit Price,Upper Circuit Price,Filler,Filler,Filler,Filler,Filler,Filler,
    Filler,Filler,Filler,Instrument Id
    '''
    file_path = input_path("bse_eqd_dp", bdate)

    _validate_file_exists(file_path, "BSE EQD DP file")

    df = pd.read_csv(file_path, header=0)
    df = df.astype(str)
    return df


# ===============================================
# FO BhavCopy_BSE_FO_0_0_0_20251128_F_0000.csv
# ===============================================

def get_fo_bhavcopy_bse_df(bdate: str) -> pd.DataFrame:
    '''
    Load BSE FO Bhavcopy reference file for the given business date.
    
    TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,
    FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,
    LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,
    TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
    '''
    file_path = input_path("bse_fo_bhav", bdate)

    _validate_file_exists(file_path, "BSE FO Bhavcopy file")

    df = pd.read_csv(file_path, header=0)
    df = df.astype(str)
    return df


# ===============================================
# CM CONTRACT BSE_EQ_SCRIP_21012026.csv 
# ===============================================

def get_bse_eq_scrip_df(bdate: str) -> pd.DataFrame:
    '''
    Load BSE EQ script reference file for the given business date.
    
    FinInstrmId, TckrSymb, SctySrs, FinInstrmNm, ISIN
    NewBrdLotQty, ParVal, SctyTpFlg, BidIntrvl, TrckgInd
    CallAuctnInd, BookClsrStartDt, BookClsrEndDt, NoDlvryStartDt, NoDlvryEndDt
    IssdCptl, PrtdToTrad, PricRg, SctyStsNrmlMkt, ElgbltyNrmlMkt
    SctyStsOddLotMkt, ElgbltyOddLotMkt, SctyStsRETDBTMkt, ElgbltyRETDBTMkt, SctyStsAuctnMkt
    ElgbltyAuctnMkt, SctyStsAddtlMkt1, ElgbltyAddtlMkt1, SctyStsAddtlMkt2, ElgbltyAddtlMkt2
    IsseDt, FrstPmtDt, MtrtyDt, MaxTradQtyPctg, ListgDt
    RmvlDt, RadmssnDt, RcrdDt, IndxPrtcptnInd, AllOrNn
    MinFill, SttlmTp, Dvdd, Rghts, Bns
    Intrst, AGMtg, EGMtg, MktMakrSprd, MktMakrMinQty
    AddtlInf, UpdDt, DelFlg, SpclExDt, Xchg
    UnqPdctIdr, SctyTp, TickSz, Rsvd01, Sts
    ExDvddDt, ExBnsDt, ExRghtsDt, FinInstrmTp, InstrmTp
    TradgPrtd, BuyBckInd, TradToTradInd, Indx, IndxInstrm
    FinInstrmAttrbts, MinLot, UndrlygInstrmAsstClss, UndrlygInstrm, UndrlygFinInstrmId
    BlckDealAllwdFlg, InstrmNm, MktTpAndId, UnitOfMeasr, PricQtQty
    PricRgTp, MaxPric, MinPric, SttlmMtd, InitlMrgnTp
    BuyInitlMrgnRate, IssePric, MaxSnglTxnQty, MaxSnglTxnVal, AsstClss
    PricNmrtr, Spcfctn, PricDnmtr, GnlNmrtr, GnlDnmtr
    LotNmrtr, LotDnmtr, DcmlstnPric, SrsSttlmTp, FreeFltCptl
    SellInitlMrgnRate, RatgDtls, FinInstrmClssfctn, SpclMrgnTp, BuySpclMrgnRat
    SellSpclMrgnRat, PreOpnAllwdFlg, ClssfctnTp, MtchgCrit, ValMtd
    SLBMElgblty, Sgmt, Ccy, SttlmCcy, Rsvd02
    Rsvd03, Rsvd04, Rsvd05, Rsvd06, Rsvd07
    '''
    file_path = input_path("bse_eq_scrip", bdate)

    _validate_file_exists(file_path, "BSE EQ Scrip file")

    df = pd.read_csv(file_path, header=0)
    # df = df[df["SctyTpFlg"].str.contains("EQ", na=False)]
    df = df.astype(str)
    return df


# ================================================
# DP230126 
# ================================================

def get_bse_cm_dp(bdate: str) -> pd.DataFrame:
    '''
    Load BSE DP reference file for the given business date.
    
    Scrip Code, Circuit Relax Flag, Previous Close Price, Lower Circuit(%), Upper Circuit (%),
    Lower Circuit Price, Upper Circuit Price, YearlyHigh, Yearly Low, Date of yearly high,
    Date of yearly low, Last trade date, Filler, Filler, Filler, Filler
    '''
    file_path = input_path("bse_cm_dp", bdate)

    _validate_file_exists(file_path, "BSE CM DP file")

    df = pd.read_csv(file_path, header=0)
    df = df.astype(str)
    return df


# ===============================================
# CM BhavCopy_BSE_FO_0_0_0_20251128_F_0000.csv
# ===============================================

def get_cm_bhavcopy_bse_df(bdate: str) -> pd.DataFrame:
    '''
    Load BSE EQD contract reference file for the given business date.
    
    TradDt, BizDt, Sgmt, Src, FinInstrmTp
    FinInstrmId, ISIN, TckrSymb, SctySrs, XpryDt
    FininstrmActlXpryDt, StrkPric, OptnTp, FinInstrmNm, OpnPric
    HghPric, LwPric, ClsPric, LastPric, PrvsClsgPric
    UndrlygPric, SttlmPric, OpnIntrst, ChngInOpnIntrst, TtlTradgVol
    TtlTrfVal, TtlNbOfTxsExctd, SsnId, NewBrdLotQty, Rmks
    Rsvd1, Rsvd2, Rsvd3, Rsvd4
    '''
    file_path = input_path("bse_cm_bhav", bdate)

    _validate_file_exists(file_path, "BSE CM Bhavcopy file")

    df = pd.read_csv(file_path, header=0)
    df = df.astype(str)
    return df


# ===============================================
# Merge FO Contract DP and BhavCopy
# ===============================================

def get_merged_fo_eqd_contract_dp_bhavcopy_df(bdate: str) -> pd.DataFrame:
    """
    Merge BSE FO EQD contract, DP, and bhavcopy data.
    """
    missing_files: List[str] = []
    eqd_contract_df = eqd_dp_df = bhavcopy_df = None
    
    # Collect required missing files before raising error
    try:
        eqd_contract_df = get_bse_eqd_contract_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))
    
    try:
        eqd_dp_df = get_bse_eqd_dp_contract_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))
    
    try:
        bhavcopy_df = get_fo_bhavcopy_bse_df(bdate)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Proceeding without BSE FO Bhavcopy data.")
        bhavcopy_df = pd.DataFrame(columns=[
            "FinInstrmId", "ISIN", "OpnPric", "HghPric", "LwPric", "ClsPric",
            "LastPric", "PrvsClsgPric", "UndrlygPric", "OpnIntrst", "TtlTradgVol", "TtlTrfVal"
        ])
    
    # Raise error if core contract/dp files are missing
    if missing_files:
        error_message = "\n".join(missing_files)
        raise FileNotFoundError(error_message)

    df = pd.merge(
        eqd_contract_df,
        eqd_dp_df,
        left_on="FinInstrmId",
        right_on="SeriesId",
        how="left",
        suffixes=("_contract", "_dp")
    )
    
    df = pd.merge(
        df,
        bhavcopy_df,
        left_on="FinInstrmId",
        right_on="FinInstrmId",
        how="left",
        suffixes=("", "_bhavcopy")
    )
    
    return df


# ===============================================
# Merge CM Scrip and BhavCopy
# ===============================================

def get_merged_cm_scrip_bhavcopy_df(bdate: str) -> pd.DataFrame:
    """
    Merge BSE CM scrip and bhavcopy data.
    """
    missing_files: List[str] = []
    cm_scrip_df = bhavcopy_df = dp_df = None
    
    # Collect required missing files before raising error
    try:
        cm_scrip_df = get_bse_eq_scrip_df(bdate)
    except FileNotFoundError as e:
        missing_files.append(str(e))
    
    try:
        dp_df = get_bse_cm_dp(bdate)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Proceeding without BSE CM DP file.")
        dp_df = pd.DataFrame(columns=["Scrip Code", "Previous Close Price", "Lower Circuit Price", "Upper Circuit Price"])

    try:
        bhavcopy_df = get_cm_bhavcopy_bse_df(bdate)
    except FileNotFoundError as e:
        print(f"Warning: {e}. Proceeding without BSE CM Bhavcopy file.")
        bhavcopy_df = pd.DataFrame(columns=[
            "FinInstrmId", "ISIN", "OpnPric", "HghPric", "LwPric", "ClsPric",
            "LastPric", "PrvsClsgPric", "UndrlygPric", "OpnIntrst", "TtlTradgVol", "TtlTrfVal"
        ])
    
    # Raise error if core scrip file is missing
    if missing_files:
        error_message = "\n".join(missing_files)
        raise FileNotFoundError(error_message)

    df = pd.merge(
        cm_scrip_df,
        bhavcopy_df,
        left_on="FinInstrmId",
        right_on="FinInstrmId",
        how="left",
        suffixes=("_scrip", "_bhavcopy")
    )
    
    df = pd.merge(
        df,
        dp_df,
        left_on="FinInstrmId",
        right_on="Scrip Code",
        how="left",
        suffixes=("", "_dp")
    )

    return df
