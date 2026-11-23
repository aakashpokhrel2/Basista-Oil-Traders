"""
Automated unit tests for Station Dashboard view.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import User
from apps.station.models import StationConfiguration, FuelType, StorageTank
from common.roles import ROLE_OWNER


class DashboardTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='station_owner',
            password='TestPassword123!',
            role=ROLE_OWNER,
            language_preference='en',
        )
        self.station = StationConfiguration.get_solo()
        self.station.station_name_en = 'Basista Oil Traders'
        self.station.save()

        # Seed Fuel Types & Tanks
        self.ms, _ = FuelType.objects.get_or_create(
            code='MS', defaults={'name_en': 'Petrol (MS)', 'name_ne': 'पेट्रोल (MS)', 'unit': 'Litres', 'is_active': True}
        )
        self.hsd, _ = FuelType.objects.get_or_create(
            code='HSD', defaults={'name_en': 'Diesel (HSD)', 'name_ne': 'डिजेल (HSD)', 'unit': 'Litres', 'is_active': True}
        )
        self.tank_ms, _ = StorageTank.objects.get_or_create(
            tank_number='T-MS-01', defaults={
                'tank_name': 'Petrol (MS) Tank', 'fuel_type': self.ms,
                'capacity_liters': Decimal('15000.00'), 'current_stock': Decimal('9000.00'), 'is_active': True
            }
        )
        self.tank_hsd, _ = StorageTank.objects.get_or_create(
            tank_number='T-HSD-01', defaults={
                'tank_name': 'Diesel (HSD) Tank', 'fuel_type': self.hsd,
                'capacity_liters': Decimal('20000.00'), 'current_stock': Decimal('12000.00'), 'is_active': True
            }
        )

    def test_dashboard_unauthenticated_redirect(self):
        """Unauthenticated user accessing dashboard must be redirected to login."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(response, f"{reverse('authentication:login')}?next={reverse('dashboard:index')}")

    def test_dashboard_authenticated(self):
        """Authenticated user successfully accesses dashboard with station metrics and Chart.js analytics."""
        self.client.login(username='station_owner', password='TestPassword123!')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Basista Oil Traders')
        self.assertContains(response, 'Bikram Sambat')
        self.assertContains(response, 'Petrol (MS) Tank')
        self.assertContains(response, 'Diesel (HSD) Tank')
        self.assertContains(response, 'salesTrendChart')
        self.assertContains(response, 'fuelRatioChart')
        self.assertContains(response, 'tankCapacityChart')
