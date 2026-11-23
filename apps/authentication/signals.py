"""
Signals to manage Django Groups and role permissions synchronization.
"""

from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from apps.authentication.models import User
from common.permissions import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    ROLE_CASHIER,
    ROLE_PUMP_OPERATOR,
)

ROLE_GROUP_MAPPING = {
    ROLE_OWNER: 'Station Owners',
    ROLE_MANAGER: 'Station Managers',
    ROLE_ACCOUNTANT: 'Accountants',
    ROLE_CASHIER: 'Cashiers',
    ROLE_PUMP_OPERATOR: 'Pump Operators',
}


@receiver(post_migrate)
def create_default_role_groups(sender, **kwargs):
    """
    Ensure all default role groups exist after migration.
    """
    for role_code, group_name in ROLE_GROUP_MAPPING.items():
        Group.objects.get_or_create(name=group_name)


@receiver(post_save, sender=User)
def sync_user_groups_on_save(sender, instance, created, **kwargs):
    """
    Sync Django groups with the user's assigned role.
    """
    group_name = ROLE_GROUP_MAPPING.get(instance.role)
    if not group_name:
        return

    target_group, _ = Group.objects.get_or_create(name=group_name)

    # Remove user from other station role groups and add to target group
    all_role_group_names = set(ROLE_GROUP_MAPPING.values())
    groups_to_remove = Group.objects.filter(name__in=all_role_group_names).exclude(name=group_name)
    instance.groups.remove(*groups_to_remove)
    instance.groups.add(target_group)
