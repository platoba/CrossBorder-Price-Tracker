from .base import BaseScraper
from .amazon import AmazonScraper
from .aliexpress import AliExpressScraper
from .shopee import ShopeeScraper
from .ali1688 import Ali1688Scraper

SCRAPERS = {
    "amazon": AmazonScraper,
    "aliexpress": AliExpressScraper,
    "shopee": ShopeeScraper,
    "1688": Ali1688Scraper,
}

def get_scraper(platform: str) -> BaseScraper:
    cls = SCRAPERS.get(platform)
    if not cls:
        raise ValueError(f"Unsupported platform: {platform}")
    return cls()
