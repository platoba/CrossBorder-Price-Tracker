"""Load miyaip static proxy pool from arsenal."""
import json
from pathlib import Path
from typing import List, Optional
from .proxy import ProxyPool


class MiyaipLoader:
    """Load miyaip static proxies from C-line arsenal."""
    
    DEFAULT_ARSENAL_PATH = Path.home() / "Documents/research/c-crawler-research/arsenal"
    
    def __init__(self, arsenal_path: Optional[Path] = None):
        self.arsenal_path = arsenal_path or self.DEFAULT_ARSENAL_PATH
        self.proxy_file = self.arsenal_path / "static-proxies-miyaip.json"
    
    def load_into_pool(self, pool: ProxyPool, country: str = "") -> int:
        """
        Load miyaip proxies into a ProxyPool.
        
        Args:
            pool: ProxyPool instance to load into
            country: Filter by country code (e.g., "US", "UK")
            
        Returns:
            Number of proxies loaded
        """
        if not self.proxy_file.exists():
            return 0
        
        try:
            with open(self.proxy_file) as f:
                data = json.load(f)
            
            proxies = data.get("proxies", [])
            loaded = 0
            
            for proxy in proxies:
                # Skip if country filter doesn't match
                if country and proxy.get("country", "").upper() != country.upper():
                    continue
                
                # Skip inactive proxies
                if not proxy.get("is_active", True):
                    continue
                
                url = proxy.get("url") or proxy.get("proxy")
                if url:
                    pool.add(
                        url=url,
                        protocol=proxy.get("protocol", "http"),
                        country=proxy.get("country", "")
                    )
                    loaded += 1
            
            return loaded
        
        except (json.JSONDecodeError, IOError) as e:
            print(f"Failed to load miyaip proxies: {e}")
            return 0
    
    def create_pool(self, country: str = "") -> ProxyPool:
        """
        Create a new ProxyPool with miyaip proxies.
        
        Args:
            country: Filter by country code
            
        Returns:
            ProxyPool instance with loaded proxies
        """
        pool = ProxyPool()
        self.load_into_pool(pool, country)
        return pool
    
    def get_proxy_stats(self) -> dict:
        """Get statistics about available miyaip proxies."""
        if not self.proxy_file.exists():
            return {"error": "Proxy file not found"}
        
        try:
            with open(self.proxy_file) as f:
                data = json.load(f)
            
            proxies = data.get("proxies", [])
            active = [p for p in proxies if p.get("is_active", True)]
            
            countries = {}
            for p in active:
                country = p.get("country", "unknown")
                countries[country] = countries.get(country, 0) + 1
            
            return {
                "total": len(proxies),
                "active": len(active),
                "inactive": len(proxies) - len(active),
                "by_country": countries,
                "expiry": data.get("expiry_date", "unknown")
            }
        
        except (json.JSONDecodeError, IOError) as e:
            return {"error": str(e)}
