"""Tests for currency converter."""
import json
import os
import tempfile
import pytest
from app.utils.currency import CurrencyConverter, _FALLBACK_RATES


@pytest.fixture
def converter(tmp_path):
    return CurrencyConverter(cache_dir=str(tmp_path))


class TestCurrencyConverter:
    def test_same_currency(self, converter):
        assert converter.convert(100, "USD", "USD") == 100

    def test_usd_to_eur(self, converter):
        result = converter.convert(100, "USD", "EUR")
        assert 80 < result < 100  # ~92

    def test_eur_to_usd(self, converter):
        result = converter.convert(92, "EUR", "USD")
        assert 90 < result < 110

    def test_to_usd(self, converter):
        result = converter.to_usd(100, "EUR")
        assert result > 100  # EUR is worth more than USD

    def test_jpy_to_usd(self, converter):
        result = converter.to_usd(15000, "JPY")
        assert 90 < result < 120

    def test_unknown_currency_raises(self, converter):
        with pytest.raises(ValueError, match="Unknown currency"):
            converter.convert(100, "USD", "XYZ")

    def test_unknown_from_currency(self, converter):
        with pytest.raises(ValueError, match="Unknown currency"):
            converter.convert(100, "FAKE", "USD")

    def test_format_price_usd(self, converter):
        assert converter.format_price(99.99, "USD") == "$99.99"

    def test_format_price_eur(self, converter):
        assert converter.format_price(85.50, "EUR") == "€85.50"

    def test_format_price_jpy(self, converter):
        result = converter.format_price(15000, "JPY")
        assert "¥" in result
        assert "15,000" in result

    def test_format_price_gbp(self, converter):
        assert converter.format_price(79.99, "GBP") == "£79.99"

    def test_format_price_unknown(self, converter):
        result = converter.format_price(100, "ZZZ")
        assert "100.00" in result

    def test_compare_prices(self, converter):
        prices = [
            {"price": 100, "currency": "USD", "platform": "amazon"},
            {"price": 92, "currency": "EUR", "platform": "aliexpress"},
            {"price": 15000, "currency": "JPY", "platform": "shopee"},
        ]
        result = converter.compare_prices(prices)
        assert len(result) == 3
        assert all("usd_price" in r for r in result)
        # Should be sorted by usd_price
        assert result[0]["usd_price"] <= result[1]["usd_price"]

    def test_compare_prices_invalid_skipped(self, converter):
        prices = [
            {"price": 100, "currency": "USD"},
            {"price": 50, "currency": "FAKE_CURRENCY"},
        ]
        result = converter.compare_prices(prices)
        assert len(result) == 1

    def test_supported_currencies(self, converter):
        supported = converter.supported_currencies
        assert "USD" in supported
        assert "EUR" in supported
        assert "CNY" in supported
        assert len(supported) >= 15

    def test_get_rate(self, converter):
        rate = converter.get_rate("USD", "EUR")
        assert rate is not None
        assert 0.8 < rate < 1.0

    def test_get_rate_unknown(self, converter):
        assert converter.get_rate("USD", "XYZ") is None

    def test_bulk_convert(self, converter):
        result = converter.bulk_convert(100, "USD", ["EUR", "GBP", "JPY"])
        assert len(result) == 3
        assert "EUR" in result
        assert "GBP" in result
        assert "JPY" in result

    def test_bulk_convert_all(self, converter):
        result = converter.bulk_convert(100, "USD")
        assert len(result) >= 15

    def test_update_rates(self, converter):
        converter.update_rates({"USD": 1.0, "TEST": 2.0})
        assert converter.convert(100, "USD", "TEST") == 200

    def test_cache_persistence(self, tmp_path):
        c1 = CurrencyConverter(cache_dir=str(tmp_path))
        c1.update_rates({"USD": 1.0, "CACHED": 5.0})

        c2 = CurrencyConverter(cache_dir=str(tmp_path))
        assert c2.convert(100, "USD", "CACHED") == 500

    def test_fallback_rates_exist(self):
        assert "USD" in _FALLBACK_RATES
        assert _FALLBACK_RATES["USD"] == 1.0
        assert len(_FALLBACK_RATES) >= 10

    def test_zero_amount(self, converter):
        assert converter.convert(0, "USD", "EUR") == 0

    def test_negative_amount(self, converter):
        result = converter.convert(-100, "USD", "EUR")
        assert result < 0

    def test_case_insensitive(self, converter):
        r1 = converter.convert(100, "usd", "eur")
        r2 = converter.convert(100, "USD", "EUR")
        assert r1 == r2
