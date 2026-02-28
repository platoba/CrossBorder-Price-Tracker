# Changelog

## [2.0.0] - 2026-02-28

### Added
- **Currency Converter** (`app/utils/currency.py`): 18-currency converter with caching, bulk conversion, price formatting
- **Price Comparator** (`app/services/comparator.py`): Cross-platform price comparison, deal scoring (0-100), similar product discovery (Jaccard), price spread/volatility analysis
- **Price Predictor** (`app/services/predictor.py`): SMA/EMA moving averages, linear regression with 7-day forecast, Z-score anomaly detection, weekly seasonal patterns, BUY/HOLD/WAIT signal generation
- **Alert Rules Engine** (`app/services/rules.py`): 8 rule types (price_drop/rise, target_price, back/out_of_stock, new_lowest, percentage/absolute_change), platform/tag/product_id filters, cooldown + daily limits, persistence
- **Watchlist Manager** (`app/services/watchlist.py`): Named watchlists, bulk URL import, merge, cross-list search, summary statistics
- **Export Engine** (`app/services/exporter.py`): CSV/JSON/HTML/Markdown export for products, history, alerts, and full reports
- 137 new tests (6 test files) — total 211 tests, all passing
- Updated README with full module documentation

## [1.0.0] - 2026-02-28

### Added
- Initial release
- 4-platform scrapers: Amazon (US/UK/DE/JP), AliExpress, Shopee, 1688
- SQLite price tracking with history
- Multi-channel notifications (Telegram/Email/Webhook)
- Proxy pool with health scoring
- CLI with 8 commands (add/import/check/monitor/list/history/report/stats)
- Price analysis reports with buy recommendations
- Docker Compose deployment
- GitHub Actions CI
- 74 tests
