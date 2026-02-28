"""Multi-currency converter with cached exchange rates."""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Fallback rates (approximate, updated periodically)
_FALLBACK_RATES: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 149.5,
    "CAD": 1.36,
    "AUD": 1.53,
    "CNY": 7.24,
    "HKD": 7.82,
    "SGD": 1.34,
    "MYR": 4.47,
    "THB": 35.6,
    "VND": 24500.0,
    "PHP": 55.8,
    "IDR": 15700.0,
    "BRL": 4.97,
    "TWD": 31.5,
    "KRW": 1330.0,
    "INR": 83.1,
}


class CurrencyConverter:
    """Convert between currencies with caching."""

    def __init__(self, cache_dir: str = "data", cache_ttl: int = 86400):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "exchange_rates.json"
        self.cache_ttl = cache_ttl
        self._rates: Dict[str, float] = {}
        self._last_update: float = 0
        self._load_cache()

    def _load_cache(self):
        """Load cached rates from disk."""
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text())
                self._rates = data.get("rates", {})
                self._last_update = data.get("timestamp", 0)
            except (json.JSONDecodeError, KeyError):
                self._rates = {}
                self._last_update = 0

    def _save_cache(self):
        """Save rates to disk cache."""
        data = {
            "rates": self._rates,
            "timestamp": self._last_update,
            "base": "USD",
        }
        self.cache_file.write_text(json.dumps(data, indent=2))

    @property
    def rates(self) -> Dict[str, float]:
        """Get current exchange rates (USD-based)."""
        if self._rates and (time.time() - self._last_update) < self.cache_ttl:
            return self._rates
        return _FALLBACK_RATES.copy()

    def update_rates(self, new_rates: Dict[str, float]):
        """Manually update rates (e.g., from API response)."""
        self._rates = new_rates
        self._last_update = time.time()
        self._save_cache()

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert amount between currencies."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return amount

        rates = self.rates

        # Convert to USD first, then to target
        from_rate = rates.get(from_currency)
        to_rate = rates.get(to_currency)

        if from_rate is None:
            raise ValueError(f"Unknown currency: {from_currency}")
        if to_rate is None:
            raise ValueError(f"Unknown currency: {to_currency}")

        # amount in FROM → USD → TO
        usd_amount = amount / from_rate
        return round(usd_amount * to_rate, 4)

    def to_usd(self, amount: float, currency: str) -> float:
        """Convert any amount to USD."""
        return self.convert(amount, currency, "USD")

    def format_price(self, amount: float, currency: str) -> str:
        """Format price with currency symbol."""
        symbols = {
            "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
            "CNY": "¥", "CAD": "C$", "AUD": "A$", "HKD": "HK$",
            "KRW": "₩", "INR": "₹", "BRL": "R$", "THB": "฿",
        }
        symbol = symbols.get(currency.upper(), currency.upper() + " ")

        # No decimals for high-value currencies
        no_decimal = {"JPY", "KRW", "VND", "IDR"}
        if currency.upper() in no_decimal:
            return f"{symbol}{amount:,.0f}"
        return f"{symbol}{amount:,.2f}"

    def compare_prices(self, prices: list) -> list:
        """
        Compare prices across currencies.

        Args:
            prices: List of dicts with 'price', 'currency', and optional metadata

        Returns:
            List sorted by USD equivalent, with usd_price added
        """
        result = []
        for item in prices:
            try:
                usd_price = self.to_usd(item["price"], item["currency"])
                entry = {**item, "usd_price": round(usd_price, 2)}
                result.append(entry)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping price comparison entry: {e}")
                continue

        return sorted(result, key=lambda x: x["usd_price"])

    @property
    def supported_currencies(self) -> list:
        """List supported currency codes."""
        return sorted(self.rates.keys())

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Get exchange rate between two currencies."""
        try:
            return self.convert(1.0, from_currency, to_currency)
        except ValueError:
            return None

    def bulk_convert(self, amount: float, from_currency: str,
                     to_currencies: list = None) -> Dict[str, float]:
        """Convert amount to multiple currencies at once."""
        if to_currencies is None:
            to_currencies = self.supported_currencies

        results = {}
        for tc in to_currencies:
            try:
                results[tc] = self.convert(amount, from_currency, tc)
            except ValueError:
                continue
        return results
