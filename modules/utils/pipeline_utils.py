import cv2
import re
import easyocr
import numpy as np
import base64
import requests
import json
import requests
import deepl
from deep_translator import GoogleTranslator
import stanza
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

from ..ocr.manga_ocr.manga_ocr import MangaOcr
from ..ocr.pororo.main import PororoOcr
from typing import List, Tuple
from .textblock import TextBlock
from .detection import does_rectangle_fit, do_rectangles_overlap
from .download import get_models, manga_ocr_data, pororo_data

manga_ocr_path = 'models/ocr/manga-ocr-base'

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
    "Italian": "it"
    }

def get_language_codes(src_lng: str, trg_lng: str):
    src_lng_cd = language_codes[src_lng]
    trg_lng_cd = language_codes[trg_lng]

    return src_lng_cd, trg_lng_cd

def rgba2hex(rgba_list):
    r,g,b,a = [int(num) for num in rgba_list]
    return "#{:02x}{:02x}{:02x}{:02x}".format(r, g, b, a)

def encode_image_array(img_array: np.ndarray):
    _, img_bytes = cv2.imencode('.png', img_array)
    return base64.b64encode(img_bytes).decode('utf-8')

def adjust_text_line_coordinates(coords, width_expansion_percentage: int, height_expansion_percentage: int):
    top_left_x, top_left_y, bottom_right_x, bottom_right_y = coords
    # Calculate width, height, and respective expansion offsets
    width = bottom_right_x - top_left_x
    height = bottom_right_y - top_left_y
    width_expansion_offset = int(((width * width_expansion_percentage) / 100) / 2)
    height_expansion_offset = int(((height * height_expansion_percentage) / 100) / 2)

    # Define the rectangle origin points (bottom left, top right) with expansion/contraction
    pt1_expanded = (
        top_left_x - width_expansion_offset,
        top_left_y - height_expansion_offset,
    )
    pt2_expanded = (
        bottom_right_x + width_expansion_offset,
        bottom_right_y + height_expansion_offset,
    )

    return pt1_expanded[0], pt1_expanded[1], pt2_expanded[0], pt2_expanded[1]

def adjust_blks_size(blk_list: List[TextBlock], img_shape: Tuple[int, int, int], w_expan: int = 0, h_expan: int = 0):
    im_h, im_w = img_shape[:2]
    for blk in blk_list:
        coords = blk.xyxy
        expanded_coords = adjust_text_line_coordinates(coords, w_expan, h_expan)

        # Ensuring that the box does not exceed image boundaries
        new_x1 = max(expanded_coords[0], 0)
        new_y1 = max(expanded_coords[1], 0)
        new_x2 = min(expanded_coords[2], im_w)
        new_y2 = min(expanded_coords[3], im_h)

        blk.xyxy[:] = [new_x1, new_y1, new_x2, new_y2]

def get_gpt_ocr(base64_image: str, client):
    response = client.chat.completions.create(
    model="gpt-4-vision-preview",
    messages=[
    {
      "role": "user",
      "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
        {"type": "text", "text": """ Write out the text in this image. Do NOT Translate. Do not write anything else"""},
      ]
    }
  ],
  max_tokens=500,
  )
    text = response.choices[0].message.content
    text = text.replace('\n', ' ') if '\n' in text else text
    return text

def sort_textblock_rectangles(coords_text_list: List[Tuple[Tuple[int, int, int, int], str]], direction: str = 'ver_rtl', threshold: int = 5):
    
    def in_same_line(coor_a, coor_b):
        # For horizontal text, check if word boxes are in the same horizontal band
        if 'hor' in direction:
            return abs(coor_a[1] - coor_b[1]) <= threshold
        # For vertical text, check if word boxes are in the same vertical band
        elif 'ver' in direction:
            return abs(coor_a[0] - coor_b[0]) <= threshold

    # Group word bounding boxes into lines
    lines = []
    remaining_boxes = coords_text_list[:]  # create a shallow copy

    while remaining_boxes:
        box = remaining_boxes.pop(0)  # Start with the first bounding box
        current_line = [box]

        boxes_to_check_against = remaining_boxes[:]
        for comparison_box in boxes_to_check_against:
            if in_same_line(box[0], comparison_box[0]):
                remaining_boxes.remove(comparison_box)
                current_line.append(comparison_box)

        lines.append(current_line)

    # Sort the boxes in each line based on the reading direction
    for i, line in enumerate(lines):
        if direction == 'hor_ltr':
            lines[i] = sorted(line, key=lambda box: box[0][0])  # Sort by leftmost x-coordinate
        elif direction == 'hor_rtl':
            lines[i] = sorted(line, key=lambda box: -box[0][0])  # Sort by leftmost x-coordinate, reversed
        elif direction in ['ver_ltr', 'ver_rtl']:
            lines[i] = sorted(line, key=lambda box: box[0][1])  # Sort by topmost y-coordinate

    # Sort the lines themselves based on the orientation of the text
    if 'hor' in direction:
        lines.sort(key=lambda line: min(box[0][1] for box in line))  # Sort by topmost y-coordinate for horizontal text
    elif direction == 'ver_ltr':
        lines.sort(key=lambda line: min(box[0][0] for box in line)) # Sort by leftmost x-coordinate for vertical text
    elif direction == 'ver_rtl':
        lines.sort(key=lambda line: min(box[0][0] for box in line), reverse=True)  # Reversed order of sort by leftmost x-coordinate 

    # Flatten the list of lines to return a single list with all grouped boxes
    grouped_boxes = [box for line in lines for box in line]
    
    return grouped_boxes

