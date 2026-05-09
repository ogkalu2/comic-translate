import numpy as np
import imkit as imk

from .orientation import infer_orientation, infer_reading_order, \
    infer_text_direction


# Unified grouping implementation (handles polygons or bboxes)

def _is_box(item):
    return (
        isinstance(item, (list, tuple, np.ndarray))
        and len(item) == 4
        and not isinstance(item[0], (list, tuple, np.ndarray))
    )

def _bbox_from_item(item):
    if _is_box(item):
        x1, y1, x2, y2 = item
        return (int(x1), int(y1), int(x2), int(y2))
    # polygon
    xs = [p[0] for p in item]
    ys = [p[1] for p in item]
    return (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

def _center_from_item(item):
    if _is_box(item):
        x1, y1, x2, y2 = item
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    xs = [p[0] for p in item]
    ys = [p[1] for p in item]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def group_items_into_lines(
    items: list, 
    direction: str = 'hor_ltr', 
    band_ratio: float = 0.5,
) -> list[list]:
    """Group detections (either boxes [x1,y1,x2,y2] or polygons [[x,y],...]) into reading lines.

    Returns list of lines where each line is a list of the original items (not their bboxes).
    """
    if not items:
        return []

    # Compute bboxes for adaptive band and sorting keys
    bboxes = [_bbox_from_item(it) for it in items]

    widths = [(x2 - x1) for x1, y1, x2, y2 in bboxes]
    heights = [(y2 - y1) for x1, y1, x2, y2 in bboxes]
    median_w = np.median(widths) if widths else 1.0
    median_h = np.median(heights) if heights else 1.0

    if 'hor' in direction:
        adaptive_band = band_ratio * median_h
    else:
        adaptive_band = band_ratio * median_w

    def in_same_line(i, j):
        center_i = _center_from_item(items[i])
        center_j = _center_from_item(items[j])
        if 'hor' in direction:
            return abs(center_i[1] - center_j[1]) <= adaptive_band
        return abs(center_i[0] - center_j[0]) <= adaptive_band

    # Union-Find
    parent = list(range(len(items)))
    def find(u):
        if parent[u] == u:
            return u
        parent[u] = find(parent[u])
        return parent[u]
    def union(u, v):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[rv] = ru

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if in_same_line(i, j):
                union(i, j)

    groups = {}
    for idx, it in enumerate(items):
        root = find(idx)
        groups.setdefault(root, []).append(it)

    lines = list(groups.values())

    # sorting helpers
    def min_x_of(it):
        if _is_box(it):
            return it[0]
        return min(p[0] for p in it)
    def min_y_of(it):
        if _is_box(it):
            return it[1]
        return min(p[1] for p in it)

    # Sort items within each line according to reading direction
    for idx, line in enumerate(lines):
        if direction == 'hor_ltr':
            lines[idx] = sorted(line, key=min_x_of)
        elif direction == 'hor_rtl':
            lines[idx] = sorted(line, key=lambda it: -min_x_of(it))
        else:  # vertical
            lines[idx] = sorted(line, key=min_y_of)

    # Sort the lines themselves based on orientation
    if 'hor' in direction:
        lines.sort(key=lambda line: min(min_y_of(it) for it in line))
    elif direction == 'ver_ltr':
        lines.sort(key=lambda line: min(min_x_of(it) for it in line))
    else:  # ver_rtl
        lines.sort(key=lambda line: min(min_x_of(it) for it in line), reverse=True)

    return lines


def group_items_into_lines_auto(items: list, band_ratio: float = 0.5) -> list[list]:
    """Auto infer combined direction and group lines for boxes or polygons."""
    if not items:
        return []
    direction = infer_text_direction(items)
    return group_items_into_lines(items, direction=direction, band_ratio=band_ratio)


def group_items_into_lines_separated(
    items: list,
    orientation: str | None = None,
    reading_order: str | None = None,
    band_ratio: float = 0.5,
) -> tuple[list[list], str, str]:
    """Group items returning (lines, orientation, reading_order).

    orientation: 'horizontal' | 'vertical' (auto if None)
    reading_order: 'ltr' | 'rtl' (auto defaults: hor->ltr, ver->rtl)
    """
    if not items:
        # default orientation/reading_order when empty
        return [], (orientation or 'horizontal'), (reading_order or 'ltr')

    # choose orientation inference based on item shape
    if orientation is None:
        orientation = infer_orientation(items)

    reading_order = infer_reading_order(orientation, reading_order)

    if orientation == 'horizontal':
        direction = 'hor_ltr' if reading_order == 'ltr' else 'hor_rtl'
    else:
        direction = 'ver_rtl' if reading_order == 'rtl' else 'ver_ltr'

    lines = group_items_into_lines(items, direction=direction, band_ratio=band_ratio)
    return lines, orientation, reading_order


# Line merging utilities

def merge_items_in_line(line: list) -> list[list[int]]:
    """Merge items (boxes or polygons) in a line into a single rotated rectangle polygon (4 points)."""
    pts = []
    for it in line:
        if _is_box(it):
            # It's a bounding box [x1, y1, x2, y2]
            x1, y1, x2, y2 = it
            pts.extend([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
        else:
            # It's a polygon [[x1,y1], [x2,y2], ...]
            pts.extend(it)
    
    pts_np = np.array(pts, dtype=np.float32)
    if len(pts_np) == 0:
        return []
    
    # Use minimum area rectangle to get the best fitting rotated rectangle
    rect = imk.min_area_rect(pts_np)
    box = imk.box_points(rect)
    return [[int(x), int(y)] for x, y in box]


def merge_line_groups(lines: list[list]) -> list[list[list[int]]]:
    """Convert list of oriented lines (boxes/polys) into one rotated bbox (polygon) per line."""
    out = []
    for line in lines:
        merged_item = merge_items_in_line(line)
        if merged_item:
            out.append(merged_item)
    return out


def visualize_text_lines(lines, image, output_path: str, line_thickness: int = 3):
    """
    Draws the grouped text lines on an image and saves it to a file.
    
    Args:
        lines: list of lines, each containing bounding boxes or polygons. Can be:
            - list[list[tuple[int, int, int, int]]]: list of lines with bounding boxes
            - list[list[list[list[int]]]]: list of lines with polygons 
            - list[tuple[int, int, int, int]]: Flat list of bounding boxes
            - list[list[list[int]]]: Flat list of polygons
        image: PIL Image or numpy array to draw on.
        output_path (str): Path where the output image will be saved.
        line_thickness (int): Thickness of the bounding box lines.
    """
    from PIL import Image, ImageDraw
    import numpy as np
    
    # Convert numpy array to PIL Image if needed
    if isinstance(image, np.ndarray):
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
        image = Image.fromarray(image)
    
    # Create a copy to draw on
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    
    # Define colors for different lines (RGB tuples)
    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (255, 255, 0),  # Yellow
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cyan
        (255, 128, 0),  # Orange
        (128, 0, 255),  # Purple
        (255, 192, 203), # Pink
        (128, 128, 128), # Gray
    ]
    
    # Allow: (a) list of lines (each a list of boxes/polys),
    #        (b) flat list of boxes, or (c) flat list of polygons.
    def _is_box(obj):
        if isinstance(obj, (list, tuple, np.ndarray)) and len(obj) == 4 and not (
            isinstance(obj[0], (list, tuple, np.ndarray))
        ):
            try:
                float(obj[0]); float(obj[1]); float(obj[2]); float(obj[3])
                return True
            except Exception:
                return False
        return False

    def _is_point(obj):
        return (
            isinstance(obj, (list, tuple, np.ndarray))
            and len(obj) == 2
            and all(isinstance(v, (int, float, np.integer, np.floating)) for v in (obj[0], obj[1]))
        )

    def _is_polygon(obj):
        if isinstance(obj, (list, tuple, np.ndarray)) and len(obj) >= 3:
            first = obj[0]
            return _is_point(first)
        return False

    if lines and all(_is_box(item) for item in lines):
        # Flat list of boxes -> wrap each as its own line
        lines_to_draw = [[box] for box in lines]
    elif lines and all(_is_polygon(item) for item in lines):
        # Flat list of polygons -> wrap each as its own line
        lines_to_draw = [[poly] for poly in lines]
    else:
        lines_to_draw = lines

    # Draw bounding boxes for each (possibly rewrapped) line
    for line_idx, line in enumerate(lines_to_draw):
        color = colors[line_idx % len(colors)]
        for item in line:
            if _is_box(item):
                x1, y1, x2, y2 = map(int, item)
                draw.rectangle([x1, y1, x2, y2], outline=color, width=line_thickness)
            elif _is_polygon(item):
                pts = [(int(p[0]), int(p[1])) for p in item]
                # Close the polygon if not closed
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                draw.line(pts, fill=color, width=line_thickness)
            else:
                # skip malformed entries
                continue
    
    # Save the image
    img_copy.save(output_path)
    print(f"Text lines visualization saved to: {output_path}")