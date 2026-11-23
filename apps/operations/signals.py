"""
Signals for operations app: initializes default shift schedules on migrate.
"""

from datetime import time
from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def create_default_shift_schedules(sender, **kwargs):
    if sender.name != 'apps.operations':
        return

    from apps.operations.models import ShiftSchedule

    schedules = [
        {
            'name_en': 'Day Shift (06:00 - 14:00)',
            'name_ne': 'दिवा सिफ्ट (०६:०० - १४:००)',
            'start_time': time(6, 0),
            'end_time': time(14, 0),
        },
        {
            'name_en': 'Evening Shift (14:00 - 22:00)',
            'name_ne': 'साँझको सिफ्ट (१४:०० - २२:००)',
            'start_time': time(14, 0),
            'end_time': time(22, 0),
        },
        {
            'name_en': 'Night Shift (22:00 - 06:00)',
            'name_ne': 'रात्रिकालीन सिफ्ट (२२:०० - ०६:००)',
            'start_time': time(22, 0),
            'end_time': time(6, 0),
        },
    ]

    for item in schedules:
        ShiftSchedule.objects.get_or_create(
            name_en=item['name_en'],
            defaults=item
        )
