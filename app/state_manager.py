import json
import dearpygui.dearpygui as dpg
import locale
import os
from typing import Dict, List

class LanguageSettings:
    def __init__(self):
        self.current_language = self.parse_locale(locale.getdefaultlocale())
        self.previous_language = self.current_language
    
    def parse_locale(self, default_locale):
        locale_code, _ = default_locale
        if locale_code:
            if locale_code.split('_')[0] in ['en', 'fr', 'ru', 'de', 'nl', 'ja', 'ko', 'es', 'it']:
                return locale_code.split('_')[0]
            elif locale_code in ['zh_CN', 'zh_SG']:
                return 'zh-CN'
            elif locale_code in ['zh_TW', 'zh_HK']:
                return 'zh-TW'
            else:
                return 'en'
        else:
            return 'en'
    
    def get_curr_lang(self):
        return self.current_language
    
    def set_curr_lang(self, lang_code):
        self.previous_language = self.current_language
        self.current_language = lang_code
    
    def get_prev_lang(self):
        return self.previous_language
    
class UserData:
    def __init__(self):
        self.data = {}
    
    def set_data(self, key, value):
        self.data[key] = value
    
    def get_data(self, key):
        return self.data.get(key, None)  # Return None if key does not exist
    
    def get_all_data(self):
        return self.data

    def clear_data(self):
        self.data = {}

