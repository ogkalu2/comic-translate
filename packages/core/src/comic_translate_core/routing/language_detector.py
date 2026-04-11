"""
Language detection for comic blocks using multiple detection strategies.
"""

import re
from typing import Dict, List, Optional, Tuple


class LanguageDetector:
    """
    Detects language of text using character range analysis and pattern matching.
    
    Supports:
    - Japanese (Hiragana, Katakana, Kanji)
    - Chinese (Simplified/Traditional)
    - Korean (Hangul)
    - English/Latin scripts
    - Thai
    - Arabic
    """
    
    # Unicode ranges for language detection
    UNICODE_RANGES = {
        "ja": [
            (0x3040, 0x309F),  # Hiragana
            (0x30A0, 0x30FF),  # Katakana
            (0x4E00, 0x9FFF),  # CJK Unified Ideographs (shared with Chinese)
            (0x3400, 0x4DBF),  # CJK Extension A
        ],
        "zh": [
            (0x4E00, 0x9FFF),  # CJK Unified Ideographs
            (0x3400, 0x4DBF),  # CJK Extension A
            (0x2F00, 0x2FDF),  # Kangxi Radicals
            (0x2E80, 0x2EFF),  # CJK Radicals Supplement
        ],
        "ko": [
            (0xAC00, 0xD7AF),  # Hangul Syllables
            (0x1100, 0x11FF),  # Hangul Jamo
            (0x3130, 0x318F),  # Hangul Compatibility Jamo
        ],
        "th": [
            (0x0E00, 0x0E7F),  # Thai
        ],
        "ar": [
            (0x0600, 0x06FF),  # Arabic
            (0x0750, 0x077F),  # Arabic Supplement
        ],
    }
    
    # Common Japanese particles and markers for disambiguation
    JA_MARKERS = {"の", "は", "を", "に", "が", "で", "と", "も", "から", "まで", "です", "ます"}
    
    # Common Chinese markers
    ZH_MARKERS = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一"}
    
    def __init__(self, default_lang: str = "en"):
        """
        Initialize the language detector.
        
        Args:
            default_lang: Default language when detection is uncertain
        """
        self.default_lang = default_lang
    
    def _count_chars_in_range(self, text: str, ranges: List[Tuple[int, int]]) -> int:
        """Count characters that fall within Unicode ranges."""
        count = 0
        for char in text:
            code = ord(char)
            for start, end in ranges:
                if start <= code <= end:
                    count += 1
                    break
        return count
    
    def _has_markers(self, text: str, markers: set) -> int:
        """Count occurrences of language-specific markers."""
        count = 0
        for marker in markers:
            count += text.count(marker)
        return count
    
    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect the language of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if not text or not text.strip():
            return self.default_lang, 0.0
        
        text = text.strip()
        total_chars = len(text)
        
        if total_chars == 0:
            return self.default_lang, 0.0
        
        # Count characters in each language's Unicode range
        scores: Dict[str, float] = {}
        
        for lang, ranges in self.UNICODE_RANGES.items():
            char_count = self._count_chars_in_range(text, ranges)
            if char_count > 0:
                scores[lang] = char_count / total_chars
        
        # Check for Latin/English (default if no CJK detected)
        latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
        if latin_count > 0:
            scores["en"] = latin_count / total_chars
        
        if not scores:
            return self.default_lang, 0.5
        
        # Disambiguate Japanese vs Chinese using markers
        if "ja" in scores and "zh" in scores:
            ja_marker_count = self._has_markers(text, self.JA_MARKERS)
            zh_marker_count = self._has_markers(text, self.ZH_MARKERS)
            
            # Check for Hiragana/Katakana (strong Japanese indicator)
            hira_kata = self._count_chars_in_range(text, [
                (0x3040, 0x309F),  # Hiragana
                (0x30A0, 0x30FF),  # Katakana
            ])
            
            # If no Hiragana/Katakana, likely Chinese
            if hira_kata == 0:
                scores["zh"] += 0.4
                scores.pop("ja", None)
            else:
                # Has Hiragana/Katakana, definitely Japanese
                scores["ja"] += 0.5
                scores.pop("zh", None)
            
            # Additional marker-based boost
            if ja_marker_count > zh_marker_count:
                scores["ja"] = scores.get("ja", 0) + 0.2
            elif zh_marker_count > ja_marker_count:
                scores["zh"] = scores.get("zh", 0) + 0.2
        
        # Find the language with highest score
        best_lang = max(scores, key=lambda k: scores[k])
        confidence = min(scores[best_lang], 1.0)
        
        return best_lang, confidence
    
    def detect_with_alternatives(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """
        Detect language with alternative possibilities.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (primary_language, confidence, alternative_languages)
        """
        if not text or not text.strip():
            return self.default_lang, 0.0, {}
        
        text = text.strip()
        total_chars = len(text)
        
        if total_chars == 0:
            return self.default_lang, 0.0, {}
        
        # Count characters in each language's Unicode range
        scores: Dict[str, float] = {}
        
        for lang, ranges in self.UNICODE_RANGES.items():
            char_count = self._count_chars_in_range(text, ranges)
            if char_count > 0:
                scores[lang] = char_count / total_chars
        
        # Check for Latin/English
        latin_count = sum(1 for c in text if c.isascii() and c.isalpha())
        if latin_count > 0:
            scores["en"] = latin_count / total_chars
        
        if not scores:
            return self.default_lang, 0.5, {}
        
        # Disambiguate Japanese vs Chinese
        if "ja" in scores and "zh" in scores:
            ja_marker_count = self._has_markers(text, self.JA_MARKERS)
            zh_marker_count = self._has_markers(text, self.ZH_MARKERS)
            
            # Check for Hiragana/Katakana (strong Japanese indicator)
            hira_kata = self._count_chars_in_range(text, [
                (0x3040, 0x309F),  # Hiragana
                (0x30A0, 0x30FF),  # Katakana
            ])
            
            # If no Hiragana/Katakana, likely Chinese
            if hira_kata == 0:
                scores["zh"] += 0.4
                scores.pop("ja", None)
            else:
                # Has Hiragana/Katakana, definitely Japanese
                scores["ja"] += 0.5
                scores.pop("zh", None)
            
            # Additional marker-based boost
            if ja_marker_count > zh_marker_count:
                scores["ja"] = scores.get("ja", 0) + 0.2
            elif zh_marker_count > ja_marker_count:
                scores["zh"] = scores.get("zh", 0) + 0.2
        
        # Normalize scores
        total_score = sum(scores.values())
        if total_score > 0:
            scores = {k: v / total_score for k, v in scores.items()}
        
        # Sort by score
        sorted_langs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_lang = sorted_langs[0][0]
        primary_confidence = sorted_langs[0][1]
        
        alternatives = {lang: conf for lang, conf in sorted_langs[1:]}
        
        return primary_lang, primary_confidence, alternatives
    
    def is_mixed_language(self, text: str, threshold: float = 0.3) -> bool:
        """
        Check if text contains multiple languages.
        
        Args:
            text: Text to analyze
            threshold: Minimum ratio for secondary language detection
            
        Returns:
            True if text contains significant mixed languages
        """
        _, _, alternatives = self.detect_with_alternatives(text)
        
        for confidence in alternatives.values():
            if confidence >= threshold:
                return True
        
        return False
