"""
Seed default roles, permissions, and initial station demo accounts.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.authentication.models import User
from common.roles import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    ROLE_CASHIER,
    ROLE_PUMP_OPERATOR,
)
from apps.authentication.signals import ROLE_GROUP_MAPPING


class Command(BaseCommand):
    help = 'Seeds initial user roles, groups, and demo staff accounts for the petrol station.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing station groups and demo staff..."))

        # 1. Create all 5 role groups
        for role_code, group_name in ROLE_GROUP_MAPPING.items():
            grp, created = Group.objects.get_or_create(name=group_name)
            status_text = "Created" if created else "Exists"
            self.stdout.write(f"  - Group [{group_name}]: {status_text}")

        # 2. Demo users definitions
        users_data = [
            {
                'username': 'owner',
                'first_name': 'Ram',
                'last_name': 'Basista',
                'email': 'owner@basistaoil.com.np',
                'role': ROLE_OWNER,
                'phone_number': '9851011223',
                'employee_id': 'EMP-OWN-01',
                'language_preference': 'en',
                'password': 'OwnerPassword123!',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'manager',
                'first_name': 'Bikash',
                'last_name': 'Shrestha',
                'email': 'manager@basistaoil.com.np',
                'role': ROLE_MANAGER,
                'phone_number': '9841234567',
                'employee_id': 'EMP-MGR-01',
                'language_preference': 'ne',
                'password': 'ManagerPassword123!',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'accountant',
                'first_name': 'Sita',
                'last_name': 'Adhikari',
                'email': 'accountant@basistaoil.com.np',
                'role': ROLE_ACCOUNTANT,
                'phone_number': '9801122334',
                'employee_id': 'EMP-ACC-01',
                'language_preference': 'en',
                'password': 'AccountantPassword123!',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'cashier',
                'first_name': 'Dipendra',
                'last_name': 'Thapa',
                'email': 'cashier@basistaoil.com.np',
                'role': ROLE_CASHIER,
                'phone_number': '9860123456',
                'employee_id': 'EMP-CSH-01',
                'language_preference': 'ne',
                'password': 'CashierPassword123!',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'operator1',
                'first_name': 'Santosh',
                'last_name': 'Chaudhary',
                'email': 'operator1@basistaoil.com.np',
                'role': ROLE_PUMP_OPERATOR,
                'phone_number': '9812345678',
                'employee_id': 'EMP-OP-01',
                'language_preference': 'ne',
                'password': 'OperatorPassword123!',
                'is_staff': False,
                'is_superuser': False,
            },
        ]

        created_count = 0
        for udata in users_data:
            username = udata['username']
            password = udata.pop('password')
            user, created = User.objects.get_or_create(username=username, defaults=udata)
            if created:
                user.set_password(password)
                user.save()
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  + Created user: {username} ({user.get_role_display()})"))
            else:
                self.stdout.write(f"  . User already exists: {username}")

        self.stdout.write(self.style.SUCCESS(f"\nCompleted! {created_count} users seeded successfully."))
