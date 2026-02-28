"""Amazon scraper - supports US/UK/DE/JP."""
import re
import logging
from typing import Optional
from .base import BaseScraper
from app.models.product import ScrapedProduct, extract_product_id

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    platform = "amazon"

    PRICE_SELECTORS = [
        r'class="a-price-whole">([^<]+)</span>.*?class="a-price-fraction">([^<]+)<',
        r'"priceAmount":([0-9.]+)',
        r'id="priceblock_ourprice"[^>]*>\s*\$?\s*([0-9,.]+)',
        r'id="priceblock_dealprice"[^>]*>\s*\$?\s*([0-9,.]+)',
        r'class="a-price"[^>]*>.*?class="a-offscreen">([^<]+)<',
    ]

    CURRENCY_MAP = {
        "amazon.com": "USD", "amazon.co.uk": "GBP",
        "amazon.de": "EUR", "amazon.co.jp": "JPY",
        "amazon.fr": "EUR", "amazon.es": "EUR",
        "amazon.it": "EUR", "amazon.ca": "CAD",
    }

    def _detect_currency(self, url: str) -> str:
        for domain, currency in self.CURRENCY_MAP.items():
            if domain in url:
                return currency
        return "USD"

    def scrape(self, url: str) -> Optional[ScrapedProduct]:
        html = self.fetch(url)
        if not html:
            return None
        return self.parse_price(html, url)

    def parse_price(self, html: str, url: str) -> Optional[ScrapedProduct]:
        product_id = extract_product_id(url, "amazon")
        title = ""
        title_m = re.search(r'id="productTitle"[^>]*>\s*([^<]+)', html)
        if title_m:
            title = title_m.group(1).strip()

        price = self._extract_price(html)
        in_stock = "In Stock" in html or "inStock" in html or "In stock" in html
        currency = self._detect_currency(url)

        rating = 0.0
        rating_m = re.search(r'([0-9.]+) out of 5', html)
        if rating_m:
            rating = float(rating_m.group(1))

        review_count = 0
        review_m = re.search(r'(\d[\d,]*)\s*(?:global\s+)?ratings', html)
        if review_m:
            review_count = int(review_m.group(1).replace(",", ""))

        seller = ""
        seller_m = re.search(r'id="sellerProfileTriggerId"[^>]*>([^<]+)', html)
        if seller_m:
            seller = seller_m.group(1).strip()

        return ScrapedProduct(
            url=url, platform="amazon", product_id=product_id,
            title=title, price=price, currency=currency,
            in_stock=in_stock, seller=seller,
            rating=rating, review_count=review_count,
        )

    def _extract_price(self, html: str) -> float:
        for pattern in self.PRICE_SELECTORS:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                groups = [g for g in m.groups() if g]
                if len(groups) == 2:
                    whole = groups[0].replace(",", "").strip()
                    fraction = groups[1].strip()
                    try:
                        return float(f"{whole}.{fraction}")
                    except ValueError:
                        continue
                elif len(groups) == 1:
                    price_str = groups[0].replace(",", "").replace("$", "").replace("€", "").replace("£", "").replace("¥", "").strip()
                    try:
                        return float(price_str)
                    except ValueError:
                        continue
        return 0.0
