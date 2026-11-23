"""
Automated unit tests for Authentication, Custom User Model, and Role-Based Access Control (RBAC).
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import Group
from apps.authentication.models import User
from common.roles import (
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_ACCOUNTANT,
    ROLE_CASHIER,
    ROLE_PUMP_OPERATOR,
)


class UserAuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = 'SecureTest123!'

        # Create users for all 5 roles
        self.owner = User.objects.create_user(
            username='owner_user',
            password=self.password,
            email='owner@station.np',
            role=ROLE_OWNER,
            phone_number='9851000001',
            employee_id='EMP-OWN',
            language_preference='en',
            is_staff=True,
        )

        self.manager = User.objects.create_user(
            username='manager_user',
            password=self.password,
            email='manager@station.np',
            role=ROLE_MANAGER,
            phone_number='9851000002',
            employee_id='EMP-MGR',
            language_preference='ne',
            is_staff=True,
        )

        self.accountant = User.objects.create_user(
            username='accountant_user',
            password=self.password,
            email='accountant@station.np',
            role=ROLE_ACCOUNTANT,
            phone_number='9851000003',
            employee_id='EMP-ACC',
            language_preference='en',
        )

        self.cashier = User.objects.create_user(
            username='cashier_user',
            password=self.password,
            email='cashier@station.np',
            role=ROLE_CASHIER,
            phone_number='9851000004',
            employee_id='EMP-CSH',
            language_preference='ne',
        )

        self.operator = User.objects.create_user(
            username='operator_user',
            password=self.password,
            email='operator@station.np',
            role=ROLE_PUMP_OPERATOR,
            phone_number='9851000005',
            employee_id='EMP-OP1',
            language_preference='ne',
        )

    def test_custom_user_fields(self):
        """Verify custom user fields and helper properties."""
        self.assertEqual(self.owner.role, ROLE_OWNER)
        self.assertTrue(self.owner.is_owner)
        self.assertTrue(self.owner.can_manage_users)
        self.assertTrue(self.owner.can_modify_fuel_prices)
        self.assertTrue(self.owner.can_view_financials)

        self.assertEqual(self.manager.role, ROLE_MANAGER)
        self.assertTrue(self.manager.is_manager)
        self.assertTrue(self.manager.can_manage_users)

        self.assertEqual(self.operator.role, ROLE_PUMP_OPERATOR)
        self.assertTrue(self.operator.is_pump_operator)
        self.assertFalse(self.operator.can_manage_users)

    def test_automatic_group_synchronization(self):
        """Verify that user role correctly adds user to the respective Django Group."""
        self.assertTrue(self.owner.groups.filter(name='Station Owners').exists())
        self.assertTrue(self.manager.groups.filter(name='Station Managers').exists())
        self.assertTrue(self.accountant.groups.filter(name='Accountants').exists())
        self.assertTrue(self.cashier.groups.filter(name='Cashiers').exists())
        self.assertTrue(self.operator.groups.filter(name='Pump Operators').exists())

    def test_login_successful(self):
        """Test successful login with valid credentials."""
        response = self.client.post(reverse('authentication:login'), {
            'username': 'owner_user',
            'password': self.password,
        })
        self.assertRedirects(response, reverse('dashboard:index'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.owner.pk)

    def test_login_invalid_credentials(self):
        """Test login fails with incorrect password."""
        response = self.client.post(reverse('authentication:login'), {
            'username': 'owner_user',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertContains(response, 'Please enter a correct')

    def test_logout(self):
        """Test logout clears session and redirects to login."""
        self.client.login(username='owner_user', password=self.password)
        response = self.client.get(reverse('authentication:logout'))
        self.assertRedirects(response, reverse('authentication:login'))
        self.assertFalse('_auth_user_id' in self.client.session)

    def test_rbac_user_management_access(self):
        """Owner and Manager should have access to user management, others should be restricted."""
        user_list_url = reverse('authentication:user_list')

        # 1. Anonymous user redirected to login
        response = self.client.get(user_list_url)
        self.assertRedirects(response, f"{reverse('authentication:login')}?next={user_list_url}")

        # 2. Owner has access
        self.client.login(username='owner_user', password=self.password)
        response = self.client.get(user_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff & User Management')
        self.client.logout()

        # 3. Manager has access
        self.client.login(username='manager_user', password=self.password)
        response = self.client.get(user_list_url)
        self.assertEqual(response.status_code, 200)
        self.client.logout()

        # 4. Cashier is restricted (redirected to dashboard with error message)
        self.client.login(username='cashier_user', password=self.password)
        response = self.client.get(user_list_url)
        self.assertRedirects(response, reverse('dashboard:index'))
        self.client.logout()

        # 5. Pump Operator is restricted
        self.client.login(username='operator_user', password=self.password)
        response = self.client.get(user_list_url)
        self.assertRedirects(response, reverse('dashboard:index'))
        self.client.logout()

    def test_create_user_view(self):
        """Owner should be able to create new staff user."""
        self.client.login(username='owner_user', password=self.password)
        response = self.client.post(reverse('authentication:user_create'), {
            'username': 'new_operator',
            'first_name': 'Hari',
            'last_name': 'Prasad',
            'email': 'hari@station.np',
            'role': ROLE_PUMP_OPERATOR,
            'phone_number': '9840001122',
            'employee_id': 'EMP-OP2',
            'language_preference': 'ne',
            'password1': 'NewPass12345!',
            'password2': 'NewPass12345!',
            'is_active': True,
        })
        self.assertRedirects(response, reverse('authentication:user_list'))
        self.assertTrue(User.objects.filter(username='new_operator').exists())
        new_op = User.objects.get(username='new_operator')
        self.assertEqual(new_op.role, ROLE_PUMP_OPERATOR)
        self.assertTrue(new_op.groups.filter(name='Pump Operators').exists())
