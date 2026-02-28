"""SQLite database for price tracking."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: str = "data/prices.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    platform TEXT NOT NULL,
                    product_id TEXT,
                    title TEXT,
                    currency TEXT DEFAULT 'USD',
                    current_price REAL,
                    lowest_price REAL,
                    highest_price REAL,
                    target_price REAL,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    last_checked TEXT,
                    check_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    tags TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    in_stock INTEGER DEFAULT 1,
                    seller TEXT,
                    recorded_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    old_price REAL,
                    new_price REAL,
                    change_pct REAL,
                    notified INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
                CREATE INDEX IF NOT EXISTS idx_history_product ON price_history(product_id);
                CREATE INDEX IF NOT EXISTS idx_history_time ON price_history(recorded_at);
                CREATE INDEX IF NOT EXISTS idx_alerts_product ON alerts(product_id);
            """)

    @contextmanager
    def conn(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection.cursor()
            connection.commit()
        finally:
            connection.close()

    def add_product(self, url: str, platform: str, product_id: str = "",
                    title: str = "", target_price: float = None, tags: str = "") -> int:
        with self.conn() as c:
            c.execute(
                """INSERT OR IGNORE INTO products (url, platform, product_id, title, target_price, tags)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url, platform, product_id, title, target_price, tags)
            )
            if c.rowcount == 0:
                c.execute("SELECT id FROM products WHERE url = ?", (url,))
                return c.fetchone()["id"]
            return c.lastrowid

    def record_price(self, product_id: int, price: float, currency: str = "USD",
                     in_stock: bool = True, seller: str = "") -> Optional[dict]:
        with self.conn() as c:
            # Get current state
            c.execute("SELECT current_price, lowest_price, highest_price FROM products WHERE id = ?",
                      (product_id,))
            row = c.fetchone()
            if not row:
                return None

            old_price = row["current_price"]
            lowest = row["lowest_price"]
            highest = row["highest_price"]

            # Record history
            c.execute(
                "INSERT INTO price_history (product_id, price, currency, in_stock, seller) VALUES (?, ?, ?, ?, ?)",
                (product_id, price, currency, 1 if in_stock else 0, seller)
            )

            # Update product
            new_lowest = min(price, lowest) if lowest is not None else price
            new_highest = max(price, highest) if highest is not None else price
            now = datetime.utcnow().isoformat()
            c.execute(
                """UPDATE products SET current_price=?, lowest_price=?, highest_price=?,
                   currency=?, updated_at=?, last_checked=?, check_count=check_count+1
                   WHERE id=?""",
                (price, new_lowest, new_highest, currency, now, now, product_id)
            )

            # Calculate change
            result = {"product_id": product_id, "price": price, "old_price": old_price}
            if old_price and old_price > 0:
                change_pct = ((price - old_price) / old_price) * 100
                result["change_pct"] = round(change_pct, 2)
            return result

    def get_active_products(self) -> list:
        with self.conn() as c:
            c.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY id")
            return [dict(r) for r in c.fetchall()]

    def get_product(self, product_id: int) -> Optional[dict]:
        with self.conn() as c:
            c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            row = c.fetchone()
            return dict(row) if row else None

    def get_product_by_url(self, url: str) -> Optional[dict]:
        with self.conn() as c:
            c.execute("SELECT * FROM products WHERE url = ?", (url,))
            row = c.fetchone()
            return dict(row) if row else None

    def get_price_history(self, product_id: int, days: int = 30) -> list:
        with self.conn() as c:
            c.execute(
                """SELECT * FROM price_history WHERE product_id = ?
                   AND recorded_at >= datetime('now', ?)
                   ORDER BY recorded_at""",
                (product_id, f"-{days} days")
            )
            return [dict(r) for r in c.fetchall()]

    def add_alert(self, product_id: int, alert_type: str,
                  old_price: float, new_price: float, change_pct: float) -> int:
        with self.conn() as c:
            c.execute(
                """INSERT INTO alerts (product_id, alert_type, old_price, new_price, change_pct)
                   VALUES (?, ?, ?, ?, ?)""",
                (product_id, alert_type, old_price, new_price, change_pct)
            )
            return c.lastrowid

    def get_pending_alerts(self) -> list:
        with self.conn() as c:
            c.execute(
                """SELECT a.*, p.title, p.url, p.platform FROM alerts a
                   JOIN products p ON a.product_id = p.id
                   WHERE a.notified = 0 ORDER BY a.created_at"""
            )
            return [dict(r) for r in c.fetchall()]

    def mark_alert_notified(self, alert_id: int):
        with self.conn() as c:
            c.execute("UPDATE alerts SET notified = 1 WHERE id = ?", (alert_id,))

    def record_error(self, product_id: int):
        with self.conn() as c:
            c.execute("UPDATE products SET error_count = error_count + 1 WHERE id = ?",
                      (product_id,))

    def remove_product(self, product_id: int):
        with self.conn() as c:
            c.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))

    def get_stats(self) -> dict:
        with self.conn() as c:
            c.execute("SELECT COUNT(*) as total, SUM(is_active) as active FROM products")
            products = dict(c.fetchone())
            c.execute("SELECT COUNT(*) as total FROM price_history")
            history = dict(c.fetchone())
            c.execute("SELECT COUNT(*) as total FROM alerts WHERE notified = 0")
            pending = dict(c.fetchone())
            return {
                "total_products": products["total"],
                "active_products": products["active"],
                "price_records": history["total"],
                "pending_alerts": pending["total"],
            }
