"""Proxy pool management."""
import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProxyEntry:
    url: str
    protocol: str = "http"  # http/socks5
    country: str = ""
    fail_count: int = 0
    success_count: int = 0
    is_active: bool = True

    @property
    def score(self) -> float:
        total = self.fail_count + self.success_count
        if total == 0:
            return 0.5
        return self.success_count / total


class ProxyPool:
    def __init__(self):
        self._proxies: List[ProxyEntry] = []
        self._current_index = 0

    def add(self, url: str, protocol: str = "http", country: str = ""):
        self._proxies.append(ProxyEntry(url=url, protocol=protocol, country=country))

    def add_list(self, proxy_urls: List[str], protocol: str = "http"):
        for url in proxy_urls:
            self.add(url.strip(), protocol)

    def get_next(self, country: str = "") -> Optional[str]:
        active = [p for p in self._proxies if p.is_active]
        if country:
            active = [p for p in active if p.country == country]
        if not active:
            return None
        # Weight by score
        weights = [max(p.score, 0.1) for p in active]
        proxy = random.choices(active, weights=weights, k=1)[0]
        return proxy.url

    def report_success(self, url: str):
        for p in self._proxies:
            if p.url == url:
                p.success_count += 1
                break

    def report_failure(self, url: str):
        for p in self._proxies:
            if p.url == url:
                p.fail_count += 1
                if p.score < 0.1 and p.fail_count >= 5:
                    p.is_active = False
                break

    @property
    def active_count(self) -> int:
        return sum(1 for p in self._proxies if p.is_active)

    @property
    def total_count(self) -> int:
        return len(self._proxies)

    def stats(self) -> dict:
        return {
            "total": self.total_count,
            "active": self.active_count,
            "avg_score": sum(p.score for p in self._proxies) / max(len(self._proxies), 1),
        }
