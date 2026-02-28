"""Multi-channel notification service."""
import json
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional
import httpx
from app.config import Config

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: Config = None):
        self.config = config or Config.from_env()

    def notify(self, title: str, message: str, data: dict = None) -> bool:
        """Send notification through all configured channels."""
        sent = False
        if self.config.notify.telegram_token:
            sent = self._send_telegram(title, message) or sent
        if self.config.notify.webhook_url:
            sent = self._send_webhook(title, message, data) or sent
        if self.config.notify.email_smtp:
            sent = self._send_email(title, message) or sent
        return sent

    def _send_telegram(self, title: str, message: str) -> bool:
        token = self.config.notify.telegram_token
        chat_id = self.config.notify.telegram_chat_id
        text = f"🔔 <b>{title}</b>\n\n{message}"
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram notify failed: {e}")
            return False

    def _send_webhook(self, title: str, message: str, data: dict = None) -> bool:
        payload = {"title": title, "message": message, "data": data or {}}
        try:
            resp = httpx.post(self.config.notify.webhook_url, json=payload, timeout=10)
            return resp.status_code < 300
        except Exception as e:
            logger.error(f"Webhook notify failed: {e}")
            return False

    def _send_email(self, title: str, message: str) -> bool:
        try:
            msg = MIMEText(message, "plain", "utf-8")
            msg["Subject"] = title
            msg["From"] = self.config.notify.email_from
            msg["To"] = self.config.notify.email_to
            with smtplib.SMTP(self.config.notify.email_smtp) as s:
                s.starttls()
                s.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email notify failed: {e}")
            return False


def format_price_alert(product: dict, old_price: float, new_price: float,
                       change_pct: float) -> tuple:
    """Format a price change alert."""
    direction = "📉 降价" if change_pct < 0 else "📈 涨价"
    title = f"{direction} {abs(change_pct):.1f}%"
    msg = (
        f"商品: {product.get('title', 'Unknown')}\n"
        f"平台: {product.get('platform', 'unknown').upper()}\n"
        f"原价: {product.get('currency', 'USD')} {old_price:.2f}\n"
        f"现价: {product.get('currency', 'USD')} {new_price:.2f}\n"
        f"变动: {change_pct:+.1f}%\n"
        f"链接: {product.get('url', '')}"
    )
    return title, msg
