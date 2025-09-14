import numpy as np
import imkit as imk

def _vote_spread_ratio(centers: np.ndarray) -> tuple[int, int]:
    """Vote based on overall spread ratio of text distribution."""
    xs, ys = centers[:, 0], centers[:, 1]
    range_x = xs.max() - xs.min() + 1e-6
    range_y = ys.max() - ys.min() + 1e-6
    spread_ratio = range_y / range_x
    
    if spread_ratio > 1.5:
        return 0, 1  # vertical
    else:
        return 1, 0  # horizontal


def _vote_aspect_ratio(items: list) -> tuple[int, int]:
    """Vote based on median aspect ratio of text boxes or polygons."""
    aspects = []
    for it in items:
        if not it:
            continue
        # axis-aligned bbox case
        if isinstance(it, (list, tuple, np.ndarray)) and len(it) == 4 and not isinstance(it[0], (list, tuple, np.ndarray)):
            x1, y1, x2, y2 = it
            w = max(1, x2 - x1)
            h = max(1, y2 - y1)
        else:
            # polygon case: array of points [[x,y],...]
            poly = np.asarray(it, dtype=float)
            if poly.ndim != 2 or poly.shape[1] != 2:
                continue
            xs, ys = poly[:, 0], poly[:, 1]
            w = max(1.0, xs.max() - xs.min())
            h = max(1.0, ys.max() - ys.min())
        aspects.append(h / w)
    median_aspect = float(np.median(aspects)) if aspects else 1.0

    if median_aspect > 1.2:
        return 0, 1  # vertical
    else:
        return 1, 0  # horizontal

def _vote_projection_profile(centers: np.ndarray, bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int]:
    """Vote based on projection profile anisotropy from occupancy grid."""
    if len(centers) < 2:
        return 0, 0
    
    try:
        xs, ys = centers[:, 0], centers[:, 1]
        x_min = int(np.floor(xs.min()))
        x_max = int(np.ceil(xs.max()))
        y_min = int(np.floor(ys.min()))
        y_max = int(np.ceil(ys.max()))
        w_total = max(1, x_max - x_min)
        h_total = max(1, y_max - y_min)
        
        # Choose grid size proportional to aspect, bounded by [32, 96]
        base = 64
        gw = int(np.clip(round(base * (w_total / max(w_total, h_total))), 32, 96))
        gh = int(np.clip(round(base * (h_total / max(w_total, h_total))), 32, 96))
        mask = np.zeros((gh, gw), dtype=np.uint8)
        
        # Paint each bbox (clip to bounds)
        for (x1, y1, x2, y2) in bboxes:
            gx1 = int(np.clip(round((x1 - x_min) / w_total * (gw - 1)), 0, gw - 1))
            gx2 = int(np.clip(round((x2 - x_min) / w_total * (gw - 1)), 0, gw - 1))
            gy1 = int(np.clip(round((y1 - y_min) / h_total * (gh - 1)), 0, gh - 1))
            gy2 = int(np.clip(round((y2 - y_min) / h_total * (gh - 1)), 0, gh - 1))
            if gx2 < gx1:
                gx1, gx2 = gx2, gx1
            if gy2 < gy1:
                gy1, gy2 = gy2, gy1
            mask[gy1:gy2 + 1, gx1:gx2 + 1] = 1
        
        row_sums = mask.sum(axis=1).astype(float)
        col_sums = mask.sum(axis=0).astype(float)
        r_var = float(np.var(row_sums))
        c_var = float(np.var(col_sums))
        
        if c_var > r_var * 1.3:
            return 0, 1
        elif r_var > c_var * 1.3:
            return 1, 0
    except Exception:
        pass
    return 0, 0


