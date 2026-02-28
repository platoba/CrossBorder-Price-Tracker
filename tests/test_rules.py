"""Tests for alert rules engine."""
import json
import pytest
import tempfile
from pathlib import Path
from app.services.rules import AlertRule, AlertRulesEngine, RuleType, RuleAction


@pytest.fixture
def rules_file(tmp_path):
    return str(tmp_path / "rules.json")


@pytest.fixture
def engine(rules_file):
    return AlertRulesEngine(rules_file)


def _make_product(id=1, platform="amazon", title="Test Product",
                  current_price=100, lowest_price=80, highest_price=120,
                  target_price=None, tags=""):
    return {
        "id": id, "platform": platform, "title": title,
        "current_price": current_price, "lowest_price": lowest_price,
        "highest_price": highest_price, "target_price": target_price,
        "tags": tags, "url": f"https://amazon.com/dp/TEST{id}",
    }


class TestAlertRule:
    def test_create_rule(self):
        rule = AlertRule(id="test1", name="Test", rule_type=RuleType.PRICE_DROP)
        assert rule.id == "test1"
        assert rule.enabled is True
        assert rule.created_at != ""

    def test_rule_to_dict(self):
        rule = AlertRule(id="r1", name="Drop", rule_type=RuleType.PRICE_DROP, threshold=5.0)
        d = rule.to_dict()
        assert d["id"] == "r1"
        assert d["threshold"] == 5.0

    def test_rule_from_dict(self):
        data = {"id": "r2", "name": "Rise", "rule_type": "price_rise", "threshold": 10.0}
        rule = AlertRule.from_dict(data)
        assert rule.id == "r2"
        assert rule.threshold == 10.0


class TestAlertRulesEngine:
    def test_add_rule(self, engine):
        rule = AlertRule(id="r1", name="Test", rule_type=RuleType.PRICE_DROP, threshold=5.0)
        engine.add_rule(rule)
        assert engine.get_rule("r1") is not None

    def test_remove_rule(self, engine):
        rule = AlertRule(id="r1", name="Test", rule_type=RuleType.PRICE_DROP)
        engine.add_rule(rule)
        assert engine.remove_rule("r1") is True
        assert engine.get_rule("r1") is None

    def test_remove_nonexistent(self, engine):
        assert engine.remove_rule("fake") is False

    def test_list_rules(self, engine):
        engine.add_rule(AlertRule(id="r1", name="A", rule_type=RuleType.PRICE_DROP))
        engine.add_rule(AlertRule(id="r2", name="B", rule_type=RuleType.PRICE_RISE))
        rules = engine.list_rules()
        assert len(rules) == 2

    def test_list_enabled_only(self, engine):
        engine.add_rule(AlertRule(id="r1", name="A", rule_type=RuleType.PRICE_DROP, enabled=True))
        engine.add_rule(AlertRule(id="r2", name="B", rule_type=RuleType.PRICE_RISE, enabled=False))
        rules = engine.list_rules(enabled_only=True)
        assert len(rules) == 1

    def test_toggle_rule(self, engine):
        engine.add_rule(AlertRule(id="r1", name="A", rule_type=RuleType.PRICE_DROP))
        engine.toggle_rule("r1", False)
        assert engine.get_rule("r1").enabled is False
        engine.toggle_rule("r1", True)
        assert engine.get_rule("r1").enabled is True

    def test_persistence(self, rules_file):
        e1 = AlertRulesEngine(rules_file)
        e1.add_rule(AlertRule(id="r1", name="Saved", rule_type=RuleType.PRICE_DROP))
        e2 = AlertRulesEngine(rules_file)
        assert e2.get_rule("r1") is not None
        assert e2.get_rule("r1").name == "Saved"


