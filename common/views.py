"""
Common views including bilingual language switching helper and date conversion endpoints.
"""

from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import activate, gettext_lazy as _
from django.views.decorators.http import require_POST
from common.date_utils import ad_to_bs, bs_to_ad, format_bs_date, nepali_numerals

@require_POST
def switch_language(request):
    """
    Handle language change, saving preference to user profile if authenticated and setting cookie.
    """
    from django.conf import settings
    lang_code = request.POST.get('language', 'en')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    response = redirect(next_url)

    if lang_code in ['en', 'ne']:
        activate(lang_code)
        request.session['django_language'] = lang_code
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            lang_code,
            max_age=365 * 24 * 60 * 60,
            samesite='Lax'
        )
        if request.user.is_authenticated:
            request.user.language_preference = lang_code
            request.user.save(update_fields=['language_preference'])

    return response


def convert_date_api(request):
    """
    HTMX / JSON endpoint to convert between AD and BS dates.
    Query params:
      - mode: 'ad_to_bs' or 'bs_to_ad'
      - date: 'YYYY-MM-DD'
    """
    mode = request.GET.get('mode', 'ad_to_bs')
    date_str = request.GET.get('date', '')

    if not date_str:
        return JsonResponse({'error': 'Date parameter is required'}, status=400)

    try:
        if mode == 'ad_to_bs':
            bs_obj = ad_to_bs(date_str)
            return JsonResponse({
                'ad_date': date_str,
                'bs_date': f"{bs_obj.year:04d}-{bs_obj.month:02d}-{bs_obj.day:02d}",
                'bs_formatted_en': format_bs_date(bs_obj, lang='en'),
                'bs_formatted_ne': format_bs_date(bs_obj, lang='ne'),
            })
        else:
            ad_obj = bs_to_ad(date_str)
            return JsonResponse({
                'bs_date': date_str,
                'ad_date': ad_obj.strftime('%Y-%m-%d'),
                'ad_formatted': ad_obj.strftime('%A, %B %d, %Y'),
            })
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)
