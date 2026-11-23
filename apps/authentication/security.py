"""
Authentication Security: Rate limiting, Brute-force protection, and Login Lockout.
"""

from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.db import models


# Security parameters
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 15


class LoginAttempt(models.Model):
    """
    Tracks failed and successful login attempts for brute-force rate-limiting
    and security auditing.
    """
    username = models.CharField(max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    attempt_time = models.DateTimeField(default=timezone.now, db_index=True)
    is_successful = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-attempt_time']
        indexes = [
            models.Index(fields=['username', 'attempt_time']),
            models.Index(fields=['ip_address', 'attempt_time']),
        ]

    def __str__(self):
        status = "SUCCESS" if self.is_successful else f"FAILED ({self.failure_reason})"
        return f"{self.attempt_time.strftime('%Y-%m-%d %H:%M:%S')} | {self.username} | {self.ip_address} | {status}"


def get_client_ip(request) -> str:
    """Extract client IP address from HTTP request headers."""
    if not request:
        return ''
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def check_login_lockout(username: str, ip_address: str = None) -> tuple[bool, int]:
    """
    Check if a username or IP address is currently locked out due to consecutive failed attempts.
    Returns: (is_locked, remaining_minutes)
    """
    window_start = timezone.now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)

    # Check by username
    if username:
        recent_by_user = LoginAttempt.objects.filter(
            username__iexact=username,
            attempt_time__gte=window_start
        ).order_by('-attempt_time')

        # Check consecutive failures since the last success
        consecutive_failures = 0
        latest_attempt_time = None
        for att in recent_by_user:
            if att.is_successful:
                break
            consecutive_failures += 1
            if latest_attempt_time is None:
                latest_attempt_time = att.attempt_time

        if consecutive_failures >= MAX_FAILED_LOGIN_ATTEMPTS and latest_attempt_time:
            lockout_expiry = latest_attempt_time + timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
            remaining_seconds = (lockout_expiry - timezone.now()).total_seconds()
            if remaining_seconds > 0:
                remaining_mins = max(1, int(remaining_seconds // 60) + 1)
                return True, remaining_mins

    # Check by IP address
    if ip_address:
        recent_by_ip = LoginAttempt.objects.filter(
            ip_address=ip_address,
            attempt_time__gte=window_start
        ).order_by('-attempt_time')

        consecutive_ip_failures = 0
        latest_ip_time = None
        for att in recent_by_ip:
            if att.is_successful:
                break
            consecutive_ip_failures += 1
            if latest_ip_time is None:
                latest_ip_time = att.attempt_time

        if consecutive_ip_failures >= (MAX_FAILED_LOGIN_ATTEMPTS * 2) and latest_ip_time:
            lockout_expiry = latest_ip_time + timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
            remaining_seconds = (lockout_expiry - timezone.now()).total_seconds()
            if remaining_seconds > 0:
                remaining_mins = max(1, int(remaining_seconds // 60) + 1)
                return True, remaining_mins

    return False, 0


def record_login_attempt(username: str, ip_address: str, is_successful: bool, failure_reason: str = ''):
    """Record a login attempt in the database."""
    LoginAttempt.objects.create(
        username=username or 'anonymous',
        ip_address=ip_address or None,
        attempt_time=timezone.now(),
        is_successful=is_successful,
        failure_reason=failure_reason
    )
