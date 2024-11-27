import numpy as np
import base64, json
import easyocr
import cv2, os
import requests
from paddleocr import PaddleOCR
from typing import List
from ..utils.translator_utils import get_llm_client
from ..utils.textblock import TextBlock, adjust_text_line_coordinates
from ..utils.pipeline_utils import lists_to_blk_list
from ..utils.download import get_models, manga_ocr_data, pororo_data
from ..ocr.manga_ocr.manga_ocr import MangaOcr
from ..ocr.pororo.main import PororoOcr
from ..utils.pipeline_utils import language_codes

from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential


current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))
        
class OCRProcessor:
    manga_ocr_cache = None
    easyocr_cache = None
    pororo_cache = None

    def __init__(self):
        pass

    def initialize(self, main_page, source_lang: str):
        self.main_page = main_page
        self.settings = main_page.settings_page
        self.source_lang = source_lang
        self.source_lang_english = self.get_english_lang(main_page, self.source_lang)
        self.ocr_model = self.settings.get_tool_selection('ocr')
        self.microsoft_ocr = True if self.ocr_model == self.settings.ui.tr("Microsoft OCR") else False
        self.google_ocr = True if self.ocr_model == self.settings.ui.tr("Google Cloud Vision") else False
        self.device = 'cuda' if self.settings.is_gpu_enabled() else 'cpu'

        if self.source_lang_english in ["French", "German", "Dutch", "Russian", "Spanish", "Italian"] and self.ocr_model == self.settings.ui.tr("Default"):
            self.gpt_ocr = True
        else:
            self.gpt_ocr = False

    def get_english_lang(self, main_page, translated_lang: str) -> str:
        return main_page.lang_mapping.get(translated_lang, translated_lang)

    def set_source_orientation(self, blk_list: List[TextBlock]):
        # The orientation of the text of the source comic is set by the source language elsewhere in the code.
        # Might add a dedicated Orientation variable later

        source_lang_code = language_codes[self.source_lang_english]
        for blk in blk_list:
            blk.source_lang = source_lang_code

    def process(self, img: np.ndarray, blk_list: List[TextBlock]):
        self.set_source_orientation(blk_list)
        if self.source_lang == self.settings.ui.tr('Chinese') and (not self.microsoft_ocr and not self.google_ocr):
            return self._ocr_paddle(img, blk_list)
        
        elif self.microsoft_ocr:
            credentials = self.settings.get_credentials(self.settings.ui.tr("Microsoft Azure"))
            api_key = credentials['api_key_ocr']
            endpoint = credentials['endpoint']
            return self._ocr_microsoft(img, blk_list, api_key=api_key, 
                                   endpoint=endpoint)
        elif self.google_ocr:
            credentials = self.settings.get_credentials(self.settings.ui.tr("Google Cloud"))
            api_key = credentials['api_key']
            return self._ocr_google(img, blk_list, api_key=api_key)

        elif self.gpt_ocr:
            credentials = self.settings.get_credentials(self.settings.ui.tr("Open AI GPT"))
            api_key = credentials['api_key']
            gpt_client = get_llm_client('GPT', api_key)
            return self._ocr_gpt(img, blk_list, gpt_client)
        else:
            return self._ocr_default(img, blk_list, self.source_lang, self.device)

    def _ocr_paddle(self, img: np.ndarray, blk_list: List[TextBlock]):
        
        ch_ocr = PaddleOCR(lang='ch')
        result = ch_ocr.ocr(img)
        result = result[0]

        texts_bboxes = [tuple(coord for point in bbox for coord in point) for bbox, _ in result] if result else []
        condensed_texts_bboxes = [(x1, y1, x2, y2) for (x1, y1, x2, y1_, x2_, y2, x1_, y2_) in texts_bboxes]

        texts_string = [line[1][0] for line in result] if result else []

        blk_list = lists_to_blk_list(blk_list, condensed_texts_bboxes, texts_string)

        return blk_list
        

    def _ocr_microsoft(self, img: np.ndarray, blk_list: List[TextBlock], api_key: str, endpoint: str):

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

    def _ocr_google(self, img: np.ndarray, blk_list: List[TextBlock], api_key:str):
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

    def _ocr_gpt(self, img: np.ndarray, blk_list: List[TextBlock], client, expansion_percentage: int = 0):
        for blk in blk_list:
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(blk.xyxy, expansion_percentage, expansion_percentage, img)

            # Check if the coordinates are valid and the bounding box does not extend outside the image
            if x1 < x2 and y1 < y2:
                cv2_to_gpt = cv2.imencode('.png', img[y1:y2, x1:x2])[1]
                cv2_to_gpt = base64.b64encode(cv2_to_gpt).decode('utf-8')
                text = get_gpt_ocr(cv2_to_gpt, client)
                blk.text = text

        return blk_list

    def _ocr_default(self, img: np.ndarray, blk_list: List[TextBlock], source_language: str, device: str, expansion_percentage: int = 5):
        gpu_state = False if device == 'cpu' else True

        for blk in blk_list:
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(blk.xyxy, expansion_percentage, expansion_percentage, img)

            # Check if the coordinates are valid and the bounding box does not extend outside the image
            if x1 < x2 and y1 < y2:
                if source_language == self.main_page.tr('Japanese'):
                    if self.manga_ocr_cache is None:
                        get_models(manga_ocr_data)
                        manga_ocr_path = os.path.join(project_root, 'models/ocr/manga-ocr-base')
                        self.manga_ocr_cache = MangaOcr(pretrained_model_name_or_path=manga_ocr_path, device=device)
                    blk.text = self.manga_ocr_cache(img[y1:y2, x1:x2])

                elif source_language == self.main_page.tr('English'):
                    if self.easyocr_cache is None:
                        self.easyocr_cache = easyocr.Reader(['en'], gpu = gpu_state)

                    result = self.easyocr_cache.readtext(img[y1:y2, x1:x2], paragraph=True)
                    texts = []
                    for r in result:
                        if r is None:
                            continue
                        texts.append(r[1])
                    text = ' '.join(texts)
                    blk.text = text
                
                elif source_language == self.main_page.tr('Korean'):
                    if self.pororo_cache is None:
                        get_models(pororo_data)
                        self.pororo_cache = PororoOcr()
                    
                    self.pororo_cache.run_ocr(img[y1:y2, x1:x2])
                    result = self.pororo_cache.get_ocr_result()
                    descriptions = result['description']
                    all_descriptions = ' '.join(descriptions)
                    blk.text = all_descriptions     

            else:
                print('Invalid textbbox to target img')
                blk.text = ['']

        return blk_list

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
    max_tokens=1000,
    )
    text = response.choices[0].message.content
    text = text.replace('\n', ' ') if '\n' in text else text
    return text





