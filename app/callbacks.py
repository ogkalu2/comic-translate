import dearpygui.dearpygui as dpg
from tkinter import filedialog
import os, shutil
from .state_manager import AppStateManager, open_lang_file

# Callback functions for interactions
# Show relevant selection warning
def on_combo_change(state_manager: AppStateManager):
    current_language = state_manager.lang_settings.get_curr_lang()
    loc = open_lang_file(current_language)
    lang_mappings = loc["lang_mappings"]
    ocr_mappings =  loc["ocr_mappings"]

    selected_ocr = dpg.get_value("ocr_dropdown")
    selected_source_lang = dpg.get_value("source_lang_dropdown")
    
    if dpg.get_value("stop_gpt_ocr_warning_checkbox") == False:
        if selected_ocr: 
            # If the OCR is the "Default" Option
            if ocr_mappings[selected_ocr] == "Default": 
                # if it is among the languages that use GPT-4-Vision as the default
                if lang_mappings[selected_source_lang] in ["Russian", "French", "German", "Dutch", "Spanish", "Italian"]:
                    # Show Warning
                    dpg.configure_item("gpt_for_ocr_warning", show=True)

def import_images(state_manager: AppStateManager):
    file_paths = filedialog.askopenfilenames(title="Choose input image(s)", filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp")])
    if file_paths:
        state_manager.user_data.set_data("file_paths", file_paths)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

def import_cbr_et_el(state_manager: AppStateManager):
    file = filedialog.askopenfilename(filetypes=[("Comic Book Archive files", "*.cbr *.cbz *.cb7 *.cbt")])
    if file:
        state_manager.user_data.set_data("file_paths", file)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

def import_ebook(state_manager: AppStateManager):
    file = filedialog.askopenfilename(filetypes=[("Ebook", "*.pdf *.epub")])
    if file:
        state_manager.user_data.set_data("file_paths", file)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)

def set_font_list(font_folder_path, combobox_id):
    font_files = [f for f in os.listdir(font_folder_path) if f.endswith((".ttf", ".ttc", ".otf", ".woff", ".woff2"))]
    dpg.configure_item(combobox_id, items=font_files)

def import_font(sender, app_data, user_data):
    file_path = filedialog.askopenfilename(filetypes=[("Font files", "*.ttf *.ttc *.otf *.woff *.woff2")])
    if file_path:
        font_folder_path = os.path.join(os.getcwd(), "fonts")
        if not os.path.exists(font_folder_path):
            os.makedirs(font_folder_path)
        shutil.copy(file_path, font_folder_path)
        set_font_list(font_folder_path, user_data)
        # Set the value of the combobox to the newly imported font filename
        filename = os.path.basename(file_path)
        dpg.set_value(user_data, filename)
        dpg.configure_item("import_confirmed", show=True)
    else:
        dpg.configure_item("import_not_confirmed", show=True)