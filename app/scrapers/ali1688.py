"""1688.com scraper."""
import re
import json
import logging
from typing import Optional
from .base import BaseScraper
from app.models.product import ScrapedProduct, extract_product_id

logger = logging.getLogger(__name__)


class Ali1688Scraper(BaseScraper):
    platform = "1688"

    def scrape(self, url: str) -> Optional[ScrapedProduct]:
        html = self.fetch(url)
        if not html:
            return None
        return self.parse_price(html, url)

    def parse_price(self, html: str, url: str) -> Optional[ScrapedProduct]:
        product_id = extract_product_id(url, "1688")
        title = ""
        price = 0.0

        # Title
        m = re.search(r'<title>([^<]+)</title>', html)
        if m:
            title = m.group(1).split("-")[0].strip()

        # Price patterns
        patterns = [
            r'"price":"?([0-9.]+)"?',
            r'class="price"[^>]*>¥?\s*([0-9.]+)',
            r'"retailPrice":"?([0-9.]+)"?',
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
            url=url, platform="1688", product_id=product_id,
            title=title, price=price, currency="CNY",
        )
