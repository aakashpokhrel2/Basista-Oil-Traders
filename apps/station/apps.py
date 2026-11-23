from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class StationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.station'
    verbose_name = _('Station & Fuel Configuration')

    def ready(self):
        import apps.station.signals  # noqa
