import cv2
import numpy as np
import os
import base64

from .textblock import TextBlock, sort_textblock_rectangles
from ..detection.utils.general import does_rectangle_fit, is_mostly_contained, \
                                      get_inpaint_bboxes
from ..inpainting.lama import LaMa
from ..inpainting.mi_gan import MIGAN
from ..inpainting.aot import AOT
from ..inpainting.schema import Config
from app.ui.messages import Messages
from PySide6.QtCore import Qt


language_codes = {
    "Korean": "ko",
    "Japanese": "ja",
    "Chinese": "zh",
    "Simplified Chinese": "zh-CN",
    "Traditional Chinese": "zh-TW",
    "English": "en",
    "Russian": "ru",
    "French": "fr",
    "German": "de",
    "Dutch": "nl",
    "Spanish": "es",
    "Italian": "it",
    "Turkish": "tr",
    "Polish": "pl",
    "Portuguese": "pt",
    "Brazilian Portuguese": "pt-br",
    "Thai": "th",
    "Vietnamese": "vi",
    "Indonesian": "id",
    "Hungarian": "hu",
    "Finnish": "fi",
    "Arabic": "ar",
    }

def get_layout_direction(language: str) -> Qt.LayoutDirection:
    return Qt.LayoutDirection.RightToLeft if language == 'Arabic' else Qt.LayoutDirection.LeftToRight


inpaint_map = {
    "LaMa": LaMa,
    "MI-GAN": MIGAN,
    "AOT": AOT,
}

def get_config(settings_page):
    strategy_settings = settings_page.get_hd_strategy_settings()
    if strategy_settings['strategy'] == settings_page.ui.tr("Resize"):
        config = Config(hd_strategy="Resize", hd_strategy_resize_limit = strategy_settings['resize_limit'])
    elif strategy_settings['strategy'] == settings_page.ui.tr("Crop"):
        config = Config(hd_strategy="Crop", hd_strategy_crop_margin = strategy_settings['crop_margin'],
                        hd_strategy_crop_trigger_size = strategy_settings['crop_trigger_size'])
    else:
        config = Config(hd_strategy="Original")

    return config

def get_language_code(lng: str):
    lng_cd = language_codes.get(lng, None)
    return lng_cd

def rgba2hex(rgba_list):
    r,g,b,a = [int(num) for num in rgba_list]
    return "#{:02x}{:02x}{:02x}{:02x}".format(r, g, b, a)

def encode_image_array(img_array: np.ndarray):
    _, img_bytes = cv2.imencode('.png', img_array)
    return base64.b64encode(img_bytes).decode('utf-8')

def lists_to_blk_list(blk_list: list[TextBlock], texts_bboxes: list, texts_string: list):  
    group = list(zip(texts_bboxes, texts_string))  

    for blk in blk_list:
        blk_entries = []
        
        for line, text in group:
            if blk.bubble_xyxy is not None:
                if does_rectangle_fit(blk.bubble_xyxy, line):
                    blk_entries.append((line, text))  
                elif is_mostly_contained(blk.bubble_xyxy, line, 0.5):
                    blk_entries.append((line, text)) 

            elif does_rectangle_fit(blk.xyxy, line):
                blk_entries.append((line, text)) 
            elif is_mostly_contained(blk.xyxy, line, 0.5):
                blk_entries.append((line, text)) 

        # Sort and join text entries
        sorted_entries = sort_textblock_rectangles(blk_entries, blk.source_lang_direction)
        if blk.source_lang in ['ja', 'zh']:
            blk.text = ''.join(text for bbox, text in sorted_entries)
        else:
            blk.text = ' '.join(text for bbox, text in sorted_entries)

    return blk_list

