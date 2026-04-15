from __future__ import annotations

import logging
from typing import Dict, List

from PySide6.QtGui import QColor

from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import OutlineInfo, OutlineType
from modules.rendering.render import is_vertical_block, pyside_word_wrap
from modules.utils.image_utils import get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.textblock import TextBlock
from ..render_state import build_render_template_map_from_snapshot, get_target_snapshot, set_target_snapshot
from ..virtual_page import PageStatus, VirtualPage

logger = logging.getLogger(__name__)


class RenderEmitMixin:
    def _emit_and_store_virtual_page_results(
        self,
        vpage: VirtualPage,
        blk_list_virtual: List[TextBlock],
    ):
        image_path = vpage.physical_page_path
        page_state = self.main_page.image_states[image_path]
        viewer_state = page_state.setdefault("viewer_state", {})
        text_items_state = viewer_state.setdefault("text_items_state", [])
        page_blk_list = page_state.setdefault("blk_list", [])

        should_emit_live = False
        webtoon_manager = None
        if self.main_page.webtoon_mode:
            webtoon_manager = self.main_page.image_viewer.webtoon_manager
            if vpage.physical_page_index in webtoon_manager.loaded_pages:
                should_emit_live = True

        if should_emit_live:
            logger.info("Emitting and storing text items for confirmed virtual page %s", vpage.virtual_id)
        else:
            logger.info("Storing text items for confirmed virtual page %s (parent not visible)", vpage.virtual_id)

        render_settings = self.main_page.render_settings()
        font = render_settings.font_family
        base_font_color = QColor(render_settings.color)
        max_font_size = render_settings.max_font_size
        min_font_size = render_settings.min_font_size
        line_spacing = float(render_settings.line_spacing)
        outline_width = float(render_settings.outline_width)
        outline = render_settings.outline
        outline_color = QColor(render_settings.outline_color) if outline else None
        bold = render_settings.bold
        italic = render_settings.italic
        underline = render_settings.underline
        alignment = self.main_page.button_to_alignment[render_settings.alignment_id]
        direction = render_settings.direction

        target_lang = self.main_page.image_states[image_path]["target_lang"]
        target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
        trg_lng_cd = get_language_code(target_lang_en)
        target_snapshot = get_target_snapshot(page_state, target_lang) or viewer_state
        template_map = build_render_template_map_from_snapshot(target_snapshot)

        page_y_position_in_scene = 0
        if webtoon_manager and vpage.physical_page_index < len(webtoon_manager.image_positions):
            page_y_position_in_scene = webtoon_manager.image_positions[vpage.physical_page_index]

        for blk_virtual in blk_list_virtual:
            physical_coords = vpage.virtual_to_physical_coords(blk_virtual.xyxy)
            x1, y1, x2, y2 = physical_coords
            block_width = x2 - x1
            block_height = y2 - y1

            translation = blk_virtual.translation
            if not translation or len(translation) < 1:
                continue

            if webtoon_manager and self._should_suppress_clipped_block(
                vpage.physical_page_index, physical_coords, vpage.physical_height
            ):
                continue

            block_uid = str(getattr(blk_virtual, "block_uid", "") or "")
            template = template_map.get((block_uid, (), 0.0), {}) if block_uid else {}
            if not template:
                template = template_map.get(
                    ("", tuple(map(int, physical_coords)), float(getattr(blk_virtual, "angle", 0.0) or 0.0)),
                    {},
                )

            font_for_block = template.get("font_family", font)
            line_spacing_for_block = float(template.get("line_spacing", line_spacing))
            outline_width_for_block = float(template.get("outline_width", outline_width))
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

            vertical = is_vertical_block(blk_virtual, trg_lng_cd)
            translation, font_size, rendered_width, rendered_height = pyside_word_wrap(
                translation,
                font_for_block,
                block_width,
                block_height,
                line_spacing_for_block,
                outline_width_for_block,
                bold_for_block,
                italic_for_block,
                underline_for_block,
                alignment_for_block,
                direction_for_block,
                max_font_size,
                min_font_size,
                vertical,
                return_metrics=True,
            )

            if is_no_space_lang(trg_lng_cd):
                translation = translation.replace(" ", "")

            resolved_font_color = get_smart_text_color(blk_virtual.font_color, template_font_color or base_font_color)

            render_blk = blk_virtual.deep_copy()
            render_blk.xyxy = list(physical_coords)
            if render_blk.bubble_xyxy:
                render_blk.bubble_xyxy = vpage.virtual_to_physical_coords(render_blk.bubble_xyxy)

            render_blk.xyxy[1] += page_y_position_in_scene
            render_blk.xyxy[3] += page_y_position_in_scene
            if render_blk.bubble_xyxy:
                render_blk.bubble_xyxy[1] += page_y_position_in_scene
                render_blk.bubble_xyxy[3] += page_y_position_in_scene

            render_blk.translation = translation
            if should_emit_live:
                self.main_page.blk_rendered.emit(translation, font_size, render_blk, image_path)
                self.main_page.blk_list.append(render_blk)

            text_props = TextItemProperties(
                text=translation,
                source_text=blk_virtual.translation or blk_virtual.text or translation,
                font_family=font_for_block,
                font_size=font_size,
                text_color=resolved_font_color,
                alignment=alignment_for_block,
                line_spacing=line_spacing_for_block,
                outline_color=outline_color_for_block,
                outline_width=outline_width_for_block,
                outline=outline_enabled,
                bold=bold_for_block,
                italic=italic_for_block,
                underline=underline_for_block,
                position=(x1, y1),
                rotation=blk_virtual.angle,
                scale=1.0,
                transform_origin=(blk_virtual.tr_origin_point if blk_virtual.tr_origin_point else (0, 0)),
                width=rendered_width,
                height=rendered_height,
                direction=direction_for_block,
                vertical=vertical,
                block_uid=getattr(blk_virtual, "block_uid", ""),
                selection_outlines=[
                    OutlineInfo(0, len(translation), outline_color_for_block, outline_width_for_block, OutlineType.Full_Document)
                ] if outline_enabled and outline_color_for_block is not None else [],
            )
            text_items_state.append(text_props.to_dict())
            page_blk_list.append(render_blk)

            if webtoon_manager and vpage.physical_page_index < len(webtoon_manager.image_positions):
                src_idx = vpage.physical_page_index
                src_pos = float(webtoon_manager.image_positions[src_idx])
                for tgt_idx in (src_idx - 1, src_idx + 1):
                    if tgt_idx < 0 or tgt_idx >= len(webtoon_manager.image_positions):
                        continue
                    if tgt_idx >= len(webtoon_manager.image_heights):
                        continue

                    tgt_pos = float(webtoon_manager.image_positions[tgt_idx])
                    tgt_h = float(webtoon_manager.image_heights[tgt_idx])
                    if tgt_h <= 0:
                        continue

                    dy = src_pos - tgt_pos
                    mapped = [float(x1), float(y1) + dy, float(x2), float(y2) + dy]
                    clipped = [mapped[0], max(0.0, mapped[1]), mapped[2], min(tgt_h, mapped[3])]
                    if clipped[3] <= clipped[1]:
                        continue
                    if self._rect_area_xyxy(clipped) <= 20.0:
                        continue
                    self._spanning_claims_by_page[tgt_idx].append(clipped)

        set_target_snapshot(page_state, target_lang, viewer_state)

    def _finalize_and_emit_for_virtual_page(self, vpage: VirtualPage):
        virtual_page_id = vpage.virtual_id

        merged_blocks = self._merge_virtual_page_results(virtual_page_id)
        all_patches = []
        for chunk_id in self.virtual_page_to_chunks.get(virtual_page_id, []):
            chunk_data = self.virtual_chunk_results.get(chunk_id)
            if chunk_data and "patches" in chunk_data and virtual_page_id in chunk_data["patches"]:
                all_patches.extend(chunk_data["patches"][virtual_page_id])

        deduped_virtual_patches = self._filter_duplicate_patches([], all_patches)
        if deduped_virtual_patches:
            page_patches = self.final_patches_for_save[vpage.physical_page_path]
            new_page_patches = self._filter_duplicate_patches(page_patches, deduped_virtual_patches)
            if new_page_patches:
                logger.info("Emitting %s inpaint patches for confirmed VP %s", len(new_page_patches), virtual_page_id)
                self.main_page.patches_processed.emit(new_page_patches, vpage.physical_page_path)
                page_patches.extend(new_page_patches)

        if merged_blocks:
            self._emit_and_store_virtual_page_results(vpage, merged_blocks)

    def _check_and_render_page(
        self,
        p_idx: int,
        total_images: int,
        image_list: List[str],
        timestamp: str,
        physical_to_virtual_mapping: Dict,
    ):
        if self.physical_page_status.get(p_idx) != PageStatus.LIVE_DATA_FINALIZED:
            return

        prev_page_ready = (p_idx == 0) or (self.physical_page_status.get(p_idx - 1) in [PageStatus.LIVE_DATA_FINALIZED, PageStatus.RENDERED])
        next_page_ready = (p_idx == total_images - 1) or (self.physical_page_status.get(p_idx + 1) in [PageStatus.LIVE_DATA_FINALIZED, PageStatus.RENDERED])

        if prev_page_ready and next_page_ready:
            logger.info("Page %s and its neighbors' states are ready. Proceeding with final render.", p_idx)
            image_path = image_list[p_idx]
            virtual_pages = physical_to_virtual_mapping.get(p_idx)
            if not virtual_pages:
                logger.warning("Skipping render for page %s as it has no virtual pages (might have been skipped).", p_idx)
                self.physical_page_status[p_idx] = PageStatus.RENDERED
                return

            self._prepare_physical_page_for_render(p_idx, image_path, virtual_pages)
            self._save_final_rendered_page(p_idx, image_path, timestamp)
            self.physical_page_status[p_idx] = PageStatus.RENDERED
            logger.info("Successfully rendered and saved physical page %s.", p_idx)
