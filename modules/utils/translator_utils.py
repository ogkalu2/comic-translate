import cv2
import base64
import json
import re
import stanza
import numpy as np
from openai import OpenAI
import google.generativeai as genai
import anthropic
from .textblock import TextBlock
from typing import List


def encode_image_array(img_array: np.ndarray):
    _, img_bytes = cv2.imencode('.png', img_array)
    return base64.b64encode(img_bytes).decode('utf-8')

def get_llm_client(translator: str, api_key: str, api_url: str = ""):
    if 'Custom' in translator:
        client = OpenAI(api_key=api_key, base_url=api_url)
    elif 'Deepseek' in translator:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    elif 'GPT' in translator:
        client  = OpenAI(api_key = api_key)
    elif 'Claude' in translator:
        client = anthropic.Anthropic(api_key = api_key)
    elif 'Gemini' in translator:
        client = genai
        client.configure(api_key = api_key)
    else:
        client = None

    return client

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
        translation_dict = json.loads(json_string)
        
        for idx, blk in enumerate(blk_list):
            block_key = f"block_{idx}"
            if block_key in translation_dict:
                blk.translation = translation_dict[block_key]
            else:
                print(f"Warning: {block_key} not found in JSON string.")
    else:
        print("No JSON found in the input string.")

def set_upper_case(blk_list: List[TextBlock], upper_case: bool):
    for blk in blk_list:
        translation = blk.translation
        if upper_case and not translation.isupper():
            blk.translation = translation.upper() 
        elif not upper_case and translation.isupper():
            blk.translation = translation.capitalize()
        else:
            blk.translation = translation

def format_translations(blk_list: List[TextBlock], trg_lng_cd: str, upper_case: bool =True):
    for blk in blk_list:
        translation = blk.translation
        if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja', 'th']):

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
            set_upper_case(blk_list, upper_case)

def is_there_text(blk_list: List[TextBlock]) -> bool:
    return any(blk.text for blk in blk_list)
