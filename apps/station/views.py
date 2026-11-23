"""
Views for Petrol Station Settings, Fuel Configuration, Tanks, Pumps, Nozzles, and Prices.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, CreateView, UpdateView

from apps.station.forms import (
    StationConfigurationForm,
    FuelTypeForm,
    StorageTankForm,
    PumpForm,
    NozzleForm,
    FuelPriceForm,
)
from apps.station.models import (
    StationConfiguration,
    FuelType,
    StorageTank,
    Pump,
    Nozzle,
    FuelPrice,
)
from common.permissions import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    RoleRequiredMixin,
    manager_or_owner_required,
    owner_required,
)


# ==============================================================================
# 1. Station Configuration View (Owner Only)
# ==============================================================================

@owner_required
def station_settings_view(request):
    """View and update single station configuration profile."""
    config = StationConfiguration.get_solo()

    if request.method == 'POST':
        form = StationConfigurationForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, _('Station settings updated successfully.'))
            return redirect('station:settings')
    else:
        form = StationConfigurationForm(instance=config)

    context = {
        'title': _('Station Profile & Configuration'),
        'form': form,
        'config': config,
    }
    return render(request, 'station/station_settings.html', context)


# ==============================================================================
# 2. Fuel Types CRUD
# ==============================================================================

class FuelTypeListView(RoleRequiredMixin, ListView):
    model = FuelType
    template_name = 'station/fuel_type_list.html'
    context_object_name = 'fuels'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        return FuelType.objects.annotate(
            tanks_count=Count('tanks', distinct=True),
            nozzles_count=Count('nozzles', distinct=True)
        ).order_by('display_order', 'name_en')


class FuelTypeCreateView(RoleRequiredMixin, CreateView):
    model = FuelType
    form_class = FuelTypeForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:fuel_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Fuel type '%(name)s' created successfully.") % {'name': self.object.name_en})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add Fuel Product')
        context['back_url'] = reverse_lazy('station:fuel_list')
        return context


class FuelTypeUpdateView(RoleRequiredMixin, UpdateView):
    model = FuelType
    form_class = FuelTypeForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:fuel_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Fuel type '%(name)s' updated successfully.") % {'name': self.object.name_en})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Fuel: %(name)s') % {'name': self.object.name_en}
        context['back_url'] = reverse_lazy('station:fuel_list')
        return context


@manager_or_owner_required
def fuel_type_toggle_view(request, pk):
    fuel = get_object_or_404(FuelType, pk=pk)
    fuel.is_active = not fuel.is_active
    fuel.save(update_fields=['is_active'])
    status_str = _("activated") if fuel.is_active else _("deactivated")
    messages.success(request, _("Fuel product '%(name)s' has been %(status)s.") % {'name': fuel.name_en, 'status': status_str})
    return redirect('station:fuel_list')


# ==============================================================================
# 3. Storage Tank Management
# ==============================================================================

class StorageTankListView(RoleRequiredMixin, ListView):
    model = StorageTank
    template_name = 'station/tank_list.html'
    context_object_name = 'tanks'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        return StorageTank.objects.select_related('fuel_type').annotate(
            nozzles_count=Count('nozzles')
        ).order_by('tank_number')


class StorageTankCreateView(RoleRequiredMixin, CreateView):
    model = StorageTank
    form_class = StorageTankForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:tank_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Storage tank '%(number)s' added.") % {'number': self.object.tank_number})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add Storage Tank')
        context['back_url'] = reverse_lazy('station:tank_list')
        return context


class StorageTankUpdateView(RoleRequiredMixin, UpdateView):
    model = StorageTank
    form_class = StorageTankForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:tank_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Storage tank '%(number)s' updated.") % {'number': self.object.tank_number})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Storage Tank: %(number)s') % {'number': self.object.tank_number}
        context['back_url'] = reverse_lazy('station:tank_list')
        return context


# ==============================================================================
# 4. Dispensing Pumps and Nozzles
# ==============================================================================

class PumpListView(RoleRequiredMixin, ListView):
    model = Pump
    template_name = 'station/pump_list.html'
    context_object_name = 'pumps'
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        return Pump.objects.prefetch_related(
            Prefetch('nozzles', queryset=Nozzle.objects.select_related('fuel_type', 'tank'))
        ).order_by('pump_number')


class PumpCreateView(RoleRequiredMixin, CreateView):
    model = Pump
    form_class = PumpForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:pump_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Pump #%(num)s created.") % {'num': self.object.pump_number})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add Dispensing Pump')
        context['back_url'] = reverse_lazy('station:pump_list')
        return context


class PumpUpdateView(RoleRequiredMixin, UpdateView):
    model = Pump
    form_class = PumpForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:pump_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Pump #%(num)s updated.") % {'num': self.object.pump_number})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Pump #%(num)s') % {'num': self.object.pump_number}
        context['back_url'] = reverse_lazy('station:pump_list')
        return context


class NozzleCreateView(RoleRequiredMixin, CreateView):
    model = Nozzle
    form_class = NozzleForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:pump_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def get_initial(self):
        initial = super().get_initial()
        pump_id = self.request.GET.get('pump')
        if pump_id:
            try:
                pump = Pump.objects.get(pk=pump_id)
                initial['pump'] = pump
                next_nozzle_num = pump.nozzles.count() + 1
                initial['nozzle_number'] = next_nozzle_num
                initial['nozzle_code'] = f"P{pump.pump_number}-N{next_nozzle_num}"
            except Pump.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Nozzle '%(code)s' added.") % {'code': self.object.nozzle_code})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add Dispensing Nozzle')
        context['back_url'] = reverse_lazy('station:pump_list')
        return context


class NozzleUpdateView(RoleRequiredMixin, UpdateView):
    model = Nozzle
    form_class = NozzleForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:pump_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Nozzle '%(code)s' updated.") % {'code': self.object.nozzle_code})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Nozzle: %(code)s') % {'code': self.object.nozzle_code}
        context['back_url'] = reverse_lazy('station:pump_list')
        return context


# ==============================================================================
# 5. Fuel Price Management & History
# ==============================================================================

class FuelPriceListView(RoleRequiredMixin, ListView):
    model = FuelPrice
    template_name = 'station/price_list.html'
    context_object_name = 'prices'
    paginate_by = 20
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER, ROLE_ACCOUNTANT]

    def get_queryset(self):
        qs = FuelPrice.objects.select_related('fuel_type', 'created_by', 'approved_by')
        fuel_code = self.request.GET.get('fuel', '').strip()
        status = self.request.GET.get('status', '').strip()

        if fuel_code:
            qs = qs.filter(fuel_type__code=fuel_code)
        if status:
            qs = qs.filter(approval_status=status)

        return qs.order_by('-effective_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch current effective prices for all active fuels
        active_fuels = FuelType.objects.filter(is_active=True).order_by('display_order')
        current_rates = []
        for fuel in active_fuels:
            current_rates.append({
                'fuel': fuel,
                'price': fuel.get_current_price(),
            })

        context['current_rates'] = current_rates
        context['fuels_filter'] = active_fuels
        context['selected_fuel'] = self.request.GET.get('fuel', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class FuelPriceCreateView(RoleRequiredMixin, CreateView):
    model = FuelPrice
    form_class = FuelPriceForm
    template_name = 'station/station_form.html'
    success_url = reverse_lazy('station:price_list')
    allowed_roles = [ROLE_OWNER, ROLE_MANAGER]

    def form_valid(self, form):
        price = form.save(commit=False)
        price.created_by = self.request.user
        if price.approval_status == 'APPROVED':
            price.approved_by = self.request.user
            price.approved_at = timezone.now()
        price.save()

        messages.success(
            self.request,
            _("Fuel price revision for %(fuel)s recorded (NPR %(price)s/L).") % {
                'fuel': price.fuel_type.name_en,
                'price': price.selling_price
            }
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Record New Fuel Price Revision')
        context['back_url'] = reverse_lazy('station:price_list')
        return context


@manager_or_owner_required
def fuel_price_approve_view(request, pk):
    price = get_object_or_404(FuelPrice, pk=pk)
    if price.approval_status == 'PENDING':
        price.approval_status = 'APPROVED'
        price.approved_by = request.user
        price.approved_at = timezone.now()
        price.save(update_fields=['approval_status', 'approved_by', 'approved_at'])
        try:
            from apps.audit.services import record_audit_event
            record_audit_event(
                action='PRICE_CHANGE',
                model_name='FuelPrice',
                record_id=price.pk,
                user=request.user,
                previous_value={},
                updated_value={'purchase_price': float(price.purchase_price), 'selling_price': float(price.selling_price)},
                reason=f"Approved price revision for {price.fuel_type.name_en} ({price.fuel_type.code})"
            )
        except Exception:
            pass
        messages.success(request, _("Price revision for %(fuel)s has been approved.") % {'fuel': price.fuel_type.name_en})
    else:
        messages.info(request, _("Price revision status is already %(status)s.") % {'status': price.get_approval_status_display()})

    return redirect('station:price_list')
