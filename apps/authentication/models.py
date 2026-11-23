"""
Custom User Model for Petrol Station Management System.
Implements Role-Based Access Control and language preferences.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from common.roles import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    ROLE_CASHIER,
    ROLE_PUMP_OPERATOR,
    ROLE_CHOICES,
)


class User(AbstractUser):
    """
    Custom user model with station-specific roles and bilingual settings.
    """
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_PUMP_OPERATOR,
        verbose_name=_('Role'),
        db_index=True,
        help_text=_('Operational role determining system access and permissions.')
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name=_('Phone Number'),
        help_text=_('Contact number (e.g. 98XXXXXXXX)')
    )
    language_preference = models.CharField(
        max_length=5,
        choices=[
            ('en', _('English')),
            ('ne', _('Nepali (नेपाली)')),
        ],
        default='en',
        verbose_name=_('Language Preference'),
        help_text=_('Preferred user interface language')
    )
    employee_id = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('Employee ID / Code'),
        help_text=_('Unique station identification code (e.g. EMP-001)')
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Address'),
        help_text=_('Current residential address in Nepal')
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['role', 'username']

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return f"{full_name} ({self.get_role_display()})"
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_owner(self) -> bool:
        return self.is_superuser or self.role == ROLE_OWNER

    @property
    def is_manager(self) -> bool:
        return self.is_superuser or self.role in [ROLE_OWNER, ROLE_MANAGER]

    @property
    def is_accountant(self) -> bool:
        return self.is_superuser or self.role in [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    @property
    def is_cashier(self) -> bool:
        return self.is_superuser or self.role in [ROLE_OWNER, ROLE_MANAGER, ROLE_CASHIER]

    @property
    def is_pump_operator(self) -> bool:
        return self.role == ROLE_PUMP_OPERATOR

    @property
    def can_manage_users(self) -> bool:
        return self.is_superuser or self.role in [ROLE_OWNER, ROLE_MANAGER]

    @property
    def can_modify_fuel_prices(self) -> bool:
        return self.is_superuser or self.role in [ROLE_OWNER, ROLE_MANAGER]

    @property
    def can_view_financials(self) -> bool:
        return self.is_superuser or self.role in [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]


# Expose security login attempt model
from apps.authentication.security import LoginAttempt
