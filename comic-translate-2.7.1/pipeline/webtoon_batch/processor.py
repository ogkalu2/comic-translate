from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from .chunk import ChunkMixin
from .flow import FlowMixin
from .render import RenderMixin

if TYPE_CHECKING:
    from controller import ComicTranslate
    from pipeline.cache_manager import CacheManager
    from pipeline.block_detection import BlockDetectionHandler
    from pipeline.inpainting import InpaintingHandler
    from pipeline.ocr_handler import OCRHandler

logger = logging.getLogger(__name__)


class WebtoonBatchProcessor(FlowMixin, ChunkMixin, RenderMixin):
    """
    Handles seam-aware webtoon batch processing with virtual-page streaming.

    Physical pages are split into fixed-height virtual pages (no overlap), then
    processed as adjacent pairs (n, n+1). Split blocks are merged and processed
    once on a minimal stitched crop, so OCR/inpainting never sees cut blocks.
    """

    def __init__(
        self: WebtoonBatchProcessor,
        main_page: ComicTranslate,
        cache_manager: CacheManager,
        block_detection_handler: BlockDetectionHandler,
        inpainting_handler: InpaintingHandler,
        ocr_handler: OCRHandler,
    ):
        self.main_page = main_page
        self.cache_manager = cache_manager
        # Use shared handlers from the main pipeline.
        self.block_detection = block_detection_handler
        self.inpainting = inpainting_handler
        self.ocr_handler = ocr_handler

        # State tracking for per-page patch accumulation.
        self.final_patches_for_save = defaultdict(list)
        self._reported_image_load_failures = set()

        # Seam matching / crop settings.
        self.min_virtual_chunk_height = 2000
        self.max_virtual_chunk_height = 3500
        self.target_virtual_chunk_height = 2400
        self.edge_threshold = 50
        self.seam_crop_pad_x = 48
        self.seam_crop_pad_y = 48

    def skip_save(
        self: WebtoonBatchProcessor,
        directory,
        timestamp,
        base_name,
        extension,
        archive_bname,
        image,
    ):
        logger.info("Skipping fallback translated image save for '%s'.", base_name)

    def log_skipped_image(
        self: WebtoonBatchProcessor,
        directory,
        timestamp,
        image_path,
        reason="",
        full_traceback="",
    ):
        # Deprecated: skip details are captured by batch reporting/UI signals.
        return
