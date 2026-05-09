import dataclasses
import unicodedata
from enum import Enum, auto
from functools import cached_property, lru_cache

from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QTextCharFormat, QFont, QFontMetricsF, \
                           QTextLine, QPainterPath



class PlacementRule(Enum):
    UPRIGHT = auto()
    UPRIGHT_CENTERED = auto()
    ROTATE_EDGE_ALIGNED = auto()
    ROTATE_CENTERED = auto()

class GlyphPlacement:
    """Determines glyph placement rules for vertical text."""

    _FORCE_CENTERED_PUNCTUATION = {'。', '．', '，', '、', '·', '：', '；', '！', '？'}

    @classmethod
    @lru_cache(maxsize=1024)
    def get_rule(cls, char: str) -> tuple[PlacementRule, bool, bool]:
        """
        Determines the placement rule for a character.

        Returns:
            - PlacementRule: The primary layout rule.
            - is_open_bracket: True if it's an opening bracket/quote.
            - is_close_bracket: True if it's a closing bracket/quote.
        """
        cat = unicodedata.category(char)
        eaw = unicodedata.east_asian_width(char)

        is_open = cat == "Ps"
        is_close = cat == "Pe"

        # Rule 1: Punctuation and Symbols that need rotation.
        # Exclude alphanumeric characters (letters/numbers) from rotation
        # even if they are "Narrow" (Na) or "Halfwidth" (H), to support upright Latin/Cyrillic/Thai etc.
        if is_open or is_close or (eaw in ("Na", "H") and not char.isalnum()):
            # For brackets, alignment is based on open/close status.
            if is_open or is_close:
                return (PlacementRule.ROTATE_EDGE_ALIGNED, is_open, is_close)
            # For other half-width chars or connectors, center them when rotated.
            else:
                return (PlacementRule.ROTATE_CENTERED, False, False)

        # Rule 2: Punctuation that stays upright but must be centered.
        if char in cls._FORCE_CENTERED_PUNCTUATION:
            return (PlacementRule.UPRIGHT_CENTERED, False, False)

        # Rule 3: Default for CJK and other standard characters.
        return (PlacementRule.UPRIGHT, False, False)


@dataclasses.dataclass(frozen=True)
class FontKey:
    family: str
    point_size: float
    weight: int
    italic: bool


class FontMetricsCache:
    def __init__(self):
        self._fonts = {}
        self._metrics = {}
        self._char_widths = {}
        self._bounding_rects = {}
        self._pixel_bounds = {}

    def _get_font_key(self, font: QFont) -> FontKey:
        return FontKey(font.family(), font.pointSizeF(), font.weight(), font.italic())

    def get_metrics(self, font: QFont) -> QFontMetricsF:
        key = self._get_font_key(font)
        if key not in self._metrics:
            self._metrics[key] = QFontMetricsF(font)
        return self._metrics[key]

    def get_char_width(self, char: str, font: QFont) -> float:
        key = self._get_font_key(font)
        cache_key = (key, char)
        if cache_key not in self._char_widths:
            fm = self.get_metrics(font)
            self._char_widths[cache_key] = fm.horizontalAdvance(char)
        return self._char_widths[cache_key]

    def get_bounding_rects(self, char: str, font: QFont) -> tuple[QRectF, QRectF]:
        key = self._get_font_key(font)
        cache_key = (key, char)
        if cache_key not in self._bounding_rects:
            fm = self.get_metrics(font)
            self._bounding_rects[cache_key] = (fm.tightBoundingRect(char), fm.boundingRect(char))
        return self._bounding_rects[cache_key]

    def get_precise_bounds(self, line_text: str, line: QTextLine, font: QFont, stroke_width: float, space_shift: float = 0) -> list[float]:
        key = self._get_font_key(font)
        cache_key = (key, line_text, stroke_width, int(line.height()), int(line.naturalTextWidth()), space_shift)
        if cache_key in self._pixel_bounds:
            return self._pixel_bounds[cache_key]
        
        result = self._get_precise_bounds_painterpath(line_text, line, font, stroke_width, space_shift)

        self._pixel_bounds[cache_key] = result
        return result

    def _get_precise_bounds_painterpath(self, line_text: str, line: QTextLine, font: QFont, stroke_width: float, space_shift: float) -> list[float]:
        """High accuracy method using QPainterPath for text outline."""
        path = QPainterPath()
        
        # Get the baseline position
        baseline_y = line.ascent()
        current_x = -space_shift
        
        # Add each character to the path
        for char in line_text:
            path.addText(QPointF(current_x, baseline_y), font, char)
            current_x += QFontMetricsF(font).horizontalAdvance(char)
        
        # Get the bounding rectangle
        bounds = path.boundingRect()
        
        # Adjust for stroke width
        x = bounds.x() - stroke_width
        y = bounds.y() - stroke_width
        w = bounds.width() + stroke_width * 2
        h = bounds.height() + stroke_width * 2
        
        return [max(0, x), max(0, y), max(1, w), max(1, h)]


# Main Class to Interface with Font Metrics
class CharacterStyle:
    _metrics_cache = FontMetricsCache()

    def __init__(self, char_format: QTextCharFormat):
        self.char_format = char_format
        self.font = self.char_format.font()
        self.stroke_width = self.char_format.textOutline().widthF() / 2
        self.font_metrics = self._metrics_cache.get_metrics(self.font)

    @cached_property
    def standard_char_bounds(self) -> QRectF:
        _, br_hanzi = self._metrics_cache.get_bounding_rects('木', self.font)
        _, br_punct = self._metrics_cache.get_bounding_rects('啊', self.font)
        left = min(br_hanzi.left(), br_punct.left())
        right = max(br_hanzi.right(), br_punct.right())
        return QRectF(left, br_hanzi.top(), right - left, br_hanzi.height())

    @cached_property
    def tight_char_bounds(self) -> QRectF:
        tbr_hanzi, _ = self._metrics_cache.get_bounding_rects('木', self.font)
        tbr_punct, _ = self._metrics_cache.get_bounding_rects('啊', self.font)
        left = min(tbr_hanzi.left(), tbr_punct.left())
        right = max(tbr_hanzi.right(), tbr_punct.right())
        return QRectF(left, tbr_hanzi.top(), right - left, tbr_hanzi.height())

    @property
    def space_width(self) -> float:
        return self._metrics_cache.get_char_width(' ', self.font)

    def get_char_bounds(self, char: str) -> tuple[QRectF, QRectF]:
        return self._metrics_cache.get_bounding_rects(char, self.font)

    def get_precise_bounds(self, line_text: str, line: QTextLine, space_shift: float = 0) -> list[float]:
        return self._metrics_cache.get_precise_bounds(line_text, line, self.font, self.stroke_width, space_shift)
