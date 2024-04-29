import dearpygui.dearpygui as dpg
import sys
from ultralytics import YOLO
import os, string, shutil
import cv2
import threading
from threading import Thread
import tempfile
from datetime import datetime
from matplotlib import pyplot as plt

from modules.inpainting.lama import LaMa
from modules.inpainting.schema import Config
from app.archives import extract_archive, make
from modules.utils import TextBlock, sort_regions, visualize_textblocks
from app.localizations.progress_mappings import progress_mappings
from modules.utils.detection import combine_results, make_bubble_mask, bubble_interior_bounds
from modules.rendering.render import draw_text
from modules.translator import Translator
from app.state_manager import AppStateManager, open_lang_file, all_loc_mappings
from app.callbacks import show_error_mac
from modules.utils.pipeline_utils import *
from modules.utils.translator_utils import get_client, get_api_key, get_raw_translation, get_raw_text, format_translations


class ProcessThread(Thread):
    def __init__(self, target, args=(), kwargs=None, error_callback=None, **extra_kwargs):
        super().__init__(target=target, args=args, kwargs=kwargs if kwargs else {}, **extra_kwargs)
        self.error_callback = error_callback

    def run(self):
        try:
            if self._target:
                self._target(*self._args, **self._kwargs)
        except Exception as e:
            if self.error_callback:
                self.error_callback(e)
            else:
                raise


# Shared variable for signaling the thread to stop
stop_event = threading.Event()

def stop_process():
    global stop_event
    stop_event.set()

def start_process(SM: AppStateManager):
    global stop_event
    stop_event.clear()
    process_thread = ProcessThread(target=process, error_callback=error_handler, args=(SM,), daemon=True)
    process_thread.start()

def error_handler(exception):
    end_process_callback()
    print(f"An Error occurred: {exception}.\n\nLast progress at {dpg.get_value('progress_bar_text')}")

    oper_system = sys.platform
    if oper_system == 'darwin':
        show_error_mac(exception)
    else:
        from tkinter import messagebox
        messagebox.showerror('Error', f"{exception}.\n\nLast progress at {dpg.get_value('progress_bar_text')}")

def end_process_callback():
    dpg.hide_item("progress_bar_text")
    dpg.hide_item("progress_bar")
    dpg.hide_item("progress_bar_hint")
    dpg.configure_item("progress_bar_tooltip_window", show=False)
    dpg.hide_item("cancel_translation_button")
    dpg.enable_item("translate_button")

