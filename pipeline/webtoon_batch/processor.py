import logging
from collections import defaultdict

from ..virtual_page import PageStatus, VirtualPageCreator
from .chunk import ChunkMixin
from .dedupe import DedupeMixin
from .flow import FlowMixin
from .render import RenderMixin

logger = logging.getLogger(__name__)


class WebtoonBatchProcessor(FlowMixin, ChunkMixin, DedupeMixin, RenderMixin):
    """
    Handles batch processing of webtoon translation using virtual pages and
    overlapping sliding windows.
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

        # Virtual page settings.
        self.max_virtual_height = 2000
        self.overlap_height = 200
        self.virtual_page_creator = VirtualPageCreator(
            max_virtual_height=self.max_virtual_height,
            overlap_height=self.overlap_height,
        )

        # State tracking for virtual chunks/pages.
        self.virtual_chunk_results = defaultdict(list)
        self.virtual_page_processing_count = defaultdict(int)
        self.finalized_virtual_pages = set()
        self.physical_page_results = defaultdict(list)
        self.physical_page_status = defaultdict(lambda: PageStatus.UNPROCESSED)
        self.final_patches_for_save = defaultdict(list)

        # Edge detection settings.
        self.edge_threshold = 50

    def skip_save(self, directory, timestamp, base_name, extension, archive_bname, image):
        logger.info("Skipping fallback translated image save for '%s'.", base_name)

    def log_skipped_image(self, directory, timestamp, image_path, reason="", full_traceback=""):
        # Deprecated: skip details are captured by batch reporting/UI signals.
        return
