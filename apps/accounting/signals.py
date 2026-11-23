from django.db.models.signals import post_migrate
from django.dispatch import receiver
from apps.accounting.apps import AccountingConfig


@receiver(post_migrate, sender=AccountingConfig)
def seed_accounting_defaults(sender, **kwargs):
    """Seed baseline Chart of Accounts and Expense Categories on migration."""
    from apps.accounting.services import get_or_create_default_accounts
    from apps.expenses.services import seed_default_expense_categories
    try:
        get_or_create_default_accounts()
        seed_default_expense_categories()
    except Exception:
        pass
