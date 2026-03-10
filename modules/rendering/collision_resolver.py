from dataclasses import dataclass, field
from typing import List, Dict, Optional
import numpy as np

@dataclass
class RenderBox:
    id: str
    x: int          # anchor — immutable
    y: int          # anchor — immutable
    width: int
    height: int
    translated_text: str
    font_size: float
    collision_resolved: bool = False
    expansion_applied: bool = False
    needs_review: bool = False

def _overlaps(a: RenderBox, b: RenderBox) -> bool:
    return not (
        a.x + a.width <= b.x or b.x + b.width <= a.x or
        a.y + a.height <= b.y or b.y + b.height <= a.y
    )

def _has_collision(box: RenderBox, others: List[RenderBox]) -> bool:
    return any(_overlaps(box, o) for o in others)

def _try_font_reduction(box: RenderBox, min_size: float = 8.0) -> bool:
    if box.font_size <= min_size:
        return False
    box.font_size = max(min_size, box.font_size * 0.85)
    box.collision_resolved = True
    return True

class CollisionResolver:
    def resolve(
        self,
        boxes: List[RenderBox],
        bubble_masks: Dict[str, np.ndarray],
        min_font_size: float = 8.0,
    ) -> List[RenderBox]:
        # Sort top-to-bottom, right-to-left (manga reading order)
        sorted_boxes = sorted(boxes, key=lambda b: (b.y, -b.x))

        for box in sorted_boxes:
            siblings = [b for b in sorted_boxes if b.id != box.id]
            if not _has_collision(box, siblings):
                continue

            # Reduce font size up to 3 times
            for _ in range(3):
                if not _has_collision(box, siblings):
                    break
                if not _try_font_reduction(box, min_font_size):
                    break

            if _has_collision(box, siblings):
                box.needs_review = True

        return sorted_boxes
