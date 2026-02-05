from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import imkit as imk
from PIL import Image


_NAMED_COLORS_RGB: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "lime": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "gray": (128, 128, 128),
    "silver": (192, 192, 192),
    "maroon": (128, 0, 0),
    "olive": (128, 128, 0),
    "green": (0, 128, 0),
    "purple": (128, 0, 128),
    "teal": (0, 128, 128),
    "navy": (0, 0, 128),
}


def rgb_to_hex(rgb: Iterable[int]) -> str:
    r, g, b = [int(x) for x in rgb]
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def nearest_named_color(rgb: Iterable[int]) -> tuple[str, float]:
    """Return (name, squared_distance) to the nearest named RGB color."""
    r, g, b = [float(int(x)) for x in rgb]
    best_name = "black"
    best_d2 = float("inf")
    for name, (rr, gg, bb) in _NAMED_COLORS_RGB.items():
        d2 = (r - rr) ** 2 + (g - gg) ** 2 + (b - bb) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_name = name
    return best_name, best_d2


def _luma_u8(rgb_u8: np.ndarray) -> np.ndarray:
    rgb = rgb_u8.astype(np.float32)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _chroma_u8(rgb_u8: np.ndarray) -> np.ndarray:
    """Per-pixel chroma: max(R,G,B) - min(R,G,B), returned as uint8."""
    i16 = rgb_u8.astype(np.int16)
    return (i16.max(axis=-1) - i16.min(axis=-1)).astype(np.uint8)

def _snap_neutral_extremes(
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int] | None,
) -> tuple[int, int, int]:
    """Snap near-neutral high-contrast foregrounds to pure black/white.

    When text is anti-aliased (or slightly blurred/halftoned), the median of
    stroke pixels can drift toward grey. For typical comics, that's almost
    always intended to be solid black/white ink.
    """
    if bg_rgb is None:
        return fg_rgb

    fr, fg, fb = fg_rgb
    br, bg, bb = bg_rgb
    fg_l = float(_luma_u8(np.array([fr, fg, fb], dtype=np.uint8)))
    bg_l = float(_luma_u8(np.array([br, bg, bb], dtype=np.uint8)))
    fg_chroma = float(max(fg_rgb) - min(fg_rgb))

    # Only snap neutrals.
    if fg_chroma > 35:
        return fg_rgb

    # Strong luminance separation implies intended black/white.
    if bg_l - fg_l >= 120 and bg_l >= 150 and fg_l <= 120:
        return (0, 0, 0)
    if fg_l - bg_l >= 120 and fg_l >= 150 and bg_l <= 120:
        return (255, 255, 255)

    # Common comic case: dark text on (near) white bubble.
    if bg_l >= 190 and fg_l <= 95:
        return (0, 0, 0)

    # Common reverse case: light text on (near) black bubble.
    if bg_l <= 55 and fg_l >= 160:
        return (255, 255, 255)

    return fg_rgb

def _robust_cluster_rgb(
    pixels_rgb: np.ndarray,
    *,
    prefer: str,
    tail_frac: float = 0.18,
) -> tuple[int, int, int]:
    """Pick a robust representative RGB from pixels, biased to darkest/lightest tail.

    This helps avoid anti-aliased edge mixing that makes pure black/white look grey.
    """
    if pixels_rgb.size == 0:
        return (0, 0, 0)
    px = pixels_rgb.astype(np.uint8, copy=False)
    luma = _luma_u8(px)
    n = int(luma.size)
    if n < 50:
        rgb = np.median(px.astype(np.float32), axis=0)
        return tuple(int(v) for v in np.clip(np.round(rgb), 0, 255))

    k = max(30, int(round(n * float(tail_frac))))
    if prefer == "dark":
        idx = np.argpartition(luma, k - 1)[:k]
    else:
        idx = np.argpartition(luma, n - k)[n - k :]

    rgb = np.median(px[idx].astype(np.float32), axis=0)
    return tuple(int(v) for v in np.clip(np.round(rgb), 0, 255))


