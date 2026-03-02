"""Tests for anti-crawl detection and engine escalation."""
import pytest
from app.utils.anti_crawl import (
    AntiCrawlDetector,
    EngineEscalator,
    EngineLevel,
    BlockType,
)


class TestAntiCrawlDetector:
    """Test anti-crawl detection."""
    
    def test_detect_timeout(self):
        detector = AntiCrawlDetector()
        result = detector.detect(200, "OK", 35.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.TIMEOUT
        assert result.confidence >= 0.8
        assert result.recommended_level == EngineLevel.L2_JS_RENDER
    
    def test_detect_403_blocked(self):
        detector = AntiCrawlDetector()
        result = detector.detect(403, "Forbidden", 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.BLOCKED
        assert result.confidence >= 0.9
        assert result.recommended_level == EngineLevel.L4_FINGERPRINT
    
    def test_detect_429_rate_limit(self):
        detector = AntiCrawlDetector()
        result = detector.detect(429, "Too Many Requests", 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.RATE_LIMITED
        assert result.recommended_level == EngineLevel.L4_FINGERPRINT
    
    def test_detect_captcha_pattern(self):
        detector = AntiCrawlDetector()
        html = "<html><body>Please verify you are human with reCAPTCHA</body></html>"
        result = detector.detect(200, html, 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.CAPTCHA
        assert result.recommended_level == EngineLevel.L6_ULTIMATE
    
    def test_detect_cloudflare_challenge(self):
        detector = AntiCrawlDetector()
        html = "<html><body>Cloudflare challenge page</body></html>"
        result = detector.detect(200, html, 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.CAPTCHA
    
    def test_detect_access_denied(self):
        detector = AntiCrawlDetector()
        html = "<html><body>Access Denied - Suspicious Activity Detected</body></html>"
        result = detector.detect(200, html, 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.BLOCKED
    
    def test_detect_rate_limit_text(self):
        detector = AntiCrawlDetector()
        html = "<html><body>Rate limit exceeded. Please slow down.</body></html>"
        result = detector.detect(200, html, 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.RATE_LIMITED
    
    def test_detect_auth_expired(self):
        detector = AntiCrawlDetector()
        result = detector.detect(401, "Unauthorized", 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.AUTH_EXPIRED
        assert result.recommended_level == EngineLevel.L1_STATIC
    
    def test_detect_suspicious_short_response(self):
        detector = AntiCrawlDetector()
        result = detector.detect(200, "OK", 1.0)
        
        assert result.is_blocked
        assert result.block_type == BlockType.UNKNOWN
        assert result.confidence < 0.8  # Lower confidence for heuristic
    
    def test_detect_normal_response(self):
        detector = AntiCrawlDetector()
        html = "<html><body>" + "Normal content " * 50 + "</body></html>"
        result = detector.detect(200, html, 1.0)
        
        assert not result.is_blocked
        assert result.block_type is None
        assert result.confidence == 1.0


class TestEngineEscalator:
    """Test engine escalation logic."""
    
    def test_initial_level(self):
        escalator = EngineEscalator()
        level = escalator.get_level("example.com")
        assert level == EngineLevel.L1_STATIC
    
    def test_escalate_after_three_failures(self):
        escalator = EngineEscalator()
        target = "example.com"
        
        # First two failures - no escalation
        result1 = escalator.record_failure(target, EngineLevel.L1_STATIC)
        assert result1 is None
        
        result2 = escalator.record_failure(target, EngineLevel.L1_STATIC)
        assert result2 is None
        
        # Third failure - escalate
        result3 = escalator.record_failure(target, EngineLevel.L1_STATIC)
        assert result3 == EngineLevel.L2_JS_RENDER
        
        # Verify level is updated
        assert escalator.get_level(target) == EngineLevel.L2_JS_RENDER
    
    def test_escalate_multiple_levels(self):
        escalator = EngineEscalator()
        target = "example.com"
        
        # Escalate from L1 to L2
        for _ in range(3):
            escalator.record_failure(target, EngineLevel.L1_STATIC)
        
        # Escalate from L2 to L3
        for _ in range(3):
            escalator.record_failure(target, EngineLevel.L2_JS_RENDER)
        
        assert escalator.get_level(target) == EngineLevel.L3_BATCH
    
    def test_success_clears_failures(self):
        escalator = EngineEscalator()
        target = "example.com"
        
        # Record some failures
        escalator.record_failure(target, EngineLevel.L1_STATIC)
        escalator.record_failure(target, EngineLevel.L1_STATIC)
        
        # Record success
        escalator.record_success(target, EngineLevel.L1_STATIC)
        
        # Next failures should start from scratch
        result = escalator.record_failure(target, EngineLevel.L1_STATIC)
        assert result is None  # Not escalated yet
    
    def test_max_level_no_escalation(self):
        escalator = EngineEscalator()
        target = "example.com"
        
        # Manually set to L6
        escalator.record_success(target, EngineLevel.L6_ULTIMATE)
        
        # Try to escalate beyond L6
        result = None
        for _ in range(3):
            result = escalator.record_failure(target, EngineLevel.L6_ULTIMATE)
        
        # Should return None (no further escalation)
        assert result is None
        # Level should stay at L6
        assert escalator.get_level(target) == EngineLevel.L6_ULTIMATE
    
    def test_stats(self):
        escalator = EngineEscalator()
        
        escalator.record_success("site1.com", EngineLevel.L1_STATIC)
        escalator.record_success("site2.com", EngineLevel.L2_JS_RENDER)
        escalator.record_failure("site3.com", EngineLevel.L1_STATIC)
        
        stats = escalator.stats()
        
        assert stats["tracked_targets"] == 2  # Only successful ones tracked
        assert stats["active_failures"] == 1
        assert stats["level_distribution"][EngineLevel.L1_STATIC.name] == 1
        assert stats["level_distribution"][EngineLevel.L2_JS_RENDER.name] == 1
    
    def test_different_targets_independent(self):
        escalator = EngineEscalator()
        
        # Escalate site1
        for _ in range(3):
            escalator.record_failure("site1.com", EngineLevel.L1_STATIC)
        
        # site2 should still be at L1
        assert escalator.get_level("site1.com") == EngineLevel.L2_JS_RENDER
        assert escalator.get_level("site2.com") == EngineLevel.L1_STATIC