def generate_mask(img: np.ndarray, blk_list: list[TextBlock], default_padding: int = 5) -> np.ndarray:
    """
    Generate a mask by fitting a merged shape around each block's inpaint bboxes,
    then dilating that shape according to padding logic.
    """
    h, w, _ = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)
    LONG_EDGE = 2048

    for blk in blk_list:
        bboxes = get_inpaint_bboxes(blk.xyxy, img)
        blk.inpaint_bboxes = bboxes
        if bboxes is None or len(bboxes) == 0:
            continue

        # 1) Compute tight per-block ROI
        xs = [x for x1, _, x2, _ in bboxes for x in (x1, x2)]
        ys = [y for _, y1, _, y2 in bboxes for y in (y1, y2)]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        roi_w, roi_h = max_x - min_x + 1, max_y - min_y + 1

        # 2) Down-sample factor to limit mask size
        ds = max(1.0, max(roi_w, roi_h) / LONG_EDGE)
        mw, mh = int(roi_w / ds) + 2, int(roi_h / ds) + 2

        # 3) Paint bboxes into small mask
        small = np.zeros((mh, mw), dtype=np.uint8)
        for x1, y1, x2, y2 in bboxes:
            x1i = int((x1 - min_x) / ds)
            y1i = int((y1 - min_y) / ds)
            x2i = int((x2 - min_x) / ds)
            y2i = int((y2 - min_y) / ds)
            cv2.rectangle(small, (x1i, y1i), (x2i, y2i), 255, -1)

        # 4) Close small mask to bridge gaps
        KSIZE = 15
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (KSIZE, KSIZE))
        closed = cv2.morphologyEx(small, cv2.MORPH_CLOSE, kernel)

        # 5) Extract all contours
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        # 6) Merge contours: collect valid polygons in full image coords
        polys = []
        for cnt in contours:
            pts = cnt.squeeze(1)
            if pts.ndim != 2 or pts.shape[0] < 3:
                continue
            pts_f = (pts.astype(np.float32) * ds)
            pts_f[:, 0] += min_x
            pts_f[:, 1] += min_y
            polys.append(pts_f.astype(np.int32))
        if not polys:
            continue

        # 7) Create per-block mask and fill all polygons
        block_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(block_mask, polys, 255)

        # 8) Determine dilation kernel size
        kernel_size = default_padding
        src_lang = getattr(blk, 'source_lang', None)
        if src_lang and src_lang not in ['ja', 'ko']:
            kernel_size = 3
        # Adjust for text bubbles: only consider contours wholly inside the bubble
        if getattr(blk, 'text_class', None) == 'text_bubble' and getattr(blk, 'bubble_xyxy', None) is not None:
            bx1, by1, bx2, by2 = blk.bubble_xyxy
            # filter polygons fully within bubble bounds
            valid = [p for p in polys 
                     if (p[:,0] >= bx1).all() and (p[:,0] <= bx2).all() 
                     and (p[:,1] >= by1).all() and (p[:,1] <= by2).all()]
            if valid:
                # compute distances for each polygon and get overall minimum
                dists = []
                for p in valid:
                    left   = p[:,0].min() - bx1
                    right  = bx2 - p[:,0].max()
                    top    = p[:,1].min() - by1
                    bottom = by2 - p[:,1].max()
                    dists.extend([left, right, top, bottom])
                min_dist = min(dists)
                if kernel_size >= min_dist:
                    kernel_size = max(1, int(min_dist * 0.8))

        # 9) Dilate the block mask
        dil_kernel = np.ones((kernel_size, kernel_size), np.uint8)
        dilated = cv2.dilate(block_mask, dil_kernel, iterations=4)

        # 10) Combine with global mask
        mask = cv2.bitwise_or(mask, dilated)

    return mask

