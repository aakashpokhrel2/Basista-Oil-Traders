"""
Authentication views: Login, Logout, Password Management, and User Administration.
"""

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.translation import activate, gettext_lazy as _
from django.views.generic import ListView, CreateView, UpdateView

from apps.authentication.forms import (
    UserLoginForm,
    UserPasswordChangeCustomForm,
    UserPasswordResetCustomForm,
    UserSetPasswordCustomForm,
    UserCreateAdminForm,
    UserUpdateAdminForm,
    UserProfileUpdateForm,
)
from apps.authentication.models import User
from apps.authentication.security import record_login_attempt, get_client_ip
from common.permissions import (
    ROLE_OWNER,
    ROLE_MANAGER,
    manager_or_owner_required,
    owner_required,
    RoleRequiredMixin,
)


class UserLoginView(LoginView):
    """Custom login view with bilingual support, rate-limiting audit, and redirection."""
    template_name = 'authentication/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()
        ip = get_client_ip(self.request)
        record_login_attempt(user.username, ip, is_successful=True)
        auth_login(self.request, user)

        # Set language session if user has a preference
        if user.language_preference:
            activate(user.language_preference)
            self.request.session['django_language'] = user.language_preference

        messages.success(
            self.request,
            _("Welcome back, %(name)s! Logged in successfully.") % {'name': user.get_full_name() or user.username}
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        username = form.data.get('username', '').strip()
        ip = get_client_ip(self.request)
        error_msg = '; '.join([str(err) for errs in form.errors.values() for err in errs])
        record_login_attempt(username, ip, is_successful=False, failure_reason=error_msg)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('dashboard:index')


def user_logout_view(request):
    """Custom logout view that handles session clearing and redirects with notification."""
    auth_logout(request)
    messages.info(request, _("You have been successfully logged out."))
    return redirect('authentication:login')


class UserPasswordChangeCustomView(PasswordChangeView):
    """Password change view."""
    template_name = 'authentication/password_change.html'
    form_class = UserPasswordChangeCustomForm
    success_url = reverse_lazy('authentication:password_change_done')

    def form_valid(self, form):
        messages.success(self.request, _("Your password has been changed successfully."))
        return super().form_valid(form)


def password_change_done_view(request):
    return render(request, 'authentication/password_change_done.html')


class UserPasswordResetCustomView(PasswordResetView):
    """Request password reset link via email."""
    template_name = 'authentication/password_reset.html'
    form_class = UserPasswordResetCustomForm
    email_template_name = 'authentication/password_reset_email.html'
    success_url = reverse_lazy('authentication:password_reset_done')


class UserPasswordResetDoneCustomView(PasswordResetDoneView):
    template_name = 'authentication/password_reset_done.html'


class UserPasswordResetConfirmCustomView(PasswordResetConfirmView):
    template_name = 'authentication/password_reset_confirm.html'
    form_class = UserSetPasswordCustomForm
    success_url = reverse_lazy('authentication:password_reset_complete')


class UserPasswordResetCompleteCustomView(PasswordResetCompleteView):
    template_name = 'authentication/password_reset_complete.html'


# ==============================================================================
# User Administration Views (Owner & Manager only)
# ==============================================================================

class UserListView(RoleRequiredMixin, ListView):
    """List staff users with filtering and role display."""
    model = User
    template_name = 'authentication/user_list.html'
    context_object_name = 'users'
    paginate_by = 15
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def get_queryset(self):
        qs = User.objects.all().order_by('role', 'first_name', 'username')
        q = self.request.GET.get('q', '').strip()
        role = self.request.GET.get('role', '').strip()
        status = self.request.GET.get('status', '').strip()

        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(employee_id__icontains=q)
            )
        if role:
            qs = qs.filter(role=role)
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['selected_role'] = self.request.GET.get('role', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class UserCreateView(RoleRequiredMixin, CreateView):
    """Create new staff user."""
    model = User
    form_class = UserCreateAdminForm
    template_name = 'authentication/user_form.html'
    success_url = reverse_lazy('authentication:user_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['performing_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save(commit=False)
        # Ensure staff flag is set for backend access if needed
        if user.role in [ROLE_OWNER, ROLE_MANAGER]:
            user.is_staff = True
        user.save()
        messages.success(
            self.request,
            _("User '%(username)s' created successfully.") % {'username': user.username}
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New User / Staff Member')
        context['button_text'] = _('Create User')
        return context


class UserUpdateView(RoleRequiredMixin, UpdateView):
    """Edit existing user details and role."""
    model = User
    form_class = UserUpdateAdminForm
    template_name = 'authentication/user_form.html'
    success_url = reverse_lazy('authentication:user_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['performing_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save(commit=False)
        if user.role in [ROLE_OWNER, ROLE_MANAGER]:
            user.is_staff = True
        user.save()
        messages.success(
            self.request,
            _("User '%(username)s' updated successfully.") % {'username': user.username}
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit User: %(name)s') % {'name': self.object.username}
        context['button_text'] = _('Save Changes')
        return context


@owner_required
def toggle_user_status_view(request, pk):
    """Activate or deactivate user account (Owner only)."""
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, _("You cannot deactivate your own account."))
        return redirect('authentication:user_list')

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    status_str = _("activated") if user.is_active else _("deactivated")
    messages.success(
        request,
        _("User '%(username)s' has been %(status)s.") % {'username': user.username, 'status': status_str}
    )
    return redirect('authentication:user_list')


@login_required
def profile_view(request):
    """User self-service profile page."""
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            # Update session language
            if user.language_preference:
                activate(user.language_preference)
                request.session['django_language'] = user.language_preference
            messages.success(request, _("Your profile has been updated."))
            return redirect('authentication:profile')
    else:
        form = UserProfileUpdateForm(instance=request.user)

    return render(request, 'authentication/profile.html', {'form': form})
