"""
Date and business day utilities for trading refdata and contract download flows.
Includes holiday calendars, business date generators, previous business day calculations,
and exchange epoch conversion helpers.
"""

from datetime import date, datetime, timedelta
from typing import Any, Iterable, List, Optional, Set, Union

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

import pandas as pd


# ==============================================================================
# SAMPLE HOLIDAY CALENDAR (Weekdays)
# Note: Users can override/extend this via `set_holidays` or `add_holidays`.
# ==============================================================================

# Sample weekday trading holidays for Indian Exchanges (NSE / BSE / MCX)
# Format: YYYY-MM-DD
SAMPLE_NSE_HOLIDAYS = {
    # 2024 Holidays
    date(2024, 1, 22),  # Special Holiday (Ram Mandir Pran Pratishtha)
    date(2024, 1, 26),  # Republic Day (Friday)
    date(2024, 3, 8),  # Mahashivratri (Friday)
    date(2024, 3, 25),  # Holi (Monday)
    date(2024, 3, 29),  # Good Friday (Friday)
    date(2024, 4, 11),  # Id-Ul-Fitr (Ramzan Id) (Thursday)
    date(2024, 4, 17),  # Shri Ram Navami (Wednesday)
    date(2024, 5, 1),  # Maharashtra Day (Wednesday)
    date(2024, 5, 20),  # General Parliamentary Elections (Monday)
    date(2024, 6, 17),  # Bakri Id (Monday)
    date(2024, 7, 17),  # Moharram (Wednesday)
    date(2024, 8, 15),  # Independence Day (Thursday)
    date(2024, 10, 2),  # Mahatma Gandhi Jayanti (Wednesday)
    date(2024, 11, 1),  # Diwali * Laxmi Pujan (Friday)
    date(2024, 11, 15),  # Gurunanak Jayanti (Friday)
    date(2024, 11, 20),  # Maharashtra Assembly Elections (Wednesday)
    date(2024, 12, 25),  # Christmas (Wednesday)
    # 2025 Holidays
    date(2025, 2, 26),  # Mahashivratri (Wednesday)
    date(2025, 3, 14),  # Holi (Friday)
    date(2025, 3, 31),  # Id-Ul-Fitr (Monday)
    date(2025, 4, 10),  # Shri Mahavir Jayanti (Thursday)
    date(2025, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti (Monday)
    date(2025, 4, 18),  # Good Friday (Friday)
    date(2025, 5, 1),  # Maharashtra Day (Thursday)
    date(2025, 8, 15),  # Independence Day (Friday)
    date(2025, 8, 27),  # Ganesh Chaturthi (Wednesday)
    date(2025, 10, 2),  # Mahatma Gandhi Jayanti / Dussehra (Thursday)
    date(2025, 10, 21),  # Diwali * Laxmi Pujan (Tuesday)
    date(2025, 10, 22),  # Diwali Balipratipada (Wednesday)
    date(2025, 11, 5),  # Prakash Gurpurb Sri Guru Nanak Dev (Wednesday)
    date(2025, 12, 25),  # Christmas (Thursday)
    # 2026 Holidays
    date(2026, 1, 26),  # Republic Day (Monday)
    date(2026, 2, 16),  # Mahashivratri (Monday)
    date(2026, 3, 4),  # Holi (Wednesday)
    date(2026, 3, 20),  # Id-Ul-Fitr (Friday)
    date(2026, 3, 31),  # Mahavir Jayanti (Tuesday)
    date(2026, 4, 3),  # Good Friday (Friday)
    date(2026, 4, 14),  # Dr. Ambedkar Jayanti (Tuesday)
    date(2026, 5, 1),  # Maharashtra Day (Friday)
    date(2026, 5, 28),  # Bakri Id (Thursday)
    date(2026, 6, 26),  # Muharram (Friday)
    date(2026, 8, 15),  # Independence Day (Saturday)
    date(2026, 10, 2),  # Mahatma Gandhi Jayanti (Friday)
    date(2026, 10, 20),  # Dussehra (Tuesday)
    date(2026, 11, 9),  # Diwali Laxmi Pujan (Monday)
    date(2026, 11, 24),  # Gurunanak Jayanti (Tuesday)
    date(2026, 12, 25),  # Christmas (Friday)
}

# Global holidays mapping
EXCHANGE_HOLIDAYS: dict[str, Set[date]] = {
    "NSE": set(SAMPLE_NSE_HOLIDAYS),
    "BSE": set(SAMPLE_NSE_HOLIDAYS),
    "MCX": set(SAMPLE_NSE_HOLIDAYS),
    "DEFAULT": set(SAMPLE_NSE_HOLIDAYS),
}


# ==============================================================================
# Holiday Management Helpers
# ==============================================================================


def _parse_to_date(d: Any) -> date:
    """Helper to convert various date-like objects to datetime.date."""
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, pd.Timestamp):
        return d.date()
    if isinstance(d, str):
        cleaned = d.strip()
        for fmt in (
            "%Y-%m-%d",
            "%Y%m%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d %B %Y",
            "%d-%b-%Y",
        ):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
        return pd.to_datetime(cleaned).date()
    if isinstance(d, (int, float)):
        s = str(int(d))
        if len(s) == 8:
            return datetime.strptime(s, "%Y%m%d").date()
    raise ValueError(f"Unable to parse date: {d}")


