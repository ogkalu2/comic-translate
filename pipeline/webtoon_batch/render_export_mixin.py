from __future__ import annotations

import logging
import os

import imkit as imk

from app.path_materialization import ensure_path_materialized
from app.ui.canvas.save_renderer import ImageSaveRenderer
from modules.utils.translator_utils import get_raw_text, get_raw_translation

logger = logging.getLogger(__name__)


class RenderExportMixin:
    def _save_final_rendered_page(
        self,
        page_idx: int,
        image_path: str,
        timestamp: str,
    ):
        logger.info(
            "Starting final render process for page %s at path: %s",
            page_idx,
            image_path,
        )

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
                os.path.join(path, f"{base_name}_cleaned{extension}"),
                cleaned_image_rgb,
            )

        blk_list = self.main_page.image_states[image_path].get("blk_list", [])

        if export_settings["export_raw_text"] and blk_list:
            path = os.path.join(
                directory,
                f"comic_translate_{timestamp}",
                "raw_texts",
                archive_bname,
            )
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            raw_text = get_raw_text(blk_list)
            with open(os.path.join(path, f"{base_name}_raw.json"), "w", encoding="UTF-8") as file:
                file.write(raw_text)

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
            ) as file:
                file.write(translated_text)
