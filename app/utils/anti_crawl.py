"""Anti-crawl detection and engine escalation."""
import re
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class EngineLevel(Enum):
    """Scraping engine levels (C-line constitution)."""
    L1_STATIC = 1  # httpx/curl
    L2_JS_RENDER = 2  # Playwright/Scrapling
    L3_BATCH = 3  # Firecrawl cluster
    L4_FINGERPRINT = 4  # Fingerprint simulation
    L5_API_REVERSE = 5  # API protocol replay
    L6_ULTIMATE = 6  # Captcha solver + IP rotation


class BlockType(Enum):
    """Types of anti-crawl blocks."""
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    AUTH_EXPIRED = "auth_expired"
    UNKNOWN = "unknown"


@dataclass
class DetectionResult:
    """Anti-crawl detection result."""
    is_blocked: bool
    block_type: Optional[BlockType]
    confidence: float  # 0.0-1.0
    evidence: str
    recommended_level: Optional[EngineLevel]


class AntiCrawlDetector:
    """Detect anti-crawl measures and recommend engine escalation."""
    
    # Patterns for common anti-crawl responses
    PATTERNS = {
        BlockType.CAPTCHA: [
            r"captcha",
            r"recaptcha",
            r"hcaptcha",
            r"cloudflare.*challenge",
            r"please.*verify.*human",
        ],
        BlockType.BLOCKED: [
            r"access.*denied",
            r"403.*forbidden",
            r"blocked",
            r"suspicious.*activity",
            r"unusual.*traffic",
        ],
        BlockType.RATE_LIMITED: [
            r"rate.*limit",
            r"too.*many.*requests",
            r"429",
            r"slow.*down",
        ],
        BlockType.AUTH_EXPIRED: [
            r"session.*expired",
            r"token.*invalid",
            r"unauthorized",
            r"401",
        ],
    }
    
    def detect(
        self,
        status_code: int,
        response_text: str,
        response_time: float,
        headers: Optional[Dict[str, str]] = None
    ) -> DetectionResult:
        """
        Detect anti-crawl measures from response.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            response_time: Response time in seconds
            headers: Response headers
            
        Returns:
            DetectionResult with block type and recommended engine level
        """
        # Check timeout
        if response_time > 30:
            return DetectionResult(
                is_blocked=True,
                block_type=BlockType.TIMEOUT,
                confidence=0.9,
                evidence=f"Response time {response_time:.1f}s exceeds threshold",
                recommended_level=EngineLevel.L2_JS_RENDER
            )
        
        # Check status code
        if status_code in (403, 429):
            block_type = BlockType.RATE_LIMITED if status_code == 429 else BlockType.BLOCKED
            return DetectionResult(
                is_blocked=True,
                block_type=block_type,
                confidence=0.95,
                evidence=f"HTTP {status_code}",
                recommended_level=EngineLevel.L4_FINGERPRINT
            )
        
        if status_code == 401:
            return DetectionResult(
                is_blocked=True,
                block_type=BlockType.AUTH_EXPIRED,
                confidence=0.9,
                evidence="HTTP 401 Unauthorized",
                recommended_level=EngineLevel.L1_STATIC  # Retry with auth refresh
            )
        
        # Pattern matching on response text
        text_lower = response_text.lower()
        for block_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    confidence = 0.8 if len(response_text) < 1000 else 0.9
                    recommended = self._recommend_level(block_type)
                    return DetectionResult(
                        is_blocked=True,
                        block_type=block_type,
                        confidence=confidence,
                        evidence=f"Pattern matched: {pattern}",
                        recommended_level=recommended
                    )
        
        # Check for suspicious short responses
        if status_code == 200 and len(response_text) < 100:
            return DetectionResult(
                is_blocked=True,
                block_type=BlockType.UNKNOWN,
                confidence=0.6,
                evidence=f"Suspiciously short response: {len(response_text)} bytes",
                recommended_level=EngineLevel.L2_JS_RENDER
            )
        
        # No block detected
        return DetectionResult(
            is_blocked=False,
            block_type=None,
            confidence=1.0,
            evidence="Normal response",
            recommended_level=None
        )
    
    def _recommend_level(self, block_type: BlockType) -> EngineLevel:
        """Recommend engine level based on block type."""
        recommendations = {
            BlockType.TIMEOUT: EngineLevel.L2_JS_RENDER,
            BlockType.BLOCKED: EngineLevel.L4_FINGERPRINT,
            BlockType.CAPTCHA: EngineLevel.L6_ULTIMATE,
            BlockType.RATE_LIMITED: EngineLevel.L4_FINGERPRINT,
            BlockType.AUTH_EXPIRED: EngineLevel.L1_STATIC,
            BlockType.UNKNOWN: EngineLevel.L2_JS_RENDER,
        }
        return recommendations.get(block_type, EngineLevel.L2_JS_RENDER)


class EngineEscalator:
    """Manage engine level escalation based on failures."""
    
    def __init__(self):
        self._failure_counts: Dict[str, int] = {}
        self._current_levels: Dict[str, EngineLevel] = {}
    
    def record_failure(self, target: str, current_level: EngineLevel) -> Optional[EngineLevel]:
        """
        Record a failure and return escalated level if needed.
        
        Args:
            target: Target URL or domain
            current_level: Current engine level
            
        Returns:
            Escalated engine level if threshold reached, None otherwise
        """
        key = f"{target}:{current_level.value}"
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        
        # Escalate after 3 consecutive failures (C-line constitution)
        if self._failure_counts[key] >= 3:
            next_level = self._escalate(current_level)
            if next_level:
                self._current_levels[target] = next_level
                self._failure_counts[key] = 0  # Reset counter
                return next_level
        
        return None
    
    def record_success(self, target: str, level: EngineLevel):
        """Record a successful scrape and potentially downgrade."""
        self._current_levels[target] = level
        # Clear failure counts for this target
        for key in list(self._failure_counts.keys()):
            if key.startswith(f"{target}:"):
                del self._failure_counts[key]
    
    def get_level(self, target: str) -> EngineLevel:
        """Get current recommended level for target."""
        return self._current_levels.get(target, EngineLevel.L1_STATIC)
    
    def _escalate(self, current: EngineLevel) -> Optional[EngineLevel]:
        """Escalate to next level."""
        levels = list(EngineLevel)
        try:
            idx = levels.index(current)
            if idx < len(levels) - 1:
                return levels[idx + 1]
        except ValueError:
            pass
        return None
    
    def stats(self) -> Dict[str, Any]:
        """Get escalation statistics."""
        return {
            "tracked_targets": len(self._current_levels),
            "active_failures": len(self._failure_counts),
            "level_distribution": {
                level.name: sum(1 for v in self._current_levels.values() if v == level)
                for level in EngineLevel
            }
        }