def lists_to_blk_list(blk_list: List[TextBlock], texts_bboxes: List, texts_string: List):

    for blk in blk_list:
        blk_entries = []
        group = list(zip(texts_bboxes, texts_string))  
        
        for line, text in group:
            if blk.bubble_xyxy is not None:
                if does_rectangle_fit(blk.bubble_xyxy, line):
                    blk_entries.append((line, text))  
                elif do_rectangles_overlap(blk.bubble_xyxy, line):
                    blk_entries.append((line, text)) 
            elif do_rectangles_overlap(blk.xyxy, line):
                blk_entries.append((line, text)) 


        # Sort and join text entries
        sorted_entries = sort_textblock_rectangles(blk_entries, blk.source_lang_direction)
        if blk.source_lang in ['ja', 'zh']:
            blk.text = ''.join(text for bbox, text in sorted_entries)
        else:
            blk.text = ' '.join(text for bbox, text in sorted_entries)

    return blk_list

def ocr_blk_list_microsoft(img: np.ndarray, blk_list: List[TextBlock], api_key: str, endpoint: str):
    texts_bboxes = []
    texts_string = []

    client = ImageAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    image_buffer = cv2.imencode('.png', img)[1].tobytes()
    result = client.analyze(image_data=image_buffer, visual_features=[VisualFeatures.READ])

    if result.read is not None:
        for line in result.read.blocks[0].lines:
            x1 = line.bounding_polygon[0]['x']
            x2 = line.bounding_polygon[2]['x']
            y1 = line.bounding_polygon[0]['y']
            y2 = line.bounding_polygon[2]['y']
            texts_bboxes.append((x1, y1, x2, y2))
            texts_string.append(line.text)

    blk_list = lists_to_blk_list(blk_list, texts_bboxes, texts_string)

    return blk_list

def ocr_blk_list_google(img: np.ndarray, blk_list: List[TextBlock], api_key:str):
    texts_bboxes = []
    texts_string = []

    cv2_to_google = cv2.imencode('.png', img)[1].tobytes()
    payload = {"requests": [{"image": {"content": base64.b64encode(cv2_to_google).decode('utf-8')}, "features": [{"type": "TEXT_DETECTION"}]}]}
    headers = {"Content-Type": "application/json"}
    response = requests.post("https://vision.googleapis.com/v1/images:annotate", headers=headers, params={"key": api_key}, data=json.dumps(payload))
    result = response.json()
    texts = result['responses'][0]['textAnnotations']

    for index, text in enumerate(texts):
        if index == 0:
            continue
        x1 = text['boundingPoly']['vertices'][0]['x']
        x2 = text['boundingPoly']['vertices'][2]['x']
        y1 = text['boundingPoly']['vertices'][0]['y']
        y2 = text['boundingPoly']['vertices'][2]['y']
        string = text['description']
        texts_bboxes.append((x1, y1, x2, y2))
        texts_string.append(string)

    blk_list = lists_to_blk_list(blk_list, texts_bboxes, texts_string)
    
    return blk_list

def ocr_blk_list_paddle(img, blk_list):
    from paddleocr import PaddleOCR
    
    ch_ocr = PaddleOCR(lang='ch')
    result = ch_ocr.ocr(img)
    result = result[0]

    texts_bboxes = [tuple(coord for point in bbox for coord in point) for bbox, _ in result] if result else []
    condensed_texts_bboxes = [(x1, y1, x2, y2) for (x1, y1, x2, y1_, x2_, y2, x1_, y2_) in texts_bboxes]

    texts_string = [line[1][0] for line in result] if result else []

    blk_list = lists_to_blk_list(blk_list, condensed_texts_bboxes, texts_string)
    
    return blk_list

def ensure_within_bounds(coords, im_width, im_height, width_expansion_percentage: int, height_expansion_percentage: int):
    x1, y1, x2, y2 = coords

    width = x2 - x1
    height = y2 - y1
    width_expansion_offset = int((width * width_expansion_percentage) / 100)
    height_expansion_offset = int((height * height_expansion_percentage) / 100)

    x1 = max(x1 - width_expansion_offset, 0)
    x2 = min(x2 + width_expansion_offset, im_width)
    y1 = max(y1 - height_expansion_offset, 0)
    y2 = min(y2 + height_expansion_offset, im_height)

    return x1, y1, x2, y2

