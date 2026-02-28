"""User-Agent randomization."""
import random

CHROME_VERSIONS = [
    "120.0.6099.109", "121.0.6167.85", "122.0.6261.57", "123.0.6312.58",
    "124.0.6367.91", "125.0.6422.76", "126.0.6478.61",
]

PLATFORMS = [
    ("Windows NT 10.0; Win64; x64", "Windows"),
    ("Macintosh; Intel Mac OS X 10_15_7", "macOS"),
    ("X11; Linux x86_64", "Linux"),
]

MOBILE_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.76 Mobile Safari/537.36",
]


def random_ua(mobile: bool = False) -> str:
    if mobile:
        return random.choice(MOBILE_UAS)
    platform, _ = random.choice(PLATFORMS)
    chrome = random.choice(CHROME_VERSIONS)
    return f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome} Safari/537.36"


def random_headers(mobile: bool = False, referer: str = "") -> dict:
    headers = {
        "User-Agent": random_ua(mobile),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    return headers
