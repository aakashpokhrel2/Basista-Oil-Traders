"""
Custom template filters and tags for Bikram Sambat dates, Devanagari numbers, and bilingual formatting.
"""

from django import template
from django.utils.translation import get_language
from common.date_utils import (
    ad_to_bs,
    format_bs_date,
    nepali_numerals,
    format_currency_npr,
    nepali_to_english_numerals,
)

register = template.Library()


@register.filter(name='to_bs')
def to_bs(value, fmt='iso'):
    """
    Convert Gregorian (AD) date to Bikram Sambat (BS).
    Usage: {{ order.created_at|to_bs }} or {{ date|to_bs:"friendly" }}
    """
    if not value:
        return ''

    bs_date = ad_to_bs(value)
    if not bs_date:
        return ''

    current_lang = get_language() or 'en'

    if fmt == 'iso':
        return f"{bs_date.year:04d}-{bs_date.month:02d}-{bs_date.day:02d} BS"
    elif fmt == 'devanagari':
        return format_bs_date(bs_date, lang='ne', include_weekday=False)
    elif fmt == 'full':
        return format_bs_date(bs_date, lang=current_lang, include_weekday=True)
    elif fmt == 'friendly':
        return format_bs_date(bs_date, lang=current_lang, include_weekday=False)

    return f"{bs_date.year:04d}-{bs_date.month:02d}-{bs_date.day:02d}"


@register.filter(name='ad_to_bs_nepali')
def ad_to_bs_nepali(value):
    """Alias for to_bs with friendly formatting."""
    return to_bs(value, fmt='friendly')


@register.filter(name='nepali_number')
def nepali_number(value):
    """
    Convert ASCII numerals to Devanagari numerals.
    Usage: {{ user.id|nepali_number }}
    """
    if value is None:
        return ''
    return nepali_numerals(str(value))


@register.filter(name='currency_npr')
def currency_npr(amount):
    """
    Format monetary amounts in Nepalese Rupees.
    Usage: {{ sale.total_amount|currency_npr }}
    """
    lang = get_language() or 'en'
    return format_currency_npr(amount, lang=lang)


@register.filter(name='role_badge_class')
def role_badge_class(role):
    """
    Return Tailwind CSS color classes for user role badge.
    """
    badges = {
        'OWNER': 'bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-200',
        'MANAGER': 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/40 dark:text-blue-200',
        'ACCOUNTANT': 'bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200',
        'CASHIER': 'bg-teal-100 text-teal-800 border-teal-300 dark:bg-teal-900/40 dark:text-teal-200',
        'PUMP_OPERATOR': 'bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-800 dark:text-slate-300',
    }
    return badges.get(role, 'bg-gray-100 text-gray-800 border-gray-300')


@register.filter(name='bs_month_name')
def bs_month_name(month_num):
    """Return BS month name based on active language."""
    from common.date_utils import BS_MONTHS_EN, BS_MONTHS_NE
    lang = get_language() or 'en'
    try:
        m = int(month_num)
        if 1 <= m <= 12:
            return BS_MONTHS_NE[m] if lang == 'ne' else BS_MONTHS_EN[m]
    except (ValueError, TypeError):
        pass
    return str(month_num)


@register.filter(name='percentage')
def percentage(value, total):
    """Compute percentage for progress bars and tank capacity gauges."""
    try:
        val = float(value)
        tot = float(total)
        if tot <= 0:
            return 0
        pct = (val / tot) * 100
        return round(min(max(pct, 0), 100), 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

