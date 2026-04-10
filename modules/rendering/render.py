from PIL.DdsImagePlugin import item
import numpy as np
from typing import Tuple, List

from PIL import Image, ImageFont, ImageDraw
from PySide6.QtGui import QFont, QTextDocument,\
      QTextCursor, QTextBlockFormat, QTextOption
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .hyphen_textwrap import wrap as hyphen_wrap
from modules.utils.textblock import TextBlock
from modules.utils.textblock import adjust_blks_size
from modules.detection.utils.geometry import shrink_bbox
from app.ui.canvas.text.vertical_layout import VerticalTextDocumentLayout
from modules.utils.language_utils import get_language_code

from dataclasses import dataclass

@dataclass
class TextRenderingSettings:
    alignment_id: int
    font_family: str
    min_font_size: int
    max_font_size: int
    color: str
    upper_case: bool
    outline: bool
    outline_color: str
    outline_width: str
    bold: bool
    italic: bool
    underline: bool
    line_spacing: str
    direction: Qt.LayoutDirection

def array_to_pil(rgb_image: np.ndarray):
    # Image is already in RGB format, just convert to PIL
    pil_image = Image.fromarray(rgb_image)
    return pil_image

def pil_to_array(pil_image: Image):
    # Convert the PIL image to a numpy array (already in RGB)
    numpy_image = np.array(pil_image)
    return numpy_image

def is_vertical_language_code(lang_code: str | None) -> bool:
    """Return True if the language code should use vertical layout.

    Currently treats Japanese and simplified/traditional Chinese as
    vertical-capable languages.
    """
    if not lang_code:
        return False
    code = lang_code.lower()
    return code in {"zh-cn", "zh-tw", "ja"}

def is_vertical_block(blk, lang_code: str | None) -> bool:
    """Return True if this block should be rendered vertically.

    A block is considered vertical when its direction flag is "vertical"
    and the target language code is one of the vertical-capable ones.
    """
    return getattr(blk, "direction", "") == "vertical" and is_vertical_language_code(lang_code)


def resolve_init_font_size(blk: TextBlock | None, default_max_font_size: int, min_font_size: int) -> int:
    """Pick a per-block initial font size for wrapping.

    We prefer the detector-estimated font size when available, but still
    clamp it to the user-configured min/max range so older projects and noisy
    detections remain stable.
    """
    candidate = default_max_font_size
    if blk is not None:
        candidate = getattr(blk, "font_size_px", 0) or getattr(blk, "max_font_size", 0) or candidate

    try:
        candidate = int(round(float(candidate)))
    except (TypeError, ValueError):
        candidate = int(round(float(default_max_font_size or min_font_size or 1)))

    lower_bound = max(1, int(round(min_font_size or 1)))
    upper_bound = max(lower_bound, int(round(default_max_font_size or lower_bound)))
    item.set_vertical(bool(property.vertical))
    item.set_layout_box_size(property.width, property.height)
    item.set_color(property.text_color)
    return max(lower_bound, min(candidate, upper_bound))


