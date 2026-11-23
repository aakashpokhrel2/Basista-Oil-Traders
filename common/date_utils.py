"""
Date conversion and formatting utilities for Gregorian (AD) and Bikram Sambat (BS).
Uses nepali-datetime library for verified Nepal calendar calculations.
"""

from datetime import date, datetime
import re
from decimal import Decimal
import nepali_datetime
from django.utils import timezone

# Devanagari digit translation table
DEVANAGARI_DIGITS = {
    '0': '०', '1': '१', '2': '२', '3': '३', '4': '४',
    '5': '५', '6': '६', '7': '७', '8': '८', '9': '९',
}

ENGLISH_DIGITS = {v: k for k, v in DEVANAGARI_DIGITS.items()}

# Nepali BS Month Names
BS_MONTHS_EN = [
    '', 'Baishakh', 'Jestha', 'Ashadh', 'Shrawan', 'Bhadra', 'Ashwin',
    'Kartik', 'Mangsir', 'Poush', 'Magh', 'Falgun', 'Chaitra'
]

BS_MONTHS_NE = [
    '', 'वैशाख', 'जेठ', 'असार', 'साउन', 'भदौ', 'असोज',
    'कात्तिक', 'मंसिर', 'पुस', 'माघ', 'फागुन', 'चैत'
]

WEEKDAYS_EN = [
    'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'
]

WEEKDAYS_NE = [
    'आइतबार', 'सोमबार', 'मङ्गलबार', 'बुधबार', 'बिहीबार', 'शुक्रबार', 'शनिबार'
]


def nepali_numerals(value) -> str:
    """
    Convert ASCII numerals in a string/number to Devanagari numerals.
    Examples: 1234 -> १२३४, 2083-08-07 -> २०८३-०८-०७
    """
    if value is None:
        return ''
    val_str = str(value)
    return ''.join(DEVANAGARI_DIGITS.get(char, char) for char in val_str)


def nepali_to_english_numerals(value: str) -> str:
    """
    Convert Devanagari numerals to standard ASCII numerals.
    Example: २०८३-०८-०७ -> 2083-08-07
    """
    if not value:
        return ''
    return ''.join(ENGLISH_DIGITS.get(char, char) for char in str(value))


def ad_to_bs(ad_date) -> nepali_datetime.date:
    """
    Convert Gregorian (AD) date or datetime to Bikram Sambat (BS) date.
    Accepts datetime.date, datetime.datetime, or ISO date string (YYYY-MM-DD).
    """
    if ad_date is None:
        return None

    if isinstance(ad_date, str):
        ad_date = datetime.strptime(ad_date.strip(), '%Y-%m-%d').date()
    elif isinstance(ad_date, datetime):
        # Convert timezone-aware datetimes to local time zone
        if timezone.is_aware(ad_date):
            ad_date = timezone.localtime(ad_date).date()
        else:
            ad_date = ad_date.date()

    return nepali_datetime.date.from_datetime_date(ad_date)


def bs_to_ad(bs_date_input) -> date:
    """
    Convert Bikram Sambat (BS) date to Gregorian (AD) date.
    Accepts nepali_datetime.date object or string formatted as 'YYYY-MM-DD' or 'YYYY/MM/DD'.
    Handles both ASCII and Devanagari numerals.
    """
    if bs_date_input is None:
        return None

    if isinstance(bs_date_input, nepali_datetime.date):
        return bs_date_input.to_datetime_date()

    if isinstance(bs_date_input, str):
        # Normalize devanagari numerals if present
        clean_str = nepali_to_english_numerals(bs_date_input.strip())
        parts = re.split(r'[-/.]', clean_str)
        if len(parts) == 3:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            bs_obj = nepali_datetime.date(year, month, day)
            return bs_obj.to_datetime_date()

    raise ValueError(f"Invalid BS date format: {bs_date_input}")


def get_current_bs_date() -> nepali_datetime.date:
    """
    Get current date in Bikram Sambat (BS) based on Asia/Kathmandu time.
    """
    now_ad = timezone.localtime(timezone.now()).date()
    return ad_to_bs(now_ad)


