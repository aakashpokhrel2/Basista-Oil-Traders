"""
Role definitions, permission checks, decorators, and mixins for role-based access control (RBAC).
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.utils.translation import gettext_lazy as _
from common.roles import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    ROLE_CASHIER,
    ROLE_PUMP_OPERATOR,
    ROLE_CHOICES,
)

# Role Hierarchies and Permissions
ROLE_ACCESS_HIERARCHY = {
    ROLE_OWNER: {
        'can_manage_users': True,
        'can_view_audit_logs': True,
        'can_modify_fuel_prices': True,
        'can_access_financial_reports': True,
        'can_manage_inventory': True,
        'can_enter_daily_sales': True,
        'can_manage_credit': True,
        'can_record_expenses': True,
        'can_record_meter_reading': True,
    },
    ROLE_MANAGER: {
        'can_manage_users': False,
        'can_view_audit_logs': False,
        'can_modify_fuel_prices': True,
        'can_access_financial_reports': True,
        'can_manage_inventory': True,
        'can_enter_daily_sales': True,
        'can_manage_credit': True,
        'can_record_expenses': True,
        'can_record_meter_reading': True,
    },
    ROLE_ACCOUNTANT: {
        'can_manage_users': False,
        'can_view_audit_logs': False,
        'can_modify_fuel_prices': False,
        'can_access_financial_reports': True,
        'can_manage_inventory': False,
        'can_enter_daily_sales': False,
        'can_manage_credit': True,
        'can_record_expenses': True,
        'can_record_meter_reading': False,
    },
    ROLE_CASHIER: {
        'can_manage_users': False,
        'can_view_audit_logs': False,
        'can_modify_fuel_prices': False,
        'can_access_financial_reports': False,
        'can_manage_inventory': False,
        'can_enter_daily_sales': True,
        'can_manage_credit': False,
        'can_record_expenses': True,
        'can_record_meter_reading': True,
    },
    ROLE_PUMP_OPERATOR: {
        'can_manage_users': False,
        'can_view_audit_logs': False,
        'can_modify_fuel_prices': False,
        'can_access_financial_reports': False,
        'can_manage_inventory': False,
        'can_enter_daily_sales': False,
        'can_manage_credit': False,
        'can_record_expenses': False,
        'can_record_meter_reading': True,
    },
}


def role_required(allowed_roles):
    """
    Decorator to restrict view access to users with specified role(s).
    Redirects unauthenticated users to login, and returns 403 or redirects
    unauthorized users with an error message.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('authentication:login')

            # Superusers always have full access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(request.user, 'role', None)
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(
                request,
                _("You do not have permission to access this resource.")
            )
            return redirect('dashboard:index')

        return _wrapped_view
    return decorator


class RoleRequiredMixin(AccessMixin):
    """
    CBV mixin that verifies the current user has one of the allowed roles.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        user_role = getattr(request.user, 'role', None)
        if user_role not in self.allowed_roles:
            messages.error(
                request,
                _("You do not have permission to access this page.")
            )
            return redirect('dashboard:index')

        return super().dispatch(request, *args, **kwargs)


def owner_required(view_func):
    """Decorator restricting access exclusively to Owner / Administrator."""
    return role_required([ROLE_OWNER])(view_func)


def manager_or_owner_required(view_func):
    """Decorator allowing access to Owner and Manager."""
    return role_required([ROLE_OWNER, ROLE_MANAGER])(view_func)


def financial_access_required(view_func):
    """Decorator allowing access to Owner, Manager, and Accountant."""
    return role_required([ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT])(view_func)