def _parse_to_datetime(d: Any) -> datetime:
    """Helper to convert various date-like objects to datetime.datetime."""
    if isinstance(d, datetime):
        return d
    if isinstance(d, date):
        return datetime.combine(d, datetime.min.time())
    if isinstance(d, pd.Timestamp):
        return d.to_pydatetime()
    if isinstance(d, str):
        cleaned = d.strip()
        for fmt in (
            "%Y-%m-%d",
            "%Y%m%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%d %B %Y",
            "%d-%b-%Y",
        ):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return pd.to_datetime(cleaned).to_pydatetime()
    if isinstance(d, (int, float)):
        s = str(int(d))
        if len(s) == 8:
            return datetime.strptime(s, "%Y%m%d")
    raise ValueError(f"Unable to parse datetime: {d}")


def set_holidays(exchange: str, holidays: Iterable[Union[date, datetime, str]]) -> None:
    """
    Override the holiday list for a specific exchange.

    Args:
        exchange (str): Exchange name ('NSE', 'BSE', 'MCX', etc.)
        holidays (Iterable): List/Set of dates or date strings
    """
    exch_key = exchange.upper().strip()
    parsed = {_parse_to_date(h) for h in holidays}
    EXCHANGE_HOLIDAYS[exch_key] = parsed


def add_holidays(exchange: str, holidays: Iterable[Union[date, datetime, str]]) -> None:
    """
    Add holidays to an existing exchange holiday list.

    Args:
        exchange (str): Exchange name ('NSE', 'BSE', 'MCX', etc.)
        holidays (Iterable): List/Set of dates or date strings
    """
    exch_key = exchange.upper().strip()
    if exch_key not in EXCHANGE_HOLIDAYS:
        EXCHANGE_HOLIDAYS[exch_key] = set()
    for h in holidays:
        EXCHANGE_HOLIDAYS[exch_key].add(_parse_to_date(h))


def get_holidays(exchange: str = "NSE") -> Set[date]:
    """
    Get the set of holiday dates for an exchange.

    Args:
        exchange (str): Exchange identifier (e.g. 'NSE', 'BSE', 'MCX')

    Returns:
        Set[date]: Set of holiday dates
    """
    exch_key = exchange.upper().strip() if exchange else "DEFAULT"
    return EXCHANGE_HOLIDAYS.get(exch_key, EXCHANGE_HOLIDAYS.get("DEFAULT", set()))


def is_holiday(d: Union[date, datetime, str], exchange: str = "NSE") -> bool:
    """
    Check if a given date is a trading holiday for the specified exchange.
    """
    target_date = _parse_to_date(d)
    holidays = get_holidays(exchange)
    return target_date in holidays


