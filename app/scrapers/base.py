"""Base scraper with retry + proxy + rate limiting."""
import time
import logging
import httpx
from abc import ABC, abstractmethod
from typing import Optional
from app.models.product import ScrapedProduct
from app.utils.ua import random_headers
from app.config import Config

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all platform scrapers."""

    platform: str = ""
    base_delay: float = 2.0

    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        self._last_request = 0.0

    def _get_client(self, proxy_url: str = None) -> httpx.Client:
        proxies = proxy_url or self.config.proxy.url
        return httpx.Client(
            timeout=30,
            follow_redirects=True,
            proxy=proxies,
            headers=random_headers(),
        )

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        delay = self.config.request_delay
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def fetch(self, url: str, proxy_url: str = None) -> Optional[str]:
        self._rate_limit()
        retries = self.config.max_retries
        for attempt in range(retries):
            try:
                with self._get_client(proxy_url) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    return resp.text
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{retries} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
        return None

    @abstractmethod
    def scrape(self, url: str) -> Optional[ScrapedProduct]:
        """Scrape product data from URL."""
        ...

    @abstractmethod
    def parse_price(self, html: str, url: str) -> Optional[ScrapedProduct]:
        """Parse price from HTML content."""
        ...
