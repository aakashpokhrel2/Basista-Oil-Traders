from django.views.generic import ListView
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from apps.audit.models import AuditLog
from common.permissions import RoleRequiredMixin
from common.roles import ROLE_OWNER


class AuditLogListView(RoleRequiredMixin, ListView):
    """Owner-only view of the complete station security and audit trail."""
    model = AuditLog
    template_name = 'audit/audit_list.html'
    context_object_name = 'logs'
    paginate_by = 30
    allowed_roles = [ROLE_OWNER]

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user')
        action = self.request.GET.get('action', '').strip()
        model_name = self.request.GET.get('model', '').strip()
        q = self.request.GET.get('q', '').strip()

        if action:
            qs = qs.filter(action=action)
        if model_name:
            qs = qs.filter(model_name=model_name)
        if q:
            qs = qs.filter(
                Q(record_id__icontains=q) |
                Q(reason__icontains=q) |
                Q(user__username__icontains=q)
            )
        return qs.order_by('-timestamp', '-id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = _('System Security & Operational Audit Log')
        ctx['action_choices'] = AuditLog.ACTION_CHOICES
        ctx['selected_action'] = self.request.GET.get('action', '')
        ctx['selected_model'] = self.request.GET.get('model', '')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx
