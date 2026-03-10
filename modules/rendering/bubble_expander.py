import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from modules.rendering.collision_resolver import RenderBox

@dataclass
class BubbleDetectionParams:
    min_area_px: int = 2000
    max_area_ratio: float = 0.8     # Bubble should not cover > 80% of image
    min_solidity: float = 0.70
    max_texture_variance: float = 5000.0
    aspect_ratio_min: float = 0.3
    aspect_ratio_max: float = 3.0
    canny_low: int = 50
    canny_high: int = 150
    mask_erosion_px: int = 8

class ArtStyleProfile:
    @staticmethod
    def clean_digital() -> BubbleDetectionParams:
        return BubbleDetectionParams(min_solidity=0.85, max_texture_variance=30)

    @staticmethod
    def classic_screentone() -> BubbleDetectionParams:
        return BubbleDetectionParams(min_solidity=0.70, max_texture_variance=80)

    @staticmethod
    def rough_sketch() -> BubbleDetectionParams:
        return BubbleDetectionParams(min_solidity=0.60, max_texture_variance=120)


class BubbleDetector:
    def __init__(self, params: Optional[BubbleDetectionParams] = None):
        self.params = params or BubbleDetectionParams()

    def detect(self, image: np.ndarray) -> List[np.ndarray]:
        p = self.params
        h, w = image.shape[:2]
        total_area = h * w

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        edges = cv2.Canny(blurred, p.canny_low, p.canny_high)
        combined = cv2.bitwise_or(binary, edges)

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        masks = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < p.min_area_px or area > total_area * p.max_area_ratio:
                continue

            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < p.min_solidity:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / bh if bh > 0 else 0
            if not (p.aspect_ratio_min <= aspect <= p.aspect_ratio_max):
                continue

            # Compute variance only inside the contour, not the bounding box
            cnt_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(cnt_mask, [cnt], -1, 255, thickness=cv2.FILLED)
            interior_pixels = gray[cnt_mask > 0]
            if interior_pixels.size > 0 and float(interior_pixels.var()) > p.max_texture_variance:
                continue

            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
            kernel = np.ones((p.mask_erosion_px, p.mask_erosion_px), np.uint8)
            mask = cv2.erode(mask, kernel, iterations=1)
            if mask.any():
                masks.append(mask)

        return masks


class BubbleExpander:
    @staticmethod
    def make_fallback_mask(box: RenderBox, image_h: int, image_w: int) -> np.ndarray:
        """Return a full-image mask covering the box's bounding rect as a safe zone."""
        mask = np.zeros((image_h, image_w), dtype=np.uint8)
        x2 = min(box.x + box.width, image_w)
        y2 = min(box.y + box.height, image_h)
        mask[box.y:y2, box.x:x2] = 255
        return mask

    def expand(
        self,
        box: RenderBox,
        bubble_mask: np.ndarray,
        max_expand_px: int = 20,
    ) -> RenderBox:
        h, w = bubble_mask.shape[:2]
        new_x = max(0, box.x - max_expand_px)
        new_y = max(0, box.y - max_expand_px)
        new_w = min(w - new_x, box.width + 2 * max_expand_px)
        new_h = min(h - new_y, box.height + 2 * max_expand_px)

        corners = [
            (new_x, new_y), (new_x + new_w - 1, new_y),
            (new_x, new_y + new_h - 1), (new_x + new_w - 1, new_y + new_h - 1),
        ]
        for cx, cy in corners:
            cx = min(cx, w - 1)
            cy = min(cy, h - 1)
            if bubble_mask[cy, cx] == 0:
                return box

        from copy import copy
        expanded = copy(box)
        expanded.x = new_x
        expanded.y = new_y
        expanded.width = new_w
        expanded.height = new_h
        expanded.expansion_applied = True
        return expanded