def process(SM: AppStateManager):
    global stop_event
    file_paths =  SM.user_data.get_data("file_paths")
    if not file_paths:
        dpg.configure_item("import_not_confirmed", show=True)
        return

    save_to_cbr_et_al = False
    temp_dir = ''

    if isinstance(file_paths, str) and file_paths.lower().endswith(('.cbr', '.cbz', '.cbt', '.cb7', '.pdf', '.epub')):
        save_to_cbr_et_al = True
        cbr_et_al_directory = os.path.dirname(file_paths)
        cbr_et_al_base_name = os.path.splitext(os.path.basename(file_paths))[0]
        cbr_et_al_extension = os.path.splitext(file_paths)[1]
        temp_dir = tempfile.mkdtemp()
        file_paths = extract_archive(file_paths, temp_dir)
    
    current_language = SM.lang_settings.get_curr_lang()
    translations = open_lang_file(current_language)
    lang_mappings, ocr_mappings, translator_mappings, alignment_mappings = all_loc_mappings(translations)

    # Options
    en_source_lang = lang_mappings[dpg.get_value("source_lang_dropdown")]
    en_target_lang = lang_mappings[dpg.get_value("target_lang_dropdown")]
    upper_case = dpg.get_value("upper_case_checkbox")
    font = dpg.get_value("font_dropdown")
    en_translator = translator_mappings[dpg.get_value("translator_dropdown")]
    en_ocr = ocr_mappings[dpg.get_value("ocr_dropdown")]
    open_ai_api_key = dpg.get_value("gpt_api_key")
    anthropic_ai_api_key = dpg.get_value("claude_api_key")
    gemini_api_key = dpg.get_value("gemini_api_key")
    yandex_api_key = dpg.get_value("yandex_api_key")
    deepl_api_key = dpg.get_value("deepl_api_key")
    google_api_key = dpg.get_value("google_api_key")
    microsoft_api_key = dpg.get_value("microsoft_api_key")
    microsoft_endpoint_url = dpg.get_value("microsoft_endpoint_url")
    preview_annot_img = dpg.get_value("preview_annot_img_checkbox")
    preview_inpainted_img = dpg.get_value("preview_inpainted_img_checkbox")
    use_gpu = dpg.get_value("use_gpu_checkbox")
    export_rw_txt = dpg.get_value("export_raw_text_checkbox")
    export_tr_txt = dpg.get_value("export_translated_text_checkbox")
    export_annot_img = dpg.get_value("export_annot_img_checkbox")
    export_inpainted_img = dpg.get_value("export_inpainted_img_checkbox")
    extra_context = dpg.get_value("gpt_extra_context")
    width_adjust_percent = dpg.get_value("width_adjustment_number")
    height_adjust_percent = dpg.get_value("height_adjustment_number")
    en_alignment = alignment_mappings[dpg.get_value("text_alignment_dropdown")]
    font_color = rgba2hex(dpg.get_value("font_color"))

    src_lng_cd, trg_lng_cd = get_language_codes(en_source_lang, en_target_lang)
    font_path = f'fonts/{font}'

    # Error Handling
    if en_translator == "DeepL" and not deepl_api_key:
        dpg.configure_item("api_key_translator_error", show=True)
        return
    
    if en_translator == "Yandex" and not yandex_api_key:
        dpg.configure_item("api_key_translator_error", show=True)
        return
    
    if 'GPT' in en_translator and not open_ai_api_key:
        dpg.configure_item("api_key_translator_error", show=True)
        return
    
    if 'Gemini' in en_translator and not gemini_api_key:
        dpg.configure_item("api_key_translator_error", show=True)
        return
    
    if 'Claude' in en_translator and not anthropic_ai_api_key:
        dpg.configure_item("api_key_translator_error", show=True)
        return
    
    if en_ocr == "Microsoft OCR" and not microsoft_api_key:
        dpg.configure_item("api_key_ocr_error", show=True)
        return
    
    if en_ocr == "Google Cloud Vision" and not google_api_key:
        dpg.configure_item("api_key_ocr_error", show=True)
        return
    
    if en_ocr == "Microsoft OCR" and not microsoft_endpoint_url:
        dpg.configure_item("endpoint_url_error", show=True)
        return

    if en_source_lang in ["French", "German", "Dutch", "Russian", "Spanish", "Italian"] and en_ocr == "Default":
        if not open_ai_api_key:
            dpg.configure_item("api_key_ocr_gpt-4v_error", show=True)
            return
 
    if en_target_lang == "Traditional Chinese" and en_translator == "DeepL":
        dpg.configure_item("deepl_ch_error", show=True)
        return

    # Setting State
    if use_gpu:
        device = 'cuda'
        yolo_device = 0
    else:
        device = 'cpu'
        yolo_device = 'cpu'

    client = get_client(en_translator)
    api_key = get_api_key(en_translator)

    if en_source_lang in ["French", "German", "Dutch", "Russian", "Spanish", "Italian"] and en_ocr == "Default":
        gpt_ocr = True
    else:
        gpt_ocr = False
                    
    microsoft_ocr = True if en_ocr == "Microsoft OCR" else False
    google_ocr = True if en_ocr == "Google Cloud Vision" else False
    
    # Start 
    dpg.disable_item("translate_button")
    dpg.show_item("cancel_translation_button")

    dpg.show_item("progress_bar")
    dpg.configure_item("progress_bar_tooltip_window", show=True)
    dpg.show_item("progress_bar_hint")

    timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
    for index, image_path in enumerate(file_paths):
        # Progress Bar Start
        total_images = len(file_paths)
        i = 0
        dpg.set_value("progress_bar", i)

        # Copies image and remove non-unicode characters
        if not image_path.isascii():
            name = ''.join(c for c in image_path if c in string.printable)
            dir_name = ''.join(c for c in os.path.dirname(image_path) if c in string.printable)

            os.makedirs(dir_name, exist_ok=True)

            if os.path.splitext(os.path.basename(name))[1] == '':
                basename = ""
                ext = os.path.splitext(os.path.basename(name))[0]
            else:
                basename = os.path.splitext(os.path.basename(name))[0]
                ext = os.path.splitext(os.path.basename(name))[1]
                
            sanitized_path = os.path.join(dir_name, basename + str(index) + ext)
            try:
                shutil.copy(image_path, sanitized_path)
                image_path = sanitized_path
            except IOError as e:
                print(f"An error occurred while copying or deleting the file: {e}")

        base_name = os.path.splitext(os.path.basename(image_path))[0]
        directory = os.path.dirname(image_path)
        extension = os.path.splitext(image_path)[1]

        img = cv2.imread(image_path)
        if img is None:
            continue

        dpg.show_item("progress_bar_text")
        dpg.set_value("progress_bar_text", progress_mappings('Forming TextBlocks', SM.lang_settings.get_curr_lang(), index, total_images))

        if stop_event.is_set():
            end_process_callback()
            return  
        
        # Forming TextBlocks
        h, w, c = img.shape
        # With extreme ratios (e.g korean webtoons), best inference size is image size. Else, training size
        size = (h,w) if h >= w *5 else 1024

        bubble_detection = YOLO('models/detection/comic-speech-bubble-detector.pt')
        text_segmentation = YOLO('models/detection/comic-text-segmenter.pt')

        bble_detec_result = bubble_detection(img, device=yolo_device, imgsz=size, conf=0.1, verbose=False)[0] 
        txt_seg_result = text_segmentation(img, device=yolo_device, imgsz=size, conf=0.1, verbose=False)[0]

        combined = combine_results(bble_detec_result, txt_seg_result)

        blk_list: List[TextBlock] = []
        for txt_bbox, bble_bbox, txt_seg_points, txt_class in combined:
            text_region = TextBlock(txt_bbox, txt_seg_points, bble_bbox, txt_class, alignment=en_alignment, source_lang=src_lng_cd)
            blk_list.append(text_region)
        if blk_list:
            blk_list = sort_regions(blk_list)

        # OCR
        if en_source_lang == 'Chinese' and (not microsoft_ocr and not google_ocr):
            ocr_blk_list_paddle(img, blk_list)
        elif microsoft_ocr:
            ocr_blk_list_microsoft(img, blk_list, api_key=microsoft_api_key, endpoint=microsoft_endpoint_url)
        elif google_ocr:
            ocr_blk_list_google(img, blk_list, google_api_key)
        elif gpt_ocr:
            ocr_blk_list_gpt(img, blk_list, client)
        else:
            ocr_blk_list(img, blk_list, en_source_lang, device)
        
        if len(blk_list) == 0:
            if save_to_cbr_et_al:
                cv2.imwrite(os.path.join(directory, f"{base_name}_translated{extension}"), img)
            else:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_translated{extension}"), img)

        i+=0.2
        dpg.set_value("progress_bar", i)

        # Clean Image of text
        # Load the inpainting model
        if stop_event.is_set():
            end_process_callback()
            return 
        dpg.set_value("progress_bar_text", progress_mappings('Text Removal', SM.lang_settings.get_curr_lang(), index, total_images))
        

        inpainter = LaMa(device)
        conf = Config(hd_strategy="Resize", hd_strategy_resize_limit=640)

        msk = generate_mask(img, blk_list)

        inpaint_input_img = inpainter(img, msk, conf)
        inpaint_input_img = cv2.convertScaleAbs(inpaint_input_img) 
        inpaint_input_img = cv2.cvtColor(inpaint_input_img, cv2.COLOR_BGR2RGB)

        i+=0.2
        dpg.set_value("progress_bar", i)

        if preview_inpainted_img:
            plt.figure(figsize=(7, 7))
            plt.axis('off')
            plt.imshow(cv2.cvtColor(inpaint_input_img, cv2.COLOR_BGR2RGB))
            plt.show()
        
        # Saving the Inpainted Image
        if export_inpainted_img:
            if save_to_cbr_et_al:
                path = os.path.join(cbr_et_al_directory, f"comic_translate_{timestamp}", f"{cbr_et_al_base_name}_cleaned_images")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_cleaned{extension}"), inpaint_input_img)
            else:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "cleaned_images")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_cleaned{extension}"), inpaint_input_img)

        if stop_event.is_set():
            end_process_callback()
            return 
        dpg.set_value("progress_bar_text", progress_mappings('Translating', SM.lang_settings.get_curr_lang(), index, total_images))
        
        # Get Translations/ Export if selected
        entire_raw_text = get_raw_text(blk_list)
        translator = Translator(client, api_key)
        translator.translate(blk_list, en_translator, en_target_lang, src_lng_cd, trg_lng_cd, img, inpaint_input_img, extra_context)    
        entire_translated_text = get_raw_translation(blk_list)

        # Saving the Raw Texts
        if export_rw_txt:
            if save_to_cbr_et_al:
                path = os.path.join(cbr_et_al_directory, f"comic_translate_{timestamp}", f"{cbr_et_al_base_name}_raw_texts")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_raw.txt"), 'w', encoding='UTF-8')
                file.write(entire_raw_text)
            else:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "raw_texts")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_raw.txt"), 'w', encoding='UTF-8')
                file.write(entire_raw_text)
        
        # Saving the Translated Texts
        if export_tr_txt:
            if save_to_cbr_et_al:
                path = os.path.join(cbr_et_al_directory, f"comic_translate_{timestamp}", f"{cbr_et_al_base_name}_translated_texts")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_translated.txt"), 'w', encoding='UTF-8')
                file.write(entire_translated_text)
            else:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_texts")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_translated.txt"), 'w', encoding='UTF-8')
                file.write(entire_translated_text)
        
        i+=0.2
        dpg.set_value("progress_bar", i)
        dpg.set_value("progress_bar_text", progress_mappings('Rendering Text', SM.lang_settings.get_curr_lang(), index, total_images))

        if stop_event.is_set():
            end_process_callback()
            return 
        format_translations(blk_list, trg_lng_cd, upper_case=upper_case)

        # Using Speech Bubble detection to find best Text Render Area
        for blk in blk_list:
            if blk.text_class == 'text_bubble':
                bx1, by1, bx2, by2 = blk.bubble_xyxy
                bubble_clean_frame = inpaint_input_img[by1:by2, bx1:bx2]
                bubble_mask = make_bubble_mask(bubble_clean_frame)
                text_draw_bounds = bubble_interior_bounds(bubble_mask)

                bdx1, bdy1, bdx2, bdy2 = text_draw_bounds

                bdx1 += bx1
                bdy1 += by1

                bdx2 += bx1
                bdy2 += by1

                if en_source_lang == 'Japanese':
                    blk.xyxy[:] = [bdx1, bdy1, bdx2, bdy2]
                else:
                    tx1, ty1, tx2, ty2  = blk.xyxy

                    nx1 = max(bdx1, tx1)
                    nx2 = min(bdx2, tx2)
                    
                    blk.xyxy[:] = [nx1, ty1, nx2, ty2]

        adjust_blks_size(blk_list, img.shape, width_adjust_percent, height_adjust_percent)

        annot_img = img.copy()
        annot_img = visualize_textblocks(annot_img, blk_list)

        # Show all detected text, textblocks
        if preview_annot_img:
            plt.figure(figsize=(7, 7))
            plt.axis('off')
            plt.imshow(cv2.cvtColor(annot_img, cv2.COLOR_BGR2RGB))
            plt.show()

        if export_annot_img:
            if save_to_cbr_et_al:
                path = os.path.join(cbr_et_al_directory, f"comic_translate_{timestamp}", f"{cbr_et_al_base_name}_annotated_images")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_annot{extension}"), annot_img)
            else:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "annotated_images")
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_annot{extension}"), annot_img)
        
        if stop_event.is_set():
            end_process_callback()
            return 
        
        # Render Text
        rendered_image = draw_text(inpaint_input_img, blk_list, font_path, 40, colour=font_color)

        # Save Translated Image
        if save_to_cbr_et_al:
            cv2.imwrite(os.path.join(directory, f"{base_name}_translated{extension}"), rendered_image)
        else:
            path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images")
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            cv2.imwrite(os.path.join(path, f"{base_name}_translated{extension}"), rendered_image)

        i+=0.4
        dpg.set_value("progress_bar", i)
    
    if save_to_cbr_et_al:
        save_as = {
        '.pdf': dpg.get_value('save_pdf_as_dropdown'),
        '.cbz': dpg.get_value('save_cbz_as_dropdown'),
        '.cbr': dpg.get_value('save_cbr_as_dropdown'),
        '.cbt': dpg.get_value('save_cbt_as_dropdown'),
        '.cb7': dpg.get_value('save_cb7_as_dropdown'),
        '.epub': dpg.get_value('save_epub_as_dropdown')
        }
        save_as_ext = save_as[cbr_et_al_extension.lower()]
        original_ext = cbr_et_al_extension
        make(original_ext, save_as_ext, temp_dir, cbr_et_al_directory, cbr_et_al_base_name, en_target_lang)

    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    end_process_callback()
    dpg.configure_item("translation_complete", show=True)
