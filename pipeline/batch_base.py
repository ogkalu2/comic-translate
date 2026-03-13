from __future__ import annotations

import os
import threading
import logging
import shutil
import imkit as imk
from typing import TYPE_CHECKING

from modules.utils.common_utils import is_directory_empty
from modules.utils.archives import make, resolve_save_as_ext

if TYPE_CHECKING:
    from .cache_manager import CacheManager
    from .block_detection import BlockDetectionHandler
    from .inpainting import InpaintingHandler
    from .ocr_handler import OCRHandler

logger = logging.getLogger(__name__)


class BatchProcessorBase:
    """Shared base class for BatchProcessor and WebtoonBatchProcessor."""

    _inpainter_lock = threading.Lock()  # class-level: shared across all instances

    def __init__(self, main_page, cache_manager, block_detection, inpainting, ocr_handler):
        self.main_page = main_page
        self.cache_manager = cache_manager
        self.block_detection = block_detection
        self.inpainting = inpainting
        self.ocr_handler = ocr_handler

    # ------------------------------------------------------------------
    # Skip / log helpers
    # ------------------------------------------------------------------

    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        path = os.path.join(directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        imk.write_image(os.path.join(path, f"{base_name}_translated{extension}"), image)

    def log_skipped_image(self, directory, timestamp, image_path, reason="", full_traceback=""):
        skipped_file = os.path.join(directory, f"comic_translate_{timestamp}", "skipped_images.txt")
        os.makedirs(os.path.dirname(skipped_file), exist_ok=True)
        with open(skipped_file, 'a', encoding='UTF-8') as file:
            file.write(image_path + "\n")
            file.write(reason + "\n")
            if full_traceback:
                file.write("Full Traceback:\n")
                file.write(full_traceback + "\n")
            file.write("\n")

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def _is_cancelled(self) -> bool:
        worker = getattr(self.main_page, "current_worker", None)
        return bool(worker and worker.is_cancelled)

    # ------------------------------------------------------------------
    # Archive path resolution
    # ------------------------------------------------------------------

    def _resolve_archive_info(self, image_path: str) -> tuple[str, str]:
        """Return (directory, archive_bname) for the given image path.

        Falls back to the image's own directory when the path is not part of
        any known archive.
        """
        directory = os.path.dirname(image_path)
        archive_bname = ""
        for archive in self.main_page.file_handler.archive_info:
            if image_path in archive['extracted_images']:
                archive_path = archive['archive_path']
                directory = os.path.dirname(archive_path)
                archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
                break
        return directory, archive_bname

    # ------------------------------------------------------------------
    # Thread-safe inpainter init
    # ------------------------------------------------------------------

    def _ensure_inpainter(self):
        """Thread-safe lazy initialisation. Delegates to InpaintingHandler."""
        with BatchProcessorBase._inpainter_lock:
            self.inpainting._ensure_inpainter()

    # ------------------------------------------------------------------
    # Archive packing (end-of-batch)
    # ------------------------------------------------------------------

    def _pack_archives(self, timestamp: str, total_images: int, export_settings: dict):
        """Pack translated images back into archives after a batch run."""
        archive_info_list = self.main_page.file_handler.archive_info
        if not (archive_info_list and export_settings.get('auto_save')):
            return

        archive_save_as = export_settings.get('archive_save_as')
        for archive_index, archive in enumerate(archive_info_list):
            archive_index_input = total_images + archive_index

            self.main_page.progress_update.emit(archive_index_input, total_images, 1, 3, True)
            if self._is_cancelled():
                return

            archive_path = archive['archive_path']
            archive_ext = os.path.splitext(archive_path)[1]
            archive_bname = os.path.splitext(os.path.basename(archive_path))[0].strip()
            archive_directory = os.path.dirname(archive_path)
            save_as_ext = resolve_save_as_ext(archive_ext, archive_save_as)

            save_dir = os.path.join(archive_directory, f"comic_translate_{timestamp}", "translated_images", archive_bname)
            check_from = os.path.join(archive_directory, f"comic_translate_{timestamp}")

            if not os.path.exists(save_dir) or is_directory_empty(save_dir):
                logger.warning("Skipping archive creation for %s: render directory is empty.", archive_bname)
                continue

            self.main_page.progress_update.emit(archive_index_input, total_images, 2, 3, True)
            if self._is_cancelled():
                return

            make(save_as_ext=save_as_ext, input_dir=save_dir,
                 output_dir=archive_directory, output_base_name=archive_bname)

            self.main_page.progress_update.emit(archive_index_input, total_images, 3, 3, True)
            if self._is_cancelled():
                return

            if os.path.exists(save_dir):
                shutil.rmtree(save_dir)
            if os.path.exists(check_from) and is_directory_empty(check_from):
                shutil.rmtree(check_from)