def ocr_blk_list_gpt(img: np.ndarray, blk_list: List[TextBlock], client, expansion_percentage: int = 0):
    im_h, im_w = img.shape[:2]
    for blk in blk_list:
        if blk.bubble_xyxy is not None:
            x1, y1, x2, y2 = blk.bubble_xyxy
        else:
            x1, y1, x2, y2 = adjust_text_line_coordinates(blk.xyxy, expansion_percentage, expansion_percentage)
            x1, y1, x2, y2 = ensure_within_bounds((x1, y1, x2, y2), im_w, im_h, expansion_percentage, expansion_percentage)

        # Check if the coordinates are valid and the bounding box does not extend outside the image
        if x1 < x2 and y1 < y2:
            cv2_to_gpt = cv2.imencode('.png', img[y1:y2, x1:x2])[1]
            cv2_to_gpt = base64.b64encode(cv2_to_gpt).decode('utf-8')
            text = get_gpt_ocr(cv2_to_gpt, client)
            blk.text = text

def ocr_blk_list(img: np.ndarray, blk_list: List[TextBlock], source_language: str, device: str, expansion_percentage: int = 5):
    gpu_state = False if device == 'cpu' else True

    im_h, im_w = img.shape[:2]
    for blk in blk_list:
        if blk.bubble_xyxy is not None:
            x1, y1, x2, y2 = blk.bubble_xyxy
        else:
            x1, y1, x2, y2 = adjust_text_line_coordinates(blk.xyxy, expansion_percentage, expansion_percentage)
            x1, y1, x2, y2 = ensure_within_bounds((x1, y1, x2, y2), im_w, im_h, expansion_percentage, expansion_percentage)

        # Check if the coordinates are valid and the bounding box does not extend outside the image
        if x1 < x2 and y1 < y2:
            if source_language == 'Japanese':
                get_models(manga_ocr_data)
                manga_ocr = MangaOcr(pretrained_model_name_or_path=manga_ocr_path, device=device)
                blk.text = manga_ocr(img[y1:y2, x1:x2])

            elif source_language == 'English':
                reader = easyocr.Reader(['en'], gpu = gpu_state)
                result = reader.readtext(img[y1:y2, x1:x2], paragraph=True)
                texts = []
                for r in result:
                    if r is None:
                        continue
                    texts.append(r[1])
                text = ' '.join(texts)
                blk.text = text
            
            elif source_language == 'Korean':
                get_models(pororo_data)
                kor_ocr = PororoOcr()
                kor_ocr.run_ocr(img[y1:y2, x1:x2])
                result = kor_ocr.get_ocr_result()
                descriptions = result['description']
                all_descriptions = ' '.join(descriptions)
                blk.text = all_descriptions     

        else:
            print('Invalid textbbox to target img')
            blk.text = ['']

def get_gpt_model(translator: str):    
    if translator == "GPT-4":
        model = "gpt-4-1106-preview"
    elif translator == "GPT-3.5":
        model = "gpt-3.5-turbo"
    elif translator == "GPT-4-Vision":
        model = "gpt-4-vision-preview"
    return model

def get_gpt_system_prompt(source_lang: str, target_lang: str):
    return f"""You are an expert translator who translates {source_lang} to {target_lang}. You pay attention to style, formality, idioms, slang etc and try to convey it in the way a {target_lang} speaker would understand.

BE MORE NATURAL. NEVER USE 당신, 그녀, 그 or its Japanese equivalents.

Specifically, you will be translating text OCR'd from a comic. The OCR is not perfect and as such you may receive text with typos or other mistakes.
To aid you and provide context, You may be given the image of the page and/or extra context about the comic. You will be given a json string of the detected text blocks and the text to translate. 
Return the json string with the texts translated. DO NOT translate the keys of the json. 

For each block:
- If it's already in {target_lang} or looks like gibberish, OUTPUT IT AS IT IS instead
- DO NOT give explanations

Do Your Best! I'm really counting on you."""

def get_gpt_translation(client, text: str, model: str, system_prompt: str, image: np.ndarray, extra_info: str = ""):
    encoded_image = encode_image_array(image)
        
    user_prompt = f"{extra_info}\nMake the translation sound as natural as possible.\nTranslate this:\n{text}"

    if model == "gpt-4-vision-preview":
        response = client.chat.completions.create(
        model=model,
        messages =
        [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "text", "text": user_prompt},{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}]}
        ],
        temperature=1,
        max_tokens=700,
        )
    else:
        response = client.chat.completions.create(
        model=model,
        messages=
        [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
        ],
        temperature=1,
        max_tokens=700,
        )
    translated = response.choices[0].message.content
    return translated

