import logging
from modules.detection.utils.general import get_inpaint_bboxes
from .webtoon_utils import (
    filter_and_convert_visible_blocks, 
    restore_original_block_coordinates,
    convert_bboxes_to_webtoon_coordinates
)

logger = logging.getLogger(__name__)


class SegmentationHandler:
    """Handles text segmentation processing for both regular and webtoon modes."""
    
    def __init__(self, main_page, pipeline):
        self.main_page = main_page
        self.pipeline = pipeline

    def segment_webtoon_visible_area(self):
        """Perform segmentation on the visible area in webtoon mode."""
        
        if not (self.main_page.image_viewer.hasPhoto() and 
                self.main_page.webtoon_mode):
            logger.warning("segment_webtoon_visible_area called but not in webtoon mode")
            return
        
        # Get the visible area image and mapping data
        visible_image, mappings = self.main_page.image_viewer.get_visible_area_image()
        if visible_image is None or not mappings:
            logger.warning("No visible area found for segmentation")
            return
        
        # Filter blocks to only those in the visible area and convert coordinates
        # Note: Segmentation always processes all visible blocks, so single_block=False
        visible_blocks = filter_and_convert_visible_blocks(
            self.main_page, self.pipeline, mappings, single_block=False
        )
        if not visible_blocks:
            logger.info("No blocks found in visible area for segmentation")
            return
        
        # Perform segmentation on the visible image with filtered blocks
        results = []
        image_height, image_width = visible_image.shape[:2]
        
        for blk in visible_blocks:
            # Coordinates are already integers, just ensure they're within bounds
            x1 = max(0, min(blk.xyxy[0], image_width - 1))
            y1 = max(0, min(blk.xyxy[1], image_height - 1))
            x2 = max(x1 + 1, min(blk.xyxy[2], image_width))
            y2 = max(y1 + 1, min(blk.xyxy[3], image_height))
            
            bounded_xyxy = [x1, y1, x2, y2]
            bboxes = get_inpaint_bboxes(bounded_xyxy, visible_image)
            results.append((blk, bboxes))
        
        # Convert bbox coordinates back to webtoon scene coordinates and update original blocks
        webtoon_manager = self.main_page.image_viewer.webtoon_manager
        for blk, bboxes in results:
            if not hasattr(blk, '_original_xyxy'):
                continue
            
            if bboxes is not None:
                mapping = blk._mapping
                page_idx = blk._page_index
                converted_bboxes = convert_bboxes_to_webtoon_coordinates(bboxes, mapping, page_idx, webtoon_manager)
                blk.inpaint_bboxes = converted_bboxes
            else:
                blk.inpaint_bboxes = None

        # Restore original block coordinates and clean up
        processed_blocks = [blk for blk, _ in results]
        restore_original_block_coordinates(processed_blocks)
        
        # Return results with converted bboxes from the blocks
        final_results = []
        for blk, _ in results:
            final_results.append((blk, blk.inpaint_bboxes))
        
        logger.info(f"Segmentation completed for {len(visible_blocks)} blocks in visible area")
        
        return final_results
