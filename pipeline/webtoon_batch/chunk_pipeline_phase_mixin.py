from __future__ import annotations

import logging

import imkit as imk
import requests
from PySide6.QtCore import QCoreApplication

from app.ui.messages import Messages
from modules.translation.processor import Translator
from modules.utils.device import resolve_device
from modules.utils.exceptions import InsufficientCreditsException
from modules.utils.pipeline_config import get_config, inpaint_map
from modules.utils.textblock import sort_blk_list
from modules.detection.utils.orientation import infer_orientation, infer_reading_order

logger = logging.getLogger(__name__)


class ChunkPipelinePhaseMixin:
    def _run_chunk_ocr(self, chunk_id: str, combined_image, blk_list, vpage1, vpage2):
        if not blk_list:
            return []

        self.ocr_handler.ocr.initialize(self.main_page, "")
        try:
            self.ocr_handler.ocr.process(combined_image, blk_list)
            orientation = infer_orientation([blk.xyxy for blk in blk_list]) if blk_list else "horizontal"
            rtl = infer_reading_order(orientation) == "rtl"
            return sort_blk_list(blk_list, rtl)
        except InsufficientCreditsException:
            raise
        except Exception as exc:
            if isinstance(exc, requests.exceptions.ConnectionError):
                err_msg = QCoreApplication.translate(
                    "Messages",
                    "Unable to connect to the server.\nPlease check your internet connection.",
                )
            elif isinstance(exc, requests.exceptions.HTTPError):
                status_code = exc.response.status_code if exc.response is not None else 500
                if status_code >= 500:
                    err_msg = Messages.get_server_error_text(status_code, context="ocr")
                else:
                    try:
                        err_json = exc.response.json()
                        if "detail" in err_json and isinstance(err_json["detail"], dict):
                            err_msg = err_json["detail"].get("error_description", str(exc))
                        else:
                            err_msg = err_json.get("error_description", str(exc))
                    except Exception:
                        err_msg = str(exc)
            else:
                err_msg = str(exc)

            logger.exception("OCR failed for virtual chunk %s: %s", chunk_id, err_msg)
            self.main_page.image_skipped.emit(vpage1.physical_page_path, "OCR Chunk Failed", err_msg)
            self.main_page.image_skipped.emit(vpage2.physical_page_path, "OCR Chunk Failed", err_msg)
            return []

    def _ensure_chunk_inpainter_cache(self):
        if (
            self.inpainting.inpainter_cache is None
            or self.inpainting.cached_inpainter_key != self.main_page.settings_page.get_tool_selection("inpainter")
        ):
            backend = "onnx"
            device = resolve_device(self.main_page.settings_page.is_gpu_enabled(), backend=backend)
            inpainter_key = self.main_page.settings_page.get_tool_selection("inpainter")
            InpainterClass = inpaint_map[inpainter_key]
            self.inpainting.inpainter_cache = InpainterClass(device, backend=backend)
            self.inpainting.cached_inpainter_key = inpainter_key

    def _run_chunk_inpaint(self, combined_image, blk_list, mapping_data):
        self._ensure_chunk_inpainter_cache()
        config = get_config(self.main_page.settings_page)
        mask = self.inpainting.build_mask_from_blocks(combined_image, blk_list)
        inpaint_input_img = self.inpainting.inpainter_cache(combined_image, mask, config)
        inpaint_input_img = imk.convert_scale_abs(inpaint_input_img)
        virtual_page_patches = self._calculate_virtual_inpaint_patches(mask, inpaint_input_img, mapping_data)
        return mask, inpaint_input_img, virtual_page_patches

    def _run_chunk_translation(self, chunk_id: str, blk_list, combined_image, vpage1, vpage2):
        if not blk_list:
            return

        target_lang = self.main_page.image_states[vpage1.physical_page_path]["target_lang"]
        extra_context = self.main_page.settings_page.get_llm_settings()["extra_context"]
        translator = Translator(self.main_page, "", target_lang)
        try:
            translator.translate(blk_list, combined_image, extra_context)
        except InsufficientCreditsException:
            raise
        except Exception as exc:
            if isinstance(exc, requests.exceptions.ConnectionError):
                err_msg = QCoreApplication.translate(
                    "Messages",
                    "Unable to connect to the server.\nPlease check your internet connection.",
                )
            elif isinstance(exc, requests.exceptions.HTTPError):
                status_code = exc.response.status_code if exc.response is not None else 500
                if status_code >= 500:
                    err_msg = Messages.get_server_error_text(status_code, context="translation")
                else:
                    try:
                        err_json = exc.response.json()
                        if "detail" in err_json and isinstance(err_json["detail"], dict):
                            err_msg = err_json["detail"].get("error_description", str(exc))
                        else:
                            err_msg = err_json.get("error_description", str(exc))
                    except Exception:
                        err_msg = str(exc)
            else:
                err_msg = str(exc)

            logger.exception("Translation failed for virtual chunk %s: %s", chunk_id, err_msg)
            self.main_page.image_skipped.emit(vpage1.physical_page_path, "Translation Chunk Failed", err_msg)
            self.main_page.image_skipped.emit(vpage2.physical_page_path, "Translation Chunk Failed", err_msg)
            for blk in blk_list:
                blk.translation = ""
