"""CLI interface for CrossBorder Price Tracker."""
import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from app.config import Config
from app.models.database import Database
from app.models.product import detect_platform, extract_product_id
from app.scrapers import get_scraper
from app.services.monitor import PriceMonitor
from app.services.reporter import PriceReporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_add(args, db: Database, config: Config):
    """Add a product to track."""
    url = args.url
    platform = detect_platform(url)
    if platform == "unknown":
        print(f"❌ 无法识别平台: {url}")
        return

    product_id = extract_product_id(url, platform)
    pid = db.add_product(
        url=url, platform=platform, product_id=product_id,
        target_price=args.target, tags=args.tags or "",
    )

    # Try to scrape initial data
    try:
        scraper = get_scraper(platform)
        scraped = scraper.scrape(url)
        if scraped and scraped.price > 0:
            db.record_price(pid, scraped.price, scraped.currency, scraped.in_stock, scraped.seller)
            if scraped.title:
                with db.conn() as c:
                    c.execute("UPDATE products SET title=? WHERE id=?", (scraped.title, pid))
            print(f"✅ 已添加: {scraped.title or url}")
            print(f"   平台: {platform.upper()} | 价格: {scraped.currency} {scraped.price:.2f}")
            return
    except Exception as e:
        logger.debug(f"Initial scrape failed: {e}")

    print(f"✅ 已添加: {url} (平台: {platform})")
    print("   ⚠️ 初始价格获取失败，将在下次检查时重试")


def cmd_import(args, db: Database, config: Config):
    """Import products from CSV/JSON."""
    path = Path(args.file)
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        return

    count = 0
    if path.suffix == ".csv":
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url", "").strip()
                if not url:
                    continue
                platform = detect_platform(url)
                if platform != "unknown":
                    db.add_product(url=url, platform=platform,
                                   product_id=extract_product_id(url, platform),
                                   tags=row.get("tags", ""))
                    count += 1
    elif path.suffix == ".json":
        with open(path) as f:
            items = json.load(f)
            if isinstance(items, list):
                for item in items:
                    url = item.get("url", "") if isinstance(item, dict) else str(item)
                    platform = detect_platform(url)
                    if platform != "unknown":
                        db.add_product(url=url, platform=platform,
                                       product_id=extract_product_id(url, platform))
                        count += 1

    print(f"✅ 已导入 {count} 个商品")


def cmd_check(args, db: Database, config: Config):
    """Run a single price check."""
    monitor = PriceMonitor(config, db)
    results = monitor.check_all()
    print(f"✅ 已检查 {len(results)} 个商品")
    for r in results:
        product = db.get_product(r["product_id"])
        name = product["title"][:40] if product.get("title") else product["url"][:40]
        change = f" ({r['change_pct']:+.1f}%)" if r.get("change_pct") is not None else ""
        print(f"   {name}: {r['price']:.2f}{change}")


def cmd_monitor(args, db: Database, config: Config):
    """Start continuous monitoring."""
    monitor = PriceMonitor(config, db)
    interval = args.interval or config.check_interval
    print(f"🔄 启动持续监控 (间隔: {interval}秒)")
    try:
        monitor.run(interval)
    except KeyboardInterrupt:
        monitor.stop()
        print("\n⏹️ 监控已停止")


def cmd_list(args, db: Database, config: Config):
    """List tracked products."""
    products = db.get_active_products()
    if not products:
        print("📭 暂无追踪商品")
        return

    print(f"📦 共追踪 {len(products)} 个商品:\n")
    for p in products:
        price_str = f"{p.get('currency', 'USD')} {p['current_price']:.2f}" if p.get("current_price") else "未获取"
        title = p.get("title", "")[:50] or p["url"][:50]
        print(f"  [{p['id']}] {title}")
        print(f"      {p['platform'].upper()} | {price_str}")
        if p.get("lowest_price") and p.get("highest_price"):
            print(f"      历史: {p['lowest_price']:.2f} ~ {p['highest_price']:.2f}")
        print()


def cmd_history(args, db: Database, config: Config):
    """Show price history."""
    # Find by product_id string
    with db.conn() as c:
        c.execute("SELECT * FROM products WHERE product_id = ? OR id = ?",
                  (args.product_id, args.product_id))
        product = c.fetchone()

    if not product:
        print(f"❌ 未找到商品: {args.product_id}")
        return

    product = dict(product)
    history = db.get_price_history(product["id"], args.days)
    print(f"📈 {product.get('title', product['url'][:50])}")
    print(f"   最近 {args.days} 天价格历史 ({len(history)} 条记录):\n")
    for h in history:
        stock = "✅" if h["in_stock"] else "❌"
        print(f"   {h['recorded_at'][:16]} | {h['currency']} {h['price']:.2f} | {stock}")


def cmd_remove(args, db: Database, config: Config):
    """Remove a product from tracking."""
    db.remove_product(args.product_id)
    print(f"✅ 已停止追踪商品 #{args.product_id}")


def cmd_report(args, db: Database, config: Config):
    """Generate report."""
    reporter = PriceReporter(db)
    report = reporter.full_report(days=args.days, format=args.format)
    if args.output:
        Path(args.output).write_text(report)
        print(f"✅ 报告已保存: {args.output}")
    else:
        print(report)


def cmd_stats(args, db: Database, config: Config):
    """Show statistics."""
    stats = db.get_stats()
    print("📊 统计信息:")
    print(f"   总商品数: {stats['total_products']}")
    print(f"   活跃追踪: {stats['active_products']}")
    print(f"   价格记录: {stats['price_records']}")
    print(f"   待发通知: {stats['pending_alerts']}")


def main():
    parser = argparse.ArgumentParser(description="跨境电商多平台价格追踪器")
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # add
    p = sub.add_parser("add", help="添加商品追踪")
    p.add_argument("url", help="商品URL")
    p.add_argument("--target", type=float, help="目标价格")
    p.add_argument("--tags", help="标签(逗号分隔)")

    # import
    p = sub.add_parser("import", help="批量导入商品")
    p.add_argument("file", help="CSV/JSON文件路径")

    # check
    sub.add_parser("check", help="运行一次价格检查")

    # monitor
    p = sub.add_parser("monitor", help="启动持续监控")
    p.add_argument("--interval", type=int, help="检查间隔(秒)")

    # list
    sub.add_parser("list", help="列出追踪商品")

    # history
    p = sub.add_parser("history", help="查看价格历史")
    p.add_argument("product_id", help="商品ID")
    p.add_argument("--days", type=int, default=30, help="天数")

    # remove
    p = sub.add_parser("remove", help="移除商品追踪")
    p.add_argument("product_id", type=int, help="商品数据库ID")

    # report
    p = sub.add_parser("report", help="生成报告")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--days", type=int, default=30, help="分析天数")
    p.add_argument("--output", "-o", help="输出文件路径")

    # stats
    sub.add_parser("stats", help="显示统计信息")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    config = Config.from_env()
    db = Database(config.db_path)

    commands = {
        "add": cmd_add, "import": cmd_import, "check": cmd_check,
        "monitor": cmd_monitor, "list": cmd_list, "history": cmd_history,
        "remove": cmd_remove, "report": cmd_report, "stats": cmd_stats,
    }
    commands[args.command](args, db, config)


if __name__ == "__main__":
    main()
