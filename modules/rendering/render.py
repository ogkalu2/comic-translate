import numpy as np
from typing import Tuple, List, Optional

from PIL import Image, ImageFont, ImageDraw
from PySide6.QtGui import QFont, QTextDocument,\
      QTextCursor, QTextBlockFormat, QTextOption
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .hyphen_textwrap import wrap as hyphen_wrap
from ..utils.textblock import TextBlock
from ..detection.utils.bubbles import make_bubble_mask, bubble_interior_bounds
from ..utils.textblock import adjust_blks_size
from modules.detection.utils.geometry import shrink_bbox
from .adaptive_color import TextColorClassifier, determine_text_outline_colors
from .color_analysis import analyse_block_colors
from .settings import TextRenderingSettings, preferred_stroke_size as _preferred_stroke_size
from schemas.style_state import StyleState

_ADAPTIVE_CLASSIFIER = None


def _get_text_color_classifier():
    global _ADAPTIVE_CLASSIFIER
    if _ADAPTIVE_CLASSIFIER is None:
        try:
            _ADAPTIVE_CLASSIFIER = TextColorClassifier()
        except FileNotFoundError:
            _ADAPTIVE_CLASSIFIER = None
    return _ADAPTIVE_CLASSIFIER


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(v))):02X}" for v in rgb)
def array_to_pil(rgb_image: np.ndarray):
    # Image is already in RGB format, just convert to PIL
    pil_image = Image.fromarray(rgb_image)
    return pil_image

def pil_to_array(pil_image: Image):
    # Convert the PIL image to a numpy array (already in RGB)
    numpy_image = np.array(pil_image)
    return numpy_image

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

    font = ImageFont.truetype(font_pth, size=init_font_size)

    for blk in blk_list:
        x1, y1, width, height = blk.xywh
        tbbox_top_left = (x1, y1)

        translation = blk.translation
        if not translation or len(translation) == 1:
            continue

        if blk.min_font_size > 0:
            min_font_size = blk.min_font_size
        if blk.max_font_size > 0:
            init_font_size = blk.max_font_size
        if blk.font_color:
            colour = blk.font_color

        translation, font_size = pil_word_wrap(image, tbbox_top_left, font_pth, translation, width, height,
                                               align=blk.alignment, spacing=blk.line_spacing, init_font_size=init_font_size, min_font_size=min_font_size)
        font = font.font_variant(size=font_size)

        # Font Detection Workaround. Draws white color offset around text
        if outline:
            offsets = [(dx, dy) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) if dx != 0 or dy != 0]
            for dx, dy in offsets:
                draw.multiline_text((tbbox_top_left[0] + dx, tbbox_top_left[1] + dy), translation, font=font, fill="#FFF", align=blk.alignment, spacing=1)
        draw.multiline_text(tbbox_top_left, translation, colour, font, align=blk.alignment, spacing=1)
        
    image = pil_to_array(image)  # Already in RGB format
    return image

def get_best_render_area(blk_list: List[TextBlock], img, inpainted_img):
    # Using Speech Bubble detection to find best Text Render Area
    if inpainted_img is None or inpainted_img.size == 0:
        return blk_list
    
    for blk in blk_list:
        if blk.text_class == 'text_bubble' and blk.bubble_xyxy is not None:

            text_draw_bounds = shrink_bbox(blk.bubble_xyxy, shrink_percent=0.15)
            bdx1, bdy1, bdx2, bdy2 = text_draw_bounds
            blk.xyxy[:] = [bdx1, bdy1, bdx2, bdy2]
            adjust_blks_size(blk_list, img, -5, -5)

    return blk_list


