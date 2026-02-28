"""Configurable alert rules engine."""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RuleType(str, Enum):
    PRICE_DROP = "price_drop"
    PRICE_RISE = "price_rise"
    TARGET_PRICE = "target_price"
    BACK_IN_STOCK = "back_in_stock"
    OUT_OF_STOCK = "out_of_stock"
    NEW_LOWEST = "new_lowest"
    PERCENTAGE_CHANGE = "percentage_change"
    ABSOLUTE_CHANGE = "absolute_change"


class RuleAction(str, Enum):
    NOTIFY = "notify"
    LOG = "log"
    WEBHOOK = "webhook"
    TAG = "tag"


@dataclass
class AlertRule:
    """A single alert rule definition."""
    id: str
    name: str
    rule_type: str  # RuleType value
    enabled: bool = True
    # Conditions
    threshold: float = 0.0  # percent or absolute value
    target_price: float = 0.0
    platforms: List[str] = field(default_factory=list)  # empty = all platforms
    tags: List[str] = field(default_factory=list)  # empty = all products
    product_ids: List[int] = field(default_factory=list)  # empty = all products
    # Actions
    actions: List[str] = field(default_factory=lambda: ["notify"])
    # Cooldown
    cooldown_minutes: int = 60  # min time between triggers for same product
    max_triggers_per_day: int = 50
    # Tracking
    trigger_count: int = 0
    last_triggered: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AlertRule":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AlertRulesEngine:
    """Manage and evaluate alert rules."""

    def __init__(self, rules_file: str = "data/alert_rules.json"):
        self.rules_file = Path(rules_file)
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        self._rules: Dict[str, AlertRule] = {}
        self._trigger_log: Dict[str, List[str]] = {}  # rule_id → [timestamps]
        self._load_rules()

    def _load_rules(self):
        """Load rules from JSON file."""
        if self.rules_file.exists():
            try:
                data = json.loads(self.rules_file.read_text())
                for rd in data.get("rules", []):
                    rule = AlertRule.from_dict(rd)
                    self._rules[rule.id] = rule
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to load rules: {e}")

    def _save_rules(self):
        """Save rules to JSON file."""
        data = {
            "rules": [r.to_dict() for r in self._rules.values()],
            "updated_at": datetime.now().isoformat(),
        }
        self.rules_file.write_text(json.dumps(data, indent=2, default=str))

    def add_rule(self, rule: AlertRule) -> AlertRule:
        """Add or update a rule."""
        self._rules[rule.id] = rule
        self._save_rules()
        return rule

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            self._save_rules()
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """List all rules."""
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        """Enable or disable a rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = enabled
            self._save_rules()
            return True
        return False

    def evaluate(self, product: dict, old_price: float = None,
                 new_price: float = None, in_stock: bool = True,
                 was_in_stock: bool = True) -> List[dict]:
        """
        Evaluate all rules against a product price change.

        Args:
            product: Product dict from database
            old_price: Previous price
            new_price: Current price
            in_stock: Current stock status
            was_in_stock: Previous stock status

        Returns:
            List of triggered alert dicts
        """
        triggered = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            # Check if rule applies to this product
            if not self._rule_applies(rule, product):
                continue

            # Check cooldown
            if not self._check_cooldown(rule, product["id"]):
                continue

            # Evaluate rule type
            alert = self._evaluate_rule(rule, product, old_price, new_price,
                                        in_stock, was_in_stock)
            if alert:
                rule.trigger_count += 1
                rule.last_triggered = datetime.now().isoformat()
                self._record_trigger(rule.id, product["id"])
                triggered.append(alert)

        if triggered:
            self._save_rules()

        return triggered

    def _rule_applies(self, rule: AlertRule, product: dict) -> bool:
        """Check if a rule applies to a given product."""
        # Check specific product IDs
        if rule.product_ids and product["id"] not in rule.product_ids:
            return False

        # Check platform filter
        if rule.platforms and product.get("platform") not in rule.platforms:
            return False

        # Check tag filter
        if rule.tags:
            product_tags = set((product.get("tags") or "").split(","))
            rule_tags = set(rule.tags)
            if not product_tags & rule_tags:
                return False

        return True

    def _check_cooldown(self, rule: AlertRule, product_id: int) -> bool:
        """Check if cooldown period has passed."""
        key = f"{rule.id}:{product_id}"
        triggers = self._trigger_log.get(key, [])
        if not triggers:
            return True

        last = datetime.fromisoformat(triggers[-1])
        elapsed = (datetime.now() - last).total_seconds() / 60
        if elapsed < rule.cooldown_minutes:
            return False

        # Check daily limit
        today = datetime.now().date().isoformat()
        today_count = sum(1 for t in triggers if t.startswith(today))
        return today_count < rule.max_triggers_per_day

    def _record_trigger(self, rule_id: str, product_id: int):
        """Record a rule trigger event."""
        key = f"{rule_id}:{product_id}"
        if key not in self._trigger_log:
            self._trigger_log[key] = []
        self._trigger_log[key].append(datetime.now().isoformat())
        # Keep only last 100 triggers per key
        self._trigger_log[key] = self._trigger_log[key][-100:]

    def _evaluate_rule(self, rule: AlertRule, product: dict,
                       old_price: float, new_price: float,
                       in_stock: bool, was_in_stock: bool) -> Optional[dict]:
        """Evaluate a single rule."""
        rt = rule.rule_type

        if rt == RuleType.PRICE_DROP:
            if old_price and new_price and new_price < old_price:
                pct = ((old_price - new_price) / old_price) * 100
                if pct >= rule.threshold:
                    return self._make_alert(rule, product, old_price, new_price,
                                            f"Price dropped {pct:.1f}%")

        elif rt == RuleType.PRICE_RISE:
            if old_price and new_price and new_price > old_price:
                pct = ((new_price - old_price) / old_price) * 100
                if pct >= rule.threshold:
                    return self._make_alert(rule, product, old_price, new_price,
                                            f"Price rose {pct:.1f}%")

        elif rt == RuleType.TARGET_PRICE:
            target = rule.target_price or product.get("target_price")
            if target and new_price and new_price <= target:
                return self._make_alert(rule, product, old_price, new_price,
                                        f"Price hit target {target}")

        elif rt == RuleType.BACK_IN_STOCK:
            if in_stock and not was_in_stock:
                return self._make_alert(rule, product, old_price, new_price,
                                        "Back in stock!")

        elif rt == RuleType.OUT_OF_STOCK:
            if not in_stock and was_in_stock:
                return self._make_alert(rule, product, old_price, new_price,
                                        "Out of stock!")

        elif rt == RuleType.NEW_LOWEST:
            if new_price and product.get("lowest_price"):
                if new_price < product["lowest_price"]:
                    return self._make_alert(rule, product, old_price, new_price,
                                            f"New all-time low! (was {product['lowest_price']})")

        elif rt == RuleType.PERCENTAGE_CHANGE:
            if old_price and new_price and old_price > 0:
                pct = abs((new_price - old_price) / old_price) * 100
                if pct >= rule.threshold:
                    direction = "up" if new_price > old_price else "down"
                    return self._make_alert(rule, product, old_price, new_price,
                                            f"Price changed {pct:.1f}% {direction}")

        elif rt == RuleType.ABSOLUTE_CHANGE:
            if old_price and new_price:
                diff = abs(new_price - old_price)
                if diff >= rule.threshold:
                    direction = "up" if new_price > old_price else "down"
                    return self._make_alert(rule, product, old_price, new_price,
                                            f"Price changed {diff:.2f} {direction}")

        return None

    def _make_alert(self, rule: AlertRule, product: dict,
                    old_price: float, new_price: float,
                    message: str) -> dict:
        """Create an alert dict."""
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "rule_type": rule.rule_type,
            "product_id": product["id"],
            "product_title": product.get("title", ""),
            "platform": product.get("platform", ""),
            "url": product.get("url", ""),
            "old_price": old_price,
            "new_price": new_price,
            "message": message,
            "actions": rule.actions,
            "triggered_at": datetime.now().isoformat(),
        }

    def create_default_rules(self) -> List[AlertRule]:
        """Create a set of sensible default rules."""
        defaults = [
            AlertRule(
                id="default_drop_5",
                name="价格下降5%+",
                rule_type=RuleType.PRICE_DROP,
                threshold=5.0,
                actions=["notify", "log"],
            ),
            AlertRule(
                id="default_drop_15",
                name="价格暴跌15%+",
                rule_type=RuleType.PRICE_DROP,
                threshold=15.0,
                actions=["notify", "webhook", "log"],
                cooldown_minutes=30,
            ),
            AlertRule(
                id="default_rise_10",
                name="价格上涨10%+",
                rule_type=RuleType.PRICE_RISE,
                threshold=10.0,
                actions=["notify", "log"],
            ),
            AlertRule(
                id="default_target",
                name="达到目标价",
                rule_type=RuleType.TARGET_PRICE,
                actions=["notify", "webhook", "log"],
                cooldown_minutes=120,
            ),
            AlertRule(
                id="default_back_stock",
                name="补货提醒",
                rule_type=RuleType.BACK_IN_STOCK,
                actions=["notify"],
                cooldown_minutes=240,
            ),
            AlertRule(
                id="default_new_low",
                name="历史新低",
                rule_type=RuleType.NEW_LOWEST,
                actions=["notify", "log"],
            ),
        ]
        for rule in defaults:
            self.add_rule(rule)
        return defaults

    def stats(self) -> dict:
        """Get rule engine statistics."""
        rules = list(self._rules.values())
        return {
            "total_rules": len(rules),
            "enabled_rules": sum(1 for r in rules if r.enabled),
            "total_triggers": sum(r.trigger_count for r in rules),
            "rule_types": list(set(r.rule_type for r in rules)),
            "most_triggered": max(rules, key=lambda r: r.trigger_count).name if rules else None,
        }
