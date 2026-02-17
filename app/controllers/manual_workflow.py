from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from modules.detection.utils.content import get_inpaint_bboxes
from modules.rendering.render import pyside_word_wrap, is_vertical_block
from modules.utils.common_utils import is_close
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.pipeline_config import validate_ocr, validate_translator
from modules.utils.translator_utils import is_there_text, format_translations
from pipeline.webtoon_utils import get_visible_text_items, get_first_visible_block

if TYPE_CHECKING:
    from app.ui.canvas.text_item import TextBlockItem
    from controller import ComicTranslate
    from modules.utils.textblock import TextBlock


class ManualWorkflowController:
    def __init__(self, main: ComicTranslate) -> None:
        self.main = main

    def block_detect(self, load_rects: bool = True) -> None:
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
        if self.main.image_viewer.hasPhoto() and self.main.image_viewer.has_drawn_elements():
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
