"""Tests for price comparison engine."""
import pytest
import tempfile
from app.models.database import Database
from app.services.comparator import PriceComparator
from app.utils.currency import CurrencyConverter


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def converter(tmp_path):
    return CurrencyConverter(cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def comparator(db, converter):
    return PriceComparator(db, converter)


def _add_product(db, url, platform, title, price, currency="USD"):
    pid = db.add_product(url=url, platform=platform, title=title)
    db.record_price(pid, price, currency)
    return pid


class TestFindSimilarProducts:
    def test_find_similar_by_title(self, comparator, db):
        pid1 = _add_product(db, "https://amazon.com/dp/A1", "amazon",
                            "Wireless Bluetooth Headphones Noise Canceling", 99)
        pid2 = _add_product(db, "https://aliexpress.com/item/1.html", "aliexpress",
                            "Wireless Bluetooth Headphones Active Noise Canceling", 45)
        similar = comparator.find_similar_products(pid1, threshold=0.4)
        assert len(similar) >= 1
        assert similar[0]["id"] == pid2

    def test_no_similar_products(self, comparator, db):
        pid1 = _add_product(db, "https://amazon.com/dp/A1", "amazon",
                            "USB Cable Type C", 10)
        _add_product(db, "https://aliexpress.com/item/1.html", "aliexpress",
                     "Luxury Watch Gold Diamond", 500)
        similar = comparator.find_similar_products(pid1, threshold=0.5)
        assert len(similar) == 0

    def test_similar_sorted_by_score(self, comparator, db):
        pid1 = _add_product(db, "https://amazon.com/dp/A1", "amazon",
                            "Red Blue Green Shoes Running", 80)
        _add_product(db, "https://a.com/1", "amazon",
                     "Red Blue Shoes", 60)
        _add_product(db, "https://b.com/2", "amazon",
                     "Red Blue Green Shoes Running Fast", 70)
        similar = comparator.find_similar_products(pid1, threshold=0.3)
        assert len(similar) >= 1
        # Higher similarity first
        if len(similar) >= 2:
            assert similar[0]["similarity"] >= similar[1]["similarity"]

    def test_empty_title(self, comparator, db):
        pid1 = _add_product(db, "https://amazon.com/dp/A1", "amazon", "", 50)
        similar = comparator.find_similar_products(pid1)
        assert similar == []


class TestCrossPlatformComparison:
    def test_comparison_basic(self, comparator, db):
        pid1 = _add_product(db, "https://amazon.com/dp/A1", "amazon",
                            "Test Product Amazing", 100)
        _add_product(db, "https://aliexpress.com/item/1.html", "aliexpress",
                     "Test Product Amazing Deal", 45)
        result = comparator.cross_platform_comparison(pid1)
        assert "items" in result
        assert "best_deal" in result
        assert result["platforms_compared"] >= 1

    def test_comparison_not_found(self, comparator):
        result = comparator.cross_platform_comparison(999)
        assert "error" in result

    def test_comparison_with_savings(self, comparator, db):
        pid1 = _add_product(db, "https://amazon.com/dp/A1", "amazon",
                            "Gadget Super Cool", 100)
        _add_product(db, "https://aliexpress.com/item/1.html", "aliexpress",
                     "Gadget Super Cool Version", 50)
        result = comparator.cross_platform_comparison(pid1)
        if result.get("savings"):
            assert result["savings"]["amount"] > 0
            assert result["savings"]["percent"] > 0


class TestPlatformPriceMap:
    def test_groups_by_platform(self, comparator, db):
        _add_product(db, "https://amazon.com/dp/A1", "amazon", "Prod 1", 100)
        _add_product(db, "https://amazon.com/dp/A2", "amazon", "Prod 2", 200)
        _add_product(db, "https://aliexpress.com/item/1.html", "aliexpress", "Prod 3", 50)

        result = comparator.platform_price_map()
        assert "amazon" in result
        assert "aliexpress" in result
        assert len(result["amazon"]) == 2
        assert len(result["aliexpress"]) == 1

    def test_sorted_within_platform(self, comparator, db):
        _add_product(db, "https://amazon.com/dp/A1", "amazon", "Expensive", 200)
        _add_product(db, "https://amazon.com/dp/A2", "amazon", "Cheap", 50)

        result = comparator.platform_price_map()
        amazon = result["amazon"]
        assert amazon[0]["converted_price"] <= amazon[1]["converted_price"]


class TestCheapestByPlatform:
    def test_finds_cheapest(self, comparator, db):
        _add_product(db, "https://amazon.com/dp/A1", "amazon", "A1", 150)
        _add_product(db, "https://amazon.com/dp/A2", "amazon", "A2", 50)
        _add_product(db, "https://aliexpress.com/item/1.html", "aliexpress", "Ali1", 30)

        result = comparator.cheapest_by_platform()
        assert len(result) == 2
        # Cheapest overall should be first
        assert result[0]["product"]["converted_price"] <= result[1]["product"]["converted_price"]


class TestPriceSpreadAnalysis:
    def test_spread_with_data(self, comparator, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        for price in [100, 105, 95, 110, 90, 100, 98]:
            db.record_price(pid, price)

        result = comparator.price_spread_analysis(pid)
        assert "std_dev" in result
        assert "cv_percent" in result
        assert "stability_score" in result
        assert "volatility" in result
        assert result["data_points"] == 7

    def test_spread_insufficient_data(self, comparator, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        db.record_price(pid, 100)
        result = comparator.price_spread_analysis(pid)
        assert "error" in result


class TestDealScore:
    def test_deal_score_at_low(self, comparator, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        for price in [100, 120, 80, 90, 110]:
            db.record_price(pid, price)
        # Current price should be the last recorded (110)
        # But lowest=80, highest=120
        result = comparator.deal_score(pid)
        assert "score" in result
        assert 0 <= result["score"] <= 100

    def test_deal_score_no_data(self, comparator, db):
        result = comparator.deal_score(999)
        assert result["score"] == 0

    def test_deal_score_with_target(self, comparator, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon",
                             target_price=90)
        for price in [100, 110, 120, 85]:
            db.record_price(pid, price)
        result = comparator.deal_score(pid)
        assert result["at_target"] is True


class TestTopDeals:
    def test_top_deals(self, comparator, db):
        for i in range(5):
            pid = db.add_product(f"https://amazon.com/dp/A{i}", "amazon",
                                 title=f"Product {i}")
            for price in [100 + i * 10, 120 + i * 10, 80 + i * 5]:
                db.record_price(pid, price)

        deals = comparator.top_deals(limit=3)
        assert len(deals) <= 3
        if len(deals) >= 2:
            assert deals[0]["score"] >= deals[1]["score"]
