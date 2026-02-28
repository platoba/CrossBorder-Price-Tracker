"""Tests for scrapers."""
import pytest
from app.scrapers.amazon import AmazonScraper
from app.scrapers.aliexpress import AliExpressScraper
from app.scrapers.shopee import ShopeeScraper
from app.scrapers.ali1688 import Ali1688Scraper
from app.scrapers import get_scraper


class TestAmazonScraper:
    @pytest.fixture
    def scraper(self):
        return AmazonScraper()

    def test_parse_price_whole_fraction(self, scraper):
        html = '''
        <span class="a-price-whole">29</span>
        <span class="a-price-fraction">99</span>
        <span id="productTitle"> Test Product Title  </span>
        '''
        result = scraper.parse_price(html, "https://www.amazon.com/dp/B09V3KXJPB")
        assert result is not None
        assert result.price == 29.99
        assert result.title == "Test Product Title"

    def test_parse_price_json(self, scraper):
        html = '"priceAmount":45.50'
        result = scraper.parse_price(html, "https://www.amazon.com/dp/B123456789")
        assert result.price == 45.50

    def test_parse_price_offscreen(self, scraper):
        html = '<span class="a-price"><span class="a-offscreen">$19.99</span></span>'
        result = scraper.parse_price(html, "https://www.amazon.com/dp/B123456789")
        assert result.price == 19.99

    def test_detect_currency_uk(self, scraper):
        assert scraper._detect_currency("https://www.amazon.co.uk/dp/B123") == "GBP"

    def test_detect_currency_de(self, scraper):
        assert scraper._detect_currency("https://www.amazon.de/dp/B123") == "EUR"

    def test_detect_currency_jp(self, scraper):
        assert scraper._detect_currency("https://www.amazon.co.jp/dp/B123") == "JPY"

    def test_in_stock(self, scraper):
        html = '<span>In Stock</span><span id="productTitle">Test</span>'
        result = scraper.parse_price(html, "https://www.amazon.com/dp/B123456789")
        assert result.in_stock is True

    def test_rating(self, scraper):
        html = '<span>4.5 out of 5 stars</span><span id="productTitle">Test</span>'
        result = scraper.parse_price(html, "https://www.amazon.com/dp/B123456789")
        assert result.rating == 4.5

    def test_review_count(self, scraper):
        html = '<span>1,234 global ratings</span><span id="productTitle">Test</span>'
        result = scraper.parse_price(html, "https://www.amazon.com/dp/B123456789")
        assert result.review_count == 1234


class TestAliExpressScraper:
    @pytest.fixture
    def scraper(self):
        return AliExpressScraper()

    def test_parse_json_ld(self, scraper):
        html = '''
        <script type="application/ld+json">
        {"name": "Test AliExpress Product", "offers": {"price": 12.99}}
        </script>
        '''
        result = scraper.parse_price(html, "https://www.aliexpress.com/item/1005006.html")
        assert result.price == 12.99
        assert result.title == "Test AliExpress Product"

    def test_parse_formatted_amount(self, scraper):
        html = '"formatedAmount":"US $5.99"'
        result = scraper.parse_price(html, "https://www.aliexpress.com/item/1005006.html")
        assert result.price == 5.99

    def test_parse_subject(self, scraper):
        html = '"subject":"Cool Gadget"'
        result = scraper.parse_price(html, "https://www.aliexpress.com/item/1005006.html")
        assert result.title == "Cool Gadget"


class TestShopeeScraper:
    @pytest.fixture
    def scraper(self):
        return ShopeeScraper()

    def test_detect_region_sg(self, scraper):
        assert scraper._detect_region("https://shopee.sg/product") == "sg"

    def test_detect_region_my(self, scraper):
        assert scraper._detect_region("https://shopee.com.my/product") == "com.my"

    def test_parse_url(self, scraper):
        shop_id, item_id = scraper._parse_shopee_url("https://shopee.sg/item-i.123.456")
        assert shop_id == "123"
        assert item_id == "456"


class TestAli1688Scraper:
    @pytest.fixture
    def scraper(self):
        return Ali1688Scraper()

    def test_parse_title(self, scraper):
        html = '<title>优质商品 - 1688.com</title>'
        result = scraper.parse_price(html, "https://detail.1688.com/offer/789.html")
        assert result.title == "优质商品"

    def test_parse_price_json(self, scraper):
        html = '"price":"15.80"'
        result = scraper.parse_price(html, "https://detail.1688.com/offer/789.html")
        assert result.price == 15.80


class TestGetScraper:
    def test_get_amazon(self):
        s = get_scraper("amazon")
        assert isinstance(s, AmazonScraper)

    def test_get_aliexpress(self):
        s = get_scraper("aliexpress")
        assert isinstance(s, AliExpressScraper)

    def test_get_shopee(self):
        s = get_scraper("shopee")
        assert isinstance(s, ShopeeScraper)

    def test_get_1688(self):
        s = get_scraper("1688")
        assert isinstance(s, Ali1688Scraper)

    def test_unknown_raises(self):
        with pytest.raises(ValueError):
            get_scraper("ebay")
