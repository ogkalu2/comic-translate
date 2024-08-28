import cv2
import numpy as np
from typing import Tuple, List

from PIL import Image, ImageFont, ImageDraw
from PySide6.QtGui import QFontMetrics, QFont

from .hyphen_textwrap import wrap as hyphen_wrap
from ..utils.textblock import TextBlock
from ..detection import make_bubble_mask, bubble_interior_bounds
from ..utils.textblock import adjust_blks_size

def cv2_to_pil(cv2_image: np.ndarray):
    # Convert color channels from BGR to RGB
    rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    # Convert the NumPy array to a PIL Image
    pil_image = Image.fromarray(rgb_image)
    return pil_image

def pil_to_cv2(pil_image: Image):
    # Convert the PIL image to a numpy array
    numpy_image = np.array(pil_image)
    
    # PIL images are in RGB by default, OpenCV uses BGR, so convert the color space
    cv2_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
    
    return cv2_image

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
    image = cv2_to_pil(image)
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
        
    image = pil_to_cv2(image)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image

def get_best_render_area(blk_list: List[TextBlock], img, inpainted_img):
    # Using Speech Bubble detection to find best Text Render Area
    for blk in blk_list:
        if blk.text_class == 'text_bubble':
            bx1, by1, bx2, by2 = blk.bubble_xyxy
            bubble_clean_frame = inpainted_img[by1:by2, bx1:bx2]
            bubble_mask = make_bubble_mask(bubble_clean_frame)
            text_draw_bounds = bubble_interior_bounds(bubble_mask)

            bdx1, bdy1, bdx2, bdy2 = text_draw_bounds

            bdx1 += bx1
            bdy1 += by1

            bdx2 += bx1
            bdy2 += by1

            if blk.source_lang == 'ja':
                blk.xyxy[:] = [bdx1, bdy1, bdx2, bdy2]
                adjust_blks_size(blk_list, img, -5, -5)
            else:
                tx1, ty1, tx2, ty2  = blk.xyxy

                nx1 = max(bdx1, tx1)
                nx2 = min(bdx2, tx2)
                
                blk.xyxy[:] = [nx1, ty1, nx2, ty2]

    return blk_list


def pyside_word_wrap(text: str, font_input: str, roi_width: int, roi_height: int,
                    line_spacing, outline_width, bold, italic, underline,
                    init_font_size: int, min_font_size: int = 10) -> Tuple[str, int]:
    """Break long text to multiple lines, and reduce point size
    until all text fits within a bounding box."""
    
    def get_text_height(text, font, line_spacing):
        font_metrics = QFontMetrics(font)
        lines = text.split('\n')
        single_line_height = font_metrics.height()
        single_line_height += outline_width * 2
        total_height = single_line_height * len(lines)
        extra_spacing = single_line_height * (line_spacing - 1) * (len(lines) - 1)
        
        return total_height + extra_spacing
    
    def get_text_width(txt, font):
        fm = QFontMetrics(font)
        max_width = max(fm.horizontalAdvance(line) for line in txt.split('\n'))

        return max_width
    
    def prepare_font(font_size):
        font = QFont(font_input, font_size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setUnderline(underline)

        return font
    
    def eval_metrics(txt: str, font_sz) -> Tuple[float, float]:
        """Quick helper function to calculate width/height of text."""

        font = prepare_font(font_sz)
        width = get_text_width(txt, font)
        height = get_text_height(txt, font, line_spacing)

        return width, height

    mutable_message = text
    font_size = init_font_size
    
    while font_size > min_font_size:
        width, height = eval_metrics(mutable_message, font_size)
        if height > roi_height:
            font_size -= 1  # Reduce pointsize
            mutable_message = text  # Restore original text
        elif width > roi_width:
            columns = len(mutable_message)
            while columns > 0:
                columns -= 1
                if columns == 0:
                    break
                mutable_message = '\n'.join(hyphen_wrap(text, columns, break_on_hyphens=False, break_long_words=False, hyphenate_broken_words=True)) 
                wrapped_width, _ = eval_metrics(mutable_message, font_size)
                if wrapped_width <= roi_width:
                    break
            if columns < 1:
                font_size -= 1  # Reduce pointsize
                mutable_message = text  # Restore original text
        else:
            break

    if font_size <= min_font_size:
        font_size = min_font_size
        mutable_message = text

        # Wrap text to fit within as much as possible
        # Minimize cost function: (width - roi_width)^2 + (height - roi_height)^2
        min_cost = 1e9
        min_text = text
        for columns in range(1, len(text)):
            wrapped_text = '\n'.join(hyphen_wrap(text, columns, break_on_hyphens=False, break_long_words=False, hyphenate_broken_words=True))
            wrapped_width, wrapped_height = eval_metrics(wrapped_text, font_size)
            cost = (wrapped_width - roi_width)**2 + (wrapped_height - roi_height)**2
            if cost < min_cost:
                min_cost = cost
                min_text = wrapped_text

        mutable_message = min_text

    return mutable_message, font_size

def manual_wrap(main_page, blk_list: List[TextBlock], font_family: str, line_spacing, 
                outline_width, bold, italic, underline, init_font_size: int = 40, 
         min_font_size: int = 10):
    
    for blk in blk_list:
        x1, y1, width, height = blk.xywh

        translation = blk.translation
        if not translation or len(translation) == 1:
            continue

        translation, font_size = pyside_word_wrap(translation, font_family, width, height,
                                                 line_spacing, outline_width, bold, italic, underline,
                                                 init_font_size, min_font_size)
 
        main_page.blk_rendered.emit(translation, font_size, blk)



        
