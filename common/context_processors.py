"""
Context processors providing global petrol station metadata, bilingual station names,
and dual Gregorian (AD) / Bikram Sambat (BS) date information across all templates.
"""

from django.conf import settings
from django.utils import timezone
from django.utils.translation import get_language
from common.date_utils import (
    ad_to_bs,
    get_current_bs_date,
    format_bs_date,
    nepali_numerals,
)

def petrol_station_context(request):
    """
    Global template context variables.
    """
    now = timezone.localtime(timezone.now())
    today_ad = now.date()
    today_bs = ad_to_bs(today_ad)
    current_lang = get_language() or 'en'

    # Station name based on current active language
    try:
        from apps.station.models import StationConfiguration
        config = StationConfiguration.get_solo()
        station_name_en = config.station_name_en
        station_name_ne = config.station_name_ne
        station_location = config.station_address_ne if current_lang == 'ne' else config.station_address_en
        station_pan_vat = config.pan_vat_number
        station_currency = config.currency
        financial_year = config.financial_year
    except Exception:
        station_name_en = getattr(settings, 'STATION_NAME_EN', 'Basista Oil Traders')
        station_name_ne = getattr(settings, 'STATION_NAME_NE', 'बसिस्ट आयल ट्रेडर्स')
        station_location = getattr(settings, 'STATION_LOCATION', 'Kathmandu, Nepal')
        station_pan_vat = getattr(settings, 'STATION_PAN_VAT', '601234567')
        station_currency = 'NPR'
        financial_year = '2083/84'

    station_name = station_name_ne if current_lang == 'ne' else station_name_en

    # Format dates
    date_ad_formatted_en = today_ad.strftime('%A, %B %d, %Y')
    date_ad_formatted_ne = f"{today_ad.strftime('%Y-%m-%d')} AD"

    date_bs_formatted_en = format_bs_date(today_bs, lang='en', include_weekday=True)
    date_bs_formatted_ne = format_bs_date(today_bs, lang='ne', include_weekday=True)

    # Active user role
    user_role = None
    user_role_display = None
    if request.user.is_authenticated:
        user_role = getattr(request.user, 'role', None)
        if hasattr(request.user, 'get_role_display'):
            user_role_display = request.user.get_role_display()

    return {
        'station_name': station_name,
        'station_name_en': station_name_en,
        'station_name_ne': station_name_ne,
        'station_location': station_location,
        'station_pan_vat': station_pan_vat,
        'station_currency': station_currency,
        'financial_year': financial_year,
        'current_time_kathmandu': now,
        'current_ad_date': today_ad,
        'current_bs_date': today_bs,
        'date_ad_formatted_en': date_ad_formatted_en,
        'date_ad_formatted_ne': date_ad_formatted_ne,
        'date_bs_formatted_en': date_bs_formatted_en,
        'date_bs_formatted_ne': date_bs_formatted_ne,
        'user_role': user_role,
        'user_role_display': user_role_display,
        'active_language': current_lang,
    }
