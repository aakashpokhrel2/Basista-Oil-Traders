"""
Authentication forms styled with Tailwind CSS classes.
Includes brute-force lockout checking and managerial role restrictions.
"""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm as BaseUserCreationForm,
)
from django.utils.translation import gettext_lazy as _
from apps.authentication.models import User
from apps.authentication.security import check_login_lockout, get_client_ip
from common.permissions import ROLE_CHOICES, ROLE_OWNER, ROLE_MANAGER


class TailwindWidgetMixin:
    """Utility mixin to inject Tailwind CSS classes to form fields."""
    def apply_tailwind_classes(self):
        for field_name, field in self.fields.items():
            widget = field.widget
            widget_type = widget.__class__.__name__

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({
                    'class': 'h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500'
                })
            elif isinstance(widget, forms.Select):
                widget.attrs.update({
                    'class': 'w-full rounded-lg border border-gray-300 bg-white px-3.5 py-2.5 text-sm text-gray-900 shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20'
                })
            else:
                existing_class = widget.attrs.get('class', '')
                widget.attrs.update({
                    'class': f'{existing_class} w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 shadow-sm placeholder:text-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20'
                })


class UserLoginForm(AuthenticationForm, TailwindWidgetMixin):
    """Login form with modern styling, bilingual labels, and brute-force lockout checking."""
    username = forms.CharField(
        label=_('Username or Employee Code'),
        widget=forms.TextInput(attrs={
            'placeholder': _('Enter your username'),
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()

    def clean(self):
        username = self.cleaned_data.get('username')
        ip = get_client_ip(self.request) if hasattr(self, 'request') and self.request else ''
        if username:
            is_locked, remaining_mins = check_login_lockout(username, ip)
            if is_locked:
                raise forms.ValidationError(
                    _("Security Lockout: Too many failed login attempts! Account access temporarily locked. "
                      "Please wait %(mins)s minute(s) before trying again.") % {'mins': remaining_mins}
                )
        return super().clean()


class UserPasswordChangeCustomForm(PasswordChangeForm, TailwindWidgetMixin):
    """Password change form."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class UserPasswordResetCustomForm(PasswordResetForm, TailwindWidgetMixin):
    """Password reset request form."""
    email = forms.EmailField(
        label=_('Email Address'),
        widget=forms.EmailInput(attrs={'placeholder': _('name@example.com')})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class UserSetPasswordCustomForm(SetPasswordForm, TailwindWidgetMixin):
    """New password set form."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()


class UserCreateAdminForm(BaseUserCreationForm, TailwindWidgetMixin):
    """Form used by Owners/Managers to create new staff users."""
    first_name = forms.CharField(max_length=50, required=True, label=_('First Name'))
    last_name = forms.CharField(max_length=50, required=True, label=_('Last Name'))
    email = forms.EmailField(required=False, label=_('Email Address'))
    role = forms.ChoiceField(choices=ROLE_CHOICES, label=_('Role'))
    phone_number = forms.CharField(max_length=15, required=False, label=_('Phone Number'))
    employee_id = forms.CharField(max_length=30, required=False, label=_('Employee ID'))
    address = forms.CharField(max_length=255, required=False, label=_('Address'))
    language_preference = forms.ChoiceField(
        choices=[('en', _('English')), ('ne', _('Nepali'))],
        label=_('Default Language')
    )

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email', 'role',
            'phone_number', 'employee_id', 'address', 'language_preference', 'is_active',
        ]

    def __init__(self, *args, performing_user=None, **kwargs):
        self.performing_user = performing_user
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()

        # If performing user is not OWNER, disallow selecting Owner role
        if self.performing_user and not self.performing_user.is_owner:
            self.fields['role'].choices = [c for c in ROLE_CHOICES if c[0] != ROLE_OWNER]

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role == ROLE_OWNER and self.performing_user and not self.performing_user.is_owner:
            raise forms.ValidationError(_("Only an Owner can assign the Owner role."))
        return role


class UserUpdateAdminForm(forms.ModelForm, TailwindWidgetMixin):
    """Form used by Owners/Managers to edit user details and roles."""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'role',
            'phone_number', 'employee_id', 'address', 'language_preference', 'is_active',
        ]

    def __init__(self, *args, performing_user=None, **kwargs):
        self.performing_user = performing_user
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()

        # Non-owners cannot promote someone to Owner or edit an Owner's role
        if self.performing_user and not self.performing_user.is_owner:
            self.fields['role'].choices = [c for c in ROLE_CHOICES if c[0] != ROLE_OWNER]
            if self.instance and self.instance.is_owner:
                self.fields['role'].disabled = True
                self.fields['is_active'].disabled = True

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role == ROLE_OWNER and self.performing_user and not self.performing_user.is_owner:
            raise forms.ValidationError(_("Only an Owner can assign or modify the Owner role."))
        return role


class UserProfileUpdateForm(forms.ModelForm, TailwindWidgetMixin):
    """Self-service profile update form for logged-in user."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address', 'language_preference']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_tailwind_classes()
