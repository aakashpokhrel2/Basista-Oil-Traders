"""
Middleware to synchronize the active gettext language with the logged-in user's saved preference.
"""

from django.utils.translation import activate, get_language

class UserLanguageMiddleware:
    """
    If the user is authenticated, ensure the UI renders in their saved preferred language,
    unless an explicit session language override is active.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            user_pref = getattr(request.user, 'language_preference', None)
            session_lang = request.session.get('django_language')

            # If user has an explicit preference and no temporary session conflict, activate it
            if user_pref and user_pref in ['en', 'ne'] and not session_lang:
                activate(user_pref)
                request.session['django_language'] = user_pref
            elif session_lang and session_lang != user_pref:
                # If session has a differing preference, update user model to match
                request.user.language_preference = session_lang
                request.user.save(update_fields=['language_preference'])

        response = self.get_response(request)
        return response
