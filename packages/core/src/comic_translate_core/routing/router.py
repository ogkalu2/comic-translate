"""
Semantic router for comic block translation decisions with language-aware routing.
"""

import hashlib
from typing import Dict, List, Optional

from ..models.block_v2 import Block, BlockType
from ..models.routing import (
    EnsembleCandidate,
    LanguageDetection,
    RoutingDecision,
    TranslatorType,
)
from .language_detector import LanguageDetector
from .nsfw_detector import NSFWDetector
from .sfx_detector import SFXDetector


class SemanticRouter:
    """
    Routes comic blocks to appropriate translators based on content analysis.
    
    Enhanced routing logic with language detection:
    - credit/ui_meta → skip (no translation, no repaint)
    - nsfw_flag=true + EhTag match → local-only translation
    - sfx → local SFX corpus
    - Language detection → route to language-specific models
    - Content complexity → adaptive model selection
    - Ensemble routing for high-stakes content
    """
    
    # Language-specific translator preferences
    LANG_TRANSLATOR_MAP: Dict[str, List[TranslatorType]] = {
        "ja": [TranslatorType.CLAUDE, TranslatorType.GPT, TranslatorType.DEEPL],
        "zh": [TranslatorType.CLAUDE, TranslatorType.GPT, TranslatorType.DEEPL],
        "ko": [TranslatorType.CLAUDE, TranslatorType.GPT, TranslatorType.DEEPL],
        "en": [TranslatorType.DEEPL, TranslatorType.GPT, TranslatorType.CLAUDE],
        "th": [TranslatorType.GPT, TranslatorType.CLAUDE, TranslatorType.DEEPL],
        "ar": [TranslatorType.GPT, TranslatorType.CLAUDE, TranslatorType.DEEPL],
    }
    
    def __init__(
        self,
        nsfw_detector: Optional[NSFWDetector] = None,
        sfx_detector: Optional[SFXDetector] = None,
        language_detector: Optional[LanguageDetector] = None,
        ehtag_dict: Optional[Dict[str, str]] = None,
        enable_ensemble: bool = False,
        ensemble_threshold: float = 0.7,
    ):
        """
        Initialize the semantic router.
        
        Args:
            nsfw_detector: NSFW detector instance (creates default if None)
            sfx_detector: SFX detector instance (creates default if None)
            language_detector: Language detector instance (creates default if None)
            ehtag_dict: Optional EhTag dictionary for NSFW detection
            enable_ensemble: Enable ensemble routing for uncertain decisions
            ensemble_threshold: Confidence threshold below which ensemble is used
        """
        self.nsfw_detector = nsfw_detector or NSFWDetector()
        self.sfx_detector = sfx_detector or SFXDetector()
        self.language_detector = language_detector or LanguageDetector()
        self.ehtag_dict = ehtag_dict or {}
        self.enable_ensemble = enable_ensemble
        self.ensemble_threshold = ensemble_threshold
        
        # Simple in-memory cache for routing decisions
        self._routing_cache: Dict[str, RoutingDecision] = {}
    
    def _get_text_from_block(self, block: Block) -> str:
        """
        Extract text content from a block.
        
        Args:
            block: The block to extract text from
            
        Returns:
            Concatenated text from all original texts
        """
        if not block.original_texts:
            return ""
        return " ".join(ot.text for ot in block.original_texts)
    
    def _route_skip(self, reason: str) -> RoutingDecision:
        """Create a skip routing decision."""
        return RoutingDecision(
            translator_type=TranslatorType.SKIP,
            skip_flag=True,
            nsfw_flag=False,
            reason=reason,
        )
    
    def _route_nsfw(self, reason: str) -> RoutingDecision:
        """Create an NSFW routing decision."""
        return RoutingDecision(
            translator_type=TranslatorType.LOCAL_NSFW,
            skip_flag=False,
            nsfw_flag=True,
            reason=reason,
        )
    
    def _route_sfx(self, reason: str) -> RoutingDecision:
        """Create an SFX routing decision."""
        return RoutingDecision(
            translator_type=TranslatorType.LOCAL_SFX,
            skip_flag=False,
            nsfw_flag=False,
            reason=reason,
        )
    
    def _route_deepl(self, reason: str) -> RoutingDecision:
        """Create a DeepL routing decision."""
        return RoutingDecision(
            translator_type=TranslatorType.DEEPL,
            skip_flag=False,
            nsfw_flag=False,
            reason=reason,
        )
    
    def _generate_cache_key(self, block: Block) -> str:
        """Generate a cache key for a block."""
        text = self._get_text_from_block(block)
        key_data = f"{block.type.value}:{text}:{block.nsfw_flag}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _detect_language(self, text: str) -> LanguageDetection:
        """Detect language of text with confidence scores."""
        primary_lang, confidence, alternatives = self.language_detector.detect_with_alternatives(text)
        return LanguageDetection(
            detected_lang=primary_lang,
            confidence=confidence,
            alternative_langs=alternatives,
        )
    
    def _get_translator_for_language(self, lang: str) -> TranslatorType:
        """Get preferred translator for a language."""
        translators = self.LANG_TRANSLATOR_MAP.get(lang, [TranslatorType.DEEPL])
        return translators[0]
    
    def _create_ensemble_decision(
        self,
        primary_type: TranslatorType,
        lang_detection: LanguageDetection,
        reason: str,
    ) -> RoutingDecision:
        """Create an ensemble routing decision with multiple candidates."""
        candidates = []
        
        # Add primary translator
        candidates.append(EnsembleCandidate(
            translator_type=primary_type,
            weight=0.5,
            confidence=lang_detection.confidence,
            reason=f"Primary: {reason}",
        ))
        
        # Add language-specific alternatives
        lang = lang_detection.detected_lang
        alt_translators = self.LANG_TRANSLATOR_MAP.get(lang, [TranslatorType.DEEPL])
        
        for i, translator in enumerate(alt_translators[1:3], 1):  # Up to 2 alternatives
            weight = 0.3 / (i + 1)  # Decreasing weight
            candidates.append(EnsembleCandidate(
                translator_type=translator,
                weight=weight,
                confidence=lang_detection.confidence * 0.8,
                reason=f"Alternative {i}: {lang}-optimized",
            ))
        
        return RoutingDecision(
            translator_type=primary_type,
            reason=f"Ensemble: {reason}",
            language_detection=lang_detection,
            confidence=lang_detection.confidence,
            ensemble_candidates=candidates,
        )
    
    def route(self, block: Block) -> RoutingDecision:
        """
        Route a block to the appropriate translator with language-aware routing.
        
        Args:
            block: The block to route
            
        Returns:
            RoutingDecision with translator type, language detection, and flags
        """
        # Check cache first
        cache_key = self._generate_cache_key(block)
        if cache_key in self._routing_cache:
            cached = self._routing_cache[cache_key]
            cached.cache_key = cache_key
            return cached
        
        # 1. Check for credit/ui_meta → skip
        if block.type in (BlockType.CREDIT, BlockType.UI_META):
            decision = self._route_skip(
                f"Block type {block.type.value} requires no translation"
            )
            decision.cache_key = cache_key
            self._routing_cache[cache_key] = decision
            return decision
        
        text = self._get_text_from_block(block)
        
        # 2. Check for NSFW content (higher priority than SFX)
        if block.nsfw_flag:
            if self.ehtag_dict:
                if self.nsfw_detector.detect_from_ehtag(text, self.ehtag_dict):
                    decision = self._route_nsfw("NSFW flagged block with EhTag match")
                    decision.cache_key = cache_key
                    self._routing_cache[cache_key] = decision
                    return decision
            decision = self._route_nsfw("Block flagged as NSFW")
            decision.cache_key = cache_key
            self._routing_cache[cache_key] = decision
            return decision
        
        if self.nsfw_detector.detect(text):
            decision = self._route_nsfw("NSFW content detected in text")
            decision.cache_key = cache_key
            self._routing_cache[cache_key] = decision
            return decision
        
        if self.ehtag_dict and self.nsfw_detector.detect_from_ehtag(text, self.ehtag_dict):
            decision = self._route_nsfw("NSFW content detected via EhTag")
            decision.cache_key = cache_key
            self._routing_cache[cache_key] = decision
            return decision
        
        # 3. Check for SFX
        if block.type == BlockType.SFX:
            decision = self._route_sfx("Block type is SFX")
            decision.cache_key = cache_key
            self._routing_cache[cache_key] = decision
            return decision
        
        if self.sfx_detector.detect(text, block.bbox):
            decision = self._route_sfx("SFX detected from text/bbox analysis")
            decision.cache_key = cache_key
            self._routing_cache[cache_key] = decision
            return decision
        
        # 4. Language detection for adaptive routing
        lang_detection = self._detect_language(text)
        
        # 5. Route based on language and content
        primary_translator = self._get_translator_for_language(lang_detection.detected_lang)
        
        # 6. Check if ensemble routing should be used
        if self.enable_ensemble and lang_detection.confidence < self.ensemble_threshold:
            decision = self._create_ensemble_decision(
                primary_translator,
                lang_detection,
                f"Low confidence ({lang_detection.confidence:.2f}) - using ensemble",
            )
        else:
            decision = RoutingDecision(
                translator_type=primary_translator,
                reason=f"Language-aware routing: {lang_detection.detected_lang} ({lang_detection.confidence:.2f})",
                language_detection=lang_detection,
                confidence=lang_detection.confidence,
            )
        
        decision.cache_key = cache_key
        self._routing_cache[cache_key] = decision
        return decision
    
    def route_batch(self, blocks: List[Block]) -> Dict[str, RoutingDecision]:
        """
        Route multiple blocks at once with parallel-friendly design.
        
        Args:
            blocks: List of blocks to route
            
        Returns:
            Dictionary mapping block_uid to RoutingDecision
        """
        results = {}
        for block in blocks:
            results[block.block_uid] = self.route(block)
        return results
    
    def clear_cache(self) -> None:
        """Clear the routing decision cache."""
        self._routing_cache.clear()
    
    def get_cache_size(self) -> int:
        """Get the current size of the routing cache."""
        return len(self._routing_cache)
    
    def get_cached_decision(self, block: Block) -> Optional[RoutingDecision]:
        """
        Get a cached routing decision for a block if available.
        
        Args:
            block: The block to check
            
        Returns:
            Cached RoutingDecision or None if not cached
        """
        cache_key = self._generate_cache_key(block)
        return self._routing_cache.get(cache_key)
    
    def get_language_stats(self, blocks: List[Block]) -> Dict[str, int]:
        """
        Get language distribution statistics for a list of blocks.
        
        Args:
            blocks: List of blocks to analyze
            
        Returns:
            Dictionary mapping language codes to counts
        """
        stats: Dict[str, int] = {}
        for block in blocks:
            text = self._get_text_from_block(block)
            if text:
                lang, _ = self.language_detector.detect(text)
                stats[lang] = stats.get(lang, 0) + 1
        return stats
