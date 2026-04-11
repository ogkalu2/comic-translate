"""
SFX (Sound Effects) detection for comic blocks.
"""

from typing import List, Optional


class SFXDetector:
    """
    Detects SFX (Sound Effects) in comic blocks based on text properties and bbox.
    
    Heuristics:
    - Large bold deformed text → SFX
    - Small corner text + URL → credit
    - Short text with specific patterns → SFX
    """
    
    # Common SFX patterns (Japanese/English)
    SFX_PATTERNS: List[str] = [
        # Japanese SFX patterns
        "ドン", "バン", "ガシャ", "パチ", "ズドン", "ドカ", "ゴゴゴ",
        "バキ", "ズバ", "ドクン", "パァ", "シャー", "ザー", "ポツポツ",
        # English SFX patterns
        "boom", "crash", "bang", "pow", "zap", "whoosh", "splash",
        "thud", "slam", "wham", "bam", "pop", "snap", "crack",
    ]
    
    # URL patterns for credit detection
    URL_PATTERNS: List[str] = [
        "http://", "https://", "www.", ".com", ".net", ".org",
        ".jp", ".co.jp", ".io", ".dev",
    ]
    
    def __init__(
        self,
        custom_sfx_patterns: Optional[List[str]] = None,
        min_bbox_area: int = 5000,
        max_text_length: int = 10,
    ):
        """
        Initialize the SFX detector.
        
        Args:
            custom_sfx_patterns: Optional additional SFX patterns
            min_bbox_area: Minimum bbox area to consider as SFX (default: 5000)
            max_text_length: Maximum text length for SFX detection (default: 10)
        """
        self.sfx_patterns = set(self.SFX_PATTERNS)
        if custom_sfx_patterns:
            self.sfx_patterns.update(custom_sfx_patterns)
        
        self.min_bbox_area = min_bbox_area
        self.max_text_length = max_text_length
    
    def _calculate_bbox_area(self, bbox: List[int]) -> int:
        """
        Calculate the area of a bounding box.
        
        Args:
            bbox: Bounding box as [x1, y1, x2, y2]
            
        Returns:
            Area of the bounding box
        """
        if len(bbox) != 4:
            return 0
        x1, y1, x2, y2 = bbox
        return abs(x2 - x1) * abs(y2 - y1)
    
    def _is_corner_position(self, bbox: List[int], page_width: int = 1000, page_height: int = 1500) -> bool:
        """
        Check if the bbox is in a corner position (typical for credits).
        
        Args:
            bbox: Bounding box as [x1, y1, x2, y2]
            page_width: Page width for normalization
            page_height: Page height for normalization
            
        Returns:
            True if bbox is in a corner position
        """
        if len(bbox) != 4:
            return False
        
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Check if in corners (within 20% of edges)
        in_left = center_x < page_width * 0.2
        in_right = center_x > page_width * 0.8
        in_top = center_y < page_height * 0.2
        in_bottom = center_y > page_height * 0.8
        
        return (in_left or in_right) and (in_top or in_bottom)
    
    def _contains_url(self, text: str) -> bool:
        """
        Check if text contains URL patterns.
        
        Args:
            text: Text to check
            
        Returns:
            True if URL pattern is found
        """
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in self.URL_PATTERNS)
    
    def _matches_sfx_pattern(self, text: str) -> bool:
        """
        Check if text matches known SFX patterns.
        
        Args:
            text: Text to check
            
        Returns:
            True if SFX pattern is found
        """
        text_lower = text.lower()
        return any(pattern.lower() in text_lower for pattern in self.sfx_patterns)
    
    def detect(self, text: str, bbox: List[int]) -> bool:
        """
        Detect if a block is SFX based on text and bbox properties.
        
        Heuristics:
        1. Short text (≤ max_text_length) with large bbox area → likely SFX
        2. Text matches known SFX patterns → SFX
        3. Small corner text with URL → credit (not SFX)
        
        Args:
            text: The text content of the block
            bbox: Bounding box as [x1, y1, x2, y2]
            
        Returns:
            True if block is detected as SFX, False otherwise
        """
        if not text or not bbox:
            return False
        
        # Check for URL (credit indicator) - if found, not SFX
        if self._contains_url(text):
            return False
        
        # Check for SFX pattern match
        if self._matches_sfx_pattern(text):
            return True
        
        # Check text length and bbox area
        text_length = len(text.strip())
        bbox_area = self._calculate_bbox_area(bbox)
        
        # Short text with large area → likely SFX
        if text_length <= self.max_text_length and bbox_area >= self.min_bbox_area:
            return True
        
        # Very short text (1-3 chars) is often SFX, but only if bbox is large enough
        if text_length <= 3 and bbox_area >= self.min_bbox_area:
            return True
        
        return False
    
    def is_credit(self, text: str, bbox: List[int]) -> bool:
        """
        Detect if a block is a credit (URL, corner position, small text).
        
        Args:
            text: The text content of the block
            bbox: Bounding box as [x1, y1, x2, y2]
            
        Returns:
            True if block is detected as credit, False otherwise
        """
        if not text:
            return False
        
        # URL in text → credit
        if self._contains_url(text):
            return True
        
        # Small corner text → credit
        if self._is_corner_position(bbox) and len(text.strip()) < 50:
            return True
        
        return False