def _try_chroma_polarity(
    img: np.ndarray,
    valid_mask: np.ndarray,
) -> ForegroundColorEstimate | None:
    """Fast path: detect colored text on a neutral background via chroma.

    Runs Otsu on the per-pixel chroma channel (max-min of RGB), which
    cleanly separates saturated strokes from desaturated backgrounds even
    when luma contrast is poor (e.g. cyan on white, red on black).

    Returns *None* when the crop doesn't exhibit clear chroma bimodality,
    letting the caller fall through to the luminance-based Otsu / k-means.
    """
    chroma = _chroma_u8(img)
    valid_chroma = chroma[valid_mask]
    if valid_chroma.size == 0 or int(valid_chroma.max()) < 40:
        return None

    # Otsu on chroma to split colored ↔ neutral pixels.
    _, chroma_bin = imk.otsu_threshold(chroma)
    high = (chroma_bin > 0) & valid_mask
    low = (~chroma_bin.astype(bool)) & valid_mask

    n_valid = max(int(valid_mask.sum()), 1)
    frac_high = float(high.sum()) / n_valid

    # The minority group is our text candidate.
    if frac_high > 0.5:
        fg_mask, bg_mask = low, high
        frac = 1.0 - frac_high
    else:
        fg_mask, bg_mask = high, low
        frac = frac_high

    if not (0.005 <= frac <= 0.45):
        return None

    fg_px = img[fg_mask]
    bg_px = img[bg_mask]
    if fg_px.shape[0] < 15 or bg_px.shape[0] < 15:
        return None

    # Bias toward the most saturated interior pixels to reduce AA fringe.
    if fg_px.shape[0] > 50:
        fg_chr = _chroma_u8(fg_px.astype(np.uint8, copy=False))
        k_tail = max(20, int(fg_px.shape[0] * 0.30))
        top_idx = np.argpartition(fg_chr, fg_chr.size - k_tail)[-k_tail:]
        fg_med = np.median(fg_px[top_idx].astype(np.float32), axis=0)
    else:
        fg_med = np.median(fg_px.astype(np.float32), axis=0)
    fg_rgb_i: tuple[int, int, int] = tuple(
        int(v) for v in np.clip(np.round(fg_med), 0, 255)
    )

    bg_med = np.median(bg_px.astype(np.float32), axis=0)
    bg_rgb_i: tuple[int, int, int] = tuple(
        int(v) for v in np.clip(np.round(bg_med), 0, 255)
    )

    # The foreground must be substantially more chromatic than background.
    fg_c = float(max(fg_rgb_i) - min(fg_rgb_i))
    bg_c = float(max(bg_rgb_i) - min(bg_rgb_i))
    if fg_c < 35 or fg_c <= bg_c * 1.3:
        return None

    fg_l = float(_luma_u8(np.array(fg_rgb_i, dtype=np.uint8)))
    bg_l = float(_luma_u8(np.array(bg_rgb_i, dtype=np.uint8)))
    luma_contrast = abs(fg_l - bg_l) / 255.0
    chroma_contrast = (fg_c - bg_c) / 255.0
    conf = min(1.0, chroma_contrast * 2.5 + luma_contrast * 0.5)
    conf = max(conf, 0.55)

    return ForegroundColorEstimate(
        rgb=fg_rgb_i,
        confidence=conf,
        method="polarity",
        background_rgb=bg_rgb_i,
    )


