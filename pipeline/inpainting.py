import numpy as np
import logging
import imkit as imk

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QBrush

from modules.detection.utils.content import get_inpaint_bboxes
from modules.utils.image_utils import generate_mask
from modules.utils.textblock import TextBlock
from modules.utils.device import resolve_device
from modules.utils.pipeline_config import inpaint_map, get_config

logger = logging.getLogger(__name__)


class InpaintingHandler:
    """Handles image inpainting functionality."""
    
    def __init__(self, main_page):
        self.main_page = main_page
        self.inpainter_cache = None
        self.cached_inpainter_key = None

    def _ensure_inpainter(self):
        settings_page = self.main_page.settings_page
        inpainter_key = settings_page.get_tool_selection('inpainter')
        if self.inpainter_cache is None or self.cached_inpainter_key != inpainter_key:
            backend = 'onnx'
            device = resolve_device(settings_page.is_gpu_enabled(), backend)
            InpainterClass = inpaint_map[inpainter_key]
            self.inpainter_cache = InpainterClass(device, backend=backend)
            self.cached_inpainter_key = inpainter_key
        return self.inpainter_cache

    @staticmethod
    def _is_probable_oom(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(
            marker in text
            for marker in (
                "out of memory",
                "cuda error",
                "cudnn",
                "failed to allocate",
                "memory allocation",
            )
        )

    def supports_image_batching(self, config=None) -> bool:
        inpainter = self._ensure_inpainter()
        return bool(
            getattr(inpainter, "supports_image_batching", lambda _config=None: False)(config)
        )

    def inpaint_many(self, images, masks, config, batch_size: int | None = None):
        inpainter = self._ensure_inpainter()
        if not images:
            return []

        if not self.supports_image_batching(config):
            return [inpainter(image, mask, config) for image, mask in zip(images, masks)]

        effective_batch_size = max(1, int(batch_size or len(images)))
        results = [None] * len(images)
        next_index = 0
        current_batch_size = min(effective_batch_size, len(images))

        while next_index < len(images):
            chunk_end = min(len(images), next_index + current_batch_size)
            chunk_images = images[next_index:chunk_end]
            chunk_masks = masks[next_index:chunk_end]

            try:
                chunk_results = inpainter.inpaint_many(chunk_images, chunk_masks, config)
                if len(chunk_results) != len(chunk_images):
                    raise RuntimeError(
                        f"Inpainter returned {len(chunk_results)} results for {len(chunk_images)} images."
                    )
                for offset, result in enumerate(chunk_results):
                    results[next_index + offset] = result
                next_index = chunk_end
                current_batch_size = min(effective_batch_size, len(images) - next_index)
            except Exception as exc:
                if current_batch_size > 1 and self._is_probable_oom(exc):
                    logger.warning(
                        "Inpainting batch hit probable OOM at batch_size=%s. Retrying with a smaller batch.",
                        current_batch_size,
                    )
                    current_batch_size = max(1, current_batch_size // 2)
                    continue

                logger.debug(
                    "Batch inpainting failed; falling back to per-image processing for current chunk.",
                    exc_info=True,
                )
                for offset, (image, mask) in enumerate(zip(chunk_images, chunk_masks)):
                    results[next_index + offset] = inpainter(image, mask, config)
                next_index = chunk_end
                current_batch_size = min(effective_batch_size, len(images) - next_index)

        return results

    def manual_inpaint(self):
        image_viewer = self.main_page.image_viewer
        settings_page = self.main_page.settings_page
        mask = image_viewer.get_mask_for_inpainting()
        
        # Handle webtoon mode vs regular mode differently
        if self.main_page.webtoon_mode:
            # In webtoon mode, use visible area image for inpainting
            image, mappings = image_viewer.get_visible_area_image()
        else:
            # Regular mode - get the full image
            image = image_viewer.get_image_array()

        if image is None or mask is None:
            return None

        self._ensure_inpainter()
        config = get_config(settings_page)
        inpaint_input_img = self.inpainter_cache(image, mask, config)
        inpaint_input_img = imk.convert_scale_abs(inpaint_input_img) 

        return inpaint_input_img

    def _qimage_to_np(self, qimg: QImage):
        if qimg.width() <= 0 or qimg.height() <= 0:
            return np.zeros((max(1, qimg.height()), max(1, qimg.width())), dtype=np.uint8)
        ptr = qimg.constBits()
        arr = np.array(ptr).reshape(qimg.height(), qimg.bytesPerLine())
        return arr[:, :qimg.width()]

    def _make_segmentation_strokes_from_blocks(self, image: np.ndarray, blk_list: list[TextBlock]) -> list[dict]:
        strokes: list[dict] = []
        viewer = getattr(self.main_page, "image_viewer", None)
        drawing_manager = getattr(viewer, "drawing_manager", None) if viewer is not None else None
        make_segmentation_stroke_data = getattr(drawing_manager, "make_segmentation_stroke_data", None)
        if make_segmentation_stroke_data is None:
            return strokes

        for blk in blk_list or []:
            if not getattr(blk, "text", "") and not getattr(blk, "translation", ""):
                continue

            bboxes = getattr(blk, "inpaint_bboxes", None)
            if bboxes is None or len(bboxes) == 0:
                text_bbox = getattr(blk, "xyxy", None)
                if text_bbox is None:
                    continue
                bboxes = get_inpaint_bboxes(text_bbox, image)
                blk.inpaint_bboxes = bboxes

            if bboxes is None or len(bboxes) == 0:
                continue

            stroke = make_segmentation_stroke_data(bboxes)
            if stroke is None:
                continue

            stroke["segment_bboxes"] = [list(map(int, bbox)) for bbox in bboxes]
            stroke["segment_meta"] = {
                "text_bbox": list(map(int, blk.xyxy)) if getattr(blk, "xyxy", None) is not None else None,
                "bubble_xyxy": list(map(int, blk.bubble_xyxy)) if getattr(blk, "bubble_xyxy", None) is not None else None,
                "text_class": getattr(blk, "text_class", None),
            }
            strokes.append(stroke)

        return strokes

    def build_mask_from_blocks(self, image: np.ndarray, blk_list: list[TextBlock]) -> np.ndarray | None:
        """Build an inpaint mask using the same refined stroke pipeline as manual segmentation."""
        if image is None:
            return None

        if not blk_list:
            return np.zeros(image.shape[:2], dtype=np.uint8)

        strokes = self._make_segmentation_strokes_from_blocks(image, blk_list)
        if strokes:
            mask = self._generate_mask_from_saved_strokes(strokes, image)
            if mask is not None and np.count_nonzero(mask) > 0:
                return mask

        return generate_mask(image, blk_list)

    def _generate_mask_from_saved_strokes(self, strokes: list[dict], image: np.ndarray):
        if image is None or not strokes:
            return None
        height, width = image.shape[:2]
        if width <= 0 or height <= 0:
            return None

        human_qimg = QImage(width, height, QImage.Format_Grayscale8)
        gen_qimg = QImage(width, height, QImage.Format_Grayscale8)
        human_qimg.fill(0)
        gen_qimg.fill(0)

        human_painter = QPainter(human_qimg)
        gen_painter = QPainter(gen_qimg)

        human_painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        gen_painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        human_painter.setBrush(QBrush(QColor(255, 255, 255)))
        gen_painter.setBrush(QBrush(QColor(255, 255, 255)))

        has_any = False
        segment_blocks: list[TextBlock] = []
        for stroke in strokes:
            segment_meta = stroke.get('segment_meta') or {}
            text_bbox = segment_meta.get('text_bbox')
            segment_bboxes = stroke.get('segment_bboxes')

            if text_bbox is not None:
                text_bbox_list = list(map(int, text_bbox))
                bubble_xyxy = segment_meta.get('bubble_xyxy')
                seg_blk = TextBlock(
                    text_bbox=text_bbox_list,
                    bubble_bbox=list(map(int, bubble_xyxy)) if bubble_xyxy is not None else None,
                    text_class=segment_meta.get('text_class', ''),
                    text="segment",
                    translation="segment",
                )
                seg_blk.inpaint_bboxes = get_inpaint_bboxes(text_bbox_list, image)
                if seg_blk.inpaint_bboxes is None or len(seg_blk.inpaint_bboxes) == 0:
                    seg_blk.inpaint_bboxes = (
                        np.array(segment_bboxes, dtype=np.int32)
                        if segment_bboxes
                        else None
                    )
                if seg_blk.inpaint_bboxes is not None and len(seg_blk.inpaint_bboxes) > 0:
                    segment_blocks.append(seg_blk)
                    has_any = True
                    continue

            if segment_bboxes:
                seg_blk = TextBlock()
                seg_blk.inpaint_bboxes = np.array(segment_bboxes, dtype=np.int32)
                segment_blocks.append(seg_blk)
                has_any = True
                continue

            path = stroke.get('path')
            if path is None:
                continue
            brush_hex = QColor(stroke.get('brush', '#00000000')).name(QColor.HexArgb)
            if brush_hex == "#80ff0000":
                gen_painter.drawPath(path)
                has_any = True
                continue

            width_px = max(1, int(stroke.get('width', 25)))
            human_pen = QPen(QColor(255, 255, 255), width_px, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            human_painter.setPen(human_pen)
            human_painter.drawPath(path)
            has_any = True

        human_painter.end()
        gen_painter.end()

        if not has_any:
            return None

        human_mask = self._qimage_to_np(human_qimg)
        gen_mask = self._qimage_to_np(gen_qimg)

        def _refine_mask(mask_src: np.ndarray, base_padding: int, close_ksize: int, dilate_iters: int) -> np.ndarray:
            if np.count_nonzero(mask_src) == 0:
                return np.zeros_like(mask_src, dtype=np.uint8)

            contours, _ = imk.find_contours(mask_src)
            if not contours:
                return np.zeros_like(mask_src, dtype=np.uint8)

            refined = np.zeros_like(mask_src, dtype=np.uint8)
            h, w = mask_src.shape[:2]
            close_kernel = imk.get_structuring_element(imk.MORPH_RECT, (close_ksize, close_ksize))
            dil_kernel = np.ones((base_padding, base_padding), np.uint8)

            for cnt in contours:
                x, y, bw, bh = imk.bounding_rect(cnt)
                if bw <= 0 or bh <= 0:
                    continue

                # Add a little extra room around the stroke so the inpainted
                # region clears residual edges as well as the text itself.
                pad = max(base_padding, int(max(bw, bh) * 0.08) + 2)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w, x + bw + pad)
                y2 = min(h, y + bh + pad)
                if x1 >= x2 or y1 >= y2:
                    continue

                local = mask_src[y1:y2, x1:x2].copy()
                local = imk.morphology_ex(local, imk.MORPH_CLOSE, close_kernel)
                local = imk.dilate(local, dil_kernel, iterations=dilate_iters)
                refined[y1:y2, x1:x2] = np.where(local > 0, 255, refined[y1:y2, x1:x2])

            return refined

        segment_mask = generate_mask(image, segment_blocks) if segment_blocks else np.zeros((height, width), dtype=np.uint8)
        human_mask = _refine_mask(human_mask, base_padding=5, close_ksize=9, dilate_iters=2)
        gen_mask = _refine_mask(gen_mask, base_padding=8, close_ksize=15, dilate_iters=3)
        mask = np.where((segment_mask > 0) | (human_mask > 0) | (gen_mask > 0), 255, 0).astype(np.uint8)
        if np.count_nonzero(mask) == 0:
            return None
        return mask

    def _get_regular_patches(self, mask: np.ndarray, inpainted_image: np.ndarray):
        contours, _ = imk.find_contours(mask)
        patches = []
        for c in contours:
            x, y, w, h = imk.bounding_rect(c)
            patch = inpainted_image[y:y + h, x:x + w]
            patches.append({'bbox': [x, y, w, h], 'image': patch.copy()})
        return patches

    def inpaint_page_from_saved_strokes(self, image: np.ndarray, strokes: list[dict]):
        mask = self._generate_mask_from_saved_strokes(strokes, image)
        if mask is None:
            return []
        self._ensure_inpainter()
        config = get_config(self.main_page.settings_page)
        inpainted = self.inpainter_cache(image, mask, config)
        inpainted = imk.convert_scale_abs(inpainted)
        return self._get_regular_patches(mask, inpainted)

    def inpaint_complete(self, patch_list):
        # Handle webtoon mode vs regular mode
        if self.main_page.webtoon_mode:
            # In webtoon mode, group patches by page and apply them
            patches_by_page = {}
            for patch in patch_list:
                if 'page_index' in patch and 'file_path' in patch:
                    file_path = patch['file_path']
                    
                    if file_path not in patches_by_page:
                        patches_by_page[file_path] = []
                    
                    # Remove page-specific keys for the patch command but keep scene_pos for webtoon mode
                    clean_patch = {
                        'bbox': patch['bbox'],
                        'image': patch['image']
                    }
                    # Add scene position info for webtoon mode positioning
                    if 'scene_pos' in patch:
                        clean_patch['scene_pos'] = patch['scene_pos']
                        clean_patch['page_index'] = patch['page_index']
                    patches_by_page[file_path].append(clean_patch)
            
            # Apply patches to each page
            for file_path, patches in patches_by_page.items():
                self.main_page.image_ctrl.on_inpaint_patches_processed(patches, file_path)
                state = self.main_page.image_states.get(file_path)
                if state is not None:
                    state['brush_strokes'] = []
        else:
            # Regular mode - original behavior
            current_file = None
            if 0 <= self.main_page.curr_img_idx < len(self.main_page.image_files):
                current_file = self.main_page.image_files[self.main_page.curr_img_idx]
            self.main_page.apply_inpaint_patches(patch_list)
            if current_file:
                state = self.main_page.image_states.get(current_file)
                if state is not None:
                    state['brush_strokes'] = []
        
        self.main_page.image_viewer.clear_brush_strokes() 
        self.main_page.undo_group.activeStack().endMacro()  
        # get_best_render_area(self.main_page.blk_list, original_image, inpainted)    

    def get_inpainted_patches(self, mask: np.ndarray, inpainted_image: np.ndarray):
        # slice mask into bounding boxes
        contours, _ = imk.find_contours(mask)
        patches = []
        # Handle webtoon mode vs regular mode
        if self.main_page.webtoon_mode:
            # In webtoon mode, we need to map patches back to their respective pages
            visible_image, mappings = self.main_page.image_viewer.get_visible_area_image()
            if visible_image is None or not mappings:
                return patches
                
            for i, c in enumerate(contours):
                x, y, w, h = imk.bounding_rect(c)
                patch_bottom = y + h

                # Find all pages that this patch overlaps with
                overlapping_mappings = []
                for mapping in mappings:
                    if (y < mapping['combined_y_end'] and patch_bottom > mapping['combined_y_start']):
                        overlapping_mappings.append(mapping)
                
                if not overlapping_mappings:
                    continue
                    
                # If patch spans multiple pages, clip and redistribute
                for mapping in overlapping_mappings:
                    # Calculate the intersection with this page
                    clip_top = max(y, mapping['combined_y_start'])
                    clip_bottom = min(patch_bottom, mapping['combined_y_end'])
                    
                    if clip_bottom <= clip_top:
                        continue
                        
                    # Extract the portion of the patch for this page
                    clipped_patch = inpainted_image[clip_top:clip_bottom, x:x+w]
                    
                    # Convert coordinates back to page-local coordinates
                    page_local_y = clip_top - mapping['combined_y_start'] + mapping['page_crop_top']
                    clipped_height = clip_bottom - clip_top
                    
                    # Calculate the correct scene position by converting from visible area coordinates to scene coordinates
                    scene_y = mapping['scene_y_start'] + (clip_top - mapping['combined_y_start'])
                    
                    patches.append({
                        'bbox': [x, int(page_local_y), w, clipped_height],
                        'image': clipped_patch.copy(),
                        'page_index': mapping['page_index'],
                        'file_path': self.main_page.image_files[mapping['page_index']],
                        'scene_pos': [x, scene_y]  # Store correct scene position for webtoon mode
                    })
        else:
            # Regular mode - original behavior
            for c in contours:
                x, y, w, h = imk.bounding_rect(c)
                patch = inpainted_image[y:y+h, x:x+w]
                patches.append({
                    'bbox': [x, y, w, h],
                    'image': patch.copy(),
                })
                
        return patches
    
    def inpaint(self):
        mask = self.main_page.image_viewer.get_mask_for_inpainting()
        painted = self.manual_inpaint()              
        patches = self.get_inpainted_patches(mask, painted)
        return patches         