def pil_word_wrap(image: Image, tbbox_top_left: Tuple, font_pth: str, text: str, 
                  roi_width, roi_height, align: str, spacing, init_font_size: int, min_font_size: int = 10):
    """Break long text to multiple lines, and reduce point size
    until all text fits within a bounding box."""
    mutable_message = text
    font_size = init_font_size
    font = ImageFont.truetype(font_pth, font_size)

    def eval_metrics(txt, font):
        """Quick helper function to calculate width/height of text."""
        (left, top, right, bottom) = ImageDraw.Draw(image).multiline_textbbox(xy=tbbox_top_left, text=txt, font=font, align=align, spacing=spacing)
        return (right-left, bottom-top)

    while font_size > min_font_size:
        font = font.font_variant(size=font_size)
        width, height = eval_metrics(mutable_message, font)
        if height > roi_height:
            font_size -= 0.75  # Reduce pointsize
            mutable_message = text  # Restore original text
        elif width > roi_width:
            columns = len(mutable_message)
            while columns > 0:
                columns -= 1
                if columns == 0:
                    break
                mutable_message = '\n'.join(hyphen_wrap(text, columns, break_on_hyphens=False, break_long_words=False, hyphenate_broken_words=True)) 
                wrapped_width, _ = eval_metrics(mutable_message, font)
                if wrapped_width <= roi_width:
                    break
            if columns < 1:
                font_size -= 0.75  # Reduce pointsize
                mutable_message = text  # Restore original text
        else:
            break

    if font_size <= min_font_size:
        font_size = min_font_size
        mutable_message = text
        font = font.font_variant(size=font_size)

        # Wrap text to fit within as much as possible
        # Minimize cost function: (width - roi_width)^2 + (height - roi_height)^2
        # This is a brute force approach, but it works well enough
        min_cost = 1e9
        min_text = text
        for columns in range(1, len(text)):
            wrapped_text = '\n'.join(hyphen_wrap(text, columns, break_on_hyphens=False, break_long_words=False, hyphenate_broken_words=True))
            wrapped_width, wrapped_height = eval_metrics(wrapped_text, font)
            cost = (wrapped_width - roi_width)**2 + (wrapped_height - roi_height)**2
            if cost < min_cost:
                min_cost = cost
                min_text = wrapped_text

        mutable_message = min_text

    return mutable_message, font_size

def draw_text(image: np.ndarray, blk_list: List[TextBlock], font_pth: str, colour: str = "#000", init_font_size: int = 40, min_font_size=10, outline: bool = True):
    image = array_to_pil(image)
    draw = ImageDraw.Draw(image)

    for blk in blk_list:
        x1, y1, width, height = blk.xywh
        tbbox_top_left = (x1, y1)

        translation = blk.translation
        if not translation or len(translation) == 1:
            continue

        block_min_font_size = blk.min_font_size if blk.min_font_size > 0 else min_font_size
        block_init_font_size = resolve_init_font_size(blk, init_font_size, block_min_font_size)
        block_colour = blk.font_color if blk.font_color else colour

        translation, font_size = pil_word_wrap(image, tbbox_top_left, font_pth, translation, width, height,
                                               align=blk.alignment, spacing=blk.line_spacing, init_font_size=block_init_font_size, min_font_size=block_min_font_size)
        font = ImageFont.truetype(font_pth, size=font_size)

        # Font Detection Workaround. Draws white color offset around text
        if outline:
            offsets = [(dx, dy) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) if dx != 0 or dy != 0]
            for dx, dy in offsets:
                draw.multiline_text((tbbox_top_left[0] + dx, tbbox_top_left[1] + dy), translation, font=font, fill="#FFF", align=blk.alignment, spacing=1)
        draw.multiline_text(tbbox_top_left, translation, block_colour, font, align=blk.alignment, spacing=1)
        
    image = pil_to_array(image)  # Already in RGB format
    return image

def get_best_render_area(blk_list: List[TextBlock], img, inpainted_img=None):
    # Using Speech Bubble detection to find best Text Render Area
    
    # if inpainted_img is None or inpainted_img.size == 0:
    #     return blk_list
    
    for blk in blk_list:
        if blk.text_class == 'text_bubble' and blk.bubble_xyxy is not None:
            
            if blk.source_lang_direction == 'vertical':
                text_draw_bounds = shrink_bbox(blk.bubble_xyxy, shrink_percent=0.3)
                bdx1, bdy1, bdx2, bdy2 = text_draw_bounds
                blk.xyxy[:] = [bdx1, bdy1, bdx2, bdy2]

    if blk_list and blk_list[0].source_lang not in ['ko', 'zh']:
        adjust_blks_size(blk_list, img, -5, -5)

    return blk_list