def format_bs_date(bs_date, lang='en', include_weekday=True) -> str:
    """
    Format a Bikram Sambat date into user-friendly text in English or Nepali.
    Example EN: Mangsir 07, 2083 (Monday)
    Example NE: मंसिर ०७, २०८३, सोमबार
    """
    if bs_date is None:
        return ''

    if isinstance(bs_date, (date, datetime)):
        bs_date = ad_to_bs(bs_date)
    elif isinstance(bs_date, str):
        clean_str = nepali_to_english_numerals(bs_date.strip())
        parts = re.split(r'[-/.]', clean_str)
        if len(parts) == 3:
            bs_date = nepali_datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            return bs_date

    year = bs_date.year
    month = bs_date.month
    day = bs_date.day
    # weekday in nepali_datetime is 0=Monday .. 6=Sunday
    weekday_idx = bs_date.weekday()

    if lang == 'ne':
        m_name = BS_MONTHS_NE[month]
        w_name = WEEKDAYS_NE[weekday_idx]
        formatted = f"{m_name} {nepali_numerals(f'{day:02d}')}, {nepali_numerals(year)}"
        if include_weekday:
            formatted += f", {w_name}"
        return formatted
    else:
        m_name = BS_MONTHS_EN[month]
        w_name = WEEKDAYS_EN[weekday_idx]
        formatted = f"{m_name} {day:02d}, {year}"
        if include_weekday:
            formatted += f" ({w_name})"
        return formatted


def format_currency_npr(amount, lang='en') -> str:
    """
    Format currency in Nepalese Rupee format (lakhs / crores grouping).
    e.g. 1250000.50 -> 12,50,000.50 / १२,५०,०००.५०
    """
    if amount is None or amount == '':
        return '0.00'

    try:
        val = Decimal(str(amount))
    except Exception:
        return str(amount)

    is_negative = val < 0
    val = abs(val)

    # Split into integer and 2-decimal fractional part
    formatted_val = f"{val:.2f}"
    int_part, dec_part = formatted_val.split('.')

    # South Asian numbering system:
    # Last 3 digits grouped together, preceding digits grouped in pairs of 2.
    if len(int_part) <= 3:
        grouped_int = int_part
    else:
        last3 = int_part[-3:]
        remaining = int_part[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        grouped_int = ','.join(groups) + ',' + last3

    result = f"{'-' if is_negative else ''}{grouped_int}.{dec_part}"

    if lang == 'ne':
        return f"रु {nepali_numerals(result)}"
    return f"NPR {result}"


def get_days_in_bs_month(year: int, month: int) -> int:
    """
    Get total days in a specific Bikram Sambat month and year.
    """
    if hasattr(nepali_datetime, '_days_in_month'):
        return nepali_datetime._days_in_month(year, month)
    # Fallback by probing valid days
    for d in range(32, 28, -1):
        try:
            nepali_datetime.date(year, month, d)
            return d
        except Exception:
            continue
    return 30


def get_bs_month_date_range(year: int, month: int) -> tuple[date, date]:
    """
    Get Gregorian (AD) date range (start_ad, end_ad) corresponding to a BS month.
    Crucial for filtering database records stored in Gregorian format by BS month.
    """
    days = get_days_in_bs_month(year, month)
    bs_start = nepali_datetime.date(year, month, 1)
    bs_end = nepali_datetime.date(year, month, days)
    return bs_start.to_datetime_date(), bs_end.to_datetime_date()


def get_current_fiscal_year_bs(as_of_bs_date=None) -> str:
    """
    Compute Nepal Fiscal Year string (e.g. '2083/84' or '2083/084').
    Nepal fiscal year runs from Shrawan 1 (Month 4) to Ashadh end (Month 3).
    """
    if as_of_bs_date is None:
        as_of_bs_date = get_current_bs_date()
    elif isinstance(as_of_bs_date, (date, datetime)):
        as_of_bs_date = ad_to_bs(as_of_bs_date)

    year = as_of_bs_date.year
    month = as_of_bs_date.month

    if month >= 4:
        next_yr_short = (year + 1) % 100
        return f"{year}/{next_yr_short:02d}"
    else:
        prev_yr = year - 1
        curr_yr_short = year % 100
        return f"{prev_yr}/{curr_yr_short:02d}"


def get_fiscal_year_date_range(fiscal_year_str: str) -> tuple[date, date]:
    """
    Get Gregorian (AD) date range for a Nepal fiscal year (e.g. '2083/84' or '2083/084').
    Starts Shrawan 1 (Month 4) and ends Ashadh end (Month 3) of next BS year.
    """
    clean_str = nepali_to_english_numerals(fiscal_year_str.strip())
    parts = re.split(r'[-/]', clean_str)
    start_year = int(parts[0])

    bs_start = nepali_datetime.date(start_year, 4, 1)  # Shrawan 1
    end_year = start_year + 1
    days_in_ashadh = get_days_in_bs_month(end_year, 3)
    bs_end = nepali_datetime.date(end_year, 3, days_in_ashadh)  # Ashadh end

    return bs_start.to_datetime_date(), bs_end.to_datetime_date()


def get_all_bs_months(lang='en') -> list[tuple[int, str]]:
    """
    Get list of all 12 BS months as (month_number, month_name) tuples for forms and filters.
    """
    months = BS_MONTHS_NE if lang == 'ne' else BS_MONTHS_EN
    return [(i, months[i]) for i in range(1, 13)]

