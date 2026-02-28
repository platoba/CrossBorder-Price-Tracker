"""Cross-platform price comparison engine."""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.models.database import Database
from app.utils.currency import CurrencyConverter

logger = logging.getLogger(__name__)


class PriceComparator:
    """Compare prices across platforms and find the best deals."""

    def __init__(self, db: Database, converter: CurrencyConverter = None):
        self.db = db
        self.converter = converter or CurrencyConverter()

    def find_similar_products(self, product_id: int, threshold: float = 0.8) -> List[dict]:
        """
        Find similar products across platforms using title matching.

        Args:
            product_id: Source product ID
            threshold: Similarity threshold (0-1)

        Returns:
            List of similar products with similarity scores
        """
        source = self.db.get_product(product_id)
        if not source or not source.get("title"):
            return []

        source_title = source["title"].lower()
        source_words = set(source_title.split())
        all_products = self.db.get_active_products()
        similar = []

        for p in all_products:
            if p["id"] == product_id:
                continue
            if not p.get("title"):
                continue

            target_title = p["title"].lower()
            target_words = set(target_title.split())

            # Jaccard similarity
            if not source_words or not target_words:
                continue
            intersection = source_words & target_words
            union = source_words | target_words
            similarity = len(intersection) / len(union)

            if similarity >= threshold:
                similar.append({
                    **p,
                    "similarity": round(similarity, 3),
                })

        return sorted(similar, key=lambda x: x["similarity"], reverse=True)

    def cross_platform_comparison(self, product_id: int,
                                  target_currency: str = "USD") -> dict:
        """
        Compare a product's price with similar items on other platforms.

        Returns:
            Comparison report with best deal info
        """
        source = self.db.get_product(product_id)
        if not source:
            return {"error": "Product not found"}

        similar = self.find_similar_products(product_id, threshold=0.5)

        # Build comparison list
        items = []
        source_usd = self._to_target(
            source.get("current_price", 0),
            source.get("currency", "USD"),
            target_currency,
        )
        items.append({
            "id": source["id"],
            "platform": source["platform"],
            "title": source.get("title", ""),
            "price": source.get("current_price", 0),
            "currency": source.get("currency", "USD"),
            "converted_price": source_usd,
            "target_currency": target_currency,
            "url": source["url"],
            "is_source": True,
        })

        for s in similar:
            conv = self._to_target(
                s.get("current_price", 0),
                s.get("currency", "USD"),
                target_currency,
            )
            items.append({
                "id": s["id"],
                "platform": s["platform"],
                "title": s.get("title", ""),
                "price": s.get("current_price", 0),
                "currency": s.get("currency", "USD"),
                "converted_price": conv,
                "target_currency": target_currency,
                "url": s["url"],
                "similarity": s["similarity"],
                "is_source": False,
            })

        # Sort by converted price
        items.sort(key=lambda x: x["converted_price"] if x["converted_price"] else float("inf"))

        best_deal = items[0] if items and items[0]["converted_price"] else None
        savings = None
        if best_deal and source_usd and best_deal["converted_price"] < source_usd:
            savings = {
                "amount": round(source_usd - best_deal["converted_price"], 2),
                "percent": round(
                    ((source_usd - best_deal["converted_price"]) / source_usd) * 100, 1
                ),
                "platform": best_deal["platform"],
            }

        return {
            "source": source,
            "items": items,
            "best_deal": best_deal,
            "savings": savings,
            "platforms_compared": len(set(i["platform"] for i in items)),
            "generated_at": datetime.now().isoformat(),
        }

    def _to_target(self, price: float, from_currency: str,
                   to_currency: str) -> Optional[float]:
        """Convert price to target currency, return None on failure."""
        if not price or price <= 0:
            return None
        try:
            return round(self.converter.convert(price, from_currency, to_currency), 2)
        except (ValueError, ZeroDivisionError):
            return None

    def platform_price_map(self, target_currency: str = "USD") -> Dict[str, list]:
        """
        Group all tracked products by platform with converted prices.

        Returns:
            Dict mapping platform → list of products with converted prices
        """
        products = self.db.get_active_products()
        platform_map: Dict[str, list] = {}

        for p in products:
            platform = p["platform"]
            if platform not in platform_map:
                platform_map[platform] = []

            conv = self._to_target(
                p.get("current_price", 0),
                p.get("currency", "USD"),
                target_currency,
            )
            platform_map[platform].append({
                **p,
                "converted_price": conv,
                "target_currency": target_currency,
            })

        # Sort each platform's products by converted price
        for platform in platform_map:
            platform_map[platform].sort(
                key=lambda x: x["converted_price"] if x["converted_price"] else float("inf")
            )

        return platform_map

    def cheapest_by_platform(self, target_currency: str = "USD") -> list:
        """
        Find the cheapest product on each platform.

        Returns:
            List of cheapest products per platform
        """
        platform_map = self.platform_price_map(target_currency)
        cheapest = []
        for platform, products in platform_map.items():
            valid = [p for p in products if p.get("converted_price")]
            if valid:
                cheapest.append({
                    "platform": platform,
                    "product": valid[0],
                    "product_count": len(products),
                })
        return sorted(cheapest, key=lambda x: x["product"]["converted_price"])

    def price_spread_analysis(self, product_id: int, days: int = 30) -> dict:
        """
        Analyze price spread (volatility) for a product.

        Returns:
            Dict with spread metrics: range, std_dev, cv, stability_score
        """
        history = self.db.get_price_history(product_id, days)
        prices = [h["price"] for h in history if h["price"] > 0]

        if len(prices) < 2:
            return {"error": "Not enough data", "data_points": len(prices)}

        avg = sum(prices) / len(prices)
        min_p = min(prices)
        max_p = max(prices)
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        cv = (std_dev / avg) * 100 if avg > 0 else 0  # coefficient of variation

        # Stability score: 100 = very stable, 0 = very volatile
        stability = max(0, min(100, 100 - cv * 10))

        return {
            "product_id": product_id,
            "data_points": len(prices),
            "period_days": days,
            "min_price": round(min_p, 2),
            "max_price": round(max_p, 2),
            "avg_price": round(avg, 2),
            "price_range": round(max_p - min_p, 2),
            "std_dev": round(std_dev, 2),
            "cv_percent": round(cv, 2),
            "stability_score": round(stability, 1),
            "volatility": "low" if cv < 3 else "medium" if cv < 10 else "high",
        }

    def deal_score(self, product_id: int) -> dict:
        """
        Calculate a deal score (0-100) for a product based on current price
        relative to history.

        Higher score = better deal.
        """
        product = self.db.get_product(product_id)
        if not product or not product.get("current_price"):
            return {"score": 0, "reason": "no_data"}

        current = product["current_price"]
        lowest = product.get("lowest_price")
        highest = product.get("highest_price")

        if not lowest or not highest or highest == lowest:
            return {"score": 50, "reason": "insufficient_history"}

        # Score: 100 = at all-time low, 0 = at all-time high
        position = (highest - current) / (highest - lowest)
        score = round(position * 100, 1)

        # Bonus: below target price
        target = product.get("target_price")
        if target and current <= target:
            score = min(100, score + 15)

        label = (
            "excellent" if score >= 80
            else "good" if score >= 60
            else "fair" if score >= 40
            else "poor" if score >= 20
            else "bad"
        )

        return {
            "product_id": product_id,
            "score": score,
            "label": label,
            "current_price": current,
            "lowest_price": lowest,
            "highest_price": highest,
            "target_price": target,
            "at_target": target is not None and current <= target,
        }

    def top_deals(self, limit: int = 10) -> list:
        """Get top deals across all tracked products."""
        products = self.db.get_active_products()
        deals = []
        for p in products:
            d = self.deal_score(p["id"])
            if d["score"] > 0:
                d["title"] = p.get("title", "")
                d["platform"] = p["platform"]
                d["url"] = p["url"]
                deals.append(d)
        return sorted(deals, key=lambda x: x["score"], reverse=True)[:limit]
