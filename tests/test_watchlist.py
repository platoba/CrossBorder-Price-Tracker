"""Tests for watchlist manager."""
import pytest
from app.models.database import Database
from app.services.watchlist import WatchlistManager, Watchlist


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def manager(db, tmp_path):
    return WatchlistManager(db, str(tmp_path / "watchlists.json"))


class TestWatchlistCRUD:
    def test_create_watchlist(self, manager):
        wl = manager.create("wl1", "My List", "Test watchlist")
        assert wl.id == "wl1"
        assert wl.name == "My List"
        assert wl.created_at != ""

    def test_get_watchlist(self, manager):
        manager.create("wl1", "My List")
        wl = manager.get("wl1")
        assert wl is not None
        assert wl.name == "My List"

    def test_get_nonexistent(self, manager):
        assert manager.get("fake") is None

    def test_delete_watchlist(self, manager):
        manager.create("wl1", "To Delete")
        assert manager.delete("wl1") is True
        assert manager.get("wl1") is None

    def test_delete_nonexistent(self, manager):
        assert manager.delete("fake") is False

    def test_list_all(self, manager):
        manager.create("wl1", "List 1")
        manager.create("wl2", "List 2")
        assert len(manager.list_all()) == 2

    def test_persistence(self, db, tmp_path):
        path = str(tmp_path / "persist.json")
        m1 = WatchlistManager(db, path)
        m1.create("wl1", "Persisted")
        m2 = WatchlistManager(db, path)
        assert m2.get("wl1") is not None


class TestProductManagement:
    def test_add_product(self, manager, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        manager.create("wl1", "My List")
        assert manager.add_product("wl1", pid) is True

    def test_add_product_duplicate(self, manager, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        manager.create("wl1", "My List")
        manager.add_product("wl1", pid)
        manager.add_product("wl1", pid)  # duplicate
        wl = manager.get("wl1")
        assert wl.product_ids.count(pid) == 1

    def test_add_product_nonexistent_list(self, manager):
        assert manager.add_product("fake", 1) is False

    def test_remove_product(self, manager, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        manager.create("wl1", "My List")
        manager.add_product("wl1", pid)
        assert manager.remove_product("wl1", pid) is True
        wl = manager.get("wl1")
        assert pid not in wl.product_ids

    def test_get_products(self, manager, db):
        pid1 = db.add_product("https://amazon.com/dp/A1", "amazon", title="Product 1")
        pid2 = db.add_product("https://amazon.com/dp/A2", "amazon", title="Product 2")
        manager.create("wl1", "My List")
        manager.add_product("wl1", pid1)
        manager.add_product("wl1", pid2)
        products = manager.get_products("wl1")
        assert len(products) == 2

    def test_get_products_empty_list(self, manager):
        manager.create("wl1", "Empty")
        assert manager.get_products("wl1") == []


class TestBulkOperations:
    def test_bulk_add_urls(self, manager, db):
        manager.create("wl1", "Bulk Test")
        urls = [
            "https://amazon.com/dp/B08N5WRWNW",
            "https://aliexpress.com/item/12345.html",
            "https://invalid-url.com/nothing",
        ]
        result = manager.bulk_add_urls("wl1", urls)
        assert result["added"] == 2
        assert result["failed"] == 1

    def test_bulk_add_existing(self, manager, db):
        db.add_product("https://amazon.com/dp/B08N5WRWNW", "amazon")
        manager.create("wl1", "Bulk Test")
        urls = ["https://amazon.com/dp/B08N5WRWNW"]
        result = manager.bulk_add_urls("wl1", urls)
        assert result["added"] == 1
        assert result["skipped"] == 0

    def test_bulk_add_skip_duplicates(self, manager, db):
        pid = db.add_product("https://amazon.com/dp/B08N5WRWNW", "amazon")
        manager.create("wl1", "Bulk Test")
        manager.add_product("wl1", pid)
        urls = ["https://amazon.com/dp/B08N5WRWNW"]
        result = manager.bulk_add_urls("wl1", urls)
        assert result["skipped"] == 1

    def test_bulk_add_nonexistent_list(self, manager):
        result = manager.bulk_add_urls("fake", ["https://amazon.com/dp/A1"])
        assert "error" in result

    def test_bulk_remove(self, manager, db):
        manager.create("wl1", "Bulk Remove")
        pids = []
        for i in range(5):
            pid = db.add_product(f"https://amazon.com/dp/A{i}", "amazon")
            manager.add_product("wl1", pid)
            pids.append(pid)
        removed = manager.bulk_remove("wl1", pids[:3])
        assert removed == 3
        wl = manager.get("wl1")
        assert len(wl.product_ids) == 2


class TestMergeAndSearch:
    def test_merge_watchlists(self, manager, db):
        pid1 = db.add_product("https://amazon.com/dp/A1", "amazon")
        pid2 = db.add_product("https://amazon.com/dp/A2", "amazon")
        pid3 = db.add_product("https://amazon.com/dp/A3", "amazon")
        manager.create("src", "Source")
        manager.create("tgt", "Target")
        manager.add_product("src", pid1)
        manager.add_product("src", pid2)
        manager.add_product("tgt", pid2)
        manager.add_product("tgt", pid3)
        assert manager.merge_watchlists("src", "tgt") is True
        tgt = manager.get("tgt")
        assert len(tgt.product_ids) == 3  # pid1, pid2, pid3

    def test_merge_with_delete_source(self, manager, db):
        manager.create("src", "Source")
        manager.create("tgt", "Target")
        manager.merge_watchlists("src", "tgt", delete_source=True)
        assert manager.get("src") is None
        assert manager.get("tgt") is not None

    def test_merge_nonexistent(self, manager):
        assert manager.merge_watchlists("fake1", "fake2") is False

    def test_find_product_watchlists(self, manager, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        manager.create("wl1", "List 1")
        manager.create("wl2", "List 2")
        manager.create("wl3", "List 3")
        manager.add_product("wl1", pid)
        manager.add_product("wl3", pid)
        found = manager.find_product_watchlists(pid)
        assert len(found) == 2
        ids = {wl.id for wl in found}
        assert "wl1" in ids
        assert "wl3" in ids


class TestSummaryAndStats:
    def test_summary(self, manager, db):
        pid1 = db.add_product("https://amazon.com/dp/A1", "amazon", title="P1")
        pid2 = db.add_product("https://aliexpress.com/item/1.html", "aliexpress", title="P2")
        db.record_price(pid1, 100)
        db.record_price(pid2, 50)
        manager.create("wl1", "Test")
        manager.add_product("wl1", pid1)
        manager.add_product("wl1", pid2)
        summary = manager.summary("wl1")
        assert summary["product_count"] == 2
        assert summary["total_value"] == 150
        assert "amazon" in summary["platforms"]

    def test_summary_nonexistent(self, manager):
        assert "error" in manager.summary("fake")

    def test_stats(self, manager, db):
        manager.create("wl1", "List 1")
        manager.create("wl2", "List 2")
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        manager.add_product("wl1", pid)
        manager.add_product("wl2", pid)
        stats = manager.stats()
        assert stats["total_watchlists"] == 2
        assert stats["total_unique_products"] == 1
