import numpy as np
from typing import List
from .utils.textblock import TextBlock
from .rendering.render import cv2_to_pil
from .utils.translator_utils import encode_image_array, get_raw_text, set_texts_from_json
from deep_translator import GoogleTranslator, YandexTranslator
import deepl


class Translator:
    def __init__(self, client = None, api_key: str = ''):
        self.client = client
        self.api_key = api_key

    def get_llm_model(self, translator: str):
        model_map = {
            "GPT-4": "gpt-4-1106-preview",
            "GPT-3.5": "gpt-3.5-turbo",
            "GPT-4-Vision": "gpt-4-vision-preview",
            "Claude-3-Opus": "claude-3-opus-20240229",
            "Claude-3-Sonnet": "claude-3-sonnet-20240229",
            "Claude-3-Haiku": "claude-3-haiku-20240307",
            "Gemini-1-Pro": "gemini-1.0-pro-vision-latest",
            "Gemini-1.5-Pro": "gemini-1.5-pro-latest"
        }
        return model_map.get(translator)
    
    def get_system_prompt(self, source_lang: str, target_lang: str):
        return f"""You are an expert translator who translates {source_lang} to {target_lang}. You pay attention to style, formality, idioms, slang etc and try to convey it in the way a {target_lang} speaker would understand.
        BE MORE NATURAL. NEVER USE 당신, 그녀, 그 or its Japanese equivalents.
        Specifically, you will be translating text OCR'd from a comic. The OCR is not perfect and as such you may receive text with typos or other mistakes.
        To aid you and provide context, You may be given the image of the page and/or extra context about the comic. You will be given a json string of the detected text blocks and the text to translate. Return the json string with the texts translated. DO NOT translate the keys of the json. For each block:
        - If it's already in {target_lang} or looks like gibberish, OUTPUT IT AS IT IS instead
        - DO NOT give explanations
        Do Your Best! I'm really counting on you."""

    def get_gpt_translation(self, user_prompt: str, model: str, system_prompt: str, image: np.ndarray):
        encoded_image = encode_image_array(image)
        if model == "gpt-4-vision-preview":
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}]}
                ],
                temperature=1,
                max_tokens=700,
            )
        else:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=1,
                max_tokens=700,
            )
        translated = response.choices[0].message.content
        return translated
    
    def get_claude_translation(self, user_prompt: str, model: str, system_prompt: str, image: np.ndarray):
        encoded_image = encode_image_array(image)
        media_type = "image/png"

        response = self.client.messages.create(
            model = model,
            system = system_prompt,
            messages=[
                {"role": "user", "content": [{"type": "text", "text": user_prompt}, {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded_image}}]}
            ],
            temperature=1,
            max_tokens=700,
        )
        translated = response.content[0].text
        return translated
    
    def get_gemini_translation(self, user_prompt: str, model: str, system_prompt: str, image):

        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens": 700,
            }
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
                },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
                },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
                },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
                },
        ]

        if model == "gemini-1.0-pro-vision-latest":
            model_instance = self.client.GenerativeModel(model_name = model, generation_config=generation_config, safety_settings=safety_settings)
        else:
            model_instance = self.client.GenerativeModel(model_name = model, generation_config=generation_config, system_instruction=system_prompt, safety_settings=safety_settings)

        chat = model_instance.start_chat(history=[])

        if model == "gemini-1.0-pro-vision-latest":
            chat.send_message([system_prompt, image, user_prompt])
        else:
            chat.send_message([image, user_prompt])
        response = chat.last.text

        return response

    def translate(self, blk_list: List[TextBlock], translator: str, target_lang: str, source_lang_code: str, target_lang_code: str, image: np.ndarray, inpainted_img: np.ndarray, extra_context: str):
        # Non LLM Based
        if translator in ["Google Translate", "DeepL", "Yandex"]:
            for blk in blk_list:
                text = blk.text.replace(" ", "") if 'zh' in source_lang_code.lower() or source_lang_code.lower() == 'ja' else blk.text
                if translator == "Google Translate":
                    translation = GoogleTranslator(source='auto', target=target_lang_code).translate(text)
                elif translator == "Yandex":
                    translation = YandexTranslator(self.api_key).translate(source='auto', target=target_lang_code, text=text)
                else:
                    trans = deepl.Translator(self.api_key)
                    if target_lang == "Chinese (Simplified)":
                        result = trans.translate_text(text, source_lang=source_lang_code, target_lang="zh")
                    elif target_lang == "English":
                        result = trans.translate_text(text, source_lang=source_lang_code, target_lang="EN-US")
                    else:
                        result = trans.translate_text(text, source_lang=source_lang_code, target_lang=target_lang_code)
                    translation = result.text
                if translation is not None:
                    blk.translation = translation
        
        # Handle LLM based translations
        else:
            model = self.get_llm_model(translator)
            entire_raw_text = get_raw_text(blk_list)
            system_prompt = self.get_system_prompt(source_lang_code, target_lang_code)
            user_prompt = f"{extra_context}\nMake the translation sound as natural as possible.\nTranslate this:\n{entire_raw_text}"

            if 'GPT' in translator:
                # Adjust image based on source language
                gpt_4v_img = image if source_lang_code in ["en", "fr", "nl", "de", "ru", "es", "it"] else inpainted_img
                entire_translated_text = self.get_gpt_translation(user_prompt, model, system_prompt, gpt_4v_img)

            elif 'Claude' in translator:
                entire_translated_text = self.get_claude_translation(user_prompt, model, system_prompt, image)

            elif 'Gemini' in translator:
                image = cv2_to_pil(image)
                entire_translated_text = self.get_gemini_translation(user_prompt, model, system_prompt, image)

            set_texts_from_json(blk_list, entire_translated_text)

        return blk_list