def validate_ocr(main_page, source_lang):
    settings_page = main_page.settings_page
    tr = settings_page.ui.tr
    settings = settings_page.get_all_settings()
    credentials = settings.get('credentials', {})
    source_lang_en = main_page.lang_mapping.get(source_lang, source_lang)
    ocr_tool = settings['tools']['ocr']
    
    # Validate OCR API keys
    if (ocr_tool == tr("Microsoft OCR") and 
        not credentials.get(tr("Microsoft Azure"), {}).get("api_key_ocr")):
        Messages.show_api_key_ocr_error(main_page)
        return False
    
    if (ocr_tool == tr("Google Cloud Vision") and 
        not credentials.get(tr("Google Cloud"), {}).get("api_key")):
        Messages.show_api_key_ocr_error(main_page)
        return False
        
    # Validate Microsoft Endpoint
    if (ocr_tool == tr('Microsoft OCR') and 
        not credentials.get(tr('Microsoft Azure'), {}).get('endpoint')):
        Messages.show_endpoint_url_error(main_page)
        return False
        
    # Validate GPT OCR
    if (ocr_tool == tr('GPT-4.1-mini') and 
        not credentials.get(tr('Open AI GPT'), {}).get('api_key')):
        Messages.show_api_key_ocr_error(main_page)
        return False
    
    if source_lang_en == "Russian":
        if (ocr_tool == tr('Default') and 
            not credentials.get(tr('Open AI GPT'), {}).get('api_key')):
            Messages.show_api_key_ocr_gpt4v_error(main_page)
            return False
    
    return True

def validate_translator(main_page, source_lang, target_lang):
    settings_page = main_page.settings_page
    tr = settings_page.ui.tr
    settings = settings_page.get_all_settings()
    credentials = settings.get('credentials', {})
    translator_tool = settings['tools']['translator']
    
    # Validate translator API keys
    if (translator_tool == tr("DeepL") and 
        not credentials.get(tr("DeepL"), {}).get("api_key")):
        Messages.show_api_key_translator_error(main_page)
        return False
    
    if (translator_tool == tr("Microsoft Translator") and 
        not credentials.get(tr("Microsoft Azure"), {}).get("api_key_translator")):
        Messages.show_api_key_translator_error(main_page)
        return False
        
    if (translator_tool == tr("Yandex") and 
        not credentials.get(tr("Yandex"), {}).get("api_key")):
        Messages.show_api_key_translator_error(main_page)
        return False
    
    if ('GPT' in translator_tool and 
        not credentials.get(tr('Open AI GPT'), {}).get('api_key')):
        Messages.show_api_key_translator_error(main_page)
        return False
        
    if ('Gemini' in translator_tool and 
        not credentials.get(tr('Google Gemini'), {}).get('api_key')):
        Messages.show_api_key_translator_error(main_page)
        return False
        
    if ('Claude' in translator_tool and 
        not credentials.get(tr('Anthropic Claude'), {}).get('api_key')):
        Messages.show_api_key_translator_error(main_page)
        return False
    
    # Check service-specific incompatibilities
    if translator_tool == tr('DeepL'):
        if target_lang == main_page.tr('Traditional Chinese'):
            Messages.show_deepl_ch_error(main_page)
            return False
        if target_lang == main_page.tr('Thai'):
            Messages.show_deepl_th_error(main_page)
            return False
        if target_lang == main_page.tr('Vietnamese'):
            Messages.show_deepl_vi_error(main_page)
            return False
            
    if  translator_tool == tr('Google Translate'):
            if (source_lang == main_page.tr('Brazilian Portuguese') or 
                target_lang == main_page.tr('Brazilian Portuguese')):
                Messages.show_googlet_ptbr_error(main_page)
                return False
    
    return True

def font_selected(main_page):
    if not main_page.render_settings().font_family:
        Messages.select_font_error(main_page)
        return False
    return True

def validate_settings(main_page, source_lang, target_lang):
    if not validate_ocr(main_page, source_lang):
        return False
    if not validate_translator(main_page, source_lang, target_lang):
        return False
    if not font_selected(main_page):
        return False
    
    return True

def is_directory_empty(directory):
    # Walk through the directory
    for root, dirs, files in os.walk(directory):
        # If any file is found, the directory is not empty
        if files:
            return False
    # If no files are found, check if there are any subdirectories
    for root, dirs, files in os.walk(directory):
        if dirs:
            # Recursively check subdirectories
            for dir in dirs:
                if not is_directory_empty(os.path.join(root, dir)):
                    return False
    return True
