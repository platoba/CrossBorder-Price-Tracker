"""Tests for enhanced base scraper with anti-crawl detection."""
import pytest
from unittest.mock import Mock, patch
from app.scrapers.enhanced_base import EnhancedBaseScraper
from app.models.product import ScrapedProduct
from app.utils.anti_crawl import EngineLevel, BlockType, DetectionResult
from app.config import Config


class MockEnhancedScraper(EnhancedBaseScraper):
    """Mock scraper for testing."""
    platform = "test"
    
    def scrape(self, url: str):
        html = self.fetch_with_escalation(url)
        if html:
            return ScrapedProduct(
                url=url,
                product_id="TEST123",
                title="Test Product",
                price=99.99,
                currency="USD",
                platform="test"
            )
        return None


@pytest.fixture
def scraper():
    config = Config.from_env()
    config.request_delay = 0.1
    config.max_retries = 3
    
    with patch('app.scrapers.enhanced_base.MiyaipLoader'):
        scraper = MockEnhancedScraper(config)
        scraper.miyaip_pool = Mock()
        return scraper


def test_enhanced_scraper_initialization(scraper):
    """Test enhanced scraper initializes with detector and escalator."""
    assert scraper.detector is not None
    assert scraper.escalator is not None
    assert scraper._current_engine == EngineLevel.L1_STATIC


def test_get_proxy_for_engine_l1(scraper):
    """Test L1 engine uses miyaip static proxies."""
    mock_proxy = Mock()
    mock_proxy.url = "http://user:pass@1.2.3.4:8080"
    scraper.miyaip_pool.get_proxy.return_value = mock_proxy
    
    proxy = scraper._get_proxy_for_engine(EngineLevel.L1_STATIC)
    assert proxy == "http://user:pass@1.2.3.4:8080"


def test_get_proxy_for_engine_l2_plus(scraper):
    """Test L2+ engines use configured proxy."""
    proxy = scraper._get_proxy_for_engine(EngineLevel.L2_JS_RENDER)
    assert proxy == scraper.config.proxy.url


def test_fetch_single_success(scraper):
    """Test successful single fetch."""
    mock_response = Mock()
    mock_response.text = "<html>Product Page</html>"
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        with patch.object(scraper.detector, 'detect') as mock_detect:
            mock_detect.return_value = None
            
            result = scraper._fetch_single("https://example.com/product")
            assert result == "<html>Product Page</html>"


def test_fetch_single_timeout(scraper):
    """Test fetch handles timeout."""
    import httpx
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("Timeout")
        
        result = scraper._fetch_single("https://example.com/product")
        assert result is None


def test_fetch_single_http_error(scraper):
    """Test fetch handles HTTP errors."""
    import httpx
    
    mock_response = Mock()
    mock_response.status_code = 403
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=Mock(), response=mock_response
        )
        
        result = scraper._fetch_single("https://example.com/product")
        assert result is None


def test_fetch_single_anti_crawl_detection(scraper):
    """Test fetch detects anti-crawl patterns in response."""
    mock_response = Mock()
    mock_response.text = "<html><title>Access Denied</title></html>"
    mock_response.status_code = 403
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        with patch.object(scraper.detector, 'detect') as mock_detect:
            mock_detect.return_value = DetectionResult(
                is_blocked=True,
                block_type=BlockType.BLOCKED,
                confidence=0.9,
                evidence="403 status",
                recommended_level=EngineLevel.L2_JS_RENDER
            )
            
            result = scraper._fetch_single("https://example.com/product")
            assert result is None


def test_fetch_with_escalation_success_first_try(scraper):
    """Test escalation succeeds on first try."""
    with patch.object(scraper, '_fetch_single') as mock_fetch:
        mock_fetch.return_value = "<html>Success</html>"
        
        result = scraper.fetch_with_escalation("https://example.com/product")
        assert result == "<html>Success</html>"


def test_get_engine_stats(scraper):
    """Test engine statistics reporting."""
    stats = scraper.get_engine_stats()
    assert isinstance(stats, dict)


def test_scrape_with_escalation_integration(scraper):
    """Test full scrape with escalation integration."""
    with patch.object(scraper, 'fetch_with_escalation') as mock_fetch:
        mock_fetch.return_value = "<html>Product</html>"
        
        product = scraper.scrape("https://example.com/product")
        assert product is not None
        assert product.title == "Test Product"
        assert product.price == 99.99


def test_scrape_returns_none_on_fetch_failure(scraper):
    """Test scrape returns None when fetch fails."""
    with patch.object(scraper, 'fetch_with_escalation') as mock_fetch:
        mock_fetch.return_value = None
        
        product = scraper.scrape("https://example.com/product")
        assert product is None
