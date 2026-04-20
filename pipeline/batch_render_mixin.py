from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import traceback

from PySide6.QtGui import QColor

from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import OutlineInfo, OutlineType
from modules.rendering.font_sizing import resolve_init_font_size
from modules.rendering.policy import is_vertical_block
from modules.rendering.render import pyside_word_wrap
from modules.utils.image_utils import get_smart_text_color
from modules.utils.language_utils import is_no_space_lang
from modules.utils.translator_utils import format_translations, get_raw_text, get_raw_translation
from pipeline.page_state import has_runtime_patches as page_has_runtime_patches
from pipeline.render_state import (
    get_render_template_for_block,
    set_target_snapshot,
    update_render_style_overrides,
)
from pipeline.stage_state import (
    activate_target_lang,
    finalize_render_stage,
    mark_clean_ready,
    mark_ocr_ready,
    set_page_stage_validity,
)

logger = logging.getLogger(__name__)


class BatchRenderMixin:
    def _write_text_exports(
        self,
        page: PreparedBatchPage,
        export_settings: dict,
        entire_raw_text: str,
        entire_translated_text: str,
    ):
        if export_settings["export_raw_text"]:
            path = os.path.join(
                page.directory,
                f"comic_translate_{page.timestamp}",
                "raw_texts",
                page.archive_bname,
            )
            os.makedirs(path, exist_ok=True)
            with open(
                os.path.join(path, f"{page.base_name}_raw.json"),
                "w",
                encoding="utf-8",
            ) as file:
                file.write(entire_raw_text)

        if export_settings["export_translated_text"]:
            path = os.path.join(
                page.directory,
                f"comic_translate_{page.timestamp}",
                "translated_texts",
                page.archive_bname,
            )
            os.makedirs(path, exist_ok=True)
            with open(
                os.path.join(path, f"{page.base_name}_translated.json"),
                "w",
                encoding="utf-8",
            ) as file:
                file.write(entire_translated_text)

    def _validate_translation_payloads(
        self,
        page: PreparedBatchPage,
    ) -> tuple[str, str] | None:
        entire_raw_text = get_raw_text(page.blk_list)
        entire_translated_text = get_raw_translation(page.blk_list)

        try:
            raw_text_obj = json.loads(entire_raw_text)
            translated_text_obj = json.loads(entire_translated_text)
            if (not raw_text_obj) or (not translated_text_obj):
                self.skip_save(
                    page.directory,
                    page.timestamp,
                    page.base_name,
                    page.extension,
                    page.archive_bname,
                    page.image,
                )
                self.main_page.image_skipped.emit(page.image_path, "Translator", "")
                self.log_skipped_image(
                    page.directory,
                    page.timestamp,
                    page.image_path,
                    "Translator: empty JSON",
                )
                return None
        except json.JSONDecodeError as exc:
            error_message = str(exc)
            self.skip_save(
                page.directory,
                page.timestamp,
                page.base_name,
                page.extension,
                page.archive_bname,
                page.image,
            )
            self.main_page.image_skipped.emit(page.image_path, "Translator", error_message)
            self.log_skipped_image(
                page.directory,
                page.timestamp,
                page.image_path,
                f"Translator: JSONDecodeError: {error_message}",
                traceback.format_exc(),
            )
            return None

        return entire_raw_text, entire_translated_text

    def _render_page(self, page: PreparedBatchPage):
        render_settings = self.main_page.render_settings()
        upper_case = render_settings.upper_case
        outline = render_settings.outline

        format_translations(page.blk_list, page.trg_lng_cd, upper_case=upper_case)

        font = render_settings.font_family
        setting_font_color = QColor(render_settings.color)

        max_font_size = render_settings.max_font_size
        min_font_size = render_settings.min_font_size
        line_spacing = float(render_settings.line_spacing)
        outline_width = float(render_settings.outline_width)
        outline_color = QColor(render_settings.outline_color) if outline else None
        second_outline = render_settings.second_outline
        second_outline_width = float(render_settings.second_outline_width)
        second_outline_color = QColor(render_settings.second_outline_color) if second_outline else None
        text_gradient = render_settings.text_gradient
        gradient_start_color = QColor(render_settings.text_gradient_start_color) if text_gradient else None
        gradient_end_color = QColor(render_settings.text_gradient_end_color) if text_gradient else None
        bold = render_settings.bold
        italic = render_settings.italic
        underline = render_settings.underline
        alignment_id = render_settings.alignment_id
        alignment = self.main_page.button_to_alignment[alignment_id]
        direction = render_settings.direction
        file_on_display = self._current_displayed_file()

        template_map = self._build_render_template_map(page.image_path, page.target_lang)
        text_items_state = []
        for blk in page.blk_list:
            x1, y1, block_width, block_height = blk.xywh
            translation = blk.translation
            if not translation or len(translation) == 1:
                continue

            template = get_render_template_for_block(template_map, blk)
            position = template.get("position") or (x1, y1)
            block_width = float(template.get("width", block_width) or block_width)
            block_height = float(template.get("height", block_height) or block_height)
            rotation = template.get("rotation", blk.angle)
            scale = template.get("scale", 1.0)
            transform_origin = template.get("transform_origin", blk.tr_origin_point)
            font_family = template.get("font_family", font)
            line_spacing_for_block = float(template.get("line_spacing", line_spacing))
            outline_width_for_block = float(template.get("outline_width", outline_width))
            second_outline_for_block = bool(template.get("second_outline", second_outline))
            second_outline_width_for_block = float(template.get("second_outline_width", second_outline_width))
            template_second_outline_color = template.get("second_outline_color", second_outline_color)
            if template_second_outline_color is not None and not isinstance(template_second_outline_color, QColor):
                template_second_outline_color = QColor(template_second_outline_color)
            second_outline_color_for_block = template_second_outline_color if second_outline_for_block else None
            text_gradient_for_block = bool(template.get("text_gradient", text_gradient))
            template_gradient_start = template.get("text_gradient_start_color", gradient_start_color)
            template_gradient_end = template.get("text_gradient_end_color", gradient_end_color)
            if template_gradient_start is not None and not isinstance(template_gradient_start, QColor):
                template_gradient_start = QColor(template_gradient_start)
            if template_gradient_end is not None and not isinstance(template_gradient_end, QColor):
                template_gradient_end = QColor(template_gradient_end)
            bold_for_block = bool(template.get("bold", bold))
            italic_for_block = bool(template.get("italic", italic))
            underline_for_block = bool(template.get("underline", underline))
            alignment_for_block = template.get("alignment", alignment)
            direction_for_block = template.get("direction", direction)
            outline_enabled = bool(template.get("outline", outline))
            template_outline_color = template.get("outline_color", outline_color)
            if template_outline_color is not None and not isinstance(template_outline_color, QColor):
                template_outline_color = QColor(template_outline_color)
            outline_color_for_block = template_outline_color if outline_enabled else None
            template_font_color = template.get("text_color")
            if template_font_color is not None and not isinstance(template_font_color, QColor):
                template_font_color = QColor(template_font_color)

            vertical = is_vertical_block(blk, page.trg_lng_cd)
            block_init_font_size = int(
                round(template.get("font_size", resolve_init_font_size(blk, max_font_size, min_font_size)))
            )
            translation, font_size = pyside_word_wrap(
                translation,
                font_family,
                block_width,
                block_height,
                line_spacing_for_block,
                outline_width_for_block,
                bold_for_block,
                italic_for_block,
                underline_for_block,
                alignment_for_block,
                direction_for_block,
                block_init_font_size,
                min_font_size,
                vertical,
            )

            if page.image_path == file_on_display:
                self.main_page.blk_rendered.emit(translation, font_size, blk, page.image_path)

            if is_no_space_lang(page.trg_lng_cd):
                translation = translation.replace(" ", "")

            font_color = get_smart_text_color(blk.font_color, template_font_color or setting_font_color)
            text_props = TextItemProperties(
                text=translation,
                source_text=blk.translation or blk.text or translation,
                font_family=font_family,
                font_size=font_size,
                text_color=font_color,
                alignment=alignment_for_block,
                line_spacing=line_spacing_for_block,
                outline_color=outline_color_for_block,
                outline_width=outline_width_for_block,
                outline=outline_enabled,
                second_outline=second_outline_for_block,
                second_outline_color=second_outline_color_for_block,
                second_outline_width=second_outline_width_for_block,
                text_gradient=text_gradient_for_block,
                text_gradient_start_color=template_gradient_start if text_gradient_for_block else None,
                text_gradient_end_color=template_gradient_end if text_gradient_for_block else None,
                bold=bold_for_block,
                italic=italic_for_block,
                underline=underline_for_block,
                position=position,
                rotation=rotation,
                scale=scale,
                transform_origin=transform_origin,
                width=block_width,
                height=block_height,
                direction=direction_for_block,
                vertical=vertical,
                block_uid=getattr(blk, "block_uid", ""),
                selection_outlines=[
                    OutlineInfo(
                        0,
                        len(translation),
                        outline_color_for_block,
                        outline_width_for_block,
                        OutlineType.Full_Document,
                    )
                ]
                if outline_enabled and outline_color_for_block is not None
                else [],
            )
            text_items_state.append(text_props.to_dict())

        state = self.main_page.image_states[page.image_path]
        viewer_state = state.setdefault("viewer_state", {})
        viewer_state.update(
            {
                "text_items_state": text_items_state,
                "push_to_stack": False,
            }
        )
        set_target_snapshot(state, page.target_lang, viewer_state)
        update_render_style_overrides(state, viewer_state, overwrite=False)

    def _finalize_prepared_page(
        self,
        page: PreparedBatchPage,
        total_images: int,
        export_settings: dict,
        translator_key: str = "",
        extra_context: str = "",
    ) -> bool:
        payloads = self._validate_translation_payloads(page)
        if payloads is None:
            return True

        entire_raw_text, entire_translated_text = payloads
        self._write_text_exports(page, export_settings, entire_raw_text, entire_translated_text)

        self._render_page(page)

        self.emit_progress(page.index, total_images, 9, 10, False)
        if self._is_cancelled():
            return False

        state = self.main_page.image_states[page.image_path]
        state.update({"blk_list": page.blk_list, "target_lang": page.target_lang})

        if page.image_path == self._current_displayed_file():
            self.main_page.blk_list = page.blk_list

        has_runtime_patches = page_has_runtime_patches(
            state,
            self.main_page.image_patches,
            page.image_path,
        )
        ps, _ = activate_target_lang(
            state,
            page.target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        set_page_stage_validity(
            state,
            "detect",
            bool(page.blk_list),
            target_lang=page.target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        set_page_stage_validity(
            state,
            "segment",
            bool(
                state.get("brush_strokes")
                or any(getattr(blk, "inpaint_bboxes", None) is not None for blk in page.blk_list or [])
            ),
            target_lang=page.target_lang,
            has_runtime_patches=has_runtime_patches,
        )
        mark_ocr_ready(state, has_runtime_patches=has_runtime_patches)
        if self._get_cached_inpaint_patches(page.image_path):
            state["inpaint_cache"] = copy.deepcopy(self._get_cached_inpaint_patches(page.image_path))
            mark_clean_ready(state, has_runtime_patches=has_runtime_patches)
        ps, _ = finalize_render_stage(
            state,
            page.target_lang,
            has_runtime_patches=has_runtime_patches,
            ui_stage="render",
        )
        ps["ocr_cache_key"] = page.ocr_cache_key or ps.get("ocr_cache_key", "")
        ps["translator_key"] = translator_key
        context_signature = getattr(page, "translation_context_signature", "") or extra_context
        ps["extra_context_hash"] = hashlib.md5(context_signature.encode()).hexdigest() if context_signature else "no_context"
        self.main_page.render_state_ready.emit(page.image_path)

        self.emit_progress(page.index, total_images, 10, 10, False)
        return True
