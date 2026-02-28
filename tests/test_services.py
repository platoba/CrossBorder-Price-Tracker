"""Tests for services."""
import pytest
from app.config import Config, ProxyConfig, NotifyConfig
from app.models.database import Database
from app.services.monitor import PriceMonitor
from app.services.reporter import PriceReporter
from app.services.notifier import format_price_alert
from app.utils.proxy import ProxyPool
from app.utils.ua import random_ua, random_headers


class TestConfig:
    def test_default_config(self):
        c = Config()
        assert c.price_drop_threshold == 5.0
        assert c.check_interval == 3600
        assert c.max_retries == 3

    def test_proxy_url_none(self):
        p = ProxyConfig(type="none")
        assert p.url is None

    def test_proxy_url_http(self):
        p = ProxyConfig(type="http", host="1.2.3.4", port=8080)
        assert p.url == "http://1.2.3.4:8080"

    def test_proxy_url_socks5_with_auth(self):
        p = ProxyConfig(type="socks5", host="1.2.3.4", port=9595, user="u", password="p")
        assert p.url == "socks5://u:p@1.2.3.4:9595"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("PROXY_TYPE", "http")
        monkeypatch.setenv("PROXY_HOST", "proxy.example.com")
        monkeypatch.setenv("PROXY_PORT", "8888")
        monkeypatch.setenv("PRICE_DROP_THRESHOLD", "10")
        c = Config.from_env()
        assert c.proxy.type == "http"
        assert c.proxy.host == "proxy.example.com"
        assert c.price_drop_threshold == 10.0


class TestProxyPool:
    def test_add_and_count(self):
        pool = ProxyPool()
        pool.add("http://1.2.3.4:8080")
        pool.add("http://5.6.7.8:8080")
        assert pool.total_count == 2
        assert pool.active_count == 2

    def test_get_next(self):
        pool = ProxyPool()
        pool.add("http://1.2.3.4:8080")
        proxy = pool.get_next()
        assert proxy == "http://1.2.3.4:8080"

    def test_get_next_empty(self):
        pool = ProxyPool()
        assert pool.get_next() is None

    def test_report_success(self):
        pool = ProxyPool()
        pool.add("http://1.2.3.4:8080")
        pool.report_success("http://1.2.3.4:8080")
        assert pool._proxies[0].success_count == 1

    def test_deactivate_on_failures(self):
        pool = ProxyPool()
        pool.add("http://1.2.3.4:8080")
        for _ in range(10):
            pool.report_failure("http://1.2.3.4:8080")
        assert pool.active_count == 0

    def test_country_filter(self):
        pool = ProxyPool()
        pool.add("http://1.2.3.4:8080", country="US")
        pool.add("http://5.6.7.8:8080", country="DE")
        proxy = pool.get_next(country="DE")
        assert "5.6.7.8" in proxy

    def test_stats(self):
        pool = ProxyPool()
        pool.add("http://1.2.3.4:8080")
        s = pool.stats()
        assert s["total"] == 1


class TestUA:
    def test_random_ua_desktop(self):
        ua = random_ua(mobile=False)
        assert "Mozilla" in ua
        assert "Chrome" in ua

    def test_random_ua_mobile(self):
        ua = random_ua(mobile=True)
        assert "Mobile" in ua

    def test_random_headers(self):
        h = random_headers()
        assert "User-Agent" in h
        assert "Accept" in h

    def test_headers_with_referer(self):
        h = random_headers(referer="https://google.com")
        assert h["Referer"] == "https://google.com"


class TestPriceReporter:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(str(tmp_path / "test.db"))

    def test_product_summary_empty(self, db):
        reporter = PriceReporter(db)
        s = reporter.product_summary(999)
        assert s == {}

    def test_product_summary(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123", "Test")
        db.record_price(pid, 30.0)
        db.record_price(pid, 25.0)
        db.record_price(pid, 28.0)
        reporter = PriceReporter(db)
        s = reporter.product_summary(pid, 30)
        assert s["data_points"] == 3
        assert s["lowest_price"] == 25.0
        assert s["highest_price"] == 30.0

    def test_full_report_text(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123", "Test Product")
        db.record_price(pid, 30.0)
        reporter = PriceReporter(db)
        report = reporter.full_report(format="text")
        assert "价格追踪报告" in report

    def test_full_report_json(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123", "Test Product")
        db.record_price(pid, 30.0)
        reporter = PriceReporter(db)
        report = reporter.full_report(format="json")
        import json
        data = json.loads(report)
        assert "stats" in data
        assert "products" in data

    def test_buy_recommendation_strong(self, db):
        pid = db.add_product("https://amazon.com/dp/B123", "amazon", "B123", "Test")
        db.record_price(pid, 30.0)
        db.record_price(pid, 20.0)  # lowest
        db.record_price(pid, 20.5)  # near lowest
        reporter = PriceReporter(db)
        s = reporter.product_summary(pid, 30)
        assert s["recommendation"] == "strong_buy"


class TestFormatPriceAlert:
    def test_price_drop(self):
        product = {"title": "Test", "platform": "amazon", "currency": "USD", "url": "http://x"}
        title, msg = format_price_alert(product, 30.0, 25.0, -16.7)
        assert "降价" in title
        assert "16.7%" in title
        assert "30.00" in msg
        assert "25.00" in msg

    def test_price_increase(self):
        product = {"title": "Test", "platform": "amazon", "currency": "USD", "url": "http://x"}
        title, msg = format_price_alert(product, 25.0, 30.0, 20.0)
        assert "涨价" in title