def pyside_word_wrap(text: str, font_input: str, roi_width: int, roi_height: int,
                    line_spacing, outline_width, bold, italic, underline,
                    alignment, direction, init_font_size: int, min_font_size: int = 10) -> Tuple[str, int]:
    """Break long text to multiple lines, and find the largest point size
        so that all wrapped text fits within the box."""
    
    def prepare_font(font_size):
        effective_family = font_input.strip() if isinstance(font_input, str) and font_input.strip() else QApplication.font().family()
        font = QFont(effective_family, font_size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)

        return font
    
    def eval_metrics(txt: str, font_sz: float) -> Tuple[float, float]:
        """Quick helper function to calculate width/height of text using QTextDocument."""
        
        # Create a QTextDocument
        doc = QTextDocument()
        doc.setDefaultFont(prepare_font(font_sz))
        doc.setPlainText(txt)

        # Set text direction
        text_option = QTextOption()
        text_option.setTextDirection(direction)
        doc.setDefaultTextOption(text_option)
        
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
        if outline_width > 0:
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
                w, _ = eval_metrics(test, font_size)
                if w <= roi_width:
                    line = test
                    words.pop(0)
                else:
                    break
            lines.append(line)
        wrapped = "\n".join(lines)
        # measure wrapped block
        w, h = eval_metrics(wrapped, font_size)
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
    render_settings: TextRenderingSettings,
    alignment,
    background_image: Optional[np.ndarray] = None,
):

    classifier = _get_text_color_classifier()
    auto_font_color = getattr(render_settings, "auto_font_color", True)
    default_text_color = render_settings.color or "#000000"
    default_outline_color = render_settings.outline_color or "#FFFFFF"

    if auto_font_color and background_image is None:
        # Fall back to the base page image when the caller does not provide an
        # explicit sampling surface. This keeps adaptive colours working even
        # if the UI thread could not capture an augmented view of the page.
        try:
            text_ctrl = getattr(main_page, "text_ctrl", None)
            if text_ctrl is not None and hasattr(text_ctrl, "_get_current_base_image"):
                background_image = text_ctrl._get_current_base_image()
        except Exception:
            background_image = None

    font_family = render_settings.font_family
    line_spacing = float(render_settings.line_spacing)
    outline_width = float(render_settings.outline_width)
    bold = render_settings.bold
    italic = render_settings.italic
    underline = render_settings.underline
    direction = render_settings.direction
    init_font_size = render_settings.max_font_size
    min_font_size = render_settings.min_font_size

    for blk in blk_list:
        x1, y1, width, height = blk.xywh

        translation = blk.translation
        if not translation or len(translation) == 1:
            continue

        detected = False
        analysis = None
        if auto_font_color and background_image is not None:
            try:
                analysis = analyse_block_colors(background_image, blk)
            except Exception:
                analysis = None

        if analysis and analysis.fill_rgb is not None:
            style_state = getattr(blk, "style_state", None)
            if isinstance(style_state, StyleState):
                style_state = style_state.copy()
            else:
                style_state = StyleState()
            style_state.auto_color = False
            style_state.fill = tuple(int(v) for v in analysis.fill_rgb)
            blk.font_color = _rgb_to_hex(analysis.fill_rgb)
            if analysis.stroke_rgb is not None:
                blk.outline_color = _rgb_to_hex(analysis.stroke_rgb)
                style_state.stroke = tuple(int(v) for v in analysis.stroke_rgb)
                style_state.stroke_enabled = True
                style_state.stroke_size = _preferred_stroke_size(
                    render_settings, style_state, analysis.stroke_inferred
                )
                if analysis.stroke_inferred:
                    style_state.metadata["stroke_inferred"] = True
            else:
                style_state.stroke_enabled = False
                style_state.stroke = None
                style_state.stroke_size = None
            blk.style_state = style_state
            if analysis.stroke_inferred and analysis.stroke_rgb is not None:
                setattr(blk, "stroke_inferred", True)
            elif getattr(blk, 'outline_color', ''):
                pass
            elif render_settings.outline:
                blk.outline_color = default_outline_color
            else:
                blk.outline_color = ''
            detected = True

        if not detected:
            decision = None
            if auto_font_color and classifier and background_image is not None:
                try:
                    decision = determine_text_outline_colors(background_image, blk, classifier)
                except Exception:
                    decision = None

            if decision:
                blk.font_color = decision.text_hex
                blk.outline_color = decision.outline_hex
            else:
                blk.font_color = blk.font_color or default_text_color
                if not getattr(blk, 'outline_color', ''):
                    blk.outline_color = default_outline_color if render_settings.outline else ''

        translation, font_size = pyside_word_wrap(translation, font_family, width, height,
                                                 line_spacing, outline_width, bold, italic, underline,
                                                 alignment, direction, init_font_size, min_font_size)

        main_page.blk_rendered.emit(translation, font_size, blk)



        
