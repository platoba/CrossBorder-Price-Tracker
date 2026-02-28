# CrossBorder-Price-Tracker 🔍💰

跨境电商多平台价格追踪器 — 实时监控 Amazon / AliExpress / Shopee / 1688 商品价格变动，智能提醒降价。

## 功能

- 📊 **多平台抓取**: Amazon (US/UK/DE/JP) + AliExpress + Shopee + 1688
- 📈 **价格历史**: SQLite 持久化，趋势图表
- 🔔 **降价提醒**: Telegram / Email / Webhook 通知
- 🕷️ **反检测**: 代理轮转 + UA随机化 + 请求限速
- 📦 **批量监控**: CSV/JSON 导入商品列表
- 📊 **分析报告**: 价格波动分析 + 最佳入手时机推荐
- 🐳 **Docker 部署**: 一键启动，开箱即用

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

# 导出报告
python -m app.cli report --format html --days 30
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
├── cli.py              # CLI 入口
├── config.py           # 配置管理
├── models/
│   ├── product.py      # 商品模型
│   └── database.py     # SQLite ORM
├── scrapers/
│   ├── base.py         # 抓取基类
│   ├── amazon.py       # Amazon 抓取器
│   ├── aliexpress.py   # AliExpress 抓取器
│   ├── shopee.py       # Shopee 抓取器
│   └── ali1688.py      # 1688 抓取器
├── services/
│   ├── monitor.py      # 监控调度
│   ├── notifier.py     # 通知服务
│   └── reporter.py     # 报告生成
└── utils/
    ├── proxy.py        # 代理管理
    └── ua.py           # UA 随机化
```

## License

MIT
