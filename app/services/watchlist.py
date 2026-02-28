"""Named watchlist management with groups and bulk operations."""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.models.database import Database
from app.models.product import detect_platform, extract_product_id

logger = logging.getLogger(__name__)


@dataclass
class Watchlist:
    """A named collection of tracked products."""
    id: str
    name: str
    description: str = ""
    product_ids: List[int] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    notify_enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Watchlist":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class WatchlistManager:
    """Manage multiple watchlists with bulk operations."""

    def __init__(self, db: Database, data_file: str = "data/watchlists.json"):
        self.db = db
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self._watchlists: Dict[str, Watchlist] = {}
        self._load()

    def _load(self):
        """Load watchlists from JSON."""
        if self.data_file.exists():
            try:
                data = json.loads(self.data_file.read_text())
                for wd in data.get("watchlists", []):
                    wl = Watchlist.from_dict(wd)
                    self._watchlists[wl.id] = wl
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to load watchlists: {e}")

    def _save(self):
        """Save watchlists to JSON."""
        data = {
            "watchlists": [w.to_dict() for w in self._watchlists.values()],
            "updated_at": datetime.now().isoformat(),
        }
        self.data_file.write_text(json.dumps(data, indent=2, default=str))

    def create(self, id: str, name: str, description: str = "",
               tags: List[str] = None) -> Watchlist:
        """Create a new watchlist."""
        wl = Watchlist(
            id=id,
            name=name,
            description=description,
            tags=tags or [],
        )
        self._watchlists[id] = wl
        self._save()
        return wl

    def delete(self, watchlist_id: str) -> bool:
        """Delete a watchlist (does not delete products)."""
        if watchlist_id in self._watchlists:
            del self._watchlists[watchlist_id]
            self._save()
            return True
        return False

    def get(self, watchlist_id: str) -> Optional[Watchlist]:
        """Get a watchlist by ID."""
        return self._watchlists.get(watchlist_id)

    def list_all(self) -> List[Watchlist]:
        """List all watchlists."""
        return list(self._watchlists.values())

    def add_product(self, watchlist_id: str, product_id: int) -> bool:
        """Add a product to a watchlist."""
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return False
        if product_id not in wl.product_ids:
            wl.product_ids.append(product_id)
            wl.updated_at = datetime.now().isoformat()
            self._save()
        return True

    def remove_product(self, watchlist_id: str, product_id: int) -> bool:
        """Remove a product from a watchlist."""
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return False
        if product_id in wl.product_ids:
            wl.product_ids.remove(product_id)
            wl.updated_at = datetime.now().isoformat()
            self._save()
        return True

    def get_products(self, watchlist_id: str) -> List[dict]:
        """Get all products in a watchlist."""
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return []
        products = []
        for pid in wl.product_ids:
            product = self.db.get_product(pid)
            if product:
                products.append(product)
        return products

    def bulk_add_urls(self, watchlist_id: str, urls: List[str]) -> dict:
        """
        Bulk add products by URL to a watchlist.

        Returns:
            Dict with added, skipped, failed counts
        """
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return {"error": "Watchlist not found"}

        added = 0
        skipped = 0
        failed = 0

        for url in urls:
            url = url.strip()
            if not url:
                continue

            platform = detect_platform(url)
            if platform == "unknown":
                failed += 1
                continue

            # Check if already tracked
            existing = self.db.get_product_by_url(url)
            if existing:
                pid = existing["id"]
                if pid in wl.product_ids:
                    skipped += 1
                else:
                    wl.product_ids.append(pid)
                    added += 1
                continue

            # Add new product
            product_id_str = extract_product_id(url, platform)
            pid = self.db.add_product(
                url=url, platform=platform, product_id=product_id_str
            )
            wl.product_ids.append(pid)
            added += 1

        wl.updated_at = datetime.now().isoformat()
        self._save()

        return {"added": added, "skipped": skipped, "failed": failed}

    def bulk_remove(self, watchlist_id: str, product_ids: List[int]) -> int:
        """Remove multiple products from a watchlist."""
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return 0
        removed = 0
        for pid in product_ids:
            if pid in wl.product_ids:
                wl.product_ids.remove(pid)
                removed += 1
        if removed:
            wl.updated_at = datetime.now().isoformat()
            self._save()
        return removed

    def merge_watchlists(self, source_id: str, target_id: str,
                         delete_source: bool = False) -> bool:
        """Merge one watchlist into another."""
        source = self._watchlists.get(source_id)
        target = self._watchlists.get(target_id)
        if not source or not target:
            return False

        for pid in source.product_ids:
            if pid not in target.product_ids:
                target.product_ids.append(pid)

        target.updated_at = datetime.now().isoformat()

        if delete_source:
            del self._watchlists[source_id]

        self._save()
        return True

    def find_product_watchlists(self, product_id: int) -> List[Watchlist]:
        """Find all watchlists containing a specific product."""
        result = []
        for wl in self._watchlists.values():
            if product_id in wl.product_ids:
                result.append(wl)
        return result

    def summary(self, watchlist_id: str) -> dict:
        """Generate a summary for a watchlist."""
        wl = self._watchlists.get(watchlist_id)
        if not wl:
            return {"error": "Watchlist not found"}

        products = self.get_products(watchlist_id)
        prices = [p["current_price"] for p in products if p.get("current_price")]
        platforms = set(p["platform"] for p in products)

        return {
            "id": wl.id,
            "name": wl.name,
            "product_count": len(wl.product_ids),
            "active_count": len(products),
            "platforms": sorted(platforms),
            "total_value": round(sum(prices), 2) if prices else 0,
            "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
            "price_range": (round(min(prices), 2), round(max(prices), 2)) if prices else (0, 0),
            "created_at": wl.created_at,
            "updated_at": wl.updated_at,
        }

    def stats(self) -> dict:
        """Overall watchlist statistics."""
        watchlists = list(self._watchlists.values())
        all_pids = set()
        for wl in watchlists:
            all_pids.update(wl.product_ids)

        return {
            "total_watchlists": len(watchlists),
            "total_unique_products": len(all_pids),
            "avg_products_per_list": (
                round(sum(len(wl.product_ids) for wl in watchlists) / len(watchlists), 1)
                if watchlists else 0
            ),
            "largest_list": max(
                watchlists, key=lambda w: len(w.product_ids)
            ).name if watchlists else None,
        }
