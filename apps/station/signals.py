"""
Signals for apps.station: seeds default FuelTypes and StationConfiguration after migration.
"""

from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def initialize_default_station_data(sender, **kwargs):
    """
    Ensure singleton station configuration and core fuel products exist.
    """
    if sender.name != 'apps.station':
        return

    from apps.station.models import StationConfiguration, FuelType

    # 1. Initialize StationConfiguration singleton
    StationConfiguration.get_solo()

    # 2. Initialize default fuels (Petrol MS & Diesel HSD)
    FuelType.objects.get_or_create(
        code='MS',
        defaults={
            'name_en': 'Petrol (MS)',
            'name_ne': 'पेट्रोल (MS)',
            'unit': 'Litre',
            'color_code': '#059669',
            'badge_class': 'badge-petrol',
            'display_order': 1,
            'is_active': True,
        }
    )

    FuelType.objects.get_or_create(
        code='HSD',
        defaults={
            'name_en': 'Diesel (HSD)',
            'name_ne': 'डिजेल (HSD)',
            'unit': 'Litre',
            'color_code': '#1e3a8a',
            'badge_class': 'badge-diesel',
            'display_order': 2,
            'is_active': True,
        }
    )
