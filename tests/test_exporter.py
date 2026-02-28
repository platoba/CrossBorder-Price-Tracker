"""Tests for export engine."""
import json
import pytest
from pathlib import Path
from app.models.database import Database
from app.services.exporter import ExportEngine


@pytest.fixture
def db(tmp_path):
    d = Database(str(tmp_path / "test.db"))
    # Seed data
    pid1 = d.add_product("https://amazon.com/dp/A1", "amazon", title="Wireless Headphones")
    pid2 = d.add_product("https://aliexpress.com/item/1.html", "aliexpress", title="USB Cable")
    d.record_price(pid1, 99.99, "USD")
    d.record_price(pid1, 89.99, "USD")
    d.record_price(pid2, 5.99, "USD")
    # Add an alert
    d.add_alert(pid1, "price_drop", 99.99, 89.99, -10.0)
    return d


@pytest.fixture
def exporter(db):
    return ExportEngine(db)


class TestExportProducts:
    def test_csv_export(self, exporter):
        csv = exporter.export_products("csv")
        assert "url" in csv
        assert "amazon" in csv
        assert "Wireless Headphones" in csv

    def test_json_export(self, exporter):
        result = exporter.export_products("json")
        data = json.loads(result)
        assert "products" in data
        assert data["count"] == 2

    def test_html_export(self, exporter):
        html = exporter.export_products("html")
        assert "<html" in html
        assert "Wireless Headphones" in html
        assert "<table>" in html

    def test_markdown_export(self, exporter):
        md = exporter.export_products("markdown")
        assert "# 📦" in md
        assert "|" in md
        assert "AMAZON" in md.upper()

    def test_md_alias(self, exporter):
        md = exporter.export_products("md")
        assert "|" in md

    def test_unsupported_format(self, exporter):
        with pytest.raises(ValueError, match="Unsupported format"):
            exporter.export_products("xml")

    def test_specific_products(self, exporter):
        csv = exporter.export_products("csv", product_ids=[1])
        lines = csv.strip().split("\n")
        assert len(lines) == 2  # header + 1 product

    def test_output_to_file(self, exporter, tmp_path):
        output = str(tmp_path / "export.csv")
        exporter.export_products("csv", output_path=output)
        assert Path(output).exists()
        content = Path(output).read_text()
        assert "amazon" in content


class TestExportHistory:
    def test_csv_history(self, exporter):
        csv = exporter.export_history(1, days=30, format="csv")
        assert "recorded_at" in csv
        assert "price" in csv
        lines = csv.strip().split("\n")
        assert len(lines) >= 2  # header + at least 1 record

    def test_json_history(self, exporter):
        result = exporter.export_history(1, days=30, format="json")
        data = json.loads(result)
        assert "product" in data
        assert "history" in data

    def test_history_to_file(self, exporter, tmp_path):
        output = str(tmp_path / "history.csv")
        exporter.export_history(1, output_path=output)
        assert Path(output).exists()


class TestExportAlerts:
    def test_csv_alerts(self, exporter):
        csv = exporter.export_alerts("csv")
        assert "alert_type" in csv
        assert "price_drop" in csv

    def test_json_alerts(self, exporter):
        result = exporter.export_alerts("json")
        data = json.loads(result)
        assert len(data) >= 1

    def test_alerts_to_file(self, exporter, tmp_path):
        output = str(tmp_path / "alerts.json")
        exporter.export_alerts("json", output_path=output)
        assert Path(output).exists()


class TestExportFullReport:
    def test_html_report(self, exporter):
        html = exporter.export_full_report(format="html")
        assert "<html" in html
        assert "价格追踪分析报告" in html
        assert "<table>" in html

    def test_markdown_report(self, exporter):
        md = exporter.export_full_report(format="markdown")
        assert "# 📊" in md
        assert "概览" in md

    def test_json_report(self, exporter):
        result = exporter.export_full_report(format="json")
        data = json.loads(result)
        assert "stats" in data
        assert "summaries" in data

    def test_text_report(self, exporter):
        text = exporter.export_full_report(format="text")
        assert "跨境电商" in text

    def test_report_to_file(self, exporter, tmp_path):
        output = str(tmp_path / "report.html")
        exporter.export_full_report(format="html", output_path=output)
        assert Path(output).exists()
        content = Path(output).read_text()
        assert len(content) > 100