def _kmeans_rgb(
    x: np.ndarray,
    k: int,
    *,
    seed: int = 0,
    max_iter: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """Tiny k-means for RGB points.

    Args:
        x: (N, 3) float32 in [0, 255]
        k: clusters
    Returns:
        centers: (k, 3) float32
        labels: (N,) int64
    """
    n = int(x.shape[0])
    if n == 0:
        raise ValueError("kmeans: empty input")
    if k <= 0:
        raise ValueError("kmeans: k must be > 0")

    x = x.astype(np.float32, copy=False)
    rng = np.random.default_rng(seed)
    if n <= k:
        # Degenerate: every point is its own center (pad/repeat).
        centers = np.empty((k, 3), dtype=np.float32)
        centers[:n] = x
        if n < k:
            centers[n:] = centers[0]
        labels = np.arange(n, dtype=np.int64)
        return centers, labels

    init_idx = rng.choice(n, size=k, replace=False)
    centers = x[init_idx].astype(np.float32, copy=True)
    labels = np.zeros((n,), dtype=np.int64)
    x_sq = np.einsum("ij,ij->i", x, x)

    for _ in range(max_iter):
        # (N, K) squared distances via ||x-c||^2 = ||x||^2 + ||c||^2 - 2x.c
        c_sq = np.einsum("ij,ij->i", centers, centers)
        d2 = x_sq[:, None] + c_sq[None, :] - (2.0 * (x @ centers.T))
        new_labels = d2.argmin(axis=1)

        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        # Update centers; re-seed empty clusters.
        counts = np.bincount(labels, minlength=k)
        # Per-channel bincount is much faster than np.add.at for
        # small k — avoids unbuffered Python-level per-element overhead.
        sums = np.empty((k, 3), dtype=np.float32)
        for ch in range(3):
            sums[:, ch] = np.bincount(labels, weights=x[:, ch], minlength=k)

        nonempty = counts > 0
        if np.any(nonempty):
            centers[nonempty] = sums[nonempty] / counts[nonempty, None].astype(np.float32)

        empty_ids = np.flatnonzero(~nonempty)
        if empty_ids.size:
            centers[empty_ids] = x[rng.integers(0, n, size=empty_ids.size)]

    return centers, labels


@dataclass(frozen=True)
class ForegroundColorEstimate:
    rgb: tuple[int, int, int]
    confidence: float
    method: str
    background_rgb: tuple[int, int, int] | None = None

    @property
    def hex(self) -> str:
        return rgb_to_hex(self.rgb)

    @property
    def named(self) -> str:
        return nearest_named_color(self.rgb)[0]


def estimate_text_foreground_color(
    crop_rgb: np.ndarray,
    *,
    max_side: int = 256,
    sample_limit: int = 20_000,
    k: int = 3,
    seed: int = 0,
) -> ForegroundColorEstimate | None:
    """Estimate the *rendered* text foreground color from a detected crop.

    This is a post-process intended to be used when model-regressed text color
    is unreliable. It clusters crop pixels by color and selects the cluster with
    the highest "stroke-likelihood" (high edge density, not the majority).
    """
    if crop_rgb is None:
        return None
    img = np.asarray(crop_rgb)
    if img.ndim != 3 or img.shape[2] < 3:
        return None
    if img.shape[2] > 3:
        img = img[..., :3]
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)

    h, w = img.shape[:2]
    if h < 3 or w < 3:
        return None

    # Downsample for speed.
    if max(h, w) > max_side:
        scale = max_side / float(max(h, w))
        nw = max(3, int(round(w * scale)))
        nh = max(3, int(round(h * scale)))
        # Prefer nearest-neighbor to avoid creating new mixed colors (e.g., black->grey).
        img = imk.resize(img, (nw, nh), mode=Image.Resampling.NEAREST)
        h, w = img.shape[:2]

    gray = imk.to_gray(img)

    margin = max(1, min(h, w) // 20)
    valid_mask = np.ones((h, w), dtype=bool)
    if margin > 0:
        valid_mask[:margin, :] = False
        valid_mask[-margin:, :] = False
        valid_mask[:, :margin] = False
        valid_mask[:, -margin:] = False

    # --- Fast path: chroma polarity for colored text on neutral bg ---
    chroma_est = _try_chroma_polarity(img, valid_mask)
    if chroma_est is not None:
        return chroma_est

    # Fast candidate: Otsu + minority class (great for common black/white text).
    try:
        _, bin_mask = imk.otsu_threshold(gray)
        m = (bin_mask > 0)
        if m.mean() > 0.5:
            m = ~m

        # Remove border influence and erode to bias toward stroke interiors.
        if margin > 0:
            m[~valid_mask] = False

        if m.any():
            # Single 5×5 erosion ≈ two 3×3 iterations, but one C-level pass
            # instead of two — avoids an extra array copy + function call.
            kernel5 = np.ones((5, 5), dtype=np.uint8)
            m_er = imk.erode(m.astype(np.uint8) * 255, kernel5, iterations=1) > 0
            if m_er.any():
                m = m_er

            fg = img[m]
            bg = img[~m] if (~m).any() else None
            fg_rgb_med = np.median(fg.astype(np.float32), axis=0)
            fg_rgb_i = tuple(int(x) for x in np.clip(np.round(fg_rgb_med), 0, 255))
            bg_rgb_i: tuple[int, int, int] | None = None

            conf = 0.0
            if bg is not None and bg.size > 0:
                bg_rgb = np.median(bg.astype(np.float32), axis=0)
                bg_rgb_i = tuple(int(x) for x in np.clip(np.round(bg_rgb), 0, 255))
                fg_l = float(_luma_u8(np.array(fg_rgb_i)))
                bg_l = float(_luma_u8(np.array(bg_rgb_i)))
                contrast = float(abs(fg_l - bg_l) / 255.0)
                frac = float(m.mean())
                # Heuristic confidence: high contrast + reasonable stroke fraction.
                if 0.01 <= frac <= 0.55:
                    conf = min(1.0, (contrast - 0.15) / 0.35)

                # If the foreground is near-neutral and high-contrast vs background, bias
                # the estimate toward the darkest/lightest interior pixels to avoid grey.
                if conf >= 0.4:
                    fg_chroma = float(max(fg_rgb_i) - min(fg_rgb_i))
                    if fg_chroma <= 45 and abs(fg_l - bg_l) >= 60:
                        prefer = "dark" if fg_l < bg_l else "light"
                        fg_rgb_i = _robust_cluster_rgb(fg, prefer=prefer, tail_frac=0.18)

                if conf >= 0.75:
                    fg_rgb_i = _snap_neutral_extremes(fg_rgb_i, bg_rgb_i)
                    return ForegroundColorEstimate(
                        rgb=fg_rgb_i,
                        confidence=conf,
                        method="otsu",
                        background_rgb=bg_rgb_i,
                    )

                # Colored text on dark bubbles can have modest luminance contrast
                # (e.g. red on black). If the Otsu mask fraction looks plausible and
                # the foreground is clearly colorful, accept the estimate anyway.
                fg_chroma = float(max(fg_rgb_i) - min(fg_rgb_i))
                if bg_l <= 60 and (fg_l - bg_l) >= 25 and fg_chroma >= 60 and 0.002 <= frac <= 0.35:
                    return ForegroundColorEstimate(
                        rgb=fg_rgb_i,
                        confidence=max(conf, 0.65),
                        method="otsu",
                        background_rgb=bg_rgb_i,
                    )
    except Exception:
        pass

    # General case: k-means + "edge density" scoring.
    kernel = imk.get_structuring_element(imk.MORPH_RECT, (3, 3))
    grad = imk.morphology_ex(gray, imk.MORPH_GRADIENT, kernel).astype(np.uint8, copy=False)
    thr = float(np.percentile(grad, 85))
    edge_mask = grad >= thr

    if margin > 0:
        edge_mask[~valid_mask] = False

    flat_img = img.reshape(-1, 3)
    flat_edge = edge_mask.reshape(-1)
    flat_valid = valid_mask.reshape(-1)

    valid_idx_all = np.flatnonzero(flat_valid)
    n = int(valid_idx_all.size)
    if n == 0:
        return None

    rng = np.random.default_rng(seed)
    if n > sample_limit:
        pick = rng.choice(n, size=sample_limit, replace=False)
    else:
        pick = np.arange(n, dtype=np.int64)

    idx = valid_idx_all[pick]
    x = flat_img[idx].astype(np.float32, copy=False)
    edge_flags = flat_edge[idx]

    # Avoid pathological all-same-color crops.
    if float(x.std()) < 1.0:
        rgb_i = tuple(int(v) for v in np.clip(np.round(x.mean(axis=0)), 0, 255))
        return ForegroundColorEstimate(rgb=rgb_i, confidence=0.0, method="flat")

    centers, labels = _kmeans_rgb(x, k, seed=seed, max_iter=20)

    # Score: prefer clusters with many edge pixels but not the majority.
    # Vectorised stats — avoids k boolean masks + fancy-index sums.
    labels_intp = labels.astype(np.intp, copy=False)
    cluster_sizes = np.bincount(labels_intp, minlength=k).astype(np.int64)
    cluster_edge_counts = np.bincount(
        labels_intp, weights=edge_flags.astype(np.float64), minlength=k,
    ).astype(np.int64)

    total = max(float(cluster_sizes.sum()), 1.0)
    # Vectorised scoring over all k clusters.
    cs_f = cluster_sizes.astype(np.float64)
    size_fracs = cs_f / total
    edge_fracs = np.divide(
        cluster_edge_counts.astype(np.float64), np.maximum(cs_f, 1.0),
    )
    tiny_penalties = np.minimum(1.0, size_fracs / 0.02)
    scores = edge_fracs * (1.0 - size_fracs) * tiny_penalties
    scores[cluster_sizes <= 0] = -1.0
    # Top-2 scores.
    if k >= 2:
        top2 = np.argpartition(scores, -2)[-2:]
        if scores[top2[0]] > scores[top2[1]]:
            best_ci, second_ci = int(top2[0]), int(top2[1])
        else:
            best_ci, second_ci = int(top2[1]), int(top2[0])
        best_score = float(scores[best_ci])
        second_score = float(scores[second_ci])
    else:
        best_ci = int(scores.argmax())
        best_score = float(scores[best_ci])
        second_score = -1.0

    # Foreground pixels: prefer non-edge pixels inside the chosen cluster.
    sel_fg = labels == best_ci
    sel_fill = sel_fg & (~edge_flags)
    if int(sel_fill.sum()) < 50:
        sel_fill = sel_fg

    fg_pixels = x[sel_fill]
    fg_rgb = np.median(fg_pixels, axis=0)
    fg_rgb_i = tuple(int(v) for v in np.clip(np.round(fg_rgb), 0, 255))

    # Background: majority cluster.  Use k-means center (already a mean)
    # rather than recomputing median over potentially 10k+ points — the
    # background is typically uniform so mean ≈ median.
    bg_ci = int(cluster_sizes.argmax())
    bg_rgb_i: tuple[int, int, int] | None = None
    if cluster_sizes[bg_ci] > 0:
        bg_rgb_i = tuple(int(v) for v in np.clip(np.round(centers[bg_ci]), 0, 255))

    # Confidence combines: separation vs runner-up + contrast vs background.
    sep = float(max(0.0, best_score - second_score))
    conf = min(1.0, sep / 0.12)
    if bg_rgb_i is not None:
        fg_l = float(_luma_u8(np.array(fg_rgb_i)))
        bg_l = float(_luma_u8(np.array(bg_rgb_i)))
        contrast = float(abs(fg_l - bg_l) / 255.0)
        conf = float(max(conf, min(1.0, (contrast - 0.10) / 0.35)))

        # Near-neutral foregrounds (black/white text) often get pulled toward grey by
        # anti-aliased edges. Bias to darkest/lightest interior pixels.
        fg_chroma = float(max(fg_rgb_i) - min(fg_rgb_i))
        if fg_chroma <= 45 and abs(fg_l - bg_l) >= 60 and fg_pixels.size > 0:
            prefer = "dark" if fg_l < bg_l else "light"
            fg_u8 = np.clip(np.round(fg_pixels), 0, 255).astype(np.uint8)
            fg_rgb_i = _robust_cluster_rgb(fg_u8, prefer=prefer, tail_frac=0.18)

        fg_rgb_i = _snap_neutral_extremes(fg_rgb_i, bg_rgb_i)

    return ForegroundColorEstimate(
        rgb=fg_rgb_i,
        confidence=conf,
        method="kmeans",
        background_rgb=bg_rgb_i,
    )
