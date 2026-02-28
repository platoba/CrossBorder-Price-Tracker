"""Configuration management."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProxyConfig:
    type: str = "none"  # none/http/socks5/rotating
    host: str = ""
    port: int = 0
    user: str = ""
    password: str = ""

    @property
    def url(self) -> Optional[str]:
        if self.type == "none" or not self.host:
            return None
        auth = f"{self.user}:{self.password}@" if self.user else ""
        scheme = "socks5" if self.type == "socks5" else "http"
        return f"{scheme}://{auth}{self.host}:{self.port}"


@dataclass
class NotifyConfig:
    telegram_token: str = ""
    telegram_chat_id: str = ""
    webhook_url: str = ""
    email_smtp: str = ""
    email_from: str = ""
    email_to: str = ""


@dataclass
class Config:
    db_path: str = "data/prices.db"
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    price_drop_threshold: float = 5.0  # percent
    check_interval: int = 3600  # seconds
    max_retries: int = 3
    request_delay: float = 2.0  # seconds between requests
    user_agent_rotate: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        proxy = ProxyConfig(
            type=os.getenv("PROXY_TYPE", "none"),
            host=os.getenv("PROXY_HOST", ""),
            port=int(os.getenv("PROXY_PORT", "0")),
            user=os.getenv("PROXY_USER", ""),
            password=os.getenv("PROXY_PASS", ""),
        )
        notify = NotifyConfig(
            telegram_token=os.getenv("TG_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TG_CHAT_ID", ""),
            webhook_url=os.getenv("WEBHOOK_URL", ""),
            email_smtp=os.getenv("EMAIL_SMTP", ""),
            email_from=os.getenv("EMAIL_FROM", ""),
            email_to=os.getenv("EMAIL_TO", ""),
        )
        return cls(
            db_path=os.getenv("DB_PATH", "data/prices.db"),
            proxy=proxy,
            notify=notify,
            price_drop_threshold=float(os.getenv("PRICE_DROP_THRESHOLD", "5")),
            check_interval=int(os.getenv("CHECK_INTERVAL", "3600")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            request_delay=float(os.getenv("REQUEST_DELAY", "2.0")),
        )
