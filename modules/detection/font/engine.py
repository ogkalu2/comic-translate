import numpy as np
import imkit as imk


def extract_foreground_color(image: np.ndarray) -> list[int] | None:
    """Extract the foreground (text) color from a text bounding box crop.

    Uses spatial analysis: border pixels define the background colour,
    then Otsu thresholding on the colour-distance-from-background map
    cleanly separates text from background.  The median colour of
    the text pixels is returned.

    This avoids the regression-to-the-mean problem that neural
    regressors suffer from, and correctly handles:
      - black text on white bubble
      - white text on dark/coloured bubble
      - coloured text on any background
    """
    if image is None or image.size == 0:
        return None

    h, w = image.shape[:2]
    if h < 6 or w < 6:
        return None

    if len(image.shape) != 3 or image.shape[2] < 3:
        return None

    img = image[:, :, :3]  # drop alpha if present

    # Analyze the full crop.
    work = img

    wh, ww = work.shape[:2]
    if wh < 6 or ww < 6:
        return None

    # 1. Border sampling: collect a thin ring of pixels around the analysis crop.
    bw = max(2, min(wh, ww) // 8)
    if wh <= bw * 2 or ww <= bw * 2:
        return None

    # Exclude corners from top/bottom strips when possible.
    top = work[:bw, bw:-bw] if ww > bw * 2 else work[:bw, :]
    bottom = work[-bw:, bw:-bw] if ww > bw * 2 else work[-bw:, :]
    left = work[bw:-bw, :bw]
    right = work[bw:-bw, -bw:]

    border_parts = []
    for part in (top, bottom, left, right):
        if part.size > 0:
            border_parts.append(part.reshape(-1, 3))
    if not border_parts:
        return None

    border_pixels = np.concatenate(border_parts, axis=0).astype(np.float64)
    bg = np.median(border_pixels, axis=0)

    # 2. Per-pixel Euclidean distance from the background colour.
    flat = work.reshape(-1, 3).astype(np.float64)
    dist = np.sqrt(np.sum((flat - bg) ** 2, axis=1))

    # 3. Otsu threshold on the distance map to find the natural
    #    boundary between "background-like" and "text-like" pixels.
    dist_u8 = np.clip(dist, 0, 255).astype(np.uint8)
    otsu_thresh, _ = imk.otsu_threshold(dist_u8)
    # Floor: ignore tiny noise even if Otsu picks a very low split.
    threshold = max(float(otsu_thresh), 25.0)

    # 4. Extract text pixels and choose a robust foreground estimate.
    text_mask = dist > threshold
    n_text = int(np.sum(text_mask))
    if n_text < 5:
        return None

    text_pixels = flat[text_mask]
    text_ratio = n_text / float(flat.shape[0])
    bg_luma = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]

    # Printed comics often have antialiasing + halftone noise. On bright bubbles,
    # a pure median can drift too light and snap to white; on dark bubbles, it can
    # drift too dark. Bias toward the appropriate tail by background brightness.
    if bg_luma >= 170:
        fg = np.percentile(text_pixels, 20, axis=0)
    elif bg_luma <= 85:
        fg = np.percentile(text_pixels, 80, axis=0)
    else:
        fg = np.median(text_pixels, axis=0)

    fg = np.round(fg).astype(int).tolist()
    snapped = snap_extreme_neutrals(fg)

    # Targeted correction for colored text inside bright bubbles surrounded by
    # very dark borders/background. In this case bg_luma can be dark while the
    # selected mask is mostly bright fill, and the 80th percentile drifts to the
    # bubble fill colour (e.g. orange) instead of darker text (e.g. red).
    if (
        snapped not in ([0, 0, 0], [255, 255, 255])
        and bg_luma <= 85
        and text_ratio >= 0.45
    ):
        luma_vals = 0.299 * text_pixels[:, 0] + 0.587 * text_pixels[:, 1] + 0.114 * text_pixels[:, 2]
        dominant_luma = float(np.median(luma_vals))
        luma_spread = float(np.percentile(luma_vals, 90) - np.percentile(luma_vals, 10))
        if dominant_luma >= 140 and luma_spread >= 30:
            dark_tail = np.percentile(text_pixels, 20, axis=0)
            snapped = snap_extreme_neutrals(np.round(dark_tail).astype(int).tolist())

    return snapped


def snap_extreme_neutrals(rgb: list[int]) -> list[int]:
    """Snap achromatic colours to pure black or white.

    Comic text is almost never intentionally grey.  If the detected
    colour is achromatic (low chroma) it is meant to be either black
    or white, so snap to whichever is closer.  Coloured text (high
    chroma) is returned unchanged.
    """
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    chroma = max(r, g, b) - min(r, g, b)

    # Achromatic -> snap to nearest extreme.
    if chroma < 40:
        return [0, 0, 0] if luma < 128 else [255, 255, 255]

    return [r, g, b]
