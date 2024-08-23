import numpy as np
from typing import List
from .utils.textblock import TextBlock
from .rendering.render import cv2_to_pil
from .utils.translator_utils import encode_image_array, get_raw_text, set_texts_from_json, get_llm_client
from .utils.pipeline_utils import get_language_code
from deep_translator import GoogleTranslator, YandexTranslator, MicrosoftTranslator
import deepl


class Translator:
    def __init__(self, main_page, source_lang: str = "", target_lang: str = ""):
        self.main_page = main_page
        self.settings = main_page.settings_page

        self.translator_key = self.get_translator_key(self.settings.get_tool_selection('translator'))

        self.source_lang = source_lang 
        self.source_lang_en = self.get_english_lang(main_page, self.source_lang)
        self.target_lang = target_lang
        self.target_lang_en = self.get_english_lang(main_page, self.target_lang)

        self.api_key = self.get_api_key(self.translator_key)
        self.client = get_llm_client(self.translator_key, self.api_key)

        self.img_as_llm_input = self.settings.get_llm_settings()['image_input_enabled']

    def get_translator_key(self, localized_translator: str) -> str:
        # Map localized translator names to keys
        translator_map = {
            self.settings.ui.tr("GPT-4o"): "GPT-4o",
            self.settings.ui.tr("GPT-4o mini"): "GPT-4o mini",
            self.settings.ui.tr("Claude-3-Opus"): "Claude-3-Opus",
            self.settings.ui.tr("Claude-3.5-Sonnet"): "Claude-3.5-Sonnet",
            self.settings.ui.tr("Claude-3-Haiku"): "Claude-3-Haiku",
            self.settings.ui.tr("Gemini-1.5-Flash"): "Gemini-1.5-Flash",
            self.settings.ui.tr("Gemini-1.5-Pro"): "Gemini-1.5-Pro",
            self.settings.ui.tr("Google Translate"): "Google Translate",
            self.settings.ui.tr("Microsoft Translator"): "Microsoft Translator",
            self.settings.ui.tr("DeepL"): "DeepL",
            self.settings.ui.tr("Yandex"): "Yandex"
        }
        return translator_map.get(localized_translator, localized_translator)

    def get_english_lang(self, main_page, translated_lang: str) -> str:
        return main_page.lang_mapping.get(translated_lang, translated_lang)

    def get_llm_model(self, translator_key: str):
        model_map = {
            "GPT-4o": "gpt-4o",
            "GPT-4o mini": "gpt-4o-mini",
            "Claude-3-Opus": "claude-3-opus-20240229",
            "Claude-3.5-Sonnet": "claude-3-5-sonnet-20240620",
            "Claude-3-Haiku": "claude-3-haiku-20240307",
            "Gemini-1.5-Flash": "gemini-1.5-flash-latest",
            "Gemini-1.5-Pro": "gemini-1.5-pro-latest"
        }
        return model_map.get(translator_key)
    
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

        if self.img_as_llm_input:
            message = [
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}]}
                ]
        else:
            message = [
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
                ]

        response = self.client.chat.completions.create(
            model=model,
            messages=message,
            temperature=1,
            max_tokens=1000,
        )

        translated = response.choices[0].message.content
        return translated
    
    def get_claude_translation(self, user_prompt: str, model: str, system_prompt: str, image: np.ndarray):
        encoded_image = encode_image_array(image)
        media_type = "image/png"

        if self.img_as_llm_input:
            message = [
                {"role": "user", "content": [{"type": "text", "text": user_prompt}, {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded_image}}]}
            ]
        else:
            message = [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}]

        response = self.client.messages.create(
            model = model,
            system = system_prompt,
            messages=message,
            temperature=1,
            max_tokens=1000,
        )
        translated = response.content[0].text
        return translated
    
    def get_gemini_translation(self, user_prompt: str, model: str, system_prompt: str, image):

        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 0,
            "max_output_tokens": 1000,
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

        model_instance = self.client.GenerativeModel(model_name = model, generation_config=generation_config, system_instruction=system_prompt, safety_settings=safety_settings)
        chat = model_instance.start_chat(history=[])
        if self.img_as_llm_input:
            chat.send_message([image, user_prompt])
        else:
            chat.send_message([user_prompt])
        response = chat.last.text

        return response
    
    def translate(self, blk_list: List[TextBlock], image: np.ndarray, extra_context: str):
        source_lang_code = get_language_code(self.source_lang_en)
        target_lang_code = get_language_code(self.target_lang_en)

        # Non LLM Based
        if self.translator_key in ["Google Translate", "DeepL", "Yandex", "Microsoft Translator"]:
            for blk in blk_list:
                text = blk.text.replace(" ", "") if 'zh' in source_lang_code.lower() or source_lang_code.lower() == 'ja' else blk.text
                if self.translator_key == "Google Translate":
                    translation = GoogleTranslator(source='auto', target=target_lang_code).translate(text)
                elif self.translator_key == "Yandex":
                    translation = YandexTranslator(source='auto', target=target_lang_code, api_key=self.api_key).translate(text)
                elif self.translator_key == "Microsoft Translator":
                    credentials = self.settings.get_credentials("Microsoft Azure")
                    region = credentials['region_translator']
                    translation = MicrosoftTranslator(source_lang_code, target_lang_code, self.api_key, region).translate(text)
                else:  # DeepL
                    trans = deepl.Translator(self.api_key)
                    if self.target_lang == self.main_page.tr("Simplified Chinese"):
                        result = trans.translate_text(text, source_lang=source_lang_code, target_lang="zh")
                    elif self.target_lang == self.main_page.tr("English"):
                        result = trans.translate_text(text, source_lang=source_lang_code, target_lang="EN-US")
                    else:
                        result = trans.translate_text(text, source_lang=source_lang_code, target_lang=target_lang_code)
                    translation = result.text

                if translation is not None:
                    blk.translation = translation
        
        # Handle LLM based translations
        else:
            model = self.get_llm_model(self.translator_key)
            entire_raw_text = get_raw_text(blk_list)
            system_prompt = self.get_system_prompt(self.source_lang, self.target_lang)
            user_prompt = f"{extra_context}\nMake the translation sound as natural as possible.\nTranslate this:\n{entire_raw_text}"

            if 'GPT' in self.translator_key:
                entire_translated_text = self.get_gpt_translation(user_prompt, model, system_prompt, image)
            elif 'Claude' in self.translator_key:
                entire_translated_text = self.get_claude_translation(user_prompt, model, system_prompt, image)
            elif 'Gemini' in self.translator_key:
                image = cv2_to_pil(image)
                entire_translated_text = self.get_gemini_translation(user_prompt, model, system_prompt, image)

            set_texts_from_json(blk_list, entire_translated_text)

        return blk_list
    
    def get_api_key(self, translator_key: str):
        credentials = self.settings.get_credentials()

        api_key = ""

        if 'GPT' in translator_key:
            api_key = credentials.get(self.settings.ui.tr('Open AI GPT'), {}).get('api_key', "")
        elif 'Claude' in translator_key:
            api_key = credentials.get(self.settings.ui.tr('Anthropic Claude'), {}).get('api_key', "")
        elif 'Gemini' in translator_key:
            api_key = credentials.get(self.settings.ui.tr('Google Gemini'), {}).get('api_key', "")
        else:
            api_key_map = {
                "Microsoft Translator": credentials.get(self.settings.ui.tr('Microsoft Azure'), {}).get('api_key_translator', ""),
                "DeepL": credentials.get(self.settings.ui.tr('DeepL'), {}).get('api_key', ""),
                "Yandex": credentials.get(self.settings.ui.tr('Yandex'), {}).get('api_key', ""),
            }
            api_key = api_key_map.get(translator_key, "")

        if not api_key and translator_key!= 'Google Translate':
            raise ValueError(f"API key not found for translator: {translator_key}")

        return api_key