def trad_translate(blk_list: List[TextBlock], translator: str, target_lang: str, source_lang_code: str, target_lang_code: str, api_key: str = ''):

    for blk in blk_list:
        text = blk.text.replace(" ", "") if 'zh' in source_lang_code.lower() or source_lang_code.lower() == 'ja' else blk.text
        if translator == "Google Translate":
            translation = GoogleTranslator(source='auto', target=target_lang_code).translate(text)
            if translation is not None:
                blk.translation = translation

        elif translator == "DeepL":
            trans = deepl.Translator(api_key) 
            if target_lang == "Chinese (Simplified)":
                result = trans.translate_text(text, source_lang = source_lang_code, target_lang="zh")
            elif target_lang == "English":
                result = trans.translate_text(text, source_lang = source_lang_code, target_lang="EN-US")
            else:
                result = trans.translate_text(text, source_lang = source_lang_code, target_lang=target_lang_code)
            translation = result.text
            blk.translation = translation

def format_translations(blk_list: List[TextBlock], trg_lng_cd: str, upper_case: bool =True):
    for blk in blk_list:
        translation = blk.translation
        if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja']):

            if trg_lng_cd == 'zh-TW':
                trg_lng_cd = 'zh-Hant'
            elif trg_lng_cd == 'zh-CN':
                trg_lng_cd = 'zh-Hans'
            else:
                trg_lng_cd = trg_lng_cd

            stanza.download(trg_lng_cd, processors='tokenize')
            nlp = stanza.Pipeline(trg_lng_cd, processors='tokenize')
            doc = nlp(translation)
            seg_result = []
            for sentence in doc.sentences:
                for word in sentence.words:
                    seg_result.append(word.text)
            translation = ''.join(word if word in ['.', ','] else f' {word}' for word in seg_result).lstrip()
            blk.translation = translation
        else:
            blk.translation = translation.upper() if upper_case else translation.capitalize()

def generate_mask(img: np.ndarray, blk_list: List[TextBlock], default_kernel_size=5):
    h, w, c = img.shape
    mask = np.zeros((h, w), dtype=np.uint8)  # Start with a black mask

    for blk in blk_list:
        seg = blk.segm_pts
        
        if blk.source_lang == 'en':
            default_kernel_size = 1
        kernel_size = default_kernel_size # Default kernel size
        if blk.text_class == 'text_bubble':
            # Access the bounding box coordinates
            bbox = blk.bubble_xyxy
            # Calculate the minimal distance from the mask to the bounding box edges
            min_distance_to_bbox = min(
                np.min(seg[:, 0]) - bbox[0],  # left side
                bbox[2] - np.max(seg[:, 0]),  # right side
                np.min(seg[:, 1]) - bbox[1],  # top side
                bbox[3] - np.max(seg[:, 1])   # bottom side
            )
            # adjust kernel size if necessary
            if default_kernel_size >= min_distance_to_bbox:
                kernel_size = max(1, int(min_distance_to_bbox-(0.2*min_distance_to_bbox)))

        # Create a kernel for dilation based on the kernel size
        kernel = np.ones((kernel_size, kernel_size), np.uint8)

        # Draw the individual mask and dilate it
        single_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(single_mask, [seg], 255)
        single_mask = cv2.dilate(single_mask, kernel, iterations=1)

        # Merge the dilated mask with the global mask
        mask = cv2.bitwise_or(mask, single_mask)
        np.expand_dims(mask, axis=-1)

    return mask

def get_raw_text(blk_list: List[TextBlock]):
    rw_txts_dict = {}
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        rw_txts_dict[block_key] = blk.text
    
    raw_texts_json = json.dumps(rw_txts_dict, ensure_ascii=False, indent=4)
    
    return raw_texts_json

def get_raw_translation(blk_list: List[TextBlock]):
    rw_translations_dict = {}
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        rw_translations_dict[block_key] = blk.translation
    
    raw_translations_json = json.dumps(rw_translations_dict, ensure_ascii=False, indent=4)
    
    return raw_translations_json

def set_texts_from_json(blk_list: List[TextBlock], json_string: str):
    match = re.search(r"\{[\s\S]*\}", json_string)
    if match:
        # Extract the JSON string from the matched regular expression
        json_string = match.group(0)
        try:
            parsed_json = json.loads(json_string)
        except json.JSONDecodeError as e:
            print("Error decoding JSON:", e)
    else:
        print("No JSON found in the input string.")

    translation_dict = json.loads(json_string)
    
    for idx, blk in enumerate(blk_list):
        block_key = f"block_{idx}"
        if block_key in translation_dict:
            blk.translation = translation_dict[block_key]
        else:
            print(f"Warning: {block_key} not found in JSON string.")


    







