"""Price trend prediction using moving averages and basic statistics."""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app.models.database import Database

logger = logging.getLogger(__name__)


class PricePredictor:
    """Simple price trend prediction based on historical data."""

    def __init__(self, db: Database):
        self.db = db

    def moving_average(self, product_id: int, window: int = 7,
                       days: int = 90) -> List[dict]:
        """
        Calculate Simple Moving Average (SMA) for price history.

        Args:
            product_id: Product ID
            window: MA window size (days)
            days: History period

        Returns:
            List of dicts with date, price, sma
        """
        history = self.db.get_price_history(product_id, days)
        if len(history) < window:
            return []

        prices = [h["price"] for h in history]
        dates = [h["recorded_at"] for h in history]

        result = []
        for i in range(window - 1, len(prices)):
            window_prices = prices[i - window + 1:i + 1]
            sma = sum(window_prices) / len(window_prices)
            result.append({
                "date": dates[i],
                "price": prices[i],
                "sma": round(sma, 2),
                "above_sma": prices[i] > sma,
            })

        return result

    def exponential_moving_average(self, product_id: int, span: int = 7,
                                   days: int = 90) -> List[dict]:
        """
        Calculate Exponential Moving Average (EMA).

        Args:
            product_id: Product ID
            span: EMA span (smoothing period)
            days: History period
        """
        history = self.db.get_price_history(product_id, days)
        if len(history) < 2:
            return []

        prices = [h["price"] for h in history]
        dates = [h["recorded_at"] for h in history]
        multiplier = 2 / (span + 1)

        ema = [prices[0]]
        for i in range(1, len(prices)):
            val = prices[i] * multiplier + ema[-1] * (1 - multiplier)
            ema.append(round(val, 2))

        return [
            {"date": dates[i], "price": prices[i], "ema": ema[i],
             "above_ema": prices[i] > ema[i]}
            for i in range(len(prices))
        ]

    def linear_regression(self, product_id: int,
                          days: int = 30) -> Optional[dict]:
        """
        Simple linear regression on price history.

        Returns:
            Dict with slope, intercept, r_squared, predicted prices
        """
        history = self.db.get_price_history(product_id, days)
        prices = [h["price"] for h in history if h["price"] > 0]

        if len(prices) < 3:
            return None

        n = len(prices)
        x = list(range(n))  # time steps

        # Calculate regression
        x_mean = sum(x) / n
        y_mean = sum(prices) / n

        ss_xy = sum((x[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
        ss_xx = sum((x[i] - x_mean) ** 2 for i in range(n))
        ss_yy = sum((prices[i] - y_mean) ** 2 for i in range(n))

        if ss_xx == 0:
            return None

        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean

        # R-squared
        r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy != 0 else 0

        # Predict next 7 days
        predictions = []
        for i in range(n, n + 7):
            predicted = intercept + slope * i
            predictions.append({
                "day_offset": i - n + 1,
                "predicted_price": round(max(0, predicted), 2),
            })

        # Daily change rate
        daily_change = slope
        daily_change_pct = (slope / y_mean) * 100 if y_mean > 0 else 0

        return {
            "product_id": product_id,
            "data_points": n,
            "slope": round(slope, 4),
            "intercept": round(intercept, 2),
            "r_squared": round(r_squared, 4),
            "daily_change": round(daily_change, 2),
            "daily_change_pct": round(daily_change_pct, 3),
            "trend": "rising" if slope > 0.01 else "falling" if slope < -0.01 else "stable",
            "confidence": "high" if r_squared > 0.7 else "medium" if r_squared > 0.4 else "low",
            "predictions": predictions,
        }

    def forecast(self, product_id: int, days_ahead: int = 7,
                 history_days: int = 60) -> dict:
        """
        Generate price forecast combining multiple methods.

        Returns:
            Comprehensive forecast with confidence intervals
        """
        product = self.db.get_product(product_id)
        if not product:
            return {"error": "Product not found"}

        history = self.db.get_price_history(product_id, history_days)
        prices = [h["price"] for h in history if h["price"] > 0]

        if len(prices) < 5:
            return {
                "product_id": product_id,
                "error": "Insufficient data",
                "data_points": len(prices),
                "min_required": 5,
            }

        # Method 1: Linear regression
        regression = self.linear_regression(product_id, history_days)

        # Method 2: Simple average of recent prices
        recent = prices[-min(7, len(prices)):]
        recent_avg = sum(recent) / len(recent)

        # Method 3: Weighted recent average (more weight to newer)
        weights = list(range(1, len(recent) + 1))
        weighted_avg = sum(p * w for p, w in zip(recent, weights)) / sum(weights)

        # Combine forecasts
        forecasts = [recent_avg, weighted_avg]
        if regression and regression.get("predictions"):
            reg_pred = regression["predictions"][min(days_ahead - 1, 6)]["predicted_price"]
            forecasts.append(reg_pred)

        avg_forecast = sum(forecasts) / len(forecasts)

        # Calculate confidence interval
        std_dev = (sum((p - sum(prices) / len(prices)) ** 2 for p in prices) / len(prices)) ** 0.5
        ci_low = max(0, avg_forecast - 1.96 * std_dev)
        ci_high = avg_forecast + 1.96 * std_dev

        # Direction and strength
        current = product.get("current_price", 0)
        if current:
            change_pct = ((avg_forecast - current) / current) * 100
        else:
            change_pct = 0

        return {
            "product_id": product_id,
            "product_title": product.get("title", ""),
            "current_price": current,
            "forecast_price": round(avg_forecast, 2),
            "confidence_interval": {
                "low": round(ci_low, 2),
                "high": round(ci_high, 2),
            },
            "expected_change_pct": round(change_pct, 2),
            "direction": "up" if change_pct > 1 else "down" if change_pct < -1 else "stable",
            "methods": {
                "recent_avg": round(recent_avg, 2),
                "weighted_avg": round(weighted_avg, 2),
                "regression": regression,
            },
            "data_points": len(prices),
            "days_ahead": days_ahead,
            "generated_at": datetime.now().isoformat(),
        }

    def detect_anomalies(self, product_id: int, days: int = 30,
                         z_threshold: float = 2.0) -> List[dict]:
        """
        Detect price anomalies using Z-score method.

        Args:
            product_id: Product ID
            days: History period
            z_threshold: Z-score threshold for anomaly detection

        Returns:
            List of anomalous price points
        """
        history = self.db.get_price_history(product_id, days)
        prices = [h["price"] for h in history if h["price"] > 0]

        if len(prices) < 5:
            return []

        mean = sum(prices) / len(prices)
        std_dev = (sum((p - mean) ** 2 for p in prices) / len(prices)) ** 0.5

        if std_dev == 0:
            return []

        anomalies = []
        for i, h in enumerate(history):
            if h["price"] <= 0:
                continue
            z_score = (h["price"] - mean) / std_dev
            if abs(z_score) >= z_threshold:
                anomalies.append({
                    "date": h["recorded_at"],
                    "price": h["price"],
                    "z_score": round(z_score, 2),
                    "type": "spike" if z_score > 0 else "dip",
                    "deviation_pct": round(((h["price"] - mean) / mean) * 100, 1),
                })

        return anomalies

    def seasonal_pattern(self, product_id: int, days: int = 90) -> dict:
        """
        Detect weekly price patterns.

        Returns:
            Dict with day-of-week price averages
        """
        history = self.db.get_price_history(product_id, days)
        if len(history) < 14:
            return {"error": "Need at least 14 data points"}

        # Group by day of week
        day_prices: Dict[int, List[float]] = {i: [] for i in range(7)}
        for h in history:
            if h["price"] <= 0:
                continue
            try:
                dt = datetime.fromisoformat(h["recorded_at"].replace("Z", "+00:00"))
                day_prices[dt.weekday()].append(h["price"])
            except (ValueError, AttributeError):
                continue

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]

        averages = {}
        for day_num, prices in day_prices.items():
            if prices:
                avg = sum(prices) / len(prices)
                averages[day_names[day_num]] = {
                    "avg_price": round(avg, 2),
                    "data_points": len(prices),
                    "min": round(min(prices), 2),
                    "max": round(max(prices), 2),
                }

        # Find best/worst days
        if averages:
            best_day = min(averages.items(), key=lambda x: x[1]["avg_price"])
            worst_day = max(averages.items(), key=lambda x: x[1]["avg_price"])
        else:
            best_day = worst_day = (None, {})

        return {
            "product_id": product_id,
            "daily_averages": averages,
            "best_buy_day": best_day[0],
            "worst_buy_day": worst_day[0],
            "period_days": days,
        }

    def buy_signal(self, product_id: int) -> dict:
        """
        Generate a buy/wait signal based on multiple indicators.

        Returns:
            Dict with signal (BUY/WAIT/HOLD), confidence, and reasons
        """
        product = self.db.get_product(product_id)
        if not product or not product.get("current_price"):
            return {"signal": "UNKNOWN", "confidence": 0, "reasons": ["No data"]}

        current = product["current_price"]
        signals = []
        score = 50  # Start neutral

        # 1. Compare to historical low/high
        if product.get("lowest_price") and product.get("highest_price"):
            price_range = product["highest_price"] - product["lowest_price"]
            if price_range > 0:
                position = (current - product["lowest_price"]) / price_range
                if position < 0.2:
                    score += 25
                    signals.append("Near all-time low")
                elif position < 0.4:
                    score += 10
                    signals.append("Below average range")
                elif position > 0.8:
                    score -= 20
                    signals.append("Near all-time high")

        # 2. Target price
        if product.get("target_price"):
            if current <= product["target_price"]:
                score += 20
                signals.append(f"At/below target ({product['target_price']})")
            else:
                diff_pct = ((current - product["target_price"]) / product["target_price"]) * 100
                if diff_pct < 10:
                    signals.append(f"Close to target ({diff_pct:.0f}% above)")

        # 3. Trend analysis
        regression = self.linear_regression(product_id, 14)
        if regression:
            if regression["trend"] == "falling" and regression["confidence"] != "low":
                score += 15
                signals.append("Downward trend detected")
            elif regression["trend"] == "rising":
                score -= 10
                signals.append("Upward trend - may rise further")

        # 4. Anomaly check
        anomalies = self.detect_anomalies(product_id, 30)
        dips = [a for a in anomalies if a["type"] == "dip"]
        if dips:
            recent_dip = dips[-1]
            if abs(current - recent_dip["price"]) / current < 0.05:
                score += 10
                signals.append("Price near recent anomaly dip")

        # Generate signal
        if score >= 70:
            signal = "BUY"
        elif score >= 55:
            signal = "HOLD"
        else:
            signal = "WAIT"

        confidence = min(100, max(0, abs(score - 50) * 2))

        return {
            "product_id": product_id,
            "signal": signal,
            "score": score,
            "confidence": confidence,
            "current_price": current,
            "reasons": signals,
            "generated_at": datetime.now().isoformat(),
        }
