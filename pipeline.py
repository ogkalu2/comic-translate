import os
import cv2, shutil
from datetime import datetime
from typing import List
from PySide6 import QtCore

from modules.detection import TextBlockDetector
from modules.ocr.ocr import OCRProcessor
from modules.translator import Translator
from modules.utils.textblock import TextBlock, sort_blk_list
from modules.rendering.render import get_best_render_area
from modules.utils.pipeline_utils import inpaint_map, get_config
from modules.rendering.render import draw_text, get_best_render_area
from modules.utils.pipeline_utils import generate_mask, get_language_code, set_alignment, is_directory_empty
from modules.utils.translator_utils import get_raw_translation, get_raw_text, format_translations
from modules.utils.archives import make

from app.ui.canvas.rectangle import MovableRectItem

class ComicTranslatePipeline:
    def __init__(self, main_page):
        self.main_page = main_page
        self.block_detector_cache = None
        self.inpainter_cache = None
        self.cached_inpainter_key = None
        self.ocr = OCRProcessor()

    def load_box_coords(self, blk_list: List[TextBlock]):
        self.main_page.image_viewer.clear_rectangles()
        if self.main_page.image_viewer.hasPhoto() and blk_list:
            for blk in blk_list:
                x1, y1, x2, y2 = blk.xyxy
                rect = QtCore.QRectF(x1, y1, x2 - x1, y2 - y1)
                rect_item = MovableRectItem(rect, self.main_page.image_viewer._photo)
                rect_item.signals.rectangle_changed.connect(self.main_page.handle_rectangle_change)
                self.main_page.image_viewer._rectangles.append(rect_item)

            rect = self.main_page.find_corresponding_rect(self.main_page.blk_list[0], 0.5)
            self.main_page.image_viewer.select_rectangle(rect)
            self.main_page.set_tool('box')

    def detect_blocks(self, load_rects=True):
        if self.main_page.image_viewer.hasPhoto():
            if self.block_detector_cache is None:
                device = 0 if self.main_page.settings_page.is_gpu_enabled() else 'cpu'
                self.block_detector_cache = TextBlockDetector('models/detection/comic-speech-bubble-detector.pt', 
                                                'models/detection/comic-text-segmenter.pt','models/detection/manga-text-detector.pt',
                                                 device)
            image = self.main_page.image_viewer.get_cv2_image()
            blk_list = self.block_detector_cache.detect(image)

            return blk_list, load_rects

    def on_blk_detect_complete(self, result): 
        blk_list, load_rects = result
        source_lang = self.main_page.s_combo.currentText()
        source_lang_english = self.main_page.lang_mapping.get(source_lang, source_lang)
        rtl = True if source_lang_english == 'Japanese' else False
        blk_list = sort_blk_list(blk_list, rtl)
        self.main_page.blk_list = blk_list
        if load_rects:
            self.load_box_coords(blk_list)


    def manual_inpaint(self):
        image_viewer = self.main_page.image_viewer
        settings_page = self.main_page.settings_page
        mask = image_viewer.get_mask_for_inpainting()
        image = image_viewer.get_cv2_image()

        if self.inpainter_cache is None or self.cached_inpainter_key != settings_page.get_tool_selection('inpainter'):
            device = 'cuda' if settings_page.is_gpu_enabled() else 'cpu'
            inpainter_key = settings_page.get_tool_selection('inpainter')
            InpainterClass = inpaint_map[inpainter_key]
            self.inpainter_cache = InpainterClass(device)
            self.cached_inpainter_key = inpainter_key

        config = get_config(settings_page)
        inpaint_input_img = self.inpainter_cache(image, mask, config)
        inpaint_input_img = cv2.convertScaleAbs(inpaint_input_img) 

        return inpaint_input_img
    
    def inpaint_complete(self, result):
        inpainted, original_image = result
        self.main_page.set_cv2_image(inpainted)
        # get_best_render_area(self.main_page.blk_list, original_image, inpainted)
    
    def inpaint(self):
        image = self.main_page.image_viewer.get_cv2_image()
        inpainted = self.manual_inpaint()
        return inpainted, image

    def inpaint_and_set(self):
        if self.main_page.image_viewer.hasPhoto() and self.main_page.image_viewer.has_drawn_elements():
            image = self.main_page.image_viewer.get_cv2_image()

            inpainted = self.manual_inpaint()
            self.main_page.set_cv2_image(inpainted)

            get_best_render_area(self.main_page.blk_list, image, inpainted)
            self.load_box_coords(self.main_page.blk_list)

    def OCR_image(self):
        source_lang = self.main_page.s_combo.currentText()
        if self.main_page.image_viewer.hasPhoto() and self.main_page.image_viewer._rectangles:
            image = self.main_page.image_viewer.get_cv2_image()
            # Print block length
            print("Block Length: ", len(self.main_page.blk_list))
            self.ocr.initialize(self.main_page, source_lang)
            self.ocr.process(image, self.main_page.blk_list)

    def translate_image(self):
        source_lang = self.main_page.s_combo.currentText()
        target_lang = self.main_page.t_combo.currentText()
        if self.main_page.image_viewer.hasPhoto() and self.main_page.blk_list:
            settings_page = self.main_page.settings_page
            image = self.main_page.image_viewer.get_cv2_image()
            extra_context = settings_page.get_llm_settings()['extra_context']

            translator = Translator(self.main_page, source_lang, target_lang)
            translator.translate(self.main_page.blk_list, image, extra_context)

            target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
            trg_lng_cd = get_language_code(target_lang_en)
            text_rendering_settings = settings_page.get_text_rendering_settings()
            upper_case = text_rendering_settings['upper_case']
            format_translations(self.main_page.blk_list, trg_lng_cd, upper_case=upper_case)

    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        image_save = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        cv2.imwrite(os.path.join(path, f"{base_name}_translated{extension}"), image_save)

    def log_skipped_image(self, directory, timestamp, image_path):
        with open(os.path.join(directory, f"comic_translate_{timestamp}", "skipped_images.txt"), 'a', encoding='UTF-8') as file:
            file.write(image_path + "\n")

    def batch_process(self):
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        total_images = len(self.main_page.image_files)

        for index, image_path in enumerate(self.main_page.image_files):

            # index, step, total_steps, change_name
            self.main_page.progress_update.emit(index, total_images, 0, 10, True)

            settings_page = self.main_page.settings_page
            source_lang = self.main_page.image_states[image_path]['source_lang']
            target_lang = self.main_page.image_states[image_path]['target_lang']

            target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
            trg_lng_cd = get_language_code(target_lang_en)
            
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            extension = os.path.splitext(image_path)[1]
            directory = os.path.dirname(image_path)

            archive_bname = ""
            for archive in self.main_page.file_handler.archive_info:
                images = archive['extracted_images']
                archive_path = archive['archive_path']

                for img_pth in images:
                    if img_pth == image_path:
                        directory = os.path.dirname(archive_path)
                        archive_bname = os.path.splitext(os.path.basename(archive_path))[0]

            image = cv2.imread(image_path)

            # Text Block Detection
            self.main_page.progress_update.emit(index, total_images, 1, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            if self.block_detector_cache is None:
                bdetect_device = 0 if self.main_page.settings_page.is_gpu_enabled() else 'cpu'
                self.block_detector_cache = TextBlockDetector('models/detection/comic-speech-bubble-detector.pt', 
                                                            'models/detection/comic-text-segmenter.pt', 'models/detection/manga-text-detector.pt', 
                                                            bdetect_device)
            
            blk_list = self.block_detector_cache.detect(image)

            self.main_page.progress_update.emit(index, total_images, 2, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            if blk_list:
                self.ocr.initialize(self.main_page, source_lang)
                try:
                    self.ocr.process(image, blk_list)
                except Exception as e:
                    error_message = str(e)
                    print(error_message)
                    self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                    self.main_page.image_skipped.emit(image_path, "OCR", error_message)
                    self.log_skipped_image(directory, timestamp, image_path)
                    continue
            else:
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.main_page.image_skipped.emit(image_path, "Text Blocks", "")
                self.log_skipped_image(directory, timestamp, image_path)
                continue

            self.main_page.progress_update.emit(index, total_images, 3, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            # Clean Image of text
            export_settings = settings_page.get_export_settings()

            if self.inpainter_cache is None or self.cached_inpainter_key != settings_page.get_tool_selection('inpainter'):
                device = 'cuda' if settings_page.is_gpu_enabled() else 'cpu'
                inpainter_key = settings_page.get_tool_selection('inpainter')
                InpainterClass = inpaint_map[inpainter_key]
                self.inpainter_cache = InpainterClass(device)
                self.cached_inpainter_key = inpainter_key

            config = get_config(settings_page)
            mask = generate_mask(image, blk_list)

            self.main_page.progress_update.emit(index, total_images, 4, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            inpaint_input_img = self.inpainter_cache(image, mask, config)
            inpaint_input_img = cv2.convertScaleAbs(inpaint_input_img)

            # Saving cleaned image
            self.main_page.update_image_history(image_path, inpaint_input_img)

            inpaint_input_img = cv2.cvtColor(inpaint_input_img, cv2.COLOR_BGR2RGB)

            if export_settings['export_inpainted_image']:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "cleaned_images", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_cleaned{extension}"), inpaint_input_img)

            self.main_page.progress_update.emit(index, total_images, 5, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            # Get Translations/ Export if selected
            extra_context = settings_page.get_llm_settings()['extra_context']
            translator = Translator(self.main_page, source_lang, target_lang)
            try:
                translator.translate(blk_list, image, extra_context)
            except Exception as e:
                error_message = str(e)
                print(error_message)
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.main_page.image_skipped.emit(image_path, "Translator", error_message)
                self.log_skipped_image(directory, timestamp, image_path)
                continue

            entire_raw_text = get_raw_text(blk_list)
            entire_translated_text = get_raw_translation(blk_list)

            if (not entire_raw_text) or (not entire_translated_text):
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                self.main_page.image_skipped.emit(image_path, "Translator", "")
                self.log_skipped_image(directory, timestamp, image_path)
                continue

            if export_settings['export_raw_text']:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "raw_texts", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_raw.txt"), 'w', encoding='UTF-8')
                file.write(entire_raw_text)

            if export_settings['export_translated_text']:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_texts", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                file = open(os.path.join(path, os.path.splitext(os.path.basename(image_path))[0] + "_translated.txt"), 'w', encoding='UTF-8')
                file.write(entire_translated_text)

            self.main_page.progress_update.emit(index, total_images, 7, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            # Text Rendering
            text_rendering_settings = settings_page.get_text_rendering_settings()
            upper_case = text_rendering_settings['upper_case']
            outline = text_rendering_settings['outline']
            format_translations(blk_list, trg_lng_cd, upper_case=upper_case)
            get_best_render_area(blk_list, image, inpaint_input_img)

            font = text_rendering_settings['font']
            font_color = text_rendering_settings['color']
            font_path = f'fonts/{font}'
            set_alignment(blk_list, settings_page)

            max_font_size = self.main_page.settings_page.get_max_font_size()
            min_font_size = self.main_page.settings_page.get_min_font_size()

            rendered_image = draw_text(inpaint_input_img, blk_list, font_path, colour=font_color, init_font_size=max_font_size, min_font_size=min_font_size, outline=outline)

            self.main_page.progress_update.emit(index, total_images, 9, 10, False)
            if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                self.main_page.current_worker = None
                break

            # Display or set the rendered Image on the viewer once it's done
            self.main_page.image_processed.emit(index, rendered_image, image_path)

            # Saving blocks with texts to history
            self.main_page.image_states[image_path].update({
                'blk_list': blk_list                   
            })

            if index == self.main_page.current_image_index:
                self.main_page.blk_list = blk_list
                
            render_save_dir = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
            if not os.path.exists(render_save_dir):
                os.makedirs(render_save_dir, exist_ok=True)
            rendered_image_save = cv2.cvtColor(rendered_image, cv2.COLOR_BGR2RGB)
            cv2.imwrite(os.path.join(render_save_dir, f"{base_name}_translated{extension}"), rendered_image_save)

            self.main_page.progress_update.emit(index, total_images, 10, 10, False)

        archive_info_list = self.main_page.file_handler.archive_info
        if archive_info_list:
            save_as_settings = settings_page.get_export_settings()['save_as']
            for archive_index, archive in enumerate(archive_info_list):
                archive_index_input = total_images + archive_index

                self.main_page.progress_update.emit(archive_index_input, total_images, 1, 3, True)
                if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                    self.main_page.current_worker = None
                    break

                archive_path = archive['archive_path']
                archive_ext = os.path.splitext(archive_path)[1]
                archive_bname = os.path.splitext(os.path.basename(archive_path))[0]
                archive_directory = os.path.dirname(archive_path)
                save_as_ext = f".{save_as_settings[archive_ext.lower()]}"

                save_dir = os.path.join(archive_directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
                check_from = os.path.join(archive_directory, f"comic_translate_{timestamp}")

                self.main_page.progress_update.emit(archive_index_input, total_images, 2, 3, True)
                if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                    self.main_page.current_worker = None
                    break

                # Create the new archive
                output_base_name = f"{archive_bname}"
                target_lang = self.main_page.image_states[archive['extracted_images'][0]]['target_lang']
                target_lang_en = self.main_page.lang_mapping.get(target_lang, target_lang)
                trg_lng_code = get_language_code(target_lang_en)
                make(save_as_ext=save_as_ext, input_dir=save_dir, 
                    output_dir=archive_directory, output_base_name=output_base_name, 
                    trg_lng=trg_lng_code)

                self.main_page.progress_update.emit(archive_index_input, total_images, 3, 3, True)
                if self.main_page.current_worker and self.main_page.current_worker.is_cancelled:
                    self.main_page.current_worker = None
                    break

                # Clean up temporary directories
                shutil.rmtree(save_dir)
                shutil.rmtree(archive['temp_dir'])

                if is_directory_empty(check_from):
                    shutil.rmtree(check_from)