def _vote_alignment_jitter(centers: np.ndarray) -> tuple[int, int]:
    """Vote based on alignment jitter - measures how well-aligned text is in each direction."""
    if len(centers) < 3:
        return 0, 0
    
    try:
        xs, ys = centers[:, 0], centers[:, 1]
        n = len(centers)
        
        # Simple normalization using ranges
        x_range = xs.max() - xs.min() + 1e-6
        y_range = ys.max() - ys.min() + 1e-6
        
        # Test horizontal alignment: variance of Y coordinates when sorted by X
        sorted_by_x = centers[centers[:, 0].argsort()]
        y_coords_sorted_by_x = sorted_by_x[:, 1]
        
        # Test vertical alignment: variance of X coordinates when sorted by Y  
        sorted_by_y = centers[centers[:, 1].argsort()]
        x_coords_sorted_by_y = sorted_by_y[:, 0]
        
        # For horizontal layout, Y coordinates should have low variance (good alignment)
        # For vertical layout, X coordinates should have low variance (good alignment)
        
        # Use coefficient of variation for scale-invariant comparison
        y_var_normalized = np.var(y_coords_sorted_by_x) / (y_range + 1e-6)
        x_var_normalized = np.var(x_coords_sorted_by_y) / (x_range + 1e-6)
        
        # Additional check: sliding window variance for better alignment detection
        if n >= 5:
            win_size = min(max(3, n // 3), 8)
            
            # Y variance in sliding windows along X-sorted sequence
            y_sliding_vars = []
            for i in range(len(y_coords_sorted_by_x) - win_size + 1):
                window_y = y_coords_sorted_by_x[i:i + win_size]
                y_sliding_vars.append(np.var(window_y))
            y_sliding_jitter = np.mean(y_sliding_vars) / (y_range + 1e-6)
            
            # X variance in sliding windows along Y-sorted sequence  
            x_sliding_vars = []
            for i in range(len(x_coords_sorted_by_y) - win_size + 1):
                window_x = x_coords_sorted_by_y[i:i + win_size]
                x_sliding_vars.append(np.var(window_x))
            x_sliding_jitter = np.mean(x_sliding_vars) / (x_range + 1e-6)
            
            # Combine global and local variance measures
            horiz_jitter = (y_var_normalized + y_sliding_jitter) / 2
            vert_jitter = (x_var_normalized + x_sliding_jitter) / 2
        else:
            horiz_jitter = y_var_normalized
            vert_jitter = x_var_normalized

        # Lower jitter indicates better alignment
        # Use more conservative thresholds for better discrimination
        if horiz_jitter < vert_jitter * 0.6:
            return 1, 0  # horizontal (low Y jitter)
        elif vert_jitter < horiz_jitter * 0.6:
            return 0, 1  # vertical (low X jitter)
    except Exception as e:
        print(f"Error in alignment jitter calculation: {e}")
    return 0, 0


# polygon-aware projection profile (rasterize polygons instead of painting AABBs)
def _vote_projection_profile_poly(polygons: list[np.ndarray]) -> tuple[int, int]:
    if len(polygons) < 2:
        return 0, 0
    try:
        # Global extents
        all_pts = np.vstack(polygons)
        xs, ys = all_pts[:, 0], all_pts[:, 1]
        x_min = float(np.floor(xs.min()))
        x_max = float(np.ceil(xs.max()))
        y_min = float(np.floor(ys.min()))
        y_max = float(np.ceil(ys.max()))
        w_total = max(1.0, x_max - x_min)
        h_total = max(1.0, y_max - y_min)

        base = 64
        gw = int(np.clip(round(base * (w_total / max(w_total, h_total))), 32, 96))
        gh = int(np.clip(round(base * (h_total / max(w_total, h_total))), 32, 96))
        mask = np.zeros((gh, gw), dtype=np.uint8)

        # Scale polygons into grid and fill
        for cnt in polygons:
            if cnt.ndim != 2 or cnt.shape[0] < 3:
                continue
            gx = (cnt[:, 0] - x_min) / w_total * (gw - 1)
            gy = (cnt[:, 1] - y_min) / h_total * (gh - 1)
            pts = np.stack([np.clip(np.round(gx), 0, gw - 1),
                            np.clip(np.round(gy), 0, gh - 1)], axis=1).astype(np.int32)
            mask = imk.fill_poly(mask, [pts], 1)

        row_sums = mask.sum(axis=1).astype(float)
        col_sums = mask.sum(axis=0).astype(float)
        r_var = float(np.var(row_sums))
        c_var = float(np.var(col_sums))

        if c_var > r_var * 1.3:
            return 0, 1
        elif r_var > c_var * 1.3:
            return 1, 0
    except Exception:
        pass
    return 0, 0

# text flow continuity using medians from oriented sizes
def _vote_text_flow_continuity_sizes(centers: np.ndarray, med_w: float, med_h: float) -> tuple[int, int]:
    if len(centers) < 3:
        return 0, 0
    try:
        flow_scores = {'horizontal': 0, 'vertical': 0}
        for i, ci in enumerate(centers):
            candidates_right = []
            candidates_down = []
            for j, cj in enumerate(centers):
                if i == j:
                    continue
                dx = cj[0] - ci[0]
                dy = cj[1] - ci[1]
                dist = float(np.hypot(dx, dy))
                if dx > 0 and abs(dy) < abs(dx) * 0.5:
                    candidates_right.append(dist)
                if dy > 0 and abs(dx) < abs(dy) * 0.5:
                    candidates_down.append(dist)
            if candidates_right and min(candidates_right) < med_w * 3:
                flow_scores['horizontal'] += 1
            if candidates_down and min(candidates_down) < med_h * 3:
                flow_scores['vertical'] += 1

        if flow_scores['horizontal'] > flow_scores['vertical'] * 1.2:
            return 1, 0
        elif flow_scores['vertical'] > flow_scores['horizontal'] * 1.2:
            return 0, 1
    except Exception:
        pass
    return 0, 0


def _prepare_items(items):
    """Prepare centers, median sizes, and canonical bboxes/polys from either bboxes or polygons."""
    # empty
    if not items:
        return np.zeros((0, 2), dtype=float), 1.0, 1.0, [], []

    # find first non-empty element
    first = None
    for it in items:
        if it:
            first = it
            break
    if first is None:
        return np.zeros((0, 2), dtype=float), 1.0, 1.0, [], []

    # Detect bbox vs polygon by shape: bbox is (x1,y1,x2,y2)
    is_bbox_candidate = isinstance(first, (list, tuple, np.ndarray)) and len(first) == 4 and not isinstance(first[0], (list, tuple, np.ndarray))
    if is_bbox_candidate:
        # treat items as axis-aligned bboxes
        bboxes = [(int(x1), int(y1), int(x2), int(y2)) for x1, y1, x2, y2 in items if len((x1, y1, x2, y2)) == 4]
        if not bboxes:
            return np.zeros((0, 2), dtype=float), 1.0, 1.0, [], []
        centers = np.array([[(x1 + x2) / 2.0, (y1 + y2) / 2.0] for x1, y1, x2, y2 in bboxes], dtype=float)
        widths = [max(1, x2 - x1) for x1, y1, x2, y2 in bboxes]
        heights = [max(1, y2 - y1) for x1, y1, x2, y2 in bboxes]
        med_w = float(np.median(widths)) if widths else 1.0
        med_h = float(np.median(heights)) if heights else 1.0
        polys = []
        return centers, med_w, med_h, bboxes, polys

    # otherwise treat as polygons
    polys = []
    centers_list = []
    widths = []
    heights = []
    for poly in items:
        if not poly or len(poly) < 3:
            continue
        cnt = np.asarray(poly, dtype=np.float32)
        polys.append(cnt)
        rect = imk.min_area_rect(cnt)
        (cx, cy), (w, h), _ = rect
        centers_list.append([cx, cy])
        widths.append(max(float(w), 1.0))
        heights.append(max(float(h), 1.0))

    if not centers_list:
        return np.zeros((0, 2), dtype=float), 1.0, 1.0, [], []
    centers = np.asarray(centers_list, dtype=float)
    med_w = float(np.median(widths)) if widths else 1.0
    med_h = float(np.median(heights)) if heights else 1.0
    bboxes = []  # optional axis-aligned fallback can be derived when needed
    return centers, med_w, med_h, bboxes, polys


def _orientation_votes(items: list) -> tuple[int, int]:
    """Unified orientation voting entry point.
    'items' may be a list of bboxes [(x1,y1,x2,y2), ...] or polygons [[[x,y],...], ...].
    Returns (horizontal_votes, vertical_votes).
    """
    centers, med_w, med_h, bboxes, polys = _prepare_items(items)
    if centers.size == 0:
        return 0, 0

    horizontal_votes = 0
    vertical_votes = 0

    # center-only votes
    for vote_func in [_vote_alignment_jitter]:
        try:
            h, v = vote_func(centers)
            horizontal_votes += h
            vertical_votes += v
        except Exception:
            pass

    # spread
    try:
        h, v = _vote_spread_ratio(centers)
        horizontal_votes += h
        vertical_votes += v
    except Exception:
        pass

    # aspect ratio
    try:
        items = bboxes or polys
        h, v = _vote_aspect_ratio(items)
        horizontal_votes += h
        vertical_votes += v
    except Exception:
        pass

    # projection profile: prefer polygon-aware rasterization if polys available
    try:
        if polys:
            h, v = _vote_projection_profile_poly(polys)
        else:
            # bboxes variable may be empty if input was polygons, but centers exist; fall back to axis-aligned projection if bboxes present
            if bboxes:
                h, v = _vote_projection_profile(centers, bboxes)
            else:
                h, v = 0, 0
        horizontal_votes += h
        vertical_votes += v
    except Exception:
        pass

    try:
        h, v = _vote_text_flow_continuity_sizes(centers, med_w, med_h)
        horizontal_votes += h
        vertical_votes += v
    except Exception:
        pass

    return horizontal_votes, vertical_votes

def infer_orientation(items: list) -> str:
    """Infer orientation only: returns 'horizontal' or 'vertical'."""
    if not items:
        return 'horizontal'
    h_votes, v_votes = _orientation_votes(items)
    return 'vertical' if v_votes > h_votes else 'horizontal'


def infer_reading_order(orientation: str, explicit: str | None = None) -> str:
    """Determine reading order 'ltr' or 'rtl'.

    Defaults requested: horizontal -> ltr, vertical -> rtl unless explicitly overridden."""
    if explicit in {'ltr', 'rtl'}:
        return explicit
    return 'rtl' if orientation == 'vertical' else 'ltr'

def infer_text_direction(items: list) -> str:
    """Backward-compatible combined direction string.

    Combines orientation + reading order into legacy token (hor_ltr, hor_rtl, ver_ltr, ver_rtl)."""
    orientation = infer_orientation(items)
    order = infer_reading_order(orientation)
    if orientation == 'horizontal':
        return 'hor_ltr' if order == 'ltr' else 'hor_rtl'
    return 'ver_rtl' if order == 'rtl' else 'ver_ltr'