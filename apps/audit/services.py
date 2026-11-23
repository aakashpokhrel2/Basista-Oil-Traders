"""
Audit service for logging auditable operations and adjustments.
"""

from typing import Any, Optional
from django.utils import timezone
from apps.audit.models import AuditLog


def record_audit_event(
    action: str,
    model_name: str,
    record_id: Any,
    user=None,
    ip_address: Optional[str] = None,
    previous_value: Optional[dict] = None,
    updated_value: Optional[dict] = None,
    reason: str = ''
) -> AuditLog:
    """
    Append an immutable event to the audit trail.
    """
    entry = AuditLog(
        user=user if user and user.is_authenticated else None,
        action=action,
        timestamp=timezone.now(),
        ip_address=ip_address or None,
        model_name=str(model_name),
        record_id=str(record_id),
        previous_value=previous_value or {},
        updated_value=updated_value or {},
        reason=reason or ''
    )
    # Direct save bypassing instance update check
    entry.save()
    return entry
