import dearpygui.dearpygui as dpg
import os
from modules.utils.download import get_models, mandatory_models
from app.callbacks import *
from app.state_manager import AppStateManager, get_key, open_lang_file
from pipeline import start_process, stop_process

for model in mandatory_models:
    get_models(model)

supported_source_languages = ["Korean", "Japanese", "French", "Chinese", "English", "Russian", "German", "Dutch", "Spanish", "Italian"]
supported_target_languages = ["English", "Korean", "Japanese", "French", "Simplified Chinese", "Traditional Chinese", "Russian", "German", "Dutch", "Spanish", "Italian"]
supported_ocr = ["Default", "Microsoft OCR", "Google Cloud Vision"]
supported_translators = ["GPT-4-Vision", "GPT-4", "GPT-3.5", "DeepL", "Claude-3-Opus", "Claude-3-Sonnet", "Claude-3-Haiku", "Gemini-1-Pro", "Gemini-1.5-Pro", "Yandex", "Google Translate"]
dpg_windows = [
"primary_window", "import_confirmed", "import_not_confirmed", "gpt_credentials", 
"deepl_credentials", "microsoft_credentials", "google_credentials", "gpt_prompts", 
"adjust_textblocks", "text_alignment", "font", "gpt_for_ocr_warning", 
"api_key_translator_error", "api_key_ocr_error", "api_key_ocr_gpt-4v_error", 
"endpoint_url_error", "deepl_ch_error", "translation_complete", "save_as",
"gemini_credentials", "claude_credentials", "yandex_credentials"
]

font_folder_path = os.path.join(os.getcwd(), "fonts")
manga_ocr_path = 'models/ocr/manga-ocr-base'

# DearPyGui initialization
dpg.create_context()

with dpg.font_registry():
    with dpg.font("app/fonts/NotoSans-Medium.ttf", 20) as latin_cyrillic_font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)

    with dpg.font("app/fonts/NotoSansKR-Medium.ttf", 20) as ko_font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Korean)
        
    with dpg.font("app/fonts/NotoSansJP-Medium.ttf", 20) as ja_font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Japanese)

    with dpg.font("app/fonts/NotoSansTC-Medium.ttf", 20) as ch_tr_font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Full)
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Simplified_Common)
    
    with dpg.font("app/fonts/NotoSansSC-Medium.ttf", 20) as ch_sim_font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Full)
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Simplified_Common)

font_mappings = {
    "en": latin_cyrillic_font,
    "ko": ko_font,
    "ja": ja_font,
    "zh-CN": ch_sim_font,
    "zh-TW": ch_tr_font,
    "ru": latin_cyrillic_font,
    "fr": latin_cyrillic_font,
    "de": latin_cyrillic_font,
    "nl": latin_cyrillic_font,
    "es": latin_cyrillic_font,
    "it": latin_cyrillic_font 
}

state_manager = AppStateManager(font_mappings, dpg_windows)

disabled_color = (0.50 * 255, 0.50 * 255, 0.50 * 255, 1.00 * 255)
disabled_button_color = (45, 45, 48)
disabled_button_hover_color = (45, 45, 48)
disabled_button_active_color = (45, 45, 48)
with dpg.theme() as disabled_theme:
    with dpg.theme_component(dpg.mvButton, enabled_state=False):
        dpg.add_theme_color(dpg.mvThemeCol_Text, disabled_color, category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_Button, disabled_button_color, category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, disabled_button_hover_color, category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, disabled_button_active_color, category=dpg.mvThemeCat_Core)
    dpg.bind_theme(disabled_theme)

# Set main viewport settings
dpg.create_viewport(title='Comic Translate v1.0', width=400, height=500)

