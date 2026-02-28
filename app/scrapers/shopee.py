"""Shopee scraper (mobile API-based)."""
import re
import json
import logging
from typing import Optional
from .base import BaseScraper
from app.models.product import ScrapedProduct, extract_product_id
from app.utils.ua import random_headers

logger = logging.getLogger(__name__)


class ShopeeScraper(BaseScraper):
    platform = "shopee"

    API_TEMPLATE = "https://shopee.{region}/api/v4/item/get?itemid={item_id}&shopid={shop_id}"

    REGION_MAP = {
        "shopee.sg": "sg", "shopee.com.my": "com.my", "shopee.co.th": "co.th",
        "shopee.vn": "vn", "shopee.ph": "ph", "shopee.co.id": "co.id",
        "shopee.tw": "tw", "shopee.com.br": "com.br",
    }

    def _parse_shopee_url(self, url: str) -> tuple:
        m = re.search(r'i\.(\d+)\.(\d+)', url)
        if m:
            return m.group(1), m.group(2)
        m = re.search(r'\.(\d+)\?', url) or re.search(r'\.(\d+)$', url)
        return "", m.group(1) if m else ""

    def _detect_region(self, url: str) -> str:
        for domain, region in self.REGION_MAP.items():
            if domain in url:
                return region
        return "sg"

    def scrape(self, url: str) -> Optional[ScrapedProduct]:
        html = self.fetch(url)
        if not html:
            return None
        return self.parse_price(html, url)

    def parse_price(self, html: str, url: str) -> Optional[ScrapedProduct]:
        product_id = extract_product_id(url, "shopee")
        title = ""
        price = 0.0

        # Try script data
        m = re.search(r'"name":"([^"]+)"', html)
        if m:
            title = m.group(1)

        price_m = re.search(r'"price":(\d+)', html)
        if price_m:
            raw = int(price_m.group(1))
            price = raw / 100000 if raw > 100000 else raw / 100 if raw > 1000 else float(raw)

        return ScrapedProduct(
            url=url, platform="shopee", product_id=product_id,
            title=title, price=price, currency="USD",
        )
