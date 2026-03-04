import logging
from collections import defaultdict

from .chunk import ChunkMixin
from .flow import FlowMixin
from .render import RenderMixin

logger = logging.getLogger(__name__)


class WebtoonBatchProcessor(FlowMixin, ChunkMixin, RenderMixin):
    """
    Handles seam-aware webtoon batch processing with virtual-page streaming.

    Physical pages are split into fixed-height virtual pages (no overlap), then
    processed as adjacent pairs (n, n+1). Split blocks are merged and processed
    once on a minimal stitched crop, so OCR/inpainting never sees cut blocks.
    """

    def __init__(
        self,
        main_page,
        cache_manager,
        block_detection_handler,
        inpainting_handler,
        ocr_handler,
    ):
        self.main_page = main_page
        self.cache_manager = cache_manager
        # Use shared handlers from the main pipeline.
        self.block_detection = block_detection_handler
        self.inpainting = inpainting_handler
        self.ocr_handler = ocr_handler

        # State tracking for per-page patch accumulation.
        self.final_patches_for_save = defaultdict(list)

        # Seam matching / crop settings.
        self.max_virtual_height = 2000
        self.edge_threshold = 50
        self.seam_crop_pad_x = 48
        self.seam_crop_pad_y = 48

    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        logger.info("Skipping fallback translated image save for '%s'.", base_name)

    def log_skipped_image(self, directory, timestamp, image_path, reason="", full_traceback=""):
        # Deprecated: skip details are captured by batch reporting/UI signals.
        return