# Primary Window
with dpg.window(width=420, height=560, tag="primary_window"):
    with dpg.menu_bar():
        
        with dpg.menu(label= "File", tag = "file_menu_title"):
            with dpg.menu(label= "Import", tag = "import_menu_title"):
                with dpg.menu(label= "Comic", tag = "import_comic_menu_title"):
                    dpg.add_menu_item(label="Images", callback=lambda: import_images(state_manager), tag = "images_menu_item_title")
                    dpg.add_menu_item(label="CBR/CBZ/CB7/CBT", callback=lambda: import_cbr_et_al(state_manager), tag = "cbr_cbz_menu_item_title")
                    dpg.add_menu_item(label="Pdf/Epub", callback=lambda: import_ebook(state_manager), tag = "ebook_menu_item_title")
                dpg.add_menu_item(label="Font", callback=import_font, user_data="font_dropdown", tag = "import_font_menu_item_title")
            
            dpg.add_menu_item(label="Save As", callback=lambda: dpg.configure_item("save_as", show=True), tag = "save_as_menu_item_title")

        with dpg.menu(label="Settings", tag = "settings_menu_title"):
            with dpg.menu(label="Language", tag = "language_menu_title"):
                dpg.add_menu_item(label='한국어', callback=lambda: state_manager.lang_change_process('ko'), tag = 'ko_lang_select')
                dpg.add_menu_item(label='English', callback=lambda: state_manager.lang_change_process('en'), tag = 'en_lang_select')
                dpg.add_menu_item(label='Français', callback=lambda: state_manager.lang_change_process('fr'), tag = 'fr_lang_select')
                dpg.add_menu_item(label='日本語', callback=lambda: state_manager.lang_change_process('ja'), tag = 'ja_lang_select')
                dpg.add_menu_item(label='简体中文', callback=lambda: state_manager.lang_change_process('zh-CN'), tag = 'zh-CN_lang_select')
                dpg.add_menu_item(label='繁體中文', callback=lambda: state_manager.lang_change_process('zh-TW'), tag = 'zh-TW_lang_select')
                dpg.add_menu_item(label='русский', callback=lambda: state_manager.lang_change_process('ru'), tag = 'ru_lang_select')
                dpg.add_menu_item(label='Deutsch', callback=lambda: state_manager.lang_change_process('de'), tag = 'de_lang_select')
                dpg.add_menu_item(label='Nederlands', callback=lambda: state_manager.lang_change_process('nl'), tag = 'nl_lang_select')
                dpg.add_menu_item(label='Español', callback=lambda: state_manager.lang_change_process('es'), tag = 'es_lang_select')
                dpg.add_menu_item(label='Italiano', callback=lambda: state_manager.lang_change_process('it'), tag = 'it_lang_select')

                dpg.bind_item_font('ko_lang_select', ko_font)
                dpg.bind_item_font('ja_lang_select', ja_font)
                dpg.bind_item_font('zh-CN_lang_select', ch_sim_font)
                dpg.bind_item_font('zh-TW_lang_select', ch_tr_font)
                for lng in ['en_lang_select', 'it_lang_select', 'es_lang_select', 'nl_lang_select', 'de_lang_select', 'ru_lang_select', 'fr_lang_select']:
                    dpg.bind_item_font(lng, latin_cyrillic_font)

            with dpg.menu(label="Set Credentials", tag = "set_credentials_menu_title"):
                dpg.add_menu_item(label="GPT", callback=lambda: dpg.configure_item("gpt_credentials", show=True), tag = "gpt_set_credentials_menu_item_title")
                dpg.add_menu_item(label="Microsoft", callback=lambda: dpg.configure_item("microsoft_credentials", show=True), tag = "microsoft_set_credentials_menu_item_title")
                dpg.add_menu_item(label="Google", callback=lambda: dpg.configure_item("google_credentials", show=True), tag = "google_set_credentials_menu_item_title")
                dpg.add_menu_item(label="DeepL", callback=lambda: dpg.configure_item("deepl_credentials", show=True), tag = "deepl_set_credentials_menu_item_title")
                dpg.add_menu_item(label="Claude", callback=lambda: dpg.configure_item("claude_credentials", show=True), tag = "claude_set_credentials_menu_item_title")
                dpg.add_menu_item(label="Gemini", callback=lambda: dpg.configure_item("gemini_credentials", show=True), tag = "gemini_set_credentials_menu_item_title")
                dpg.add_menu_item(label="Yandex", callback=lambda: dpg.configure_item("yandex_credentials", show=True), tag = "yandex_set_credentials_menu_item_title")

            dpg.add_menu_item(label="GPT Prompt", callback=lambda: dpg.configure_item("gpt_prompts", show=True), tag = "gpt_prompts_menu_item_title")

            with dpg.menu(label="Text Rendering", tag = "text_rendering_menu_title"):
                dpg.add_menu_item(label="Adjust TextBlocks", callback=lambda: dpg.configure_item("adjust_textblocks", show=True), tag = "adjust_textblocks_menu_item_title")
                dpg.add_menu_item(label="Text Alignment", callback=lambda: dpg.configure_item("text_alignment", show=True), tag = "text_alignment_menu_item_title")
                dpg.add_menu_item(label="Font", callback=lambda: dpg.configure_item("font", show=True), tag = "font_menu_item_title") 

            dpg.add_checkbox(label="Use GPU", tag = "use_gpu_checkbox")
            dpg.add_checkbox(label="Export raw text", tag = "export_raw_text_checkbox")
            dpg.add_checkbox(label="Export translated text", tag = "export_translated_text_checkbox")
            dpg.add_checkbox(label="Preview Annotated Image", tag = "preview_annot_img_checkbox")
            dpg.add_checkbox(label="Preview Inpainted Image", tag = "preview_inpainted_img_checkbox")
            dpg.add_checkbox(label="Export Annotated Image", tag = "export_annot_img_checkbox")
            dpg.add_checkbox(label="Export Inpainted Image", tag = "export_inpainted_img_checkbox")

            
    dpg.add_text("Source Language", tag = "source_lang_dropdown_title")
    dpg.add_combo(items=supported_source_languages, width=250, tag="source_lang_dropdown", callback=lambda: on_combo_change(state_manager))

    dpg.add_text("Target Language", tag="target_lang_dropdown_title")
    dpg.add_combo(items=supported_target_languages, width=250, tag="target_lang_dropdown", callback=lambda: on_combo_change(state_manager))
    
    dpg.add_checkbox(label="Render Text in Upper Case", tag = "upper_case_checkbox")

    if not os.path.exists(font_folder_path):
        os.mkdir(font_folder_path)

    dpg.add_text("Font", tag = "font_dropdown_title")
    font_combobox_id = dpg.add_combo(width=250, tag = "font_dropdown")
    set_font_list(font_folder_path, font_combobox_id)
            
    dpg.add_text("Translator", tag = "translator_dropdown_title")
    dpg.add_combo(items=supported_translators, width=250, tag = "translator_dropdown", callback=lambda: on_combo_change(state_manager))

    dpg.add_text("OCR", tag = "ocr_dropdown_title")
    dpg.add_combo(items=supported_ocr, width=250, tag = "ocr_dropdown", callback=lambda: on_combo_change(state_manager))

    dpg.add_progress_bar(tag = "progress_bar", default_value=0, width=250)
    with dpg.tooltip("progress_bar", tag = "progress_bar_tooltip_window"):
        dpg.add_text("Progress Bar", tag = "progress_bar_hint")
    dpg.hide_item("progress_bar")
    dpg.hide_item("progress_bar_hint")
    dpg.configure_item("progress_bar_tooltip_window", show=False)

    dpg.add_text("", tag = "progress_bar_text")
    dpg.hide_item("progress_bar_text")

    with dpg.group(horizontal=True):
        dpg.add_button(label="Translate", callback =lambda: start_process(state_manager), width=120, height=30, tag = "translate_button")
        dpg.add_button(label="Cancel", callback = stop_process, width=120, height=30, tag = "cancel_translation_button")
        dpg.hide_item("cancel_translation_button")

