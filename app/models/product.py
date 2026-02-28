"""Product data models."""
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class ScrapedProduct:
    url: str
    platform: str
    product_id: str
    title: str = ""
    price: float = 0.0
    currency: str = "USD"
    in_stock: bool = True
    seller: str = ""
    image_url: str = ""
    rating: float = 0.0
    review_count: int = 0
    raw_data: dict = None

    def __post_init__(self):
        if self.raw_data is None:
            self.raw_data = {}


def detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    patterns = {
        "amazon": r"amazon\.(com|co\.uk|de|co\.jp|fr|es|it|ca|com\.au)",
        "aliexpress": r"aliexpress\.com|ali\.express",
        "shopee": r"shopee\.(sg|com\.my|co\.th|vn|ph|co\.id|tw|com\.br)",
        "1688": r"1688\.com|detail\.1688\.com",
    }
    for platform, pattern in patterns.items():
        if re.search(pattern, url_lower):
            return platform
    return "unknown"


def extract_product_id(url: str, platform: str) -> str:
    """Extract product ID from URL."""
    extractors = {
        "amazon": r"/dp/([A-Z0-9]{10})|/product/([A-Z0-9]{10})",
        "aliexpress": r"/item/(\d+)\.html|/(\d+)\.html",
        "shopee": r"\.(\d+)$|i\.\d+\.(\d+)",
        "1688": r"offer/(\d+)\.html",
    }
    pattern = extractors.get(platform)
    if pattern:
        m = re.search(pattern, url)
        if m:
            return next(g for g in m.groups() if g is not None)
    return ""
