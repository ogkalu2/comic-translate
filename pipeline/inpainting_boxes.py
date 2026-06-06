from collections.abc import Iterable


def merge_overlapping_padded_boxes(
    boxes: Iterable[tuple[int, int, int, int]],
    image_shape: tuple[int, ...],
    *,
    pad: int = 32,
) -> list[tuple[int, int, int, int]]:
    height, width = image_shape[:2]
    merged_boxes: list[tuple[int, int, int, int]] = []

    for x, y, w, h in boxes:
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(width, x + w + pad)
        y2 = min(height, y + h + pad)

        merged = False
        for i, (mx1, my1, mx2, my2) in enumerate(merged_boxes):
            if not (x2 < mx1 or x1 > mx2 or y2 < my1 or y1 > my2):
                merged_boxes[i] = (
                    min(x1, mx1),
                    min(y1, my1),
                    max(x2, mx2),
                    max(y2, my2),
                )
                merged = True
                break
        if not merged:
            merged_boxes.append((x1, y1, x2, y2))

    changed = True
    while changed:
        changed = False
        for i in range(len(merged_boxes)):
            for j in range(len(merged_boxes) - 1, i, -1):
                mx1, my1, mx2, my2 = merged_boxes[i]
                nx1, ny1, nx2, ny2 = merged_boxes[j]
                if not (mx2 < nx1 or mx1 > nx2 or my2 < ny1 or my1 > ny2):
                    merged_boxes[i] = (
                        min(mx1, nx1),
                        min(my1, ny1),
                        max(mx2, nx2),
                        max(my2, ny2),
                    )
                    merged_boxes.pop(j)
                    changed = True

    return merged_boxes