# Secondary Windows, Modal

# Confirm Imports
with dpg.window(modal=True, show=False, tag="import_confirmed", no_title_bar=True):
    dpg.add_text("Imported!", tag = "import_confirmed_title")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("import_confirmed", show=False), tag = "import_confirmed_ok")

with dpg.window(modal=True, show=False, tag="import_not_confirmed", no_title_bar=True):
    dpg.add_text("Nothing was Imported", tag = "import_not_confirmed_title")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("import_not_confirmed", show=False), tag = "import_not_confirmed_ok")

# Set Credentials for External Resources
# GPT
with dpg.window(modal=True, show=False, tag="gpt_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "gpt_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "gpt_api_key")

    dpg.add_checkbox(label="Save Key", tag = "save_keys_for_gpt_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("gpt_credentials", show=False), tag = "gpt_api_key_ok")

# Claude
with dpg.window(modal=True, show=False, tag="claude_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "claude_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "claude_api_key")

    dpg.add_checkbox(label="Save Key", tag = "save_keys_for_claude_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("claude_credentials", show=False), tag = "claude_api_key_ok")

# Gemini
with dpg.window(modal=True, show=False, tag="gemini_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "gemini_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "gemini_api_key")

    dpg.add_checkbox(label="Save Key", tag = "save_keys_for_gemini_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("gemini_credentials", show=False), tag = "gemini_api_key_ok")

# Yandex
with dpg.window(modal=True, show=False, tag="yandex_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "yandex_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "yandex_api_key")

    dpg.add_checkbox(label="Save Key", tag = "save_keys_for_yandex_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("yandex_credentials", show=False), tag = "yandex_api_key_ok")

# DeepL
with dpg.window(modal=True, show=False, tag="deepl_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "deepl_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "deepl_api_key")

    dpg.add_checkbox(label="Save Key", tag = "save_keys_for_deepl_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("deepl_credentials", show=False), tag = "deepl_api_key_ok")

# Microsoft
with dpg.window(modal=True, show=False, tag="microsoft_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "microsoft_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "microsoft_api_key")
    
    dpg.add_text("Endpoint URL", tag = "microsoft_endpoint_url_title")
    dpg.add_input_text(password=True, width=250, tag = "microsoft_endpoint_url")

    dpg.add_checkbox(label="Save", tag = "save_keys_for_microsoft_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("microsoft_credentials", show=False), tag = "microsoft_api_key_ok")

# Google (OCR)
with dpg.window(modal=True, show=False, tag="google_credentials", no_title_bar=True):
    dpg.add_text("API Key", tag = "google_api_key_title")
    dpg.add_input_text(password=True, width=250, tag = "google_api_key")

    dpg.add_checkbox(label="Save Key", tag = "save_keys_for_google_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("google_credentials", show=False), tag = "google_api_key_ok")

# Edit GPT Prompts
with dpg.window(modal=True, show=False, tag="gpt_prompts", no_title_bar=True):
    dpg.add_text("Extra Context", tag="gpt_extra_context_title")
    dpg.add_input_text(height=200, width=200, multiline=True, tag = "gpt_extra_context")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("gpt_prompts", show=False), tag = "gpt_prompts_ok")

# Textblocks
with dpg.window(modal=True, show=False, tag="adjust_textblocks", no_title_bar=True):
    dpg.add_text("Width Adjustment Percentage", tag = "width_adjustment_title")
    dpg.add_input_int(tag = "width_adjustment_number", step=1)
    dpg.set_value("width_adjustment_number", 0)
    with dpg.tooltip("width_adjustment_title"):
        dpg.add_text("Controls how much the width\nshould be expanded or reduced\nby. A value of 100 will double\nthe width while -100 will halve it.\nExpansion and Reduction\noccur equally on both sides.", tag = "width_adjustment_hint")

    dpg.add_text("Height Adjustment Percentage", tag = "height_adjustment_title")
    dpg.add_input_int(tag = "height_adjustment_number", step=1)
    dpg.set_value("height_adjustment_number", 0)
    with dpg.tooltip("height_adjustment_title"):
        dpg.add_text("Controls how much the height\nshould be expanded or reduced\nby. A value of 100 will double\nthe height while -100 will halve it.\nExpansion and Reduction\noccur equally on both sides.", tag = "height_adjustment_hint")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("adjust_textblocks", show=False), tag = "adjust_textblocks_ok")

# Text Alignment
current_language = state_manager.lang_settings.get_curr_lang()
loc = open_lang_file(current_language)
alignment_mappings = loc["alignment_mappings"]

with dpg.window(modal=True, show=False, tag="text_alignment", no_title_bar=True):
    dpg.add_text("Text Alignment", tag = "text_alignment_title")
    dpg.add_combo(items=['center', 'left', 'right'], width=150, tag="text_alignment_dropdown")
    mapped = get_key(alignment_mappings, 'center')
    dpg.configure_item("text_alignment_dropdown", default_value=mapped)

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("text_alignment", show=False), tag = "text_alignment_ok")

# Font
with dpg.window(show=False, tag="font", no_title_bar=True, width = 320, height = 350):
    dpg.add_text("Font Color", tag = "font_color_title")
    dpg.add_color_picker(default_value=(0, 0, 0, 255), tag = "font_color")
   
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("font", show=False), tag = "font_ok") 

# GPT-4-Vision Warning
with dpg.window(label="CAUTION!", modal=True, show=False, tag="gpt_for_ocr_warning", no_title_bar=False):
    dpg.add_text("The Default OCR for French,\nGerman, Dutch, Spanish, Italian\n and Russian is GPT-4-Vision.\nThis will require an API\nKey and incur costs. Expect\n about $0.04 USD per page.\n Go to Settings > Set Credentials > GPT\nto set one if you haven't already.", tag = "gpt_ocr_caution_message")
    dpg.add_checkbox(label="Don't tell me next time", tag = "stop_gpt_ocr_warning_checkbox")

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("gpt_for_ocr_warning", show=False), tag = "gpt_ocr_warning_ok")

# Error Windows
# api key for translator
with dpg.window(label="ERROR!", modal=True, show=False, tag="api_key_translator_error", no_title_bar=False):
    dpg.add_text("An API Key is required for\nthe selected translator. Go to\nSettings > Set Credentials to set one", tag = "api_key_translator_error_message")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("api_key_translator_error", show=False), tag = "api_key_translator_error_ok")

# api key for ocr
with dpg.window(label="ERROR!", modal=True, show=False, tag="api_key_ocr_error", no_title_bar=False):
    dpg.add_text("An API Key is required\nfor the selected OCR. Go to\nSettings > Set Credentials to set one", tag = "api_key_ocr_error_message")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("api_key_ocr_error", show=False), tag = "api_key_ocr_error_ok")

