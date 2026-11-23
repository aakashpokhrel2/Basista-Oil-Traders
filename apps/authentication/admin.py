from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from apps.authentication.models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'language_preference')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number', 'employee_id')
    ordering = ('role', 'username')

    fieldsets = BaseUserAdmin.fieldsets + (
        (_('Station Information & Role'), {
            'fields': ('role', 'phone_number', 'employee_id', 'address', 'language_preference'),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_('Station Information & Role'), {
            'fields': ('role', 'phone_number', 'employee_id', 'address', 'language_preference'),
        }),
    )
