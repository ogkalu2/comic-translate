import cv2
import numpy as np
import os
import base64
from .textblock import TextBlock, sort_textblock_rectangles
from ..detection import does_rectangle_fit, do_rectangles_overlap, is_mostly_contained
from typing import List
from ..inpainting.lama import LaMa
from ..inpainting.schema import Config
from app.ui.messages import Messages


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
    }


inpaint_map = {
    "LaMa": LaMa
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

def lists_to_blk_list(blk_list: List[TextBlock], texts_bboxes: List, texts_string: List):
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

def generate_mask(img: np.ndarray, blk_list: List[TextBlock], default_padding: int = 5) -> np.ndarray:
    h, w, c = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)  # Start with a black mask
    
    for blk in blk_list:
        bboxes = blk.inpaint_bboxes
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox
            
            # Determine kernel size for dilation
            kernel_size = default_padding
            if hasattr(blk, 'source_lang') and blk.source_lang not in ['ja', 'ko']:
                kernel_size = 3
            if hasattr(blk, 'text_class') and blk.text_class == 'text_bubble':
                # Calculate the minimal distance from the mask to the bounding box edges
                min_distance_to_bbox = min(
                    x1 - blk.bubble_xyxy[0],  # left side
                    blk.bubble_xyxy[2] - x2,  # right side
                    y1 - blk.bubble_xyxy[1],  # top side
                    blk.bubble_xyxy[3] - y2   # bottom side
                )
                # Adjust kernel size if necessary
                if kernel_size >= min_distance_to_bbox:
                    kernel_size = max(1, int(min_distance_to_bbox - (0.2 * min_distance_to_bbox)))
            
            # Create a temporary mask for this bbox
            temp_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.rectangle(temp_mask, (x1, y1), (x2, y2), 255, -1)
            
            # Create kernel for dilation
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            
            # Dilate the temporary mask
            dilated_mask = cv2.dilate(temp_mask, kernel, iterations=4)
            
            # Add the dilated mask to the main mask
            mask = cv2.bitwise_or(mask, dilated_mask)
    
    return mask

def validate_ocr(main_page, source_lang):

    settings_page = main_page.settings_page
    settings = settings_page.get_all_settings()

    source_lang_en = main_page.lang_mapping.get(source_lang, source_lang)

    ocr_tool = settings['tools']['ocr']

    # Validate OCR API keys
    if ocr_tool == settings_page.ui.tr("Microsoft OCR") and not settings["credentials"]["Microsoft Azure"]["api_key_ocr"]:
        Messages.show_api_key_ocr_error(main_page)
        return False
    
    if ocr_tool == settings_page.ui.tr("Google Cloud Vision") and not settings["credentials"]["Google Cloud"]["api_key"]:
        Messages.show_api_key_ocr_error(main_page)
        return False

    # Validate Microsoft Endpoint
    if ocr_tool == settings_page.ui.tr('Microsoft OCR') and not settings['credentials']['Microsoft Azure']['endpoint']:
        Messages.show_endpoint_url_error(main_page)
        return False

    # Validate GPT OCR
    if source_lang_en in ["French", "German", "Dutch", "Russian", "Spanish", "Italian"]:
        if ocr_tool == settings_page.ui.tr('Default') and not settings['credentials']['Open AI GPT']['api_key']:
            Messages.show_api_key_ocr_gpt4v_error(main_page)
            return False
    
    return True

def validate_translator(main_page, source_lang, target_lang):
    settings_page = main_page.settings_page
    settings = settings_page.get_all_settings()

    translator_tool = settings['tools']['translator']

    # Validate translator API keys
    if translator_tool == settings_page.ui.tr("DeepL") and not settings["credentials"]["DeepL"]["api_key"]:
        Messages.show_api_key_translator_error(main_page)
        return False
    
    if translator_tool == settings_page.ui.tr("Microsoft Translator") and not settings["credentials"]["Microsoft Azure"]["api_key_translator"]:
        Messages.show_api_key_translator_error(main_page)
        return False

    if translator_tool == settings_page.ui.tr("Yandex") and not settings["credentials"]["Yandex"]["api_key"]:
        Messages.show_api_key_translator_error(main_page)
        return False
    
    if 'GPT' in translator_tool and not settings['credentials']['Open AI GPT']['api_key']:
        Messages.show_api_key_translator_error(main_page)
        return False
    if 'Gemini' in translator_tool and not settings['credentials']['Google Gemini']['api_key']:
        Messages.show_api_key_translator_error(main_page)
        return False
    if 'Claude' in translator_tool and not settings['credentials']['Anthropic Claude']['api_key']:
        Messages.show_api_key_translator_error(main_page)
        return False
    
    # Check DeepL and Traditional Chinese incompatibility
    if translator_tool == 'DeepL' and target_lang == main_page.tr('Traditional Chinese'):
        Messages.show_deepl_ch_error(main_page)
        return False

    # Add Google Translate and Brazilian Portuguese incompatibility check
    if translator_tool == 'Google Translate':
        if source_lang == main_page.tr('Brazilian Portuguese') or target_lang == main_page.tr('Brazilian Portuguese'):
            Messages.show_googlet_ptbr_error(main_page)
            return False
        
    return True  

def font_selected(main_page):
    if not main_page.settings_page.get_text_rendering_settings()['font']:
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

def set_alignment(blk_list, settings_page):
    text_render_settings = settings_page.get_text_rendering_settings()
    for blk in blk_list:
        alignment = text_render_settings['alignment']
        if alignment == settings_page.ui.tr("Center"):
            blk.alignment = "center"
        elif alignment == settings_page.ui.tr("Left"):
            blk.alignment = "left"
        elif alignment == settings_page.ui.tr("Right"):
            blk.alignment = "right"

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








    