# api key for gpt-4v ocr
with dpg.window(label="ERROR!", modal=True, show=False, tag="api_key_ocr_gpt-4v_error", no_title_bar=False):
    dpg.add_text("Default Ocr for the selected\nSource Language is GPT-4-Vision\nwhich requires an API Key. Go to\nSettings > Set Credentials > GPT to set one", tag = "api_key_ocr_gpt-4v_error_message")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("api_key_ocr_gpt-4v_error", show=False), tag = "api_key_ocr_gpt-4v_error_ok")

# endpoint url
with dpg.window(label="ERROR!", modal=True, show=False, tag="endpoint_url_error", no_title_bar=False):
    dpg.add_text("An Endpoint Url is required for\n Microsoft OCR. Go to Settings >\nSet Credentials > Microsoft to set one", tag = "endpoint_url_error_message")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("endpoint_url_error", show=False), tag = "endpoint_url_error_ok")

# DeepL for Traditional Chinese
with dpg.window(label="ERROR!", modal=True, show=False, tag="deepl_ch_error", no_title_bar=False):
    dpg.add_text("DeepL does not translate\nto Traditional Chinese", tag = "deepl_ch_error_message")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("deepl_ch_error", show=False), tag = "deepl_ch_error_ok")

# Translation Complete Window
with dpg.window(modal=True, show=False, tag="translation_complete", no_title_bar=True):
    dpg.add_text("Comic has been Translated!", tag = "translation_complete_title")
    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("translation_complete", show=False), tag = "translation_complete_ok")

