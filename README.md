# CrossBorder-Price-Tracker 🔍💰

跨境电商多平台价格追踪器 — 实时监控 Amazon / AliExpress / Shopee / 1688 商品价格变动，智能提醒降价。

## 功能

### 核心功能
- 📊 **多平台抓取**: Amazon (US/UK/DE/JP) + AliExpress + Shopee + 1688
- 📈 **价格历史**: SQLite 持久化，趋势追踪
- 🔔 **降价提醒**: Telegram / Email / Webhook 通知
- 🕷️ **反检测**: 代理轮转 + UA随机化 + 请求限速
- 📦 **批量监控**: CSV/JSON 导入商品列表
- 🐳 **Docker 部署**: 一键启动，开箱即用

### v2.0 新功能
- 💱 **多币种转换**: 18种货币实时转换，跨平台价格统一对比
- 🔀 **跨平台比价**: 自动发现相似商品，找出最优价格
- 📐 **价格预测**: 线性回归 + 移动平均线 + 异常检测 + 买入信号
- 📋 **智能规则引擎**: 8种告警类型，可配置触发条件/冷却/频率限制
- 📁 **命名监控列表**: 分组管理商品，批量操作，列表合并
- 📤 **多格式导出**: CSV / JSON / HTML / Markdown 导出报告

## 快速开始

```bash
# 安装
pip install -r requirements.txt

# 添加商品监控
python -m app.cli add "https://www.amazon.com/dp/B09V3KXJPB"

# 批量导入
python -m app.cli import products.csv

# 运行一次价格检查
python -m app.cli check

# 启动定时监控 (每小时)
python -m app.cli monitor --interval 3600

# 查看价格历史
python -m app.cli history B09V3KXJPB

# 导出报告 (支持 text/json/html/markdown)
python -m app.cli report --format html --days 30

# 查看统计
python -m app.cli stats
```

## Docker 部署

```bash
cp .env.example .env
# 编辑 .env 配置代理和通知
docker compose up -d
```

## 配置

```env
# 代理配置
PROXY_TYPE=socks5          # http/socks5/rotating
PROXY_HOST=127.0.0.1
PROXY_PORT=9595
PROXY_USER=user
PROXY_PASS=pass

# Telegram 通知
TG_BOT_TOKEN=xxx
TG_CHAT_ID=xxx

# 降价阈值
PRICE_DROP_THRESHOLD=5     # 降价超过5%触发通知
CHECK_INTERVAL=3600        # 检查间隔(秒)
```

## 模块详解

### 💱 多币种转换 (Currency Converter)
支持 USD, EUR, GBP, JPY, CNY, CAD 等 18 种货币自动转换，比较不同平台不同货币标价的真实价格。

### 🔀 跨平台比价 (Price Comparator)
- **相似商品发现**: 基于标题 Jaccard 相似度自动匹配
- **Deal Score**: 0-100 综合评分（历史位置 + 目标价 + 趋势）
- **价格波动分析**: 标准差、变异系数、稳定性评分

### 📐 价格预测 (Price Predictor)
- **SMA / EMA**: 简单/指数移动平均线
- **线性回归**: 趋势预测 + R² 置信度 + 7天预测
- **异常检测**: Z-score 方法识别异常价格波动
- **季节模式**: 识别每周最佳购买日
- **买入信号**: BUY / HOLD / WAIT 综合信号

### 📋 智能规则引擎 (Alert Rules)
8 种告警类型:
| 类型 | 说明 |
|------|------|
| `price_drop` | 降价百分比超过阈值 |
| `price_rise` | 涨价百分比超过阈值 |
| `target_price` | 达到目标价格 |
| `back_in_stock` | 商品补货 |
| `out_of_stock` | 商品缺货 |
| `new_lowest` | 历史新低 |
| `percentage_change` | 任意方向变动超过阈值 |
| `absolute_change` | 绝对价格变动超过阈值 |

支持: 平台过滤 / 标签过滤 / 冷却时间 / 每日触发上限

### 📁 监控列表 (Watchlist Manager)
命名分组管理，支持: 批量URL导入 / 批量移除 / 列表合并 / 商品搜索

### 📤 导出引擎 (Export Engine)
| 格式 | 说明 |
|------|------|
| CSV | 电子表格兼容 |
| JSON | API/程序集成 |
| HTML | 带样式的可视化报告 |
| Markdown | 文档/Wiki集成 |

## 支持平台

| 平台 | 状态 | 备注 |
|------|------|------|
| Amazon US/UK/DE/JP | ✅ | Product API + 页面抓取双模式 |
| AliExpress | ✅ | API + 页面解析 |
| Shopee | ✅ | 移动端API |
| 1688 | ✅ | 页面抓取 |

## 架构

```
app/
├── cli.py                  # CLI 入口 (9个命令)
├── config.py               # 配置管理
├── models/
│   ├── product.py          # 商品模型 + 平台检测
│   └── database.py         # SQLite 数据库
├── scrapers/
│   ├── base.py             # 抓取基类 (重试+代理+限速)
│   ├── amazon.py           # Amazon 抓取器
│   ├── aliexpress.py       # AliExpress 抓取器
│   ├── shopee.py           # Shopee 抓取器
│   └── ali1688.py          # 1688 抓取器
├── services/
│   ├── monitor.py          # 监控调度
│   ├── notifier.py         # 多渠道通知
│   ├── reporter.py         # 报告生成
│   ├── comparator.py       # 🆕 跨平台比价引擎
│   ├── predictor.py        # 🆕 价格预测
│   ├── rules.py            # 🆕 智能告警规则引擎
│   ├── watchlist.py        # 🆕 监控列表管理
│   └── exporter.py         # 🆕 多格式导出引擎
└── utils/
    ├── proxy.py            # 代理管理
    ├── ua.py               # UA 随机化
    └── currency.py         # 🆕 多币种转换
```

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 211 个测试，覆盖全部模块
```

## License

MIT
