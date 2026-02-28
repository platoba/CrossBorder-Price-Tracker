"""Multi-format export engine (CSV, JSON, HTML, Markdown)."""
import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.models.database import Database
from app.services.reporter import PriceReporter

logger = logging.getLogger(__name__)


class ExportEngine:
    """Export price data in multiple formats."""

    def __init__(self, db: Database):
        self.db = db
        self.reporter = PriceReporter(db)

    def export_products(self, format: str = "csv", product_ids: List[int] = None,
                        output_path: str = None) -> str:
        """
        Export product data.

        Args:
            format: csv, json, html, markdown
            product_ids: Specific products (None = all active)
            output_path: File path (None = return string)
        """
        if product_ids:
            products = [self.db.get_product(pid) for pid in product_ids]
            products = [p for p in products if p]
        else:
            products = self.db.get_active_products()

        exporters = {
            "csv": self._to_csv,
            "json": self._to_json,
            "html": self._to_html,
            "markdown": self._to_markdown,
            "md": self._to_markdown,
        }

        exporter = exporters.get(format.lower())
        if not exporter:
            raise ValueError(f"Unsupported format: {format}. Use: {', '.join(exporters.keys())}")

        content = exporter(products)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content, encoding="utf-8")
            logger.info(f"Exported {len(products)} products to {output_path}")

        return content

    def export_history(self, product_id: int, days: int = 30,
                       format: str = "csv", output_path: str = None) -> str:
        """Export price history for a product."""
        history = self.db.get_price_history(product_id, days)
        product = self.db.get_product(product_id)

        if format == "csv":
            content = self._history_to_csv(history, product)
        elif format == "json":
            content = json.dumps({
                "product": product,
                "history": history,
                "exported_at": datetime.now().isoformat(),
            }, indent=2, default=str)
        else:
            content = self._history_to_csv(history, product)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content, encoding="utf-8")

        return content

    def export_alerts(self, format: str = "csv", output_path: str = None) -> str:
        """Export pending alerts."""
        alerts = self.db.get_pending_alerts()

        if format == "json":
            content = json.dumps(alerts, indent=2, default=str)
        else:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["id", "product_id", "title", "platform", "alert_type",
                             "old_price", "new_price", "change_pct", "url", "created_at"])
            for a in alerts:
                writer.writerow([
                    a["id"], a["product_id"], a.get("title", ""),
                    a.get("platform", ""), a["alert_type"],
                    a["old_price"], a["new_price"], a["change_pct"],
                    a.get("url", ""), a["created_at"],
                ])
            content = buf.getvalue()

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content, encoding="utf-8")

        return content

    def export_full_report(self, days: int = 30, format: str = "html",
                           output_path: str = None) -> str:
        """Export comprehensive report with summaries."""
        products = self.db.get_active_products()
        stats = self.db.get_stats()
        summaries = []
        for p in products:
            s = self.reporter.product_summary(p["id"], days)
            if s:
                summaries.append(s)

        if format == "json":
            content = json.dumps({
                "stats": stats,
                "summaries": summaries,
                "generated_at": datetime.now().isoformat(),
            }, indent=2, default=str)
        elif format == "html":
            content = self._report_to_html(stats, summaries, days)
        elif format in ("markdown", "md"):
            content = self._report_to_markdown(stats, summaries, days)
        else:
            content = self.reporter.full_report(days, "text")

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content, encoding="utf-8")

        return content

    # --- Format Implementations ---

    def _to_csv(self, products: list) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "id", "url", "platform", "product_id", "title", "currency",
            "current_price", "lowest_price", "highest_price", "target_price",
            "is_active", "check_count", "error_count", "tags",
            "created_at", "updated_at", "last_checked",
        ])
        for p in products:
            writer.writerow([
                p["id"], p["url"], p["platform"], p.get("product_id", ""),
                p.get("title", ""), p.get("currency", "USD"),
                p.get("current_price", ""), p.get("lowest_price", ""),
                p.get("highest_price", ""), p.get("target_price", ""),
                p.get("is_active", 1), p.get("check_count", 0),
                p.get("error_count", 0), p.get("tags", ""),
                p.get("created_at", ""), p.get("updated_at", ""),
                p.get("last_checked", ""),
            ])
        return buf.getvalue()

    def _to_json(self, products: list) -> str:
        return json.dumps({
            "products": products,
            "count": len(products),
            "exported_at": datetime.now().isoformat(),
        }, indent=2, default=str)

    def _to_html(self, products: list) -> str:
        rows = ""
        for p in products:
            price = p.get("current_price", 0)
            low = p.get("lowest_price", 0)
            high = p.get("highest_price", 0)
            currency = p.get("currency", "USD")
            title = p.get("title", "")[:60] or p["url"][:60]
            rows += f"""
            <tr>
                <td>{p['id']}</td>
                <td><a href="{p['url']}" target="_blank">{title}</a></td>
                <td>{p['platform'].upper()}</td>
                <td>{currency} {price:.2f}</td>
                <td>{currency} {low:.2f}</td>
                <td>{currency} {high:.2f}</td>
                <td>{p.get('check_count', 0)}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>跨境电商价格追踪 - 导出</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #333; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ border: 1px solid #ddd; padding: 10px 12px; text-align: left; }}
th {{ background: #4a90d9; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
tr:hover {{ background: #e9f0fb; }}
a {{ color: #4a90d9; text-decoration: none; }}
.meta {{ color: #888; font-size: 0.9em; margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>📦 跨境电商价格追踪</h1>
<div class="meta">导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 商品数: {len(products)}</div>
<table>
<thead><tr><th>ID</th><th>商品</th><th>平台</th><th>当前价</th><th>最低价</th><th>最高价</th><th>检查次数</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body></html>"""

    def _to_markdown(self, products: list) -> str:
        lines = [
            f"# 📦 跨境电商价格追踪",
            f"",
            f"> 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 商品数: {len(products)}",
            f"",
            "| ID | 商品 | 平台 | 当前价 | 最低价 | 最高价 |",
            "|----|------|------|--------|--------|--------|",
        ]
        for p in products:
            title = p.get("title", "")[:40] or p["url"][:40]
            cur = p.get("currency", "USD")
            price = f"{cur} {p.get('current_price', 0):.2f}"
            low = f"{cur} {p.get('lowest_price', 0):.2f}"
            high = f"{cur} {p.get('highest_price', 0):.2f}"
            lines.append(f"| {p['id']} | [{title}]({p['url']}) | {p['platform'].upper()} | {price} | {low} | {high} |")
        return "\n".join(lines)

    def _history_to_csv(self, history: list, product: dict) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["recorded_at", "price", "currency", "in_stock", "seller"])
        for h in history:
            writer.writerow([
                h["recorded_at"], h["price"], h.get("currency", "USD"),
                "Yes" if h["in_stock"] else "No", h.get("seller", ""),
            ])
        return buf.getvalue()

    def _report_to_html(self, stats: dict, summaries: list, days: int) -> str:
        rows = ""
        for s in summaries:
            p = s.get("product", {})
            rec = s.get("recommendation", "hold")
            rec_color = {
                "strong_buy": "#27ae60", "buy": "#3498db",
                "hold": "#95a5a6", "wait": "#e74c3c",
            }.get(rec, "#95a5a6")
            trend = s.get("trend", "stable")
            trend_icon = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(trend, "❓")
            rows += f"""
            <tr>
                <td><a href="{p.get('url', '')}">{p.get('title', '')[:50]}</a></td>
                <td>{p.get('platform', '').upper()}</td>
                <td>{p.get('currency', 'USD')} {s.get('current_price', 0):.2f}</td>
                <td>{s.get('lowest_price', 'N/A')}</td>
                <td>{s.get('highest_price', 'N/A')}</td>
                <td>{s.get('avg_price', 'N/A')}</td>
                <td>{trend_icon} {trend}</td>
                <td style="color:{rec_color};font-weight:bold">{rec.upper()}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>价格追踪分析报告</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }}
.stats {{ display: flex; gap: 20px; margin: 20px 0; }}
.stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; text-align: center; }}
.stat-card h3 {{ color: #888; font-size: 0.85em; margin: 0; }}
.stat-card .value {{ font-size: 2em; font-weight: bold; color: #333; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
th, td {{ border: 1px solid #eee; padding: 10px; text-align: left; }}
th {{ background: #4a90d9; color: white; }}
tr:hover {{ background: #f0f7ff; }}
a {{ color: #4a90d9; }}
</style>
</head>
<body>
<h1>📊 价格追踪分析报告</h1>
<p>分析周期: {days}天 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<div class="stats">
<div class="stat-card"><h3>追踪商品</h3><div class="value">{stats.get('active_products', 0)}</div></div>
<div class="stat-card"><h3>价格记录</h3><div class="value">{stats.get('price_records', 0)}</div></div>
<div class="stat-card"><h3>待处理提醒</h3><div class="value">{stats.get('pending_alerts', 0)}</div></div>
</div>
<table>
<thead><tr><th>商品</th><th>平台</th><th>当前价</th><th>最低</th><th>最高</th><th>均价</th><th>趋势</th><th>建议</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</body></html>"""

    def _report_to_markdown(self, stats: dict, summaries: list, days: int) -> str:
        lines = [
            f"# 📊 价格追踪分析报告",
            f"",
            f"**分析周期**: {days}天 | **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"## 概览",
            f"- 追踪商品: **{stats.get('active_products', 0)}**",
            f"- 价格记录: **{stats.get('price_records', 0)}**",
            f"- 待处理提醒: **{stats.get('pending_alerts', 0)}**",
            f"",
            "## 商品分析",
            "",
            "| 商品 | 平台 | 当前价 | 最低 | 最高 | 均价 | 趋势 | 建议 |",
            "|------|------|--------|------|------|------|------|------|",
        ]
        for s in summaries:
            p = s.get("product", {})
            trend = s.get("trend", "stable")
            trend_icon = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(trend, "❓")
            rec = s.get("recommendation", "hold")
            rec_icon = {"strong_buy": "🟢", "buy": "🔵", "hold": "⚪", "wait": "🔴"}.get(rec, "❓")
            lines.append(
                f"| {p.get('title', '')[:30]} | {p.get('platform', '').upper()} | "
                f"{s.get('current_price', 'N/A')} | {s.get('lowest_price', 'N/A')} | "
                f"{s.get('highest_price', 'N/A')} | {s.get('avg_price', 'N/A')} | "
                f"{trend_icon} {trend} | {rec_icon} {rec} |"
            )
        return "\n".join(lines)