def is_business_day(d: Union[date, datetime, str], exchange: str = "NSE") -> bool:
    """
    Check if a given date is an active business day (weekday and not a holiday).
    """
    target_date = _parse_to_date(d)
    # Saturday = 5, Sunday = 6
    if target_date.weekday() >= 5:
        return False
    return not is_holiday(target_date, exchange=exchange)


# ==============================================================================
# Business Date Calculation Functions
# ==============================================================================


def get_prev_businessday(
    bdate: Union[date, datetime, str, pd.Timestamp, None] = None,
    apply_holidays: Optional[str] = "NSE",
    business_date: Union[date, datetime, str, pd.Timestamp, None] = None,
) -> datetime:
    """
    Calculate the previous business day for a given date.
    Steps back day-by-day skipping weekends and holidays.

    Args:
        bdate: Input date (defaults to current date if None or empty)
        apply_holidays: Exchange holiday calendar to use (e.g. 'NSE', 'BSE', 'MCX', or None)
        business_date: Alias for bdate parameter

    Returns:
        datetime: Previous business day as a datetime object
    """
    target = bdate if bdate is not None else business_date
    if target is None or target == "":
        cur_dt = datetime.now()
    else:
        cur_dt = _parse_to_datetime(target)

    cur_date = cur_dt.date() - timedelta(days=1)

    while True:
        # Check weekend
        if cur_date.weekday() >= 5:
            cur_date -= timedelta(days=1)
            continue

        # Check holiday if specified
        if apply_holidays and is_holiday(cur_date, exchange=apply_holidays):
            cur_date -= timedelta(days=1)
            continue

        break

    return datetime.combine(cur_date, datetime.min.time())


def get_business_dates(
    bdate: Union[str, date, datetime, None] = "",
    timezone: str = "Asia/Kolkata",
    use_holidays: Optional[str] = "NSE",
) -> List[datetime]:
    """
    Generate a list of business dates (datetime objects) based on input.
    Supports single date strings, date ranges ('YYYYMMDD:YYYYMMDD'),
    lists of dates, or empty string (current business date).

    Args:
        bdate: Single date, date range string, list of dates, or '' for today
        timezone: Timezone for resolving today's date
        use_holidays: Exchange holiday calendar to filter against

    Returns:
        List[datetime]: List of business dates as datetime objects
    """
    # Case 1: Empty or None -> Return today's business date
    if bdate is None or bdate == "":
        if ZoneInfo is not None:
            try:
                now = datetime.now(ZoneInfo(timezone))
            except Exception:
                now = datetime.now()
        else:
            now = datetime.now()

        today_date = now.date()
        return [datetime.combine(today_date, datetime.min.time())]

    # Case 2: List or collection of dates
    if isinstance(bdate, (list, tuple, set)):
        result = []
        for item in bdate:
            result.extend(
                get_business_dates(item, timezone=timezone, use_holidays=use_holidays)
            )
        return result

    # Case 3: Single datetime or date object
    if isinstance(bdate, (datetime, date, pd.Timestamp)):
        return [_parse_to_datetime(bdate)]

    # Case 4: String processing
    if isinstance(bdate, str):
        cleaned = bdate.strip()

        # Check for range: 'YYYYMMDD:YYYYMMDD' or 'YYYY-MM-DD:YYYY-MM-DD'
        separator = None
        if ":" in cleaned:
            separator = ":"
        elif " to " in cleaned.lower():
            separator = " to "
        elif ".." in cleaned:
            separator = ".."

        if separator:
            start_str, end_str = cleaned.split(separator, 1)
            start_dt = _parse_to_date(start_str.strip())
            end_dt = _parse_to_date(end_str.strip())

            dates_list: List[datetime] = []
            curr = start_dt
            while curr <= end_dt:
                if is_business_day(curr, exchange=use_holidays or "NSE"):
                    dates_list.append(datetime.combine(curr, datetime.min.time()))
                curr += timedelta(days=1)
            return dates_list

        # Comma-separated list of dates: '20241101,20241102'
        if "," in cleaned:
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            return [
                get_business_dates(p, timezone=timezone, use_holidays=use_holidays)[0]
                for p in parts
            ]

        # Single date string
        parsed_dt = _parse_to_datetime(cleaned)
        return [parsed_dt]

    raise ValueError(f"Unsupported bdate format: {bdate}")


