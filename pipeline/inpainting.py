import numpy as np
import time
import logging
import imkit as imk

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QBrush

from modules.utils.device import resolve_device
from modules.utils.pipeline_config import inpaint_map, get_config, get_inpainter_backend
from pipeline.inpainting_boxes import merge_overlapping_padded_boxes

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
            backend = get_inpainter_backend(inpainter_key)
            device = resolve_device(settings_page.is_gpu_enabled(), backend)
            InpainterClass = inpaint_map[inpainter_key]
            logger.info("pre-inpaint: initializing inpainter '%s' on device %s", inpainter_key, device)
            t0 = time.time()
            self.inpainter_cache = InpainterClass(device, backend=backend)
            self.cached_inpainter_key = inpainter_key
            logger.info("pre-inpaint: inpainter initialized in %.2fs", time.time() - t0)
        return self.inpainter_cache

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
        inpaint_input_img = self.inpaint_image(image, mask, config)
        inpaint_input_img = imk.convert_scale_abs(inpaint_input_img) 

        return inpaint_input_img

    def _qimage_to_np(self, qimg: QImage):
        if qimg.width() <= 0 or qimg.height() <= 0:
            return np.zeros((max(1, qimg.height()), max(1, qimg.width())), dtype=np.uint8)
        ptr = qimg.constBits()
        arr = np.array(ptr).reshape(qimg.height(), qimg.bytesPerLine())
        return arr[:, :qimg.width()]

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
        for stroke in strokes:
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
        kernel = np.ones((5, 5), np.uint8)
        human_mask = imk.dilate(human_mask, kernel, iterations=2)
        gen_mask = imk.dilate(gen_mask, kernel, iterations=3)
        mask = np.where((human_mask > 0) | (gen_mask > 0), 255, 0).astype(np.uint8)
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

    def _inpaint_full_image(self, image: np.ndarray, mask: np.ndarray, config):
        if image is None:
            return None
        if mask is None or not np.any(mask):
            return image.copy()
        return self.inpainter_cache(image, mask, config)

    def _inpaint_by_patches(self, image: np.ndarray, mask: np.ndarray, config):
        inpainted_image = image.copy()
        contours, _ = imk.find_contours(mask)
        
        if not contours:
            return inpainted_image

        # 1. Extract and merge bounding boxes
        boxes = [imk.bounding_rect(c) for c in contours]
        merged_boxes = merge_overlapping_padded_boxes(boxes, image.shape)

        # 2. Patch inference
        for x1, y1, x2, y2 in merged_boxes:
            img_patch = image[y1:y2, x1:x2]
            mask_patch = mask[y1:y2, x1:x2]
            
            patch_inpainted = self.inpainter_cache(img_patch, mask_patch, config)
            inpainted_image[y1:y2, x1:x2] = patch_inpainted
            
        return inpainted_image

    def inpaint_image(self, image: np.ndarray, mask: np.ndarray, config) -> np.ndarray:
        """
        Intelligently chooses between full-image and patch-based inpainting
        based on image size, number of text blocks, and total mask area.
        """
        if image is None:
            return None
        if mask is None or not np.any(mask):
            return image.copy()

        contours, _ = imk.find_contours(mask)
        if not contours:
            return image.copy()

        boxes = [imk.bounding_rect(c) for c in contours]
        merged_boxes = merge_overlapping_padded_boxes(boxes, image.shape)
        num_patches = len(merged_boxes)

        if num_patches == 0:
            return image.copy()

        # Calculate area ratio of the text patches compared to the full image
        h_img, w_img = image.shape[:2]
        area_image = w_img * h_img
        area_patches = sum((x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in merged_boxes)
        area_ratio = area_patches / area_image

        # Huge images (>2560px) lean heavily to patches to prevent GPU OOM and long latency
        is_huge_resolution = max(w_img, h_img) > 2560
        max_patches_threshold = 12 if is_huge_resolution else 6

        # Hybrid Decision Heuristic
        if num_patches >= max_patches_threshold:
            use_patches = False
        elif area_ratio > 0.35:
            use_patches = False
        else:
            use_patches = True

        # Safety override: Force patches if full-image would likely crash GPU VRAM
        if is_huge_resolution and area_ratio < 0.70:
            use_patches = True

        if use_patches:
            logger.info(
                "Inpaint hybrid: PATCH-BASED (patches=%d, ratio=%.2f%%, size=%dx%d)",
                num_patches, area_ratio * 100, w_img, h_img
            )
            return self._inpaint_by_patches(image, mask, config)
        else:
            logger.info(
                "Inpaint hybrid: FULL-IMAGE (patches=%d, ratio=%.2f%%, size=%dx%d)",
                num_patches, area_ratio * 100, w_img, h_img
            )
            return self._inpaint_full_image(image, mask, config)

    def inpaint_page_from_saved_strokes(self, image: np.ndarray, strokes: list[dict]):
        mask = self._generate_mask_from_saved_strokes(strokes, image)
        if mask is None:
            return []
        self._ensure_inpainter()
        config = get_config(self.main_page.settings_page)
        inpainted = self.inpaint_image(image, mask, config)
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
        else:
            # Regular mode - original behavior
            self.main_page.apply_inpaint_patches(patch_list)
        
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