class TestRuleEvaluation:
    def test_price_drop(self, engine):
        rule = AlertRule(id="drop5", name="Drop 5%", rule_type=RuleType.PRICE_DROP, threshold=5.0)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, old_price=100, new_price=90)
        assert len(alerts) == 1
        assert "dropped" in alerts[0]["message"].lower()

    def test_price_drop_below_threshold(self, engine):
        rule = AlertRule(id="drop10", name="Drop 10%", rule_type=RuleType.PRICE_DROP, threshold=10.0)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, old_price=100, new_price=95)
        assert len(alerts) == 0

    def test_price_rise(self, engine):
        rule = AlertRule(id="rise5", name="Rise 5%", rule_type=RuleType.PRICE_RISE, threshold=5.0)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, old_price=100, new_price=110)
        assert len(alerts) == 1

    def test_target_price(self, engine):
        rule = AlertRule(id="target", name="Target", rule_type=RuleType.TARGET_PRICE,
                         target_price=90)
        engine.add_rule(rule)
        product = _make_product(target_price=90)
        alerts = engine.evaluate(product, old_price=100, new_price=85)
        assert len(alerts) == 1

    def test_back_in_stock(self, engine):
        rule = AlertRule(id="stock", name="Back", rule_type=RuleType.BACK_IN_STOCK)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, in_stock=True, was_in_stock=False)
        assert len(alerts) == 1

    def test_out_of_stock(self, engine):
        rule = AlertRule(id="oos", name="OOS", rule_type=RuleType.OUT_OF_STOCK)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, in_stock=False, was_in_stock=True)
        assert len(alerts) == 1

    def test_new_lowest(self, engine):
        rule = AlertRule(id="low", name="New Low", rule_type=RuleType.NEW_LOWEST)
        engine.add_rule(rule)
        product = _make_product(lowest_price=80)
        alerts = engine.evaluate(product, old_price=85, new_price=75)
        assert len(alerts) == 1

    def test_percentage_change(self, engine):
        rule = AlertRule(id="pct", name="Any 5%", rule_type=RuleType.PERCENTAGE_CHANGE,
                         threshold=5.0)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, old_price=100, new_price=93)
        assert len(alerts) == 1

    def test_absolute_change(self, engine):
        rule = AlertRule(id="abs", name="Abs $10", rule_type=RuleType.ABSOLUTE_CHANGE,
                         threshold=10.0)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, old_price=100, new_price=85)
        assert len(alerts) == 1

    def test_disabled_rule_skipped(self, engine):
        rule = AlertRule(id="disabled", name="Off", rule_type=RuleType.PRICE_DROP,
                         threshold=1.0, enabled=False)
        engine.add_rule(rule)
        product = _make_product()
        alerts = engine.evaluate(product, old_price=100, new_price=50)
        assert len(alerts) == 0


class TestRuleFilters:
    def test_platform_filter(self, engine):
        rule = AlertRule(id="amazon_only", name="Amazon", rule_type=RuleType.PRICE_DROP,
                         threshold=5.0, platforms=["amazon"])
        engine.add_rule(rule)
        # Amazon product → should trigger
        p1 = _make_product(platform="amazon")
        a1 = engine.evaluate(p1, old_price=100, new_price=90)
        assert len(a1) == 1
        # AliExpress product → should not trigger
        p2 = _make_product(id=2, platform="aliexpress")
        a2 = engine.evaluate(p2, old_price=100, new_price=90)
        assert len(a2) == 0

    def test_product_id_filter(self, engine):
        rule = AlertRule(id="specific", name="Product 42", rule_type=RuleType.PRICE_DROP,
                         threshold=5.0, product_ids=[42])
        engine.add_rule(rule)
        p1 = _make_product(id=42)
        assert len(engine.evaluate(p1, old_price=100, new_price=90)) == 1
        p2 = _make_product(id=99)
        assert len(engine.evaluate(p2, old_price=100, new_price=90)) == 0

    def test_tag_filter(self, engine):
        rule = AlertRule(id="tagged", name="Electronics", rule_type=RuleType.PRICE_DROP,
                         threshold=5.0, tags=["electronics"])
        engine.add_rule(rule)
        p1 = _make_product(tags="electronics,gadgets")
        assert len(engine.evaluate(p1, old_price=100, new_price=90)) == 1
        p2 = _make_product(tags="clothing,fashion")
        assert len(engine.evaluate(p2, old_price=100, new_price=90)) == 0


class TestDefaultRules:
    def test_create_defaults(self, engine):
        defaults = engine.create_default_rules()
        assert len(defaults) == 6
        rules = engine.list_rules()
        assert len(rules) == 6

    def test_defaults_include_common_types(self, engine):
        engine.create_default_rules()
        types = {r.rule_type for r in engine.list_rules()}
        assert RuleType.PRICE_DROP in types
        assert RuleType.BACK_IN_STOCK in types
        assert RuleType.NEW_LOWEST in types


class TestRuleStats:
    def test_stats(self, engine):
        engine.add_rule(AlertRule(id="r1", name="A", rule_type=RuleType.PRICE_DROP))
        engine.add_rule(AlertRule(id="r2", name="B", rule_type=RuleType.PRICE_RISE))
        stats = engine.stats()
        assert stats["total_rules"] == 2
        assert stats["enabled_rules"] == 2

    def test_trigger_count_increments(self, engine):
        rule = AlertRule(id="r1", name="Drop", rule_type=RuleType.PRICE_DROP, threshold=5.0,
                         cooldown_minutes=0)
        engine.add_rule(rule)
        product = _make_product()
        engine.evaluate(product, old_price=100, new_price=90)
        assert engine.get_rule("r1").trigger_count == 1