class AppStateManager:
    def __init__(self, 
                font_mappings: Dict,
                dpg_windows: List,
                state_file='app/settings.json'):

        self.state_file = state_file
        self.lang_settings = LanguageSettings()
        self.user_data = UserData()
        self.font_mappings = font_mappings  
        self.dpg_windows = dpg_windows  
    
    def get_window_sizes_and_positions(self):
        window_state = {}
        for window_id in self.dpg_windows:
            window_state[window_id] = {
                "width": dpg.get_item_width(window_id),
                "height": dpg.get_item_height(window_id),
                "position": dpg.get_item_pos(window_id)
            }
        return window_state
    
    def apply_window_sizes_and_positions(self, window_settings):
        for window_id, properties in window_settings.items():
            if dpg.does_item_exist(window_id):
                dpg.set_item_width(window_id, properties['width'])
                dpg.set_item_height(window_id, properties['height'])
                dpg.set_item_pos(window_id, properties['position'])
    
    def apply_viewport(self, viewport_state):
        for key, value in viewport_state.items():
            if key == "viewport_height":
                dpg.set_viewport_height(value)
            elif key == "viewport_width":
                dpg.set_viewport_width(value)
            elif key == "viewport_position":
                dpg.set_viewport_pos(value)
    
    def save_state(self):
        window_sizes_and_positions = self.get_window_sizes_and_positions()
        state = {
            "current_language": self.lang_settings.get_curr_lang(),
            "gpt_extra_context": dpg.get_value("gpt_extra_context"),
            "use_gpu_checkbox": dpg.get_value("use_gpu_checkbox"),
            "source_lang_dropdown": dpg.get_value("source_lang_dropdown"),
            "target_lang_dropdown": dpg.get_value("target_lang_dropdown"),
            "upper_case_checkbox": dpg.get_value("upper_case_checkbox"),
            "font_dropdown": dpg.get_value("font_dropdown"),
            "translator_dropdown": dpg.get_value("translator_dropdown"),
            "ocr_dropdown": dpg.get_value("ocr_dropdown"),
            "stop_gpt_ocr_warning_checkbox": dpg.get_value("stop_gpt_ocr_warning_checkbox"),
            "save_keys_for_gpt_checkbox": dpg.get_value("save_keys_for_gpt_checkbox"),
            "save_keys_for_deepl_checkbox": dpg.get_value("save_keys_for_deepl_checkbox"),
            "save_keys_for_microsoft_checkbox": dpg.get_value("save_keys_for_microsoft_checkbox"),
            "save_keys_for_google_checkbox": dpg.get_value("save_keys_for_google_checkbox"),
            "save_keys_for_gemini_checkbox": dpg.get_value("save_keys_for_gemini_checkbox"),
            "save_keys_for_claude_checkbox": dpg.get_value("save_keys_for_claude_checkbox"),
            "save_keys_for_yandex_checkbox": dpg.get_value("save_keys_for_yandex_checkbox"),
            "width_adjustment_number": dpg.get_value("width_adjustment_number"),
            "height_adjustment_number": dpg.get_value("height_adjustment_number"),
            "text_alignment_dropdown": dpg.get_value("text_alignment_dropdown"),
            "font_color": dpg.get_value("font_color"),
            "save_pdf_as_dropdown": dpg.get_value("save_pdf_as_dropdown"),
            "save_cbt_as_dropdown": dpg.get_value("save_cbt_as_dropdown"),
            "save_cbr_as_dropdown": dpg.get_value("save_cbr_as_dropdown"),
            "save_cb7_as_dropdown": dpg.get_value("save_cb7_as_dropdown"),
            "save_cbz_as_dropdown": dpg.get_value("save_cbz_as_dropdown"),
            "save_epub_as_dropdown": dpg.get_value("save_epub_as_dropdown"),
            "export_options": {
                "export_raw_text_checkbox": dpg.get_value("export_raw_text_checkbox"),
                "export_translated_text_checkbox": dpg.get_value("export_translated_text_checkbox"),
                "export_annot_img_checkbox": dpg.get_value("export_annot_img_checkbox"),
                "export_inpainted_img_checkbox": dpg.get_value("export_inpainted_img_checkbox"),
            },
            "preview_options": {
                "preview_annot_img_checkbox": dpg.get_value("preview_annot_img_checkbox"),
                "preview_inpainted_img_checkbox": dpg.get_value("preview_inpainted_img_checkbox"),
            },
        }

        # Save credentials only if the corresponding checkboxes are checked
        if dpg.get_value("save_keys_for_gpt_checkbox"):
            state["gpt_api_key"] = dpg.get_value("gpt_api_key")

        if dpg.get_value("save_keys_for_deepl_checkbox"):
            state["deepl_api_key"] = dpg.get_value("deepl_api_key")

        if dpg.get_value("save_keys_for_microsoft_checkbox"):
            state["microsoft_api_key"] = dpg.get_value("microsoft_api_key")
            state["microsoft_endpoint_url"] = dpg.get_value("microsoft_endpoint_url")

        if dpg.get_value("save_keys_for_google_checkbox"):
            state["google_api_key"] = dpg.get_value("google_api_key")

        if dpg.get_value("save_keys_for_gemini_checkbox"):
            state["gemini_api_key"] = dpg.get_value("gemini_api_key")

        if dpg.get_value("save_keys_for_claude_checkbox"):
            state["claude_api_key"] = dpg.get_value("claude_api_key")

        if dpg.get_value("save_keys_for_yandex_checkbox"):
            state["yandex_api_key"] = dpg.get_value("yandex_api_key")

        # Save the window positions
        state["viewport"] = {
                "viewport_height": dpg.get_viewport_height(),
                "viewport_width": dpg.get_viewport_width(),
                "viewport_position": dpg.get_viewport_pos()
            }
        state["windows"] = window_sizes_and_positions

        # Save the state to a JSON file
        with open(self.state_file, 'w') as state_file:
            json.dump(state, state_file, indent=4)
    
    def load_state(self):
        try:
            with open(self.state_file, 'r') as state_file:
                state = json.load(state_file)
                return state
        except (FileNotFoundError, json.JSONDecodeError):
            return {}  # Return an empty dictionary if the file doesn't exist or the JSON is invalid
        
    def apply_state(self, state):
        if state:
            for key, value in state.items():
                if key == "viewport":
                    self.apply_viewport(value)
                elif key == "windows":
                    self.apply_window_sizes_and_positions(value)
                elif key == "current_language":
                    self.lang_settings.set_curr_lang(value)
                    current_language = self.lang_settings.get_curr_lang()
                    if current_language in ['zh-CN', 'zh-TW', 'ja', 'ko']:
                        dpg.hide_item("upper_case_checkbox")
                    elif current_language in ['en', 'ru', 'de', 'nl', 'fr', 'es', 'it']:
                        dpg.show_item("upper_case_checkbox")
                    if current_language != 'en':
                        self.change_language(value)
                    self.change_font(value)
                elif key in ["export_options", "preview_options"]:
                    for sub_key, sub_value in value.items():
                        dpg.set_value(sub_key, sub_value)
                else:
                    dpg.set_value(key, value)

    def change_font(self, lang_code):
        font = self.font_mappings[lang_code]
        for window in self.dpg_windows:
            dpg.bind_item_font(window, font)

    def lang_change_process(self, lang_code):
        self.lang_settings.set_curr_lang(lang_code)
        current_language = self.lang_settings.get_curr_lang()
        if current_language in ['zh-CN', 'zh-TW', 'ja', 'ko']:
            dpg.hide_item("upper_case_checkbox")
        elif current_language in ['en', 'ru', 'de', 'nl', 'fr', 'it', 'es']:
            dpg.show_item("upper_case_checkbox")
        self.change_language(lang_code)
        self.change_font(lang_code)

    def change_language(self, language_code):
        current_lang_file = open_lang_file(self.lang_settings.get_prev_lang())
        lang_mappings, ocr_mappings, translator_mappings, alignment_mappings = all_loc_mappings(current_lang_file)

        next_lang_file = open_lang_file(language_code) 
        lang_mappings_next, ocr_mappings_next, translator_mappings_next, alignment_mappings_next = all_loc_mappings(next_lang_file)

        for item, text in next_lang_file["dpg_windows_ui"].items():
            if dpg.does_item_exist(item):

                item_type = dpg.get_item_type(item)
                
                if item_type == "mvAppItemType::mvInputText":  
                    dpg.set_value(item, text)
                elif item_type == "mvAppItemType::mvCombo":  
                    dpg.configure_item(item, items=text)
                    if item == "source_lang_dropdown":
                        selection = dpg.get_value("source_lang_dropdown")
                        en_selection = lang_mappings[selection] if selection else ''
                        mapped_selection = get_key(lang_mappings_next, en_selection)
                        dpg.set_value(item, mapped_selection)
                    if item == "target_lang_dropdown":
                        selection = dpg.get_value("target_lang_dropdown")
                        en_selection = lang_mappings[selection] if selection else ''
                        mapped_selection = get_key(lang_mappings_next, en_selection)
                        dpg.set_value(item, mapped_selection)
                    if item == "ocr_dropdown":
                        selection = dpg.get_value("ocr_dropdown")
                        en_selection = ocr_mappings[selection] if selection else ''
                        mapped_selection = get_key(ocr_mappings_next, en_selection)
                        dpg.set_value(item, mapped_selection)
                    if item == "translator_dropdown":
                        selection = dpg.get_value("translator_dropdown")
                        en_selection = translator_mappings[selection] if selection else ''
                        mapped_selection = get_key(translator_mappings_next, en_selection)
                        dpg.set_value(item, mapped_selection)
                    if item == "text_alignment_dropdown":
                        selection = dpg.get_value("text_alignment_dropdown")
                        en_selection = alignment_mappings[selection] if selection else ''
                        mapped_selection = get_key(alignment_mappings_next, en_selection)
                        dpg.set_value(item, mapped_selection)

                elif item_type == "mvAppItemType::mvText":  
                    dpg.configure_item(item, default_value=text)
                elif item_type in ["mvAppItemType::mvButton", "mvAppItemType::mvCheckbox", "mvAppItemType::mvWindowAppItem", "mvAppItemType::mvMenu", "mvAppItemType::mvMenuItem"]:
                    dpg.configure_item(item, label=text)

def open_lang_file(lang_code):
    loc_file_path = os.path.join(os.getcwd(), "app", "localizations", f"{lang_code}.json")
    with open(loc_file_path, 'r', encoding='utf-8') as file:
        loc_file = json.load(file)

    return loc_file

def all_loc_mappings(loc_file):
    lang_mappings = loc_file["lang_mappings"]
    ocr_mappings =  loc_file["ocr_mappings"]
    translator_mappings = loc_file["translator_mappings"]
    alignment_mappings = loc_file["alignment_mappings"]

    return lang_mappings, ocr_mappings, translator_mappings, alignment_mappings

def get_key(mappings, value):
    k=''
    for key, val in mappings.items():
        if val == value:
            k = key
    return k
        

