"""Enhanced base scraper with anti-crawl detection and engine escalation."""
import time
import logging
import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from app.models.product import ScrapedProduct
from app.utils.ua import random_headers
from app.utils.anti_crawl import AntiCrawlDetector, EngineEscalator, EngineLevel
from app.utils.miyaip_loader import MiyaipLoader
from app.utils.proxy import ProxyPool
from app.config import Config

logger = logging.getLogger(__name__)


class EnhancedBaseScraper(ABC):
    """Enhanced base scraper with anti-crawl detection and engine escalation."""

    platform: str = ""
    base_delay: float = 2.0

    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()
        self._last_request = 0.0
        self.detector = AntiCrawlDetector()
        self.escalator = EngineEscalator()
        self.miyaip = MiyaipLoader()
        try:
            self.miyaip_pool = self.miyaip.create_pool()
        except:
            self.miyaip_pool = None
        self._current_engine = EngineLevel.L1_STATIC

    def _get_client(self, proxy_url: str = None) -> httpx.Client:
        """Get HTTP client with proxy and headers."""
        proxies = proxy_url or self.config.proxy.url
        return httpx.Client(
            timeout=30,
            follow_redirects=True,
            proxy=proxies,
            headers=random_headers(),
        )

    def _rate_limit(self):
        """Rate limiting between requests."""
        elapsed = time.time() - self._last_request
        delay = self.config.request_delay
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def _get_proxy_for_engine(self, engine_level: EngineLevel) -> Optional[str]:
        """Get appropriate proxy based on engine level."""
        if engine_level == EngineLevel.L1_STATIC and self.miyaip_pool:
            # L1: Use miyaip static proxies
            proxy = self.miyaip_pool.get_proxy()
            if proxy:
                return proxy.url
        elif engine_level.value >= EngineLevel.L2_JS_RENDER.value:
            # L2+: Use configured proxy (iprocket residential)
            return self.config.proxy.url
        return None

    def fetch_with_escalation(self, url: str) -> Optional[str]:
        """Fetch with automatic engine escalation on anti-crawl detection."""
        target = url
        
        while True:
            current_level = self.escalator.get_level(target)
            logger.info(f"Fetching {url} with engine {current_level.name}")
            
            # Get proxy for current engine level
            proxy_url = self._get_proxy_for_engine(current_level)
            
            # Attempt fetch
            result = self._fetch_single(url, proxy_url)
            
            if result is None:
                # Fetch failed, check for anti-crawl
                detection = self.detector.detect(None, None, url)
                if detection:
                    logger.warning(f"Anti-crawl detected: {detection.block_type.value} (confidence: {detection.confidence})")
                    logger.warning(f"Evidence: {detection.evidence}")
                    
                    # Record failure and check if escalation needed
                    new_level = self.escalator.record_failure(target, current_level)
                    
                    if new_level:
                        logger.info(f"Escalating from {current_level.name} to {new_level.name}")
                        time.sleep(2)  # Brief pause before retry
                        continue
                    else:
                        # Reached max level
                        logger.error(f"All engine levels exhausted for {url}")
                        return None
                else:
                    # Unknown failure, escalate anyway
                    logger.warning("Unknown fetch failure, escalating")
                    new_level = self.escalator.record_failure(target, current_level)
                    if new_level:
                        time.sleep(1)
                        continue
                    else:
                        return None
            else:
                # Success! Record success and return
                self.escalator.record_success(target, current_level)
                return result

    def _fetch_single(self, url: str, proxy_url: str = None) -> Optional[str]:
        """Single fetch attempt with rate limiting."""
        self._rate_limit()
        
        try:
            with self._get_client(proxy_url) as client:
                resp = client.get(url)
                resp.raise_for_status()
                
                # Check response for anti-crawl patterns
                detection = self.detector.detect(resp.text, resp.status_code, url)
                if detection:
                    logger.warning(f"Anti-crawl pattern in response: {detection.block_type.value}")
                    return None
                
                return resp.text
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout for {url}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error for {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.warning(f"Fetch failed for {url}: {e}")
            return None

    @abstractmethod
    def scrape(self, url: str) -> Optional[ScrapedProduct]:
        """Scrape product from URL. Must be implemented by subclasses."""
        pass

    def get_engine_stats(self) -> Dict[str, Any]:
        """Get current engine escalation statistics."""
        return self.escalator.stats()
