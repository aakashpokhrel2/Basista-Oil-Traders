"""
Immutable Audit Log System for Petrol Station Operations & Financial Transactions.
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """
    Immutable audit ledger capturing every critical action, adjustment,
    approval, void/cancellation, price revision, and security event.
    """
    ACTION_CHOICES = [
        ('CREATE', _('Record Created')),
        ('UPDATE', _('Record Updated')),
        ('DELETE', _('Record Deleted')),
        ('APPROVE', _('Approved')),
        ('REJECT', _('Rejected')),
        ('CANCEL', _('Cancelled / Voided')),
        ('PRICE_CHANGE', _('Fuel Price Revised')),
        ('STOCK_ADJUSTMENT', _('Stock Adjustment')),
        ('METER_ROLLOVER', _('Meter Rollover Authorized')),
        ('LOGIN_SUCCESS', _('Successful Login')),
        ('LOGIN_FAILED', _('Failed Login Attempt')),
        ('SECURITY_LOCKOUT', _('Account Locked Out')),
        ('BACKUP', _('Database Backup Created')),
        ('RESTORE', _('Database Restore Executed')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_entries',
        verbose_name=_('Performed By')
    )
    action = models.CharField(
        max_length=40,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name=_('Action')
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_('Timestamp')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('Client IP Address')
    )
    model_name = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_('Affected Model / Entity')
    )
    record_id = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name=_('Record Identifier')
    )
    previous_value = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Previous Value')
    )
    updated_value = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Updated Value')
    )
    reason = models.TextField(
        blank=True,
        verbose_name=_('Reason for Adjustment / Audit Note')
    )

    class Meta:
        verbose_name = _('Audit Log Entry')
        verbose_name_plural = _('Audit Log Entries')
        ordering = ['-timestamp', '-id']
        indexes = [
            models.Index(fields=['model_name', 'record_id']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        user_name = self.user.username if self.user else "SYSTEM"
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_name} - {self.get_action_display()} on {self.model_name} #{self.record_id}"

    def save(self, *args, **kwargs):
        # Enforce append-only immutability: once saved, audit records cannot be modified
        if self.pk:
            raise ValidationError(_("Audit log entries are immutable and cannot be updated once saved."))
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Enforce append-only immutability: audit records cannot be deleted
        raise ValidationError(_("Audit log entries are permanent and cannot be deleted."))
