import os
import cv2
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any, Callable

from modules.detection import TextBlockDetector
from modules.ocr.maga_processor import OCRProcessor
from modules.save_renderer import ImageSaveRenderer
from modules.translator.maga_processor import Translator
from modules.utils.textblock import TextBlock, sort_blk_list
from modules.utils.maga_utils import inpaint_map, get_config
from modules.rendering.maga_render import get_best_render_area, pyside_word_wrap
from modules.utils.maga_utils import generate_mask, get_language_code, is_directory_empty
from modules.utils.translator_utils import get_raw_translation, get_raw_text, format_translations, set_upper_case
from modules.utils.archives import make
from enum import Enum


class PColor:
    def __init__(self, r=0, g=0, b=0, a=255):
        self._r = min(max(r, 0), 255)
        self._g = min(max(g, 0), 255)
        self._b = min(max(b, 0), 255)
        self._a = min(max(a, 0), 255)

    @classmethod
    def from_hex(cls, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return cls(r, g, b)
        elif len(hex_str) == 8:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            a = int(hex_str[6:8], 16)
            return cls(r, g, b, a)
        raise ValueError("无效的十六进制颜色值")

    def to_hex(self):
        return f"#{self._r:02x}{self._g:02x}{self._b:02x}"

    def to_rgba(self):
        return (self._r, self._g, self._b, self._a)

    def to_rgb(self):
        return (self._r, self._g, self._b)

    def to_normalized_rgba(self):
        return (self._r / 255.0, self._g / 255.0, self._b / 255.0, self._a / 255.0)

    def to_normalized_rgb(self):
        return (self._r / 255.0, self._g / 255.0, self._b / 255.0)

    @property
    def red(self):
        return self._r

    @property
    def green(self):
        return self._g

    @property
    def blue(self):
        return self._b

    @property
    def alpha(self):
        return self._a

class OutlineType(Enum):
    Full_Document = 'full_document'
    Selection = 'selection'

class OutlineInfo:
    start: int
    end: int
    color: PColor
    width: float
    type: OutlineType



class BatchProcessor:
    def __init__(self):
        self.block_detector_cache = None
        self.inpainter_cache = None
        self.cached_inpainter_key = None
        self.ocr = OCRProcessor()
        
    def skip_save(self, directory: str, timestamp: str, base_name: str, extension: str, archive_bname: str, image: Any) -> None:
        path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        cv2.imwrite(os.path.join(path, f"{base_name}_translated{extension}"), image)

    def log_skipped_image(self, directory: str, timestamp: str, image_path: str) -> None:
        with open(os.path.join(directory, f"comic_translate_{timestamp}", "skipped_images.txt"), 'a', encoding='UTF-8') as file:
            file.write(image_path + "\n")

    def process_one_image(self, settings, image, source_lang, target_lang):
        target_lang_en = settings.lang_mapping.get(target_lang, target_lang)
        trg_lng_cd = get_language_code(target_lang_en, target_lang_en)
        if self.block_detector_cache is None:
            device = 0 if settings.gpu_enabled else 'cpu'
            self.block_detector_cache = TextBlockDetector(
                'models/detection/comic-speech-bubble-detector.pt',
                'models/detection/comic-text-segmenter.pt',
                'models/detection/manga-text-detector.pt',
                device
            )

        blk_list = self.block_detector_cache.detect(image)
        print('------------------blk_list------------------')
        print(blk_list)

        # OCR Processing
        if blk_list:
            print('------------------ocr.initialize------------------')
            self.ocr.initialize(settings, source_lang)
            try:
                print('------------------ocr.process------------------')
                self.ocr.process(image, blk_list)
                source_lang_english = settings.lang_mapping.get(source_lang, source_lang)
                rtl = True if source_lang_english == 'Japanese' else False
                blk_list = sort_blk_list(blk_list, rtl)
            except Exception as e:
                error_msg = str(e)
                return False, error_msg
        else:
            print('------------------skip_save------------------')
            return False, 'skip_save'

        # Inpainting
        if self.inpainter_cache is None or self.cached_inpainter_key != settings.inpainter_key:
            device = 'cuda' if settings.gpu_enabled else 'cpu'
            inpainter_key = settings.inpainter_key
            InpainterClass = inpaint_map[inpainter_key]
            self.inpainter_cache = InpainterClass(device)
            self.cached_inpainter_key = inpainter_key

        mask = generate_mask(image, blk_list)
        inpaint_input_img = self.inpainter_cache(image, mask, settings.inpaint_config)
        inpaint_input_img = cv2.convertScaleAbs(inpaint_input_img)

        print('------------------Translation------------------')
        # Translation
        translator = Translator(settings, source_lang, target_lang)
        try:
            translator.translate(blk_list, image, settings.settings_page.llm.extra_context)
        except Exception as e:
            error_msg = str(e)
            return False, error_msg

        # Process translation results
        entire_raw_text = get_raw_text(blk_list)
        entire_translated_text = get_raw_translation(blk_list)

        try:
            raw_text_obj = json.loads(entire_raw_text)
            translated_text_obj = json.loads(entire_translated_text)

            if (not raw_text_obj) or (not translated_text_obj):
                return False, "Empty translation result"
        except json.JSONDecodeError as e:
            error_msg = str(e)
            return False, error_msg

        # Text Rendering
        render_settings = settings.render_settings
        format_translations(blk_list, trg_lng_cd, upper_case=render_settings.upper_case)
        get_best_render_area(blk_list, image, inpaint_input_img)

        text_items_state = []
        for blk in blk_list:
            x1, y1, width, height = blk.xywh
            translation = blk.translation
            if not translation or len(translation) == 1:
                continue

            translation, font_size = pyside_word_wrap(
                translation,
                render_settings.font_family,
                width, height,
                float(render_settings.line_spacing),
                float(render_settings.outline_width),
                render_settings.bold,
                render_settings.italic,
                render_settings.underline,
                render_settings.alignment,
                render_settings.direction,
                render_settings.max_font_size,
                render_settings.min_font_size
            )

            if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja', 'th']):
                translation = translation.replace(' ', '')

            text_items_state.append({
                'text': translation,
                'font_family': render_settings.font_family,
                'font_size': font_size,
                'text_color': render_settings.color,
                'alignment': render_settings.alignment,
                'line_spacing': float(render_settings.line_spacing),
                'outline_color': render_settings.outline_color,
                'outline_width': float(render_settings.outline_width),
                'bold': render_settings.bold,
                'italic': render_settings.italic,
                'underline': render_settings.underline,
                'position': (x1, y1),
                'rotation': blk.angle,
                'scale': 1.0,
                'transform_origin': blk.tr_origin_point,
                'width': width,
                'direction': render_settings.direction,
                'selection_outlines': [OutlineInfo(0, len(translation),
                                                   render_settings.outline_color,
                                                   float(render_settings.outline_width),
                                                   OutlineType.Full_Document)] if render_settings.outline else []
            })

        im = cv2.cvtColor(inpaint_input_img, cv2.COLOR_RGB2BGR)
        renderer = ImageSaveRenderer(im)
        viewer_state = {
            'text_items_state': text_items_state
        }
        renderer.add_state_to_image(viewer_state)
        output_image = renderer.render_to_image()

        return True, output_image

    def process_images(self, 
                       image_files: List[str],
                       image_states: Dict[str, Any],
                       settings,
                       output_path: str = None,
                       archive_info: List[Dict[str, Any]] = None,
                       progress_callback: Callable[[int, int, int, int, bool, str], None] = None,
                       cancel_check: Callable[[], bool] = None) -> None:
        """
        批量处理图片
        
        Args:
            image_files: 需要处理的图片文件路径列表
            image_states: 每个图片的状态信息
            settings: 处理设置，包含OCR、翻译、渲染等配置
            output_path: 输出目录（可选）
            archive_info: 压缩包信息（可选）
            progress_callback: 进度回调函数，参数为(当前索引,总数,当前步骤,总步骤数,是否更新名称,错误信息)
            cancel_check: 取消检查函数，返回True表示需要取消处理
        """
        timestamp = datetime.now().strftime("%b-%d-%Y_%I-%M-%S%p")
        total_images = len(image_files)
        
        for index, image_path in enumerate(image_files):
            if progress_callback:
                progress_callback(index, total_images, 0, 10, True, "")
            if cancel_check and cancel_check():
                break
                
            source_lang = image_states[image_path]['source_lang']
            target_lang = image_states[image_path]['target_lang']
            print('target_lang', target_lang)
            target_lang_en = settings.lang_mapping.get(target_lang, target_lang)
            print('target_lang_en', target_lang_en)
            trg_lng_cd = get_language_code(target_lang_en)
            if trg_lng_cd is None:
                trg_lng_cd = 'en'
            print('trg_lng_cd', trg_lng_cd)
            
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            extension = os.path.splitext(image_path)[1]

            if output_path:
                directory = output_path
            else:
                directory = os.path.dirname(image_path)
            
            archive_bname = ""
            if archive_info:
                for archive in archive_info:
                    if image_path in archive['extracted_images']:
                        directory = os.path.dirname(archive['archive_path'])
                        archive_bname = os.path.splitext(os.path.basename(archive['archive_path']))[0]
                        break
            
            image = cv2.imread(image_path)
            
            # Text Block Detection
            if progress_callback:
                progress_callback(index, total_images, 1, 10, False, "")
            if cancel_check and cancel_check():
                break
                
            if self.block_detector_cache is None:
                device = 0 if settings.gpu_enabled else 'cpu'
                # self.block_detector_cache = TextBlockDetector(
                #     'models/detection/comic-speech-bubble-detector.pt',
                #     'models/detection/comic-text-segmenter.pt',
                #     'models/detection/manga-text-detector.pt',
                #     device
                # )

                from pathlib import Path
                folder = Path(__file__).parent.parent
                self.block_detector_cache = TextBlockDetector(
                    os.path.join(folder, 'models/detection/comic-speech-bubble-detector.pt'),
                    os.path.join(folder, 'models/detection/comic-text-segmenter.pt'),
                    os.path.join(folder, 'models/detection/manga-text-detector.pt'),
                    device
                )

            blk_list = self.block_detector_cache.detect(image)
            print('------------------blk_list------------------')
            print(blk_list)

            if progress_callback:
                progress_callback(index, total_images, 2, 10, False, "")
            if cancel_check and cancel_check():
                break
                
            # OCR Processing
            if blk_list:
                print('------------------ocr.initialize------------------')
                self.ocr.initialize(settings, source_lang)
                try:
                    print('------------------ocr.process------------------')
                    self.ocr.process(image, blk_list)
                    source_lang_english = settings.lang_mapping.get(source_lang, source_lang)
                    rtl = True if source_lang_english == 'Japanese' else False
                    blk_list = sort_blk_list(blk_list, rtl)
                except Exception as e:
                    error_msg = str(e)
                    self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                    if progress_callback:
                        progress_callback(index, total_images, 2, 10, False, f"OCR Error: {error_msg}")
                    self.log_skipped_image(directory, timestamp, image_path)
                    continue
            else:
                print('------------------skip_save------------------')
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                if progress_callback:
                    progress_callback(index, total_images, 2, 10, False, "No text blocks detected")
                self.log_skipped_image(directory, timestamp, image_path)
                continue
                
            if progress_callback:
                progress_callback(index, total_images, 3, 10, False, "")
            if cancel_check and cancel_check():
                break
                
            # Inpainting
            if self.inpainter_cache is None or self.cached_inpainter_key != settings.inpainter_key:
                device = 'cuda' if settings.gpu_enabled else 'cpu'
                inpainter_key = settings.inpainter_key
                InpainterClass = inpaint_map[inpainter_key]
                self.inpainter_cache = InpainterClass(device)
                self.cached_inpainter_key = inpainter_key
                
            mask = generate_mask(image, blk_list)
            inpaint_input_img = self.inpainter_cache(image, mask, settings.inpaint_config)
            inpaint_input_img = cv2.convertScaleAbs(inpaint_input_img)
            
            if progress_callback:
                progress_callback(index, total_images, 4, 10, False, "")
            if cancel_check and cancel_check():
                break
                
            # Save cleaned image if needed
            if settings.export_inpainted_image:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "cleaned_images", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                cv2.imwrite(os.path.join(path, f"{base_name}_cleaned{extension}"), 
                           cv2.cvtColor(inpaint_input_img, cv2.COLOR_BGR2RGB))
                
            if progress_callback:
                progress_callback(index, total_images, 5, 10, False, "")
            if cancel_check and cancel_check():
                break

            print('------------------Translation------------------')
            # Translation
            translator = Translator(settings, source_lang, target_lang)
            try:
                translator.translate(blk_list, image, settings.settings_page.llm.extra_context)
            except Exception as e:
                error_msg = str(e)
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                if progress_callback:
                    progress_callback(index, total_images, 5, 10, False, f"Translation Error: {error_msg}")
                self.log_skipped_image(directory, timestamp, image_path)
                continue

            print('-------------Process translation results------------')
            # Process translation results
            entire_raw_text = get_raw_text(blk_list)
            entire_translated_text = get_raw_translation(blk_list)

            try:
                raw_text_obj = json.loads(entire_raw_text)
                translated_text_obj = json.loads(entire_translated_text)
                
                if (not raw_text_obj) or (not translated_text_obj):
                    self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                    if progress_callback:
                        progress_callback(index, total_images, 5, 10, False, "Empty translation result")
                    self.log_skipped_image(directory, timestamp, image_path)
                    continue
            except json.JSONDecodeError as e:
                error_msg = str(e)
                self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
                if progress_callback:
                    progress_callback(index, total_images, 5, 10, False, f"Invalid translation format: {error_msg}")
                self.log_skipped_image(directory, timestamp, image_path)
                continue

            # Save text files if needed
            if settings.export_raw_text:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "raw_texts", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                with open(os.path.join(path, f"{base_name}_raw.txt"), 'w', encoding='UTF-8') as f:
                    f.write(entire_raw_text)
                    
            if settings.export_translated_text:
                path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_texts", archive_bname)
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                with open(os.path.join(path, f"{base_name}_translated.txt"), 'w', encoding='UTF-8') as f:
                    f.write(entire_translated_text)
                    
            if progress_callback:
                progress_callback(index, total_images, 7, 10, False, "")
            if cancel_check and cancel_check():
                break


            print('-------------Text Rendering------------')
            # Text Rendering
            render_settings = settings.render_settings
            format_translations(blk_list, trg_lng_cd, upper_case=render_settings.upper_case)
            get_best_render_area(blk_list, image, inpaint_input_img)

            text_items_state = []
            for blk in blk_list:
                x1, y1, width, height = blk.xywh
                translation = blk.translation
                if not translation or len(translation) == 1:
                    continue
                    
                translation, font_size = pyside_word_wrap(
                    translation,
                    render_settings.font_family,
                    width, height,
                    float(render_settings.line_spacing),
                    float(render_settings.outline_width),
                    render_settings.bold,
                    render_settings.italic,
                    render_settings.underline,
                    render_settings.alignment,
                    render_settings.direction,
                    render_settings.max_font_size,
                    render_settings.min_font_size
                )
                
                if any(lang in trg_lng_cd.lower() for lang in ['zh', 'ja', 'th']):
                    translation = translation.replace(' ', '')
                    
                text_items_state.append({
                    'text': translation,
                    'font_family': render_settings.font_family,
                    'font_size': font_size,
                    'text_color': render_settings.color,
                    'alignment': render_settings.alignment,
                    'line_spacing': float(render_settings.line_spacing),
                    'outline_color': render_settings.outline_color,
                    'outline_width': float(render_settings.outline_width),
                    'bold': render_settings.bold,
                    'italic': render_settings.italic,
                    'underline': render_settings.underline,
                    'position': (x1, y1),
                    'rotation': blk.angle,
                    'scale': 1.0,
                    'transform_origin': blk.tr_origin_point,
                    'width': width,
                    'direction': render_settings.direction,
                    'selection_outlines': [OutlineInfo(0, len(translation),
                                                    render_settings.outline_color,
                                                    float(render_settings.outline_width),
                                                    OutlineType.Full_Document)] if render_settings.outline else []
                })


            print('-------------Save rendered image------------')
            # Save rendered image
            if output_path:
                sv_pth = os.path.join(directory, f"{base_name}{extension}")
            else:
                render_save_dir = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
                if not os.path.exists(render_save_dir):
                    os.makedirs(render_save_dir, exist_ok=True)
                sv_pth = os.path.join(render_save_dir, f"{base_name}_translated{extension}")

            im = cv2.cvtColor(inpaint_input_img, cv2.COLOR_RGB2BGR)
            renderer = ImageSaveRenderer(im)
            viewer_state = image_states[image_path]['viewer_state']
            viewer_state['text_items_state'] = text_items_state
            renderer.add_state_to_image(viewer_state)
            renderer.save_image(sv_pth)


if __name__ == '__main__':
    BatchProcessor().process_images()