# Save As
with dpg.window(show=False, tag = "save_as", no_title_bar=True):
    with dpg.group(horizontal=True):
        dpg.add_text("Save PDF as", tag = "save_pdf_as_title")
        dpg.add_combo(items=['.pdf', '.epub', '.cbz', '.cb7'], width = 70, tag="save_pdf_as_dropdown")
        dpg.configure_item("save_pdf_as_dropdown", default_value = '.pdf')
    
    with dpg.group(horizontal=True):
        dpg.add_text("Save CBZ as", tag = "save_cbz_as_title")
        dpg.add_combo(items=['.cbz', '.cb7', '.pdf', '.epub'], width = 70, tag="save_cbz_as_dropdown")
        dpg.configure_item("save_cbz_as_dropdown", default_value = '.cbz')

    with dpg.group(horizontal=True):
        dpg.add_text("Save CBR as", tag = "save_cbr_as_title")
        dpg.add_combo(items=['.cbz', '.cb7', '.pdf', '.epub'], width = 70, tag="save_cbr_as_dropdown")
        dpg.configure_item("save_cbr_as_dropdown", default_value = '.cbz')

    with dpg.group(horizontal=True):
        dpg.add_text("Save CB7 as", tag = "save_cb7_as_title")
        dpg.add_combo(items=['.cb7', '.cbz', '.pdf', '.epub'], width = 70, tag="save_cb7_as_dropdown")
        dpg.configure_item("save_cb7_as_dropdown", default_value = '.cb7')

    with dpg.group(horizontal=True):
        dpg.add_text("Save CBT as", tag = "save_cbt_as_title")
        dpg.add_combo(items=['.cbz', '.cb7', '.pdf', '.epub'], width = 70, tag="save_cbt_as_dropdown")
        dpg.configure_item("save_cbt_as_dropdown", default_value = '.cbz')

    with dpg.group(horizontal=True):
        dpg.add_text("Save EPUB as", tag = "save_epub_as_title")
        dpg.add_combo(items=['.epub', '.pdf', '.cbz', '.cb7'], width = 70, tag="save_epub_as_dropdown")
        dpg.configure_item("save_epub_as_dropdown", default_value = '.epub')

    dpg.add_button(label="OK", width=75, callback=lambda: dpg.configure_item("save_as", show=False), tag = "save_as_ok") 


current_language = state_manager.lang_settings.get_curr_lang()
state_manager.change_font(current_language)
saved_state = state_manager.load_state()
state_manager.apply_state(saved_state)
if current_language != 'en':
    state_manager.change_language(current_language)
dpg.set_exit_callback(state_manager.save_state)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("primary_window", True)
dpg.start_dearpygui()
dpg.destroy_context()

















