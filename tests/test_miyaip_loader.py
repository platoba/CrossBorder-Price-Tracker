"""Tests for miyaip proxy loader."""
import json
import pytest
from pathlib import Path
from app.utils.miyaip_loader import MiyaipLoader
from app.utils.proxy import ProxyPool


@pytest.fixture
def mock_arsenal_dir(tmp_path):
    """Create mock arsenal directory with proxy file."""
    arsenal = tmp_path / "arsenal"
    arsenal.mkdir()
    
    proxy_data = {
        "proxies": [
            {
                "url": "http://1.2.3.4:8080",
                "protocol": "http",
                "country": "US",
                "is_active": True
            },
            {
                "url": "http://5.6.7.8:8080",
                "protocol": "http",
                "country": "UK",
                "is_active": True
            },
            {
                "url": "http://9.10.11.12:8080",
                "protocol": "http",
                "country": "US",
                "is_active": False
            }
        ],
        "expiry_date": "2026-03-22"
    }
    
    proxy_file = arsenal / "static-proxies-miyaip.json"
    with open(proxy_file, "w") as f:
        json.dump(proxy_data, f)
    
    return arsenal


class TestMiyaipLoader:
    """Test miyaip proxy loader."""
    
    def test_load_all_proxies(self, mock_arsenal_dir):
        loader = MiyaipLoader(mock_arsenal_dir)
        pool = ProxyPool()
        
        count = loader.load_into_pool(pool)
        
        assert count == 2  # Only active proxies
        assert pool.active_count == 2
    
    def test_load_by_country(self, mock_arsenal_dir):
        loader = MiyaipLoader(mock_arsenal_dir)
        pool = ProxyPool()
        
        count = loader.load_into_pool(pool, country="US")
        
        assert count == 1  # Only US active proxy
        assert pool.active_count == 1
    
    def test_create_pool(self, mock_arsenal_dir):
        loader = MiyaipLoader(mock_arsenal_dir)
        pool = loader.create_pool()
        
        assert pool.active_count == 2
    
    def test_create_pool_with_country(self, mock_arsenal_dir):
        loader = MiyaipLoader(mock_arsenal_dir)
        pool = loader.create_pool(country="UK")
        
        assert pool.active_count == 1
    
    def test_get_proxy_stats(self, mock_arsenal_dir):
        loader = MiyaipLoader(mock_arsenal_dir)
        stats = loader.get_proxy_stats()
        
        assert stats["total"] == 3
        assert stats["active"] == 2
        assert stats["inactive"] == 1
        assert stats["by_country"]["US"] == 1
        assert stats["by_country"]["UK"] == 1
        assert stats["expiry"] == "2026-03-22"
    
    def test_missing_file(self, tmp_path):
        loader = MiyaipLoader(tmp_path / "nonexistent")
        pool = ProxyPool()
        
        count = loader.load_into_pool(pool)
        assert count == 0
        
        stats = loader.get_proxy_stats()
        assert "error" in stats
    
    def test_invalid_json(self, tmp_path):
        arsenal = tmp_path / "arsenal"
        arsenal.mkdir()
        
        proxy_file = arsenal / "static-proxies-miyaip.json"
        with open(proxy_file, "w") as f:
            f.write("invalid json{")
        
        loader = MiyaipLoader(arsenal)
        pool = ProxyPool()
        
        count = loader.load_into_pool(pool)
        assert count == 0
