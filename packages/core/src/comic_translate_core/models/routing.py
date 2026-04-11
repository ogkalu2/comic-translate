"""
Routing decision models for semantic routing and NSFW detection.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TranslatorType(str, Enum):
    """Available translator types for routing decisions."""
    LOCAL_NSFW = "local_nsfw"
    LOCAL_SFX = "local_sfx"
    DEEPL = "deepl"
    GPT = "gpt"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    SKIP = "skip"


@dataclass
class LanguageDetection:
    """Language detection result for a block."""
    detected_lang: str  # ISO 639-1 code (e.g., "ja", "en", "zh")
    confidence: float  # 0.0 to 1.0
    alternative_langs: Dict[str, float] = field(default_factory=dict)


@dataclass
class EnsembleCandidate:
    """A candidate translator in an ensemble routing decision."""
    translator_type: TranslatorType
    weight: float
    confidence: float
    reason: str


@dataclass
class RoutingDecision:
    """
    Decision output from the semantic router.
    
    Attributes:
        translator_type: The translator to use for this block
        skip_flag: If True, skip translation and repaint entirely
        nsfw_flag: If True, content is NSFW and should use local-only translation
        reason: Human-readable reason for the routing decision
        language_detection: Detected language information
        confidence: Overall confidence in the routing decision (0.0 to 1.0)
        ensemble_candidates: Optional list of ensemble candidates for multi-model routing
        cache_key: Optional cache key for result caching
    """
    translator_type: TranslatorType
    skip_flag: bool = False
    nsfw_flag: bool = False
    reason: Optional[str] = None
    language_detection: Optional[LanguageDetection] = None
    confidence: float = 1.0
    ensemble_candidates: List[EnsembleCandidate] = field(default_factory=list)
    cache_key: Optional[str] = None
