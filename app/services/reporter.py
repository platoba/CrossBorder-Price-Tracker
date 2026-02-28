"""Price analysis and report generation."""
import json
from datetime import datetime
from typing import List, Optional
from app.models.database import Database


class PriceReporter:
    def __init__(self, db: Database):
        self.db = db

    def product_summary(self, product_id: int, days: int = 30) -> dict:
        """Generate summary for a single product."""
        product = self.db.get_product(product_id)
        if not product:
            return {}
        history = self.db.get_price_history(product_id, days)
        prices = [h["price"] for h in history if h["price"] > 0]

        summary = {
            "product": product,
            "period_days": days,
            "data_points": len(prices),
            "current_price": product["current_price"],
            "lowest_price": min(prices) if prices else None,
            "highest_price": max(prices) if prices else None,
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "price_range": round(max(prices) - min(prices), 2) if prices else None,
        }

        if len(prices) >= 2:
            first, last = prices[0], prices[-1]
            summary["trend_pct"] = round(((last - first) / first) * 100, 2)
            summary["trend"] = "rising" if last > first else "falling" if last < first else "stable"

        # Buy recommendation
        if prices and product["current_price"]:
            current = product["current_price"]
            avg = summary["avg_price"]
            if current <= summary["lowest_price"] * 1.05:
                summary["recommendation"] = "strong_buy"
            elif current < avg * 0.95:
                summary["recommendation"] = "buy"
            elif current > avg * 1.1:
                summary["recommendation"] = "wait"
            else:
                summary["recommendation"] = "hold"

        return summary

    def full_report(self, days: int = 30, format: str = "text") -> str:
        """Generate full portfolio report."""
        products = self.db.get_active_products()
        stats = self.db.get_stats()

        if format == "json":
            summaries = [self.product_summary(p["id"], days) for p in products]
            return json.dumps({"stats": stats, "products": summaries}, indent=2, default=str)

        # Text report
        lines = [
            "=" * 60,
            "📊 跨境电商价格追踪报告",
            f"📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"📦 追踪商品: {stats['active_products']} 个",
            f"📈 价格记录: {stats['price_records']} 条",
            "=" * 60, ""
        ]

        for product in products:
            s = self.product_summary(product["id"], days)
            if not s:
                continue
            rec_emoji = {"strong_buy": "🟢", "buy": "🔵", "hold": "⚪", "wait": "🔴"}.get(
                s.get("recommendation", ""), "❓"
            )
            lines.extend([
                f"📦 {product.get('title', product['url'][:50])}",
                f"   平台: {product['platform'].upper()} | ID: {product.get('product_id', 'N/A')}",
                f"   当前: {product.get('currency', 'USD')} {s.get('current_price', 'N/A')}",
                f"   范围: {s.get('lowest_price', 'N/A')} ~ {s.get('highest_price', 'N/A')} (均价 {s.get('avg_price', 'N/A')})",
                f"   趋势: {s.get('trend', 'N/A')} ({s.get('trend_pct', 0):+.1f}%)" if s.get("trend") else "",
                f"   建议: {rec_emoji} {s.get('recommendation', 'N/A').upper()}",
                "",
            ])

        return "\n".join(lines)