def pyside_word_wrap(
    text: str, 
    font_input: str, 
    roi_width: int, 
    roi_height: int,
    line_spacing: float, 
    outline_width: float, 
    bold: bool, 
    italic: bool, 
    underline: bool, 
    alignment: Qt.AlignmentFlag,
    direction: Qt.LayoutDirection, 
    init_font_size: int, 
    min_font_size: int = 10, 
    vertical: bool = False,
    return_metrics: bool = False
) -> tuple:
    
    """Break long text to multiple lines, and find the largest point size
        so that all wrapped text fits within the box."""


    def prepare_font(font_size):
        effective_family = font_input.strip() if isinstance(font_input, str) and font_input.strip() else QApplication.font().family()
        font = QFont(effective_family)
        font.setPixelSize(max(1, int(round(font_size))))
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)

        return font
    

    def eval_metrics(
        txt: str,
        font_sz: float,
        vertical: bool = False,
        include_outline: bool = True
    ) -> Tuple[float, float]:
        """Quick helper function to calculate width/height of text using QTextDocument."""
        
        # Create a QTextDocument
        doc = QTextDocument()
        doc.setDefaultFont(prepare_font(font_sz))
        doc.setPlainText(txt)

        # Set text direction
        text_option = QTextOption()
        text_option.setTextDirection(direction)
        doc.setDefaultTextOption(text_option)

        if vertical:
            layout = VerticalTextDocumentLayout(
                document=doc,
                line_spacing=line_spacing
            )

            doc.setDocumentLayout(layout)
            layout.update_layout()
        else:
            # Apply line spacing
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.SelectionType.Document)
            block_format = QTextBlockFormat()
            spacing = line_spacing * 100
            block_format.setLineHeight(spacing, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            block_format.setAlignment(alignment)
            cursor.mergeBlockFormat(block_format)
        
        # Get the size of the document
        size = doc.size()
        width, height = size.width(), size.height()
        
        # Add outline width to the size
        if include_outline and outline_width > 0:
            width += 2 * outline_width
            height += 2 * outline_width
        
        return width, height

    def wrap_and_size(font_size):
        words = text.split()
        lines = []
        # build lines greedily
        while words:
            line = words.pop(0)
            # try extending the current line
            while words:
                test = f"{line} {words[0]}"
                w, h = eval_metrics(test, font_size, vertical)
                side, side_roi = (h, roi_height) if vertical else (w, roi_width)
                if side <= side_roi:
                    line = test
                    words.pop(0)
                else:
                    break
            lines.append(line)
        wrapped = "\n".join(lines)
        # measure wrapped block
        w, h = eval_metrics(wrapped, font_size, vertical)
        return wrapped, w, h
    
    # Initialize
    best_text, best_size = text, init_font_size
    found_fit = False

    lo, hi = min_font_size, init_font_size
    while lo <= hi:
        mid = (lo + hi) // 2
        wrapped, w, h = wrap_and_size(mid)
        if w <= roi_width and h <= roi_height:
            found_fit = True
            best_text, best_size = wrapped, mid
            lo = mid + 1
        else:
            hi = mid - 1

    # if nothing ever fit, force a wrap at the minimum size
    if not found_fit:
        best_text, w, h = wrap_and_size(min_font_size)
        best_size = min_font_size

    if return_metrics:
        # Match persisted state to the text item's actual geometry.
        rendered_w, rendered_h = eval_metrics(best_text, best_size, vertical, include_outline=False)
        return best_text, best_size, rendered_w, rendered_h

    return best_text, best_size

    # mutable_message = text
    # font_size = init_font_size
    # # font_size = max(roi_width, roi_height)

    # while font_size > min_font_size:
    #     width, height = eval_metrics(mutable_message, font_size)
    #     if height > roi_height:
    #         font_size -= 1  # Reduce pointsize
    #         mutable_message = text  # Restore original text
    #     elif width > roi_width:
    #         columns = len(mutable_message)
    #         while columns > 0:
    #             columns -= 1
    #             if columns == 0:
    #                 break
    #             mutable_message = '\n'.join(hyphen_wrap(text, columns, break_on_hyphens=False, break_long_words=False, hyphenate_broken_words=True)) 
    #             wrapped_width, _ = eval_metrics(mutable_message, font_size)
    #             if wrapped_width <= roi_width:
    #                 break
    #         if columns < 1:
    #             font_size -= 1  # Reduce pointsize
    #             mutable_message = text  # Restore original text
    #     else:
    #         break

    # if font_size <= min_font_size:
    #     font_size = min_font_size
    #     mutable_message = text

    #     # Wrap text to fit within as much as possible
    #     # Minimize cost function: (width - roi_width)^2 + (height - roi_height)^2
    #     min_cost = 1e9
    #     min_text = text
    #     for columns in range(1, len(text)):
    #         wrapped_text = '\n'.join(hyphen_wrap(text, columns, break_on_hyphens=False, break_long_words=False, hyphenate_broken_words=True))
    #         wrapped_width, wrapped_height = eval_metrics(wrapped_text, font_size)
    #         cost = (wrapped_width - roi_width)**2 + (wrapped_height - roi_height)**2
    #         if cost < min_cost:
    #             min_cost = cost
    #             min_text = wrapped_text

    #     mutable_message = min_text

    # return mutable_message, font_size

def manual_wrap(
    main_page, 
    blk_list: List[TextBlock], 
    image_path: str,
    font_family: str, 
    line_spacing: float, 
    outline_width: float, 
    bold: bool, 
    italic: bool, 
    underline: bool, 
    alignment: Qt.AlignmentFlag, 
    direction: Qt.LayoutDirection, 
    init_font_size: int = 40, 
    min_font_size: int = 10
):
    
    target_lang = main_page.lang_mapping.get(main_page.t_combo.currentText(), None)
    trg_lng_cd = get_language_code(target_lang)

    for blk in blk_list:
        x1, y1, width, height = blk.xywh

        translation = blk.translation
        if not translation or len(translation) == 1:
            continue

        vertical = is_vertical_block(blk, trg_lng_cd)
        block_min_font_size = blk.min_font_size if blk.min_font_size > 0 else min_font_size
        block_init_font_size = resolve_init_font_size(blk, init_font_size, block_min_font_size)

        translation, font_size = pyside_word_wrap(
            translation, 
            font_family, 
            width, 
            height,
            line_spacing, 
            outline_width, 
            bold, 
            italic, 
            underline,
            alignment, 
            direction, 
            block_init_font_size, 
            block_min_font_size,
            vertical
        )
        
        main_page.blk_rendered.emit(translation, font_size, blk, image_path)


def _pixels_to_qfont_points(size_px: float) -> float:
    """Convert image pixel sizing to QFont point sizing."""
    dpi = 96.0
    try:
        screen = QApplication.primaryScreen()
        if screen is not None:
            dpi = float(screen.logicalDotsPerInch() or dpi)
    except Exception:
        pass
    return float(size_px) * 72.0 / max(dpi, 1.0)


def resolve_init_font_size(
    blk: TextBlock | None,
    default_max_font_size: int,
    min_font_size: int,
    target: str = "qt",
) -> int:
    """Pick a per-block initial font size for wrapping.
    
    We prefer the detector-estimated font size when available, but still
    clamp it to the user-configured min/max range so older projects and noisy
    detections remain stable.

    `target` controls the units of the returned size:
    - `"qt"` returns a QFont point size for Qt text items.
    - `"pil"` returns a pixel size for PIL rendering.
    """
    geometric_cap = 0
    candidate = 0
    candidate_is_px = False
    
    if blk is not None:
        candidate = getattr(blk, "font_size_px", 0) or getattr(blk, "max_font_size", 0) or 0
        font_size_px = getattr(blk, "font_size_px", 0) or 0
        max_font_size_px = getattr(blk, "max_font_size", 0) or 0
        
        if font_size_px > 0:
            candidate = font_size_px
            candidate_is_px = True
        elif max_font_size_px > 0:
            candidate = max_font_size_px
            candidate_is_px = True
        try:
            geometric_cap = blk.max_chars and max(1.0, 200.0 / (blk.max_chars + 1))
            if geometric_cap > 0:
                candidate = min(candidate, geometric_cap)
                candidate_is_px = True
        except Exception:
            pass
        
        if candidate <= 0:
            candidate = geometric_cap
            candidate_is_px = geometric_cap > 0
    
    if candidate <= 0:
        candidate = default_max_font_size
        candidate_is_px = False

    if str(target).lower() != "pil" and candidate_is_px:
        candidate = _pixels_to_qfont_points(candidate)

    return int(round(max(min_font_size, candidate)))
        
