import cv2
import easyocr
import numpy as np
import base64
import requests
import json
import requests

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

from ..ocr.manga_ocr.manga_ocr import MangaOcr
from ..ocr.pororo.main import PororoOcr
from typing import List, Tuple
from .textblock import TextBlock, sort_textblock_rectangles
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
    "Italian": "it",
    "Turkish": "tr",
    "Polish": "pl",
    "Portuguese": "pt",
    "Portuguese (Brazilian)": "pt-br",
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
    model="gpt-4o",
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
            vertices = line.bounding_polygon
            
            # Ensure all vertices have both 'x' and 'y' coordinates
            if all('x' in vertex and 'y' in vertex for vertex in vertices):
                x1 = vertices[0]['x']
                y1 = vertices[0]['y']
                x2 = vertices[2]['x']
                y2 = vertices[2]['y']
                
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

    if texts is not None:
        for index, text in enumerate(texts):
            vertices = text['boundingPoly']['vertices']
            if index == 0:
                continue

            if all('x' in vertex and 'y' in vertex for vertex in vertices):
                x1 = vertices[0]['x']
                y1 = vertices[0]['y']
                x2 = vertices[2]['x']
                y2 = vertices[2]['y']
                
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




    