def generate_business_dates(
    business_date_str: str = "",
    use_holidays: str = "NSE",
    weekdays_only: bool = True,
    format_str: str = "%Y%m%d",
    timezone: str = "Asia/Kolkata",
) -> List[str]:
    """
    Generate business date strings formatted as YYYYMMDD (or custom format)
    for contract master generation and related flows.

    Args:
        business_date_str: Date or range string ('', 'YYYYMMDD', 'YYYYMMDD:YYYYMMDD')
        use_holidays: Exchange holiday filter ('NSE', 'BSE', 'MCX', etc.)
        weekdays_only: Whether to strictly exclude Saturday & Sunday
        format_str: Output date string format (defaults to '%Y%m%d')
        timezone: Target timezone for current date resolution (default 'Asia/Kolkata')

    Returns:
        List[str]: List of date strings
    """
    dt_list = get_business_dates(business_date_str, use_holidays=use_holidays, timezone=timezone)

    output = []
    for dt in dt_list:
        d = dt.date()
        if weekdays_only and d.weekday() >= 5:
            continue
        if use_holidays and is_holiday(d, exchange=use_holidays):
            continue
        output.append(dt.strftime(format_str))

    if not output and (business_date_str == "" or business_date_str is None):
        output = [datetime.now().strftime(format_str)]

    return output


# ==============================================================================
# Exchange Epoch Conversion Utilities
# ==============================================================================

# NSE Epoch starts at 1980-01-01 00:00:00
NSE_EPOCH_BASE = datetime(1980, 1, 1, 0, 0, 0)
UNIX_EPOCH_BASE = datetime(1970, 1, 1, 0, 0, 0)


def convert_nse_epoch_to_datetime(
    epoch: Union[int, float, str, None],
) -> Optional[datetime]:
    """
    Convert NSE epoch seconds (seconds since 1980-01-01 00:00:00) to datetime.

    Args:
        epoch: Epoch timestamp in seconds from 1980-01-01

    Returns:
        datetime or None if epoch is invalid/NaN/-1
    """
    if epoch is None or pd.isna(epoch):
        return None
    try:
        sec = int(epoch)
        if sec < 0:
            return None
        return NSE_EPOCH_BASE + timedelta(seconds=sec)
    except (ValueError, OverflowError):
        return None


def convert_datetime_to_nse_epoch(
    dt: Union[datetime, date, str, pd.Timestamp, None],
) -> int:
    """
    Convert datetime or date string to NSE epoch (seconds since 1980-01-01 00:00:00).

    Args:
        dt: Date or datetime object / string

    Returns:
        int: Seconds since 1980-01-01 00:00:00, or -1 if invalid
    """
    if dt is None or pd.isna(dt):
        return -1
    try:
        parsed_dt = _parse_to_datetime(dt)
        diff = (parsed_dt - NSE_EPOCH_BASE).total_seconds()
        return int(diff) if diff >= 0 else -1
    except Exception:
        return -1


def convert_mcx_epoch_to_datetime(
    epoch: Union[int, float, str, None],
) -> Optional[datetime]:
    """
    Convert MCX epoch (seconds or milliseconds since 1970-01-01 Unix epoch) to datetime.

    Args:
        epoch: Epoch timestamp

    Returns:
        datetime or None
    """
    if epoch is None or pd.isna(epoch):
        return None
    try:
        val = float(epoch)
        if val <= 0:
            return None
        if val > 1e11:
            val = val / 1000.0
        return datetime.fromtimestamp(val)
    except (ValueError, OverflowError, OSError):
        return None
