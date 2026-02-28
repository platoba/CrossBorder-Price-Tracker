"""Tests for product models and database."""
import os
import tempfile
import pytest
from app.models.database import Database
from app.models.product import detect_platform, extract_product_id, ScrapedProduct


class TestDetectPlatform:
    def test_amazon_us(self):
        assert detect_platform("https://www.amazon.com/dp/B09V3KXJPB") == "amazon"

    def test_amazon_uk(self):
        assert detect_platform("https://www.amazon.co.uk/dp/B09V3KXJPB") == "amazon"

    def test_amazon_de(self):
        assert detect_platform("https://www.amazon.de/dp/B09V3KXJPB") == "amazon"

    def test_amazon_jp(self):
        assert detect_platform("https://www.amazon.co.jp/dp/B09V3KXJPB") == "amazon"

    def test_aliexpress(self):
        assert detect_platform("https://www.aliexpress.com/item/1005006.html") == "aliexpress"

    def test_shopee_sg(self):
        assert detect_platform("https://shopee.sg/product-i.123.456") == "shopee"

    def test_shopee_my(self):
        assert detect_platform("https://shopee.com.my/product-i.123.456") == "shopee"

    def test_1688(self):
        assert detect_platform("https://detail.1688.com/offer/123.html") == "1688"

    def test_unknown(self):
        assert detect_platform("https://example.com/product") == "unknown"


class TestExtractProductId:
    def test_amazon_dp(self):
        assert extract_product_id("https://www.amazon.com/dp/B09V3KXJPB", "amazon") == "B09V3KXJPB"

    def test_amazon_product(self):
        assert extract_product_id("https://www.amazon.com/product/B09V3KXJPB/ref=xx", "amazon") == "B09V3KXJPB"

    def test_aliexpress(self):
        assert extract_product_id("https://www.aliexpress.com/item/1005006.html", "aliexpress") == "1005006"

    def test_1688(self):
        assert extract_product_id("https://detail.1688.com/offer/789456.html", "1688") == "789456"

    def test_no_match(self):
        assert extract_product_id("https://example.com", "unknown") == ""


class TestScrapedProduct:
    def test_defaults(self):
        p = ScrapedProduct(url="http://test.com", platform="amazon", product_id="B123")
        assert p.price == 0.0
        assert p.in_stock is True
        assert p.raw_data == {}

    def test_with_values(self):
        p = ScrapedProduct(
            url="http://test.com", platform="amazon", product_id="B123",
            title="Test Product", price=29.99, currency="USD",
        )
        assert p.title == "Test Product"
        assert p.price == 29.99


class TestDatabase:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / "test.db"))

    def test_add_product(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123", "Test")
        assert pid > 0

    def test_add_duplicate(self, db):
        pid1 = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        pid2 = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        assert pid1 == pid2

    def test_record_price(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        result = db.record_price(pid, 29.99)
        assert result is not None
        assert result["price"] == 29.99

    def test_price_change_detection(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.record_price(pid, 29.99)
        result = db.record_price(pid, 24.99)
        assert result["change_pct"] < 0

    def test_price_history(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.record_price(pid, 29.99)
        db.record_price(pid, 24.99)
        db.record_price(pid, 27.50)
        history = db.get_price_history(pid, 30)
        assert len(history) == 3

    def test_get_active_products(self, db):
        db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.add_product("https://amazon.com/dp/B456", "amazon", "B456")
        products = db.get_active_products()
        assert len(products) == 2

    def test_remove_product(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.remove_product(pid)
        products = db.get_active_products()
        assert len(products) == 0

    def test_add_alert(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        aid = db.add_alert(pid, "price_drop", 29.99, 24.99, -16.7)
        assert aid > 0

    def test_pending_alerts(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.add_alert(pid, "price_drop", 29.99, 24.99, -16.7)
        alerts = db.get_pending_alerts()
        assert len(alerts) == 1

    def test_mark_alert_notified(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        aid = db.add_alert(pid, "price_drop", 29.99, 24.99, -16.7)
        db.mark_alert_notified(aid)
        alerts = db.get_pending_alerts()
        assert len(alerts) == 0

    def test_stats(self, db):
        db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        stats = db.get_stats()
        assert stats["total_products"] == 1
        assert stats["active_products"] == 1

    def test_lowest_highest(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.record_price(pid, 30.0)
        db.record_price(pid, 20.0)
        db.record_price(pid, 25.0)
        product = db.get_product(pid)
        assert product["lowest_price"] == 20.0
        assert product["highest_price"] == 30.0

    def test_record_error(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123")
        db.record_error(pid)
        db.record_error(pid)
        product = db.get_product(pid)
        assert product["error_count"] == 2
