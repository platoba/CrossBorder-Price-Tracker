"""AliExpress scraper."""
import re
import json
import logging
from typing import Optional
from .base import BaseScraper
from app.models.product import ScrapedProduct, extract_product_id

logger = logging.getLogger(__name__)


class AliExpressScraper(BaseScraper):
    platform = "aliexpress"

    def scrape(self, url: str) -> Optional[ScrapedProduct]:
        html = self.fetch(url)
        if not html:
            return None
        return self.parse_price(html, url)

    def parse_price(self, html: str, url: str) -> Optional[ScrapedProduct]:
        product_id = extract_product_id(url, "aliexpress")
        title = ""
        price = 0.0

        # Try JSON-LD
        json_ld_m = re.search(r'<script type="application/ld\+json">\s*({.*?})\s*</script>', html, re.DOTALL)
        if json_ld_m:
            try:
                data = json.loads(json_ld_m.group(1))
                title = data.get("name", "")
                offers = data.get("offers", {})
                if isinstance(offers, dict):
                    price = float(offers.get("price", 0))
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: regex
        if not title:
            m = re.search(r'"subject":"([^"]+)"', html)
            if m:
                title = m.group(1)

        if price == 0:
            patterns = [
                r'"formatedAmount":"US\s*\$\s*([0-9.]+)"',
                r'"minPrice":"?([0-9.]+)"?',
                r'class="product-price-value"[^>]*>US\s*\$\s*([0-9.]+)',
            ]
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    try:
                        price = float(m.group(1))
                        break
                    except ValueError:
                        continue

        return ScrapedProduct(
            url=url, platform="aliexpress", product_id=product_id,
            title=title, price=price, currency="USD",
        )
