"""
NSFW content detection for comic blocks.
"""

from typing import Dict, List, Optional


class NSFWDetector:
    """
    Detects NSFW content in text using keyword matching and EhTag dictionary.
    
    This is a simple keyword-based detector that can be enhanced later
    with more sophisticated ML-based approaches.
    """
    
    # Default NSFW keywords (Japanese/English)
    DEFAULT_NSFW_KEYWORDS: List[str] = [
        # Japanese keywords
        "エロ", "hentai", "R18", "成人向け", "18禁",
        "おっぱい", "乳首", "セックス", "犯す", "凌辱",
        # English keywords
        "nsfw", "hentai", "explicit", "mature", "adult",
        "nude", "naked", "sex", "porn", "xxx",
    ]
    
    def __init__(self, custom_keywords: Optional[List[str]] = None):
        """
        Initialize the NSFW detector.
        
        Args:
            custom_keywords: Optional list of additional keywords to check
        """
        self.keywords = set(self.DEFAULT_NSFW_KEYWORDS)
        if custom_keywords:
            self.keywords.update(custom_keywords)
    
    def detect(self, text: str) -> bool:
        """
        Detect NSFW content in text using keyword matching.
        
        Args:
            text: The text to check for NSFW content
            
        Returns:
            True if NSFW content is detected, False otherwise
        """
        if not text:
            return False
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.keywords)
    
    def detect_from_ehtag(self, text: str, ehtag_dict: Dict[str, str]) -> bool:
        """
        Detect NSFW content using EhTag dictionary lookup.
        
        EhTag is a community-maintained tag dictionary for manga/doujinshi.
        This method checks if any tags in the text match NSFW categories
        in the provided dictionary.
        
        Args:
            text: The text to check
            ehtag_dict: Dictionary mapping tags to categories
                       (e.g., {"sex": "nsfw", "nudity": "nsfw"})
            
        Returns:
            True if NSFW content is detected via EhTag, False otherwise
        """
        if not text or not ehtag_dict:
            return False
        
        text_lower = text.lower()
        
        # Check if any EhTag entry matches and is NSFW
        for tag, category in ehtag_dict.items():
            if tag.lower() in text_lower and category.lower() == "nsfw":
                return True
        
        return False
