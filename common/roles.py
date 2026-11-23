"""
Station operational roles and constant definitions.
Free of Django auth imports to prevent circular dependencies during app model registration.
"""

from django.utils.translation import gettext_lazy as _

# Station Roles
ROLE_OWNER = 'OWNER'
ROLE_MANAGER = 'MANAGER'
ROLE_ACCOUNTANT = 'ACCOUNTANT'
ROLE_CASHIER = 'CASHIER'
ROLE_PUMP_OPERATOR = 'PUMP_OPERATOR'

ROLE_CHOICES = [
    (ROLE_OWNER, _('Owner / Administrator')),
    (ROLE_MANAGER, _('Manager')),
    (ROLE_ACCOUNTANT, _('Accountant')),
    (ROLE_CASHIER, _('Cashier')),
    (ROLE_PUMP_OPERATOR, _('Pump Operator')),
]
