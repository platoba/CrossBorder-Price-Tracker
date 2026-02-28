"""Tests for price predictor."""
import pytest
from datetime import datetime, timedelta
from app.models.database import Database
from app.services.predictor import PricePredictor


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def predictor(db):
    return PricePredictor(db)


def _seed_price_history(db, product_id, prices):
    """Seed price history with timestamps."""
    for i, price in enumerate(prices):
        db.record_price(product_id, price, "USD")


class TestMovingAverage:
    def test_sma_basic(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 105, 95, 110, 90, 100, 98, 102, 97, 103])
        result = predictor.moving_average(pid, window=3)
        assert len(result) > 0
        assert all("sma" in r for r in result)
        assert all("above_sma" in r for r in result)

    def test_sma_insufficient_data(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 105])
        result = predictor.moving_average(pid, window=5)
        assert result == []

    def test_sma_window_size(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        prices = list(range(100, 120))
        _seed_price_history(db, pid, prices)
        result = predictor.moving_average(pid, window=5)
        assert len(result) == len(prices) - 4


class TestExponentialMovingAverage:
    def test_ema_basic(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 105, 95, 110, 90, 100, 98])
        result = predictor.exponential_moving_average(pid, span=3)
        assert len(result) == 7
        assert all("ema" in r for r in result)

    def test_ema_insufficient(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100])
        result = predictor.exponential_moving_average(pid)
        assert result == []


class TestLinearRegression:
    def test_rising_trend(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 102, 105, 108, 110, 113, 115])
        result = predictor.linear_regression(pid)
        assert result is not None
        assert result["slope"] > 0
        assert result["trend"] == "rising"
        assert len(result["predictions"]) == 7

    def test_falling_trend(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [120, 115, 110, 105, 100, 95, 90])
        result = predictor.linear_regression(pid)
        assert result is not None
        assert result["slope"] < 0
        assert result["trend"] == "falling"

    def test_stable_trend(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 100.005, 99.995, 100.001, 99.999])
        result = predictor.linear_regression(pid)
        assert result is not None
        assert result["trend"] == "stable"

    def test_insufficient_data(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 110])
        result = predictor.linear_regression(pid)
        assert result is None

    def test_r_squared(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        # Perfect linear data should have high R²
        _seed_price_history(db, pid, [100, 110, 120, 130, 140])
        result = predictor.linear_regression(pid)
        assert result["r_squared"] > 0.95

    def test_predictions_positive(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 110, 120, 130, 140])
        result = predictor.linear_regression(pid)
        for pred in result["predictions"]:
            assert pred["predicted_price"] >= 0


class TestForecast:
    def test_forecast_basic(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon", title="Test")
        _seed_price_history(db, pid, [100, 105, 95, 110, 90, 100, 98, 102])
        result = predictor.forecast(pid)
        assert "forecast_price" in result
        assert "confidence_interval" in result
        assert "direction" in result
        assert result["data_points"] == 8

    def test_forecast_not_found(self, predictor):
        result = predictor.forecast(999)
        assert "error" in result

    def test_forecast_insufficient_data(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 110])
        result = predictor.forecast(pid)
        assert "error" in result

    def test_forecast_confidence_interval(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 105, 95, 110, 90, 100, 98])
        result = predictor.forecast(pid)
        ci = result["confidence_interval"]
        assert ci["low"] < ci["high"]
        assert ci["low"] <= result["forecast_price"]
        assert ci["high"] >= result["forecast_price"]


class TestDetectAnomalies:
    def test_detect_spike(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        prices = [100, 98, 102, 99, 101, 200, 100, 99, 101, 98]  # 200 is anomaly
        _seed_price_history(db, pid, prices)
        anomalies = predictor.detect_anomalies(pid)
        assert len(anomalies) >= 1
        spike = [a for a in anomalies if a["type"] == "spike"]
        assert len(spike) >= 1

    def test_detect_dip(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        prices = [100, 102, 98, 101, 99, 10, 100, 101, 99, 102]  # 10 is anomaly
        _seed_price_history(db, pid, prices)
        anomalies = predictor.detect_anomalies(pid)
        dips = [a for a in anomalies if a["type"] == "dip"]
        assert len(dips) >= 1

    def test_no_anomalies(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 100, 100, 100, 100])
        anomalies = predictor.detect_anomalies(pid)
        assert len(anomalies) == 0

    def test_insufficient_data(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 200])
        anomalies = predictor.detect_anomalies(pid)
        assert anomalies == []


class TestSeasonalPattern:
    def test_insufficient_data(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        _seed_price_history(db, pid, [100, 105, 95])
        result = predictor.seasonal_pattern(pid)
        assert "error" in result

    def test_with_enough_data(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        # 20 data points
        _seed_price_history(db, pid, list(range(100, 120)))
        result = predictor.seasonal_pattern(pid)
        assert "daily_averages" in result
        assert "best_buy_day" in result
        assert "worst_buy_day" in result


class TestBuySignal:
    def test_buy_signal_at_low(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon",
                             target_price=85)
        for p in [100, 110, 120, 130, 100, 90, 80]:
            db.record_price(pid, p)
        result = predictor.buy_signal(pid)
        assert "signal" in result
        assert result["signal"] in ("BUY", "HOLD", "WAIT")
        assert "reasons" in result

    def test_buy_signal_at_high(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        for p in [80, 90, 100, 110, 120, 130]:
            db.record_price(pid, p)
        result = predictor.buy_signal(pid)
        assert result["signal"] in ("BUY", "HOLD", "WAIT")

    def test_buy_signal_no_data(self, predictor, db):
        result = predictor.buy_signal(999)
        assert result["signal"] == "UNKNOWN"

    def test_buy_signal_confidence(self, predictor, db):
        pid = db.add_product("https://amazon.com/dp/A1", "amazon")
        for p in [100, 110, 120, 80, 70]:
            db.record_price(pid, p)
        result = predictor.buy_signal(pid)
        assert 0 <= result["confidence"] <= 100
