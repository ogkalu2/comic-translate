from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from PySide6 import QtCore

from modules.detection.processor import TextBlockDetector
from modules.detection.utils.content import get_inpaint_bboxes
from modules.ocr.processor import OCRProcessor
from modules.rendering.render import pyside_word_wrap, is_vertical_block, get_best_render_area
from modules.translation.processor import Translator
from modules.utils.common_utils import is_close
from modules.utils.device import resolve_device
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.pipeline_config import validate_ocr, validate_translator
from modules.utils.textblock import sort_blk_list
from modules.utils.translator_utils import is_there_text, format_translations, set_upper_case
from pipeline.webtoon_utils import get_visible_text_items, get_first_visible_block

if TYPE_CHECKING:
    from app.ui.canvas.text_item import TextBlockItem
    from controller import ComicTranslate
    from modules.utils.textblock import TextBlock


class ManualWorkflowController:
    def __init__(self, main: ComicTranslate) -> None:
        self.main = main

    def _current_file_path(self) -> str | None:
        if 0 <= self.main.curr_img_idx < len(self.main.image_files):
            return self.main.image_files[self.main.curr_img_idx]
        return None

    def _selected_page_paths(self) -> list[str]:
        return self.main.get_selected_page_paths()

    def _load_page_image(self, file_path: str):
        img = self.main.image_data.get(file_path)
        if img is None:
            img = self.main.image_ctrl.load_image(file_path)
            if img is not None:
                self.main.image_data[file_path] = img
        return img

    def _prepare_multi_page_context(self, selected_paths: list[str]) -> dict[str, Any]:
        current_file = self._current_file_path()
        current_page_unloaded = False
        if self.main.webtoon_mode:
            manager = getattr(self.main.image_viewer, "webtoon_manager", None)
            scene_mgr = getattr(manager, "scene_item_manager", None) if manager is not None else None
            if scene_mgr is not None:
                scene_mgr.save_all_scene_items_to_states()
                if (
                    current_file in selected_paths
                    and 0 <= self.main.curr_img_idx < len(self.main.image_files)
                    and self.main.curr_img_idx in manager.loaded_pages
                ):
                    scene_mgr.unload_page_scene_items(self.main.curr_img_idx)
                    current_page_unloaded = True
        else:
            self.main.image_ctrl.save_current_image_state()

        return {
            "current_file": current_file,
            "current_page_unloaded": current_page_unloaded,
        }

    def _reload_current_webtoon_page(self) -> None:
        if not self.main.webtoon_mode:
            return
        manager = getattr(self.main.image_viewer, "webtoon_manager", None)
        if manager is None:
            return
        scene_mgr = getattr(manager, "scene_item_manager", None)
        if scene_mgr is None:
            return
        page_idx = self.main.curr_img_idx
        if not (0 <= page_idx < len(self.main.image_files)):
            return
        if page_idx not in manager.loaded_pages:
            return
        scene_mgr.load_page_scene_items(page_idx)
        self.main.text_ctrl.clear_text_edits()

    def _serialize_rectangles_from_blocks(self, blk_list: list[TextBlock]) -> list[dict]:
        rects: list[dict] = []
        for blk in blk_list:
            x1, y1, x2, y2 = blk.xyxy
            rects.append(
                {
                    "rect": (float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
                    "rotation": float(getattr(blk, "angle", 0)),
                    "transform_origin": tuple(blk.tr_origin_point) if getattr(blk, "tr_origin_point", None) else (0.0, 0.0),
                }
            )
        return rects

    def _serialize_segmentation_strokes(self, blk_list: list[TextBlock]) -> list[dict]:
        strokes: list[dict] = []
        build_stroke = self.main.image_viewer.drawing_manager.make_segmentation_stroke_data
        for blk in blk_list:
            bboxes = blk.inpaint_bboxes
            if bboxes is None or len(bboxes) == 0:
                continue
            stroke = build_stroke(bboxes)
            if stroke is not None:
                strokes.append(stroke)
        return strokes

    def block_detect(self, load_rects: bool = True) -> None:
        selected_paths = self._selected_page_paths()
        if len(selected_paths) > 1:
            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()
            context = self._prepare_multi_page_context(selected_paths)
            source_lang_fallback = self.main.s_combo.currentText()

            def detect_selected_pages() -> dict[str, list[TextBlock]]:
                if self.main.pipeline.block_detection.block_detector_cache is None:
                    self.main.pipeline.block_detection.block_detector_cache = TextBlockDetector(self.main.settings_page)
                detector = self.main.pipeline.block_detection.block_detector_cache
                results: dict[str, list[TextBlock]] = {}
                for file_path in selected_paths:
                    image = self._load_page_image(file_path)
                    if image is None:
                        continue
                    blk_list = detector.detect(image)
                    if blk_list:
                        get_best_render_area(blk_list, image)
                    state = self.main.image_states.get(file_path, {})
                    source_lang = state.get("source_lang", source_lang_fallback)
                    source_lang_en = self.main.lang_mapping.get(source_lang, source_lang)
                    rtl = source_lang_en == "Japanese"
                    results[file_path] = sort_blk_list(blk_list, rtl)
                return results

            def on_detect_ready(results: dict[str, list[TextBlock]]) -> None:
                current_file = context["current_file"]
                current_blocks: list[TextBlock] | None = None
                for file_path, blk_list in (results or {}).items():
                    state = self.main.image_states.get(file_path)
                    if state is None:
                        continue
                    state["blk_list"] = blk_list
                    viewer_state = state.setdefault("viewer_state", {})
                    viewer_state["rectangles"] = self._serialize_rectangles_from_blocks(blk_list)
                    if file_path == current_file:
                        current_blocks = blk_list

                if current_blocks is not None:
                    self.main.blk_list = current_blocks.copy()
                    if self.main.webtoon_mode:
                        if context["current_page_unloaded"]:
                            self._reload_current_webtoon_page()
                    elif load_rects:
                        self.main.pipeline.load_box_coords(self.main.blk_list)

                if results:
                    self.main.mark_project_dirty()

            self.main.run_threaded(
                detect_selected_pages,
                on_detect_ready,
                self.main.default_error_handler,
                self.main.on_manual_finished,
            )
            return

        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()
        self.main.run_threaded(
            self.main.pipeline.detect_blocks,
            self.main.pipeline.on_blk_detect_complete,
            self.main.default_error_handler,
            self.main.on_manual_finished,
            load_rects,
        )

    def finish_ocr_translate(self, single_block: bool = False) -> None:
        if self.main.blk_list:
            if single_block:
                rect = self.main.image_viewer.selected_rect
            else:
                if self.main.webtoon_mode:
                    first_block = get_first_visible_block(
                        self.main.blk_list, self.main.image_viewer
                    )
                    if first_block is None:
                        first_block = self.main.blk_list[0]
                else:
                    first_block = self.main.blk_list[0]
                rect = self.main.rect_item_ctrl.find_corresponding_rect(first_block, 0.5)
            self.main.image_viewer.select_rectangle(rect)
        self.main.set_tool("box")
        self.main.on_manual_finished()

    def ocr(self, single_block: bool = False) -> None:
        if not validate_ocr(self.main):
            return
        selected_paths = self._selected_page_paths()
        if len(selected_paths) > 1 and not single_block:
            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()
            context = self._prepare_multi_page_context(selected_paths)
            source_lang_fallback = self.main.s_combo.currentText()

            def ocr_selected_pages() -> dict[str, list[TextBlock]]:
                cache_manager = self.main.pipeline.cache_manager
                ocr = OCRProcessor()
                ocr_model = self.main.settings_page.get_tool_selection("ocr")
                device = resolve_device(self.main.settings_page.is_gpu_enabled())
                results: dict[str, list[TextBlock]] = {}
                for file_path in selected_paths:
                    state = self.main.image_states.get(file_path, {})
                    blk_list = state.get("blk_list", [])
                    if not blk_list:
                        continue
                    image = self._load_page_image(file_path)
                    if image is None:
                        continue
                    source_lang = state.get("source_lang", source_lang_fallback)
                    cache_key = cache_manager._get_ocr_cache_key(image, source_lang, ocr_model, device)
                    if cache_manager._can_serve_all_blocks_from_ocr_cache(cache_key, blk_list):
                        cache_manager._apply_cached_ocr_to_blocks(cache_key, blk_list)
                    else:
                        ocr.initialize(self.main, source_lang)
                        ocr.process(image, blk_list)
                        cache_manager._cache_ocr_results(cache_key, blk_list)
                    results[file_path] = blk_list
                return results

            def on_ocr_ready(results: dict[str, list[TextBlock]]) -> None:
                current_file = context["current_file"]
                for file_path, blk_list in (results or {}).items():
                    state = self.main.image_states.get(file_path)
                    if state is None:
                        continue
                    state["blk_list"] = blk_list
                    if file_path == current_file:
                        self.main.blk_list = blk_list.copy()

                if self.main.webtoon_mode and context["current_page_unloaded"]:
                    self._reload_current_webtoon_page()

                if results:
                    self.main.mark_project_dirty()

            self.main.run_threaded(
                ocr_selected_pages,
                on_ocr_ready,
                self.main.default_error_handler,
                lambda: self.finish_ocr_translate(single_block),
            )
            return

        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()

        if self.main.webtoon_mode:
            self.main.run_threaded(
                lambda: self.main.pipeline.OCR_webtoon_visible_area(single_block),
                None,
                self.main.default_error_handler,
                lambda: self.finish_ocr_translate(single_block),
            )
        else:
            self.main.run_threaded(
                lambda: self.main.pipeline.OCR_image(single_block),
                None,
                self.main.default_error_handler,
                lambda: self.finish_ocr_translate(single_block),
            )

    def translate_image(self, single_block: bool = False) -> None:
        selected_paths = self._selected_page_paths()
        if len(selected_paths) > 1 and not single_block:
            has_any_text = False
            for file_path in selected_paths:
                blk_list = self.main.image_states.get(file_path, {}).get("blk_list", [])
                if is_there_text(blk_list):
                    has_any_text = True
                    break
            if not has_any_text:
                return
            for file_path in selected_paths:
                target_lang = self.main.image_states.get(file_path, {}).get(
                    "target_lang", self.main.t_combo.currentText()
                )
                if not validate_translator(self.main, target_lang):
                    return

            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()
            context = self._prepare_multi_page_context(selected_paths)
            source_lang_fallback = self.main.s_combo.currentText()
            target_lang_fallback = self.main.t_combo.currentText()
            settings_page = self.main.settings_page
            extra_context = settings_page.get_llm_settings()["extra_context"]
            translator_key = settings_page.get_tool_selection("translator")
            upper_case = settings_page.ui.uppercase_checkbox.isChecked()

            def translate_selected_pages() -> dict[str, list[TextBlock]]:
                cache_manager = self.main.pipeline.cache_manager
                results: dict[str, list[TextBlock]] = {}
                for file_path in selected_paths:
                    state = self.main.image_states.get(file_path, {})
                    blk_list = state.get("blk_list", [])
                    if not blk_list:
                        continue
                    image = self._load_page_image(file_path)
                    if image is None:
                        continue
                    source_lang = state.get("source_lang", source_lang_fallback)
                    target_lang = state.get("target_lang", target_lang_fallback)
                    translator = Translator(self.main, source_lang, target_lang)
                    cache_key = cache_manager._get_translation_cache_key(
                        image,
                        source_lang,
                        target_lang,
                        translator_key,
                        extra_context,
                    )
                    if cache_manager._can_serve_all_blocks_from_translation_cache(cache_key, blk_list):
                        cache_manager._apply_cached_translations_to_blocks(cache_key, blk_list)
                    else:
                        translator.translate(blk_list, image, extra_context)
                        cache_manager._cache_translation_results(cache_key, blk_list)
                    set_upper_case(blk_list, upper_case)
                    results[file_path] = blk_list
                return results

            def on_translation_ready(results: dict[str, list[TextBlock]]) -> None:
                current_file = context["current_file"]
                for file_path, blk_list in (results or {}).items():
                    state = self.main.image_states.get(file_path)
                    if state is None:
                        continue
                    state["blk_list"] = blk_list
                    if file_path == current_file:
                        self.main.blk_list = blk_list.copy()

                if self.main.webtoon_mode and context["current_page_unloaded"]:
                    self._reload_current_webtoon_page()

                if results:
                    self.main.mark_project_dirty()

            self.main.run_threaded(
                translate_selected_pages,
                on_translation_ready,
                self.main.default_error_handler,
                lambda: self.update_translated_text_items(single_block),
            )
            return

        target_lang = self.main.t_combo.currentText()
        if not is_there_text(self.main.blk_list) or not validate_translator(
            self.main, target_lang
        ):
            return
        self.main.loading.setVisible(True)
        self.main.disable_hbutton_group()

        if self.main.webtoon_mode:
            self.main.run_threaded(
                lambda: self.main.pipeline.translate_webtoon_visible_area(single_block),
                None,
                self.main.default_error_handler,
                lambda: self.update_translated_text_items(single_block),
            )
        else:
            self.main.run_threaded(
                lambda: self.main.pipeline.translate_image(single_block),
                None,
                self.main.default_error_handler,
                lambda: self.update_translated_text_items(single_block),
            )

    def _get_visible_text_items(self) -> list[TextBlockItem]:
        if not self.main.webtoon_mode:
            return self.main.image_viewer.text_items
        return get_visible_text_items(
            self.main.image_viewer.text_items, self.main.image_viewer.webtoon_manager
        )

    def update_translated_text_items(self, single_blk: bool) -> None:
        
        def set_new_text(
            text_item: TextBlockItem, 
            wrapped: str, 
            font_size: int
        ) -> None:
            
            if is_no_space_lang(trg_lng_cd):
                wrapped = wrapped.replace(" ", "")
            text_item.set_plain_text(wrapped)
            text_item.set_font_size(font_size)

        text_items_to_process = self._get_visible_text_items()
        if not text_items_to_process:
            self.finish_ocr_translate(single_blk)
            return

        rs = self.main.render_settings()
        upper = rs.upper_case
        target_lang_en = self.main.lang_mapping.get(self.main.t_combo.currentText(), None)
        trg_lng_cd = get_language_code(target_lang_en)

        def on_format_finished() -> None:
            for text_item in text_items_to_process:
                text_item.handleDeselection()
                x1, y1 = int(text_item.pos().x()), int(text_item.pos().y())
                rot = text_item.rotation()

                blk = next(
                    (
                        b
                        for b in self.main.blk_list
                        if is_close(b.xyxy[0], x1, 5)
                        and is_close(b.xyxy[1], y1, 5)
                        and is_close(b.angle, rot, 1)
                    ),
                    None,
                )
                if not (blk and blk.translation):
                    continue

                vertical = is_vertical_block(blk, trg_lng_cd)
                wrap_args = (
                    blk.translation,
                    text_item.font_family,
                    blk.xyxy[2] - blk.xyxy[0],
                    blk.xyxy[3] - blk.xyxy[1],
                    float(text_item.line_spacing),
                    float(text_item.outline_width),
                    text_item.bold,
                    text_item.italic,
                    text_item.underline,
                    text_item.alignment,
                    text_item.direction,
                    rs.max_font_size,
                    rs.min_font_size,
                    vertical,
                )

                self.main.run_threaded(
                    pyside_word_wrap,
                    lambda wrap_res, ti=text_item: set_new_text(
                        ti, wrap_res[0], wrap_res[1]
                    ),
                    self.main.default_error_handler,
                    None,
                    *wrap_args,
                )

            self.main.run_finish_only(finished_callback=self.main.on_manual_finished)

        self.main.run_threaded(
            lambda: format_translations(self.main.blk_list, trg_lng_cd, upper_case=upper),
            None,
            self.main.default_error_handler,
            on_format_finished,
        )

    def inpaint_and_set(self) -> None:
        if not self.main.image_viewer.hasPhoto():
            return

        selected_paths = self._selected_page_paths()
        if len(selected_paths) > 1:
            self.main.text_ctrl.clear_text_edits()
            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()
            context = self._prepare_multi_page_context(selected_paths)

            def inpaint_selected_pages() -> dict[str, list[dict]]:
                results: dict[str, list[dict]] = {}
                path_to_index = {p: i for i, p in enumerate(self.main.image_files)}

                for file_path in selected_paths:
                    state = self.main.image_states.get(file_path, {})
                    strokes = state.get("brush_strokes", [])
                    if not strokes:
                        continue
                    image = self._load_page_image(file_path)
                    if image is None:
                        continue

                    patches = self.main.pipeline.inpainting.inpaint_page_from_saved_strokes(
                        image,
                        strokes,
                    )

                    if self.main.webtoon_mode and patches:
                        page_idx = path_to_index.get(file_path)
                        if page_idx is not None:
                            for patch in patches:
                                x, y, _w, _h = patch['bbox']
                                scene_pos = self.main.image_viewer.page_to_scene_coordinates(
                                    page_idx,
                                    QtCore.QPointF(x, y),
                                )
                                if scene_pos is not None:
                                    patch['scene_pos'] = [scene_pos.x(), scene_pos.y()]
                                    patch['page_index'] = page_idx

                    results[file_path] = patches

                return results

            def on_selected_inpaint_ready(results: dict[str, list[dict]]) -> None:
                current_file = context["current_file"]
                processed_any = False

                for file_path, patches in (results or {}).items():
                    stack = self.main.undo_stacks.get(file_path)
                    if stack is not None:
                        stack.beginMacro("inpaint")
                    try:
                        if patches:
                            self.main.image_ctrl.on_inpaint_patches_processed(patches, file_path)
                    finally:
                        if stack is not None:
                            stack.endMacro()

                    state = self.main.image_states.get(file_path)
                    if state is not None:
                        state['brush_strokes'] = []
                    processed_any = True

                if not self.main.webtoon_mode and current_file in (results or {}):
                    self.main.image_viewer.clear_brush_strokes(page_switch=True)

                if self.main.webtoon_mode and context["current_page_unloaded"]:
                    self._reload_current_webtoon_page()

                if processed_any:
                    self.main.mark_project_dirty()

            self.main.run_threaded(
                inpaint_selected_pages,
                on_selected_inpaint_ready,
                self.main.default_error_handler,
                self.main.on_manual_finished,
            )
            return

        if self.main.image_viewer.has_drawn_elements():
            self.main.text_ctrl.clear_text_edits()
            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()
            self.main.undo_group.activeStack().beginMacro("inpaint")
            self.main.run_threaded(
                self.main.pipeline.inpaint,
                self.main.pipeline.inpaint_complete,
                self.main.default_error_handler,
                self.main.on_manual_finished,
            )

    def blk_detect_segment(
        self, 
        result: tuple[list[TextBlock], bool] | tuple[list[TextBlock], bool, Any]
    ) -> None:
        
        if len(result) == 3:
            blk_list, load_rects, _ = result
        else:
            blk_list, load_rects = result
        self.main.blk_list = blk_list
        self.main.undo_group.activeStack().beginMacro("draw_segmentation_boxes")
        for blk in self.main.blk_list:
            bboxes = blk.inpaint_bboxes
            if bboxes is not None and len(bboxes) > 0:
                self.main.image_viewer.draw_segmentation_lines(bboxes)
        self.main.undo_group.activeStack().endMacro()

    def load_segmentation_points(self) -> None:
        if self.main.image_viewer.hasPhoto():
            self.main.text_ctrl.clear_text_edits()
            self.main.set_tool("brush")
            self.main.disable_hbutton_group()
            self.main.image_viewer.clear_rectangles()
            self.main.image_viewer.clear_text_items()

            self.main.loading.setVisible(True)
            self.main.disable_hbutton_group()

            selected_paths = self._selected_page_paths()
            if len(selected_paths) > 1:
                self.main.undo_group.activeStack().beginMacro("draw_segmentation_boxes")
                context = self._prepare_multi_page_context(selected_paths)

                def compute_selected_bboxes() -> dict[str, list[TextBlock]]:
                    results: dict[str, list[TextBlock]] = {}
                    for file_path in selected_paths:
                        state = self.main.image_states.get(file_path, {})
                        blk_list = state.get("blk_list", [])
                        if not blk_list:
                            continue
                        image = self._load_page_image(file_path)
                        if image is None:
                            continue
                        for blk in blk_list:
                            blk.inpaint_bboxes = get_inpaint_bboxes(blk.xyxy, image)
                        results[file_path] = blk_list
                    return results

                def on_selected_bboxes_ready(results: dict[str, list[TextBlock]]) -> None:
                    current_file = context["current_file"]
                    for file_path, blk_list in (results or {}).items():
                        state = self.main.image_states.get(file_path)
                        if state is None:
                            continue
                        state["blk_list"] = blk_list
                        viewer_state = state.setdefault("viewer_state", {})
                        viewer_state["rectangles"] = []
                        state["brush_strokes"] = self._serialize_segmentation_strokes(blk_list)
                        if file_path == current_file:
                            self.main.blk_list = blk_list.copy()

                    if (
                        not self.main.webtoon_mode
                        and current_file is not None
                        and current_file in (results or {})
                    ):
                        for blk in self.main.blk_list:
                            bboxes = blk.inpaint_bboxes
                            if bboxes is not None and len(bboxes) > 0:
                                self.main.image_viewer.draw_segmentation_lines(bboxes)

                    if self.main.webtoon_mode and context["current_page_unloaded"]:
                        self._reload_current_webtoon_page()

                    if results:
                        self.main.mark_project_dirty()
                    self.main.undo_group.activeStack().endMacro()

                def on_selected_bboxes_error(error_tuple: tuple) -> None:
                    try:
                        self.main.undo_group.activeStack().endMacro()
                    except Exception:
                        pass
                    self.main.default_error_handler(error_tuple)

                self.main.run_threaded(
                    compute_selected_bboxes,
                    on_selected_bboxes_ready,
                    on_selected_bboxes_error,
                    self.main.on_manual_finished,
                )
                return

            if self.main.blk_list:
                self.main.undo_group.activeStack().beginMacro("draw_segmentation_boxes")

                if self.main.webtoon_mode:
                    self.main.run_threaded(
                        lambda: self.main.pipeline.segment_webtoon_visible_area(),
                        self._on_segmentation_bboxes_ready,
                        self.main.default_error_handler,
                        self.main.on_manual_finished,
                    )
                else:

                    def compute_all_bboxes() -> list[tuple[TextBlock, Any]]:
                        image = self.main.image_viewer.get_image_array()
                        results: list[tuple[TextBlock, Any]] = []
                        for blk in self.main.blk_list:
                            bboxes = get_inpaint_bboxes(blk.xyxy, image)
                            results.append((blk, bboxes))
                        return results

                    self.main.run_threaded(
                        compute_all_bboxes,
                        self._on_segmentation_bboxes_ready,
                        self.main.default_error_handler,
                        self.main.on_manual_finished,
                    )

            else:
                self.main.run_threaded(
                    self.main.pipeline.detect_blocks,
                    self.blk_detect_segment,
                    self.main.default_error_handler,
                    self.main.on_manual_finished,
                )

    def _on_segmentation_bboxes_ready(
        self, 
        results: Sequence[tuple[TextBlock, Any]]
    ) -> None:
        for blk, bboxes in results:
            blk.inpaint_bboxes = bboxes
            if bboxes is not None and len(bboxes) > 0:
                self.main.image_viewer.draw_segmentation_lines(bboxes)
        self.main.undo_group.activeStack().endMacro()
