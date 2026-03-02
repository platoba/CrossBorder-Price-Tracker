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

## [3.0.0] - 2026-03-02

### Added
- **Anti-crawl detection engine** (`app/utils/anti_crawl.py`)
  - `AntiCrawlDetector`: Pattern-based detection for 6 block types (timeout/blocked/captcha/rate-limited/auth-expired/unknown)
  - `EngineEscalator`: Automatic engine level escalation after 3 consecutive failures (C-line constitution compliance)
  - 6-level engine hierarchy: L1(static) → L2(JS render) → L3(batch) → L4(fingerprint) → L5(API reverse) → L6(ultimate)
  - Confidence scoring and evidence tracking for all detections
- **Miyaip proxy pool integration** (`app/utils/miyaip_loader.py`)
  - Load static proxies from C-line arsenal (`arsenal/static-proxies-miyaip.json`)
  - Country-based filtering (US/UK/etc.)
  - Automatic inactive proxy exclusion
  - Proxy statistics and health reporting
- **Comprehensive test coverage**
  - 24 new tests for anti-crawl detection and miyaip loader
  - Total test count: 235 tests (up from 211)
  - All tests passing with 100% success rate

### Technical Details
- Anti-crawl patterns: 20+ regex patterns for common blocks
- Escalation protocol: 3-failure threshold per engine level
- Proxy pool: Weighted random selection by success rate
- Constitution compliance: Implements C-line daily-v2 engine decision tree

### Stats
- Files added: 4 (2 modules + 2 test files)
- Tests added: 24
- Lines added: ~700
