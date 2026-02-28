"""Price monitoring scheduler."""
import time
import logging
from typing import Callable, Optional
from app.config import Config
from app.models.database import Database
from app.scrapers import get_scraper
from app.services.notifier import Notifier, format_price_alert

logger = logging.getLogger(__name__)


class PriceMonitor:
    def __init__(self, config: Config = None, db: Database = None):
        self.config = config or Config.from_env()
        self.db = db or Database(self.config.db_path)
        self.notifier = Notifier(self.config)
        self._running = False

    def check_all(self) -> list:
        """Check prices for all active products."""
        products = self.db.get_active_products()
        results = []
        for product in products:
            result = self.check_product(product)
            if result:
                results.append(result)
        self._process_alerts()
        return results

    def check_product(self, product: dict) -> Optional[dict]:
        """Check price for a single product."""
        try:
            scraper = get_scraper(product["platform"])
            scraped = scraper.scrape(product["url"])
            if not scraped or scraped.price <= 0:
                self.db.record_error(product["id"])
                logger.warning(f"Failed to scrape {product['url']}")
                return None

            # Update title if we got a better one
            if scraped.title and not product.get("title"):
                with self.db.conn() as c:
                    c.execute("UPDATE products SET title=? WHERE id=?",
                              (scraped.title, product["id"]))

            result = self.db.record_price(
                product["id"], scraped.price,
                scraped.currency, scraped.in_stock, scraped.seller,
            )

            # Check for significant price change
            if result and result.get("change_pct") is not None:
                pct = result["change_pct"]
                threshold = self.config.price_drop_threshold
                if abs(pct) >= threshold:
                    alert_type = "price_drop" if pct < 0 else "price_increase"
                    self.db.add_alert(
                        product["id"], alert_type,
                        result["old_price"], scraped.price, pct
                    )
                    logger.info(
                        f"Alert: {product['url']} price changed {pct:+.1f}% "
                        f"({result['old_price']} → {scraped.price})"
                    )

            return result

        except Exception as e:
            self.db.record_error(product["id"])
            logger.error(f"Error checking {product.get('url')}: {e}")
            return None

    def _process_alerts(self):
        """Send notifications for pending alerts."""
        alerts = self.db.get_pending_alerts()
        for alert in alerts:
            title, msg = format_price_alert(
                alert, alert["old_price"], alert["new_price"], alert["change_pct"]
            )
            if self.notifier.notify(title, msg):
                self.db.mark_alert_notified(alert["id"])

    def run(self, interval: int = None):
        """Run continuous monitoring loop."""
        interval = interval or self.config.check_interval
        self._running = True
        logger.info(f"Starting price monitor (interval: {interval}s)")
        while self._running:
            try:
                results = self.check_all()
                logger.info(f"Checked {len(results)} products")
            except Exception as e:
                logger.error(f"Monitor cycle error: {e}")
            time.sleep(interval)

    def stop(self):
        self._running = False
