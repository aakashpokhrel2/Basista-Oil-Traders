"""
Automated unit tests for Gregorian (AD) and Bikram Sambat (BS) date conversion,
Nepali numerals, and currency formatting.
"""

from datetime import date
from decimal import Decimal
from django.test import TestCase
import nepali_datetime
from common.date_utils import (
    ad_to_bs,
    bs_to_ad,
    format_bs_date,
    nepali_numerals,
    nepali_to_english_numerals,
    format_currency_npr,
)


class DateUtilsTestCase(TestCase):
    def test_ad_to_bs_conversion(self):
        """Test AD to BS conversion for known historical and future dates."""
        # Known milestone: 2024-04-13 is Baishakh 1, 2081 BS (Nepali New Year)
        ad_ny = date(2024, 4, 13)
        bs_ny = ad_to_bs(ad_ny)
        self.assertEqual(bs_ny.year, 2081)
        self.assertEqual(bs_ny.month, 1)
        self.assertEqual(bs_ny.day, 1)

        # Test string input '2026-11-23'
        bs_date = ad_to_bs('2026-11-23')
        self.assertEqual(bs_date.year, 2083)
        self.assertEqual(bs_date.month, 8)
        self.assertEqual(bs_date.day, 7)

    def test_bs_to_ad_conversion(self):
        """Test BS to AD conversion."""
        # 2081-01-01 BS -> 2024-04-13 AD
        bs_obj = nepali_datetime.date(2081, 1, 1)
        ad_date = bs_to_ad(bs_obj)
        self.assertEqual(ad_date, date(2024, 4, 13))

        # Test string input '2081-01-01'
        ad_from_str = bs_to_ad('2081-01-01')
        self.assertEqual(ad_from_str, date(2024, 4, 13))

        # Test string with Devanagari numerals: '२०८१-०१-०१'
        ad_from_devanagari = bs_to_ad('२०८१-०१-०१')
        self.assertEqual(ad_from_devanagari, date(2024, 4, 13))

    def test_nepali_numerals(self):
        """Test converting digits to Devanagari and back."""
        self.assertEqual(nepali_numerals('1234567890'), '१२३४५६७८९०')
        self.assertEqual(nepali_numerals(2083), '२०८३')
        self.assertEqual(nepali_to_english_numerals('२०८३-०८-०७'), '2083-08-07')

    def test_format_bs_date(self):
        """Test user-friendly formatting in English and Nepali."""
        bs_obj = nepali_datetime.date(2081, 1, 1)  # Saturday / शनिबार
        formatted_en = format_bs_date(bs_obj, lang='en', include_weekday=True)
        self.assertIn('Baishakh 01, 2081', formatted_en)
        self.assertIn('Saturday', formatted_en)

        formatted_ne = format_bs_date(bs_obj, lang='ne', include_weekday=True)
        self.assertIn('वैशाख', formatted_ne)
        self.assertIn('२०८१', formatted_ne)
        self.assertIn('शनिबार', formatted_ne)

    def test_format_currency_npr(self):
        """Test Nepalese Rupee South Asian comma separation."""
        # 1250000.50 -> 12,50,000.50
        amount = Decimal('1250000.50')
        curr_en = format_currency_npr(amount, lang='en')
        self.assertEqual(curr_en, 'NPR 12,50,000.50')

        curr_ne = format_currency_npr(amount, lang='ne')
        self.assertIn('रु', curr_ne)
        self.assertIn('१२,५०,०००.५०', curr_ne)
