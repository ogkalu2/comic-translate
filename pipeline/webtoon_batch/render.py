import logging
import os
from types import SimpleNamespace
from typing import Dict, List

import imkit as imk
from PySide6.QtGui import QColor

from app.path_materialization import ensure_path_materialized
from app.ui.canvas.save_renderer import ImageSaveRenderer
from app.ui.canvas.text.text_item_properties import TextItemProperties
from app.ui.canvas.text_item import OutlineInfo, OutlineType
from modules.rendering.render import get_best_render_area, is_vertical_block, pyside_word_wrap
from modules.utils.image_utils import get_smart_text_color
from modules.utils.language_utils import get_language_code, is_no_space_lang
from modules.utils.textblock import TextBlock
from modules.utils.translator_utils import format_translations, get_raw_text, get_raw_translation
from ..virtual_page import PageStatus, VirtualPage

logger = logging.getLogger(__name__)


class RenderMixin:
    def _prepare_physical_page_for_render(
        self,
        physical_page_index: int,
        image_path: str,
        virtual_pages: List[VirtualPage],
    ):
        """
        Calculate and store the final, complete block list for a physical page.
        """
        logger.info("Preparing final block list for physical page %s", physical_page_index)

        # Merge results from all virtual pages belonging to this physical page.
        all_physical_blocks = []
        for vpage in virtual_pages:
            merged_virtual_blocks = self._merge_virtual_page_results(vpage.virtual_id)
            for block in merged_virtual_blocks:
                physical_block = block.deep_copy()
                physical_block.xyxy = vpage.virtual_to_physical_coords(block.xyxy)
                if block.bubble_xyxy:
                    physical_block.bubble_xyxy = vpage.virtual_to_physical_coords(
                        block.bubble_xyxy
                    )
                all_physical_blocks.append(physical_block)

        final_blocks = self._deduplicate_physical_blocks(all_physical_blocks)
        if not final_blocks:
            logger.warning(
                "No final blocks found for physical page %s. Marking for skip.",
                physical_page_index,
            )
            self.main_page.image_states[image_path]["blk_list"] = []
            self.main_page.image_states[image_path]["skip_render"] = True
            return

        self.main_page.image_states[image_path]["skip_render"] = False
        logger.info(
            "Prepared physical page %s with %s final blocks.",
            physical_page_index,
            len(final_blocks),
        )

        render_settings = self.main_page.render_settings()
        target_lang = self.main_page.image_states[image_path]["target_lang"]
        target_lang_en = self.main_page.lang_mapping.get(target_lang, None)
        trg_lng_cd = get_language_code(target_lang_en)
        format_translations(final_blocks, trg_lng_cd, upper_case=render_settings.upper_case)

        if is_no_space_lang(trg_lng_cd):
            for blk in final_blocks:
                if blk.translation:
                    blk.translation = blk.translation.replace(" ", "")

        self.main_page.image_states[image_path].update({"blk_list": final_blocks})
        if "viewer_state" in self.main_page.image_states[image_path]:
            self.main_page.image_states[image_path]["viewer_state"]["push_to_stack"] = True

    def _emit_and_store_virtual_page_results(
        self, vpage: VirtualPage, blk_list_virtual: List[TextBlock]
    ):
        """
        Emit live render signals (if visible) and store final text item state.
        """
        image_path = vpage.physical_page_path
        # Ensure page state containers exist even if this is the first finalized virtual page.
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
            logger.info(
                "Emitting and storing text items for confirmed virtual page %s",
                vpage.virtual_id,
            )
        else:
            logger.info(
                "Storing text items for confirmed virtual page %s (parent not visible)",
                vpage.virtual_id,
            )

        render_settings = self.main_page.render_settings()
        font = render_settings.font_family
        font_color = QColor(render_settings.color)
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

        page_y_position_in_scene = 0
        if webtoon_manager and vpage.physical_page_index < len(webtoon_manager.image_positions):
            page_y_position_in_scene = webtoon_manager.image_positions[
                vpage.physical_page_index
            ]

        # In webtoon mode this is the correct stage for bubble-aware bounds:
        # after merge/dedupe, before wrapping/state creation.
        virtual_img = SimpleNamespace(shape=(vpage.crop_height, vpage.physical_width, 3))
        get_best_render_area(blk_list_virtual, virtual_img)

        for blk_virtual in blk_list_virtual:
            physical_coords = vpage.virtual_to_physical_coords(blk_virtual.xyxy)
            x1, y1, x2, y2 = physical_coords
            block_width = x2 - x1
            block_height = y2 - y1

            translation = blk_virtual.translation
            if not translation or len(translation) < 1:
                continue

            vertical = is_vertical_block(blk_virtual, trg_lng_cd)
            translation, font_size, rendered_width, rendered_height = pyside_word_wrap(
                translation,
                font,
                block_width,
                block_height,
                line_spacing,
                outline_width,
                bold,
                italic,
                underline,
                alignment,
                direction,
                max_font_size,
                min_font_size,
                vertical,
                return_metrics=True,
            )

            if is_no_space_lang(trg_lng_cd):
                translation = translation.replace(" ", "")

            font_color = get_smart_text_color(blk_virtual.font_color, font_color)

            render_blk = blk_virtual.deep_copy()
            render_blk.xyxy = list(physical_coords)
            if render_blk.bubble_xyxy:
                render_blk.bubble_xyxy = vpage.virtual_to_physical_coords(
                    render_blk.bubble_xyxy
                )

            render_blk.xyxy[1] += page_y_position_in_scene
            render_blk.xyxy[3] += page_y_position_in_scene
            if render_blk.bubble_xyxy:
                render_blk.bubble_xyxy[1] += page_y_position_in_scene
                render_blk.bubble_xyxy[3] += page_y_position_in_scene

            render_blk.translation = translation
            if should_emit_live:
                self.main_page.blk_rendered.emit(translation, font_size, render_blk, image_path)
                self.main_page.blk_list.append(render_blk)

            # Store text item state for final page save regardless of live visibility.
            text_props = TextItemProperties(
                text=translation,
                font_family=font,
                font_size=font_size,
                text_color=font_color,
                alignment=alignment,
                line_spacing=line_spacing,
                outline_color=outline_color,
                outline_width=outline_width,
                bold=bold,
                italic=italic,
                underline=underline,
                position=(x1, y1),
                rotation=blk_virtual.angle,
                scale=1.0,
                transform_origin=(
                    blk_virtual.tr_origin_point
                    if blk_virtual.tr_origin_point
                    else (0, 0)
                ),
                width=rendered_width,
                height=rendered_height,
                direction=direction,
                vertical=vertical,
                selection_outlines=[
                    OutlineInfo(
                        0,
                        len(translation),
                        outline_color,
                        outline_width,
                        OutlineType.Full_Document,
                    )
                ]
                if outline
                else [],
            )
            text_items_state.append(text_props.to_dict())
            page_blk_list.append(render_blk)

    def _finalize_and_emit_for_virtual_page(self, vpage: VirtualPage):
        """
        Merge results for a confirmed virtual page and emit patches/text items.
        """
        virtual_page_id = vpage.virtual_id

        # 1) Merge blocks for this virtual page from all processed chunks.
        merged_blocks = self._merge_virtual_page_results(virtual_page_id)
        # 2) Merge/dedupe patches for this virtual page.
        all_patches = []
        for chunk_id in self.virtual_page_to_chunks.get(virtual_page_id, []):
            chunk_data = self.virtual_chunk_results.get(chunk_id)
            if (
                chunk_data
                and "patches" in chunk_data
                and virtual_page_id in chunk_data["patches"]
            ):
                all_patches.extend(chunk_data["patches"][virtual_page_id])

        deduped_virtual_patches = self._filter_duplicate_patches([], all_patches)
        if deduped_virtual_patches:
            page_patches = self.final_patches_for_save[vpage.physical_page_path]
            new_page_patches = self._filter_duplicate_patches(
                page_patches, deduped_virtual_patches
            )
            if new_page_patches:
                logger.info(
                    "Emitting %s inpaint patches for confirmed VP %s",
                    len(new_page_patches),
                    virtual_page_id,
                )
                self.main_page.patches_processed.emit(
                    new_page_patches, vpage.physical_page_path
                )
                page_patches.extend(new_page_patches)

        # 3) Emit/store text items using the same finalized block set.
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
        """
        Check if a page and its neighbors are ready, and render/save if so.
        """
        # A page is render-ready only after live data is finalized.
        if self.physical_page_status.get(p_idx) != PageStatus.LIVE_DATA_FINALIZED:
            return

        # Neighbor gating is required for seam-aware finalization.
        prev_page_ready = (p_idx == 0) or (
            self.physical_page_status.get(p_idx - 1)
            in [PageStatus.LIVE_DATA_FINALIZED, PageStatus.RENDERED]
        )
        next_page_ready = (p_idx == total_images - 1) or (
            self.physical_page_status.get(p_idx + 1)
            in [PageStatus.LIVE_DATA_FINALIZED, PageStatus.RENDERED]
        )

        if prev_page_ready and next_page_ready:
            logger.info(
                "Page %s and its neighbors' states are ready. Proceeding with final render.",
                p_idx,
            )
            image_path = image_list[p_idx]
            virtual_pages = physical_to_virtual_mapping.get(p_idx)
            if not virtual_pages:
                logger.warning(
                    "Skipping render for page %s as it has no virtual pages (might have been skipped).",
                    p_idx,
                )
                self.physical_page_status[p_idx] = PageStatus.RENDERED
                return

            self._prepare_physical_page_for_render(p_idx, image_path, virtual_pages)
            self._save_final_rendered_page(p_idx, image_path, timestamp)
            self.physical_page_status[p_idx] = PageStatus.RENDERED
            logger.info("Successfully rendered and saved physical page %s.", p_idx)

    def _save_final_rendered_page(
        self, page_idx: int, image_path: str, timestamp: str
    ):
        """
        Handle per-page exports once a page and its neighbors are finalized.
        """
        logger.info(
            "Starting final render process for page %s at path: %s", page_idx, image_path
        )

        # Start from original physical image; patches/text exports are layered afterward.
        ensure_path_materialized(image_path)
        image = imk.read_image(image_path)
        if image is None:
            logger.error("Failed to load physical image for rendering: %s", image_path)
            return

        base_name = os.path.splitext(os.path.basename(image_path))[0].strip()
        extension = os.path.splitext(image_path)[1]
        directory = os.path.dirname(image_path)

        archive_bname = ""
        for archive in self.main_page.file_handler.archive_info:
            if image_path in archive["extracted_images"]:
                archive_path = archive["archive_path"]
                directory = os.path.dirname(archive_path)
                archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                break

        if self.main_page.image_states[image_path].get("skip_render"):
            logger.info("Skipping final render for page %s, copying original.", page_idx)
            reason = "No text blocks detected or processed successfully."
            self.skip_save(directory, timestamp, base_name, extension, archive_bname, image)
            self.log_skipped_image(directory, timestamp, image_path, reason)
            return

        settings_page = self.main_page.settings_page
        export_settings = settings_page.get_export_settings()

        # Export cleaned image (inpaint patches only) before any text rasterization.
        if export_settings["export_inpainted_image"]:
            renderer = ImageSaveRenderer(image)
            patches = self.final_patches_for_save.get(image_path, [])
            renderer.apply_patches(patches)
            path = os.path.join(
                directory,
                f"comic_translate_{timestamp}",
                "cleaned_images",
                archive_bname,
            )
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            cleaned_image_rgb = renderer.render_to_image()
            imk.write_image(
                os.path.join(path, f"{base_name}_cleaned{extension}"), cleaned_image_rgb
            )

        blk_list = self.main_page.image_states[image_path].get("blk_list", [])

        # Export raw + translated text snapshots from finalized block list.
        if export_settings["export_raw_text"] and blk_list:
            path = os.path.join(
                directory, f"comic_translate_{timestamp}", "raw_texts", archive_bname
            )
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            raw_text = get_raw_text(blk_list)
            with open(os.path.join(path, f"{base_name}_raw.json"), "w", encoding="UTF-8") as f:
                f.write(raw_text)

        if export_settings["export_translated_text"] and blk_list:
            path = os.path.join(
                directory,
                f"comic_translate_{timestamp}",
                "translated_texts",
                archive_bname,
            )
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            translated_text = get_raw_translation(blk_list)
            with open(
                os.path.join(path, f"{base_name}_translated.json"),
                "w",
                encoding="UTF-8",
            ) as f:
                f.write(translated_text)
