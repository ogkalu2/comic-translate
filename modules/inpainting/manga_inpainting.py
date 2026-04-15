"""
CUHK MangaInpainting — InpaintModel Integration
================================================

Production-grade integration of the CUHK "Seamless Manga Inpainting with
Semantics Awareness" (SIGGRAPH 2021) into the Comic-Translate inpainting
pipeline.

This module implements a **per-region context-aware** 3-stage inference pipeline:
    1. Connected-component analysis to isolate each mask region
    2. Per-region context analysis using MEDIAN-based flat detection
    3. Flat regions (speech bubbles) → local color fill (white)
    4. Complex regions → full CUHK neural pipeline

Architecture:
    - ScreenVAE encoder — Extract screentone representations
    - SemanticInpaintGenerator — Iteratively predict structural lines + screentones
    - MangaInpaintGenerator — Contextual-attention appearance synthesis

Features:
    - Per-region local context detection prevents screentone hallucination
    - Automatic checkpoint download from Google Drive via ``gdown``
    - Clean structural line extraction with aggressive noise suppression
    - Full device-agnostic operation (CPU / CUDA / MPS / XPU)
"""

from __future__ import annotations

import os
import logging
from typing import Optional

import numpy as np
import imkit as imk

from .base import InpaintModel
from .schema import Config
from ..utils.torch_autocast import TorchAutocastMixin
from ..utils.download import models_base_dir, notify_download_event

logger = logging.getLogger(__name__)

# Directory where CUHK MangaInpainting checkpoints are stored
_CHECKPOINT_DIR = os.path.join(models_base_dir, 'inpainting', 'manga-inpainting')

# Google Drive file IDs for the official pre-trained models
_GDRIVE_IDS = {
    'mangainpaintor': '1YeVwaNfchLhy3lAA7jOLBP-W23onjy8S',
    'screenvae': '1QaXqR4KWl_lxntSy32QpQpXb-1-EP7_L',
}

# Required checkpoint files
_REQUIRED_FILES = {
    'semantic_gen': 'SemanticInpaintingModel_gen.pth',
    'manga_gen': 'MangaInpaintingModel_gen.pth',
    'screenvae_enc': 'latest_net_enc.pth',
}

# Iterative mask erosion schedule
_SHRINK_ITERS = 5

# --- Per-region context detection tuning ---
# Width of the analysis ring around each mask region (pixels)
_BORDER_PX = 10
# Minimum border samples for reliable analysis
_MIN_BORDER_SAMPLES = 20
# MEDIAN threshold: if median of surrounding pixels > this → flat
# Manga speech bubbles have mostly white (240-255) with thin black border lines
# Using MEDIAN (not mean) makes this robust to bubble-outline pixels
_FLAT_MEDIAN_THRESHOLD = 210


def _ensure_checkpoint_dir() -> str:
    """Create and return the checkpoint directory path."""
    os.makedirs(_CHECKPOINT_DIR, exist_ok=True)
    return _CHECKPOINT_DIR


def _get_missing_files() -> list[str]:
    """Return list of missing checkpoint filenames."""
    return [
        fname for fname in _REQUIRED_FILES.values()
        if not os.path.exists(os.path.join(_CHECKPOINT_DIR, fname))
    ]


def _download_checkpoints():
    """Download CUHK MangaInpainting checkpoints from Google Drive."""
    import tempfile
    import zipfile
    import shutil

    try:
        import gdown
    except ImportError:
        raise RuntimeError(
            "CUHK MangaInpainting requires the 'gdown' package for automatic "
            "checkpoint download.\n"
            "Install it with: pip install gdown\n\n"
            "Alternatively, manually download the checkpoints from:\n"
            "  MangaInpainting: https://drive.google.com/file/d/1YeVwaNfchLhy3lAA7jOLBP-W23onjy8S\n"
            "  ScreenVAE:       https://drive.google.com/file/d/1QaXqR4KWl_lxntSy32QpQpXb-1-EP7_L\n"
            f"Extract and place the .pth files into:\n  {_CHECKPOINT_DIR}"
        )

    save_dir = _ensure_checkpoint_dir()

    for archive_name, gdrive_id in _GDRIVE_IDS.items():
        if archive_name == 'mangainpaintor':
            needed = [_REQUIRED_FILES['semantic_gen'], _REQUIRED_FILES['manga_gen']]
        else:
            needed = [_REQUIRED_FILES['screenvae_enc']]

        if all(os.path.exists(os.path.join(save_dir, f)) for f in needed):
            logger.info(f"Checkpoints for '{archive_name}' already present, skipping download.")
            continue

        logger.info(f"Downloading '{archive_name}' from Google Drive (id={gdrive_id})...")
        notify_download_event('start', f'manga-inpainting-{archive_name}')

        with tempfile.TemporaryDirectory(dir=save_dir) as tmp_dir:
            url = f"https://drive.google.com/uc?id={gdrive_id}"
            tmp_path = os.path.join(tmp_dir, f"{archive_name}.zip")

            try:
                output = gdown.download(url, tmp_path, quiet=False)
                if output is None:
                    raise RuntimeError(f"gdown returned None for {archive_name}")
            except Exception as e:
                logger.error(f"Failed to download {archive_name}: {e}")
                notify_download_event('end', f'manga-inpainting-{archive_name}')
                raise RuntimeError(
                    f"Failed to download CUHK MangaInpainting checkpoint '{archive_name}'.\n"
                    f"Error: {e}\n\n"
                    "Please manually download from Google Drive and extract .pth files to:\n"
                    f"  {save_dir}"
                ) from e

            extracted = False
            if zipfile.is_zipfile(tmp_path):
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    zf.extractall(tmp_dir)
                extracted = True
            else:
                try:
                    import tarfile
                    if tarfile.is_tarfile(tmp_path):
                        with tarfile.open(tmp_path, 'r:*') as tf:
                            tf.extractall(tmp_dir)
                        extracted = True
                except Exception:
                    pass

            if not extracted:
                if len(needed) == 1:
                    shutil.copy2(tmp_path, os.path.join(save_dir, needed[0]))
                else:
                    raise RuntimeError(
                        f"Downloaded file for '{archive_name}' is not a recognized archive."
                    )
            else:
                for root, _dirs, files in os.walk(tmp_dir):
                    for fname in files:
                        if fname in needed:
                            src = os.path.join(root, fname)
                            dst = os.path.join(save_dir, fname)
                            shutil.copy2(src, dst)
                            logger.info(f"Extracted: {fname} → {save_dir}")

        notify_download_event('end', f'manga-inpainting-{archive_name}')

    still_missing = _get_missing_files()
    if still_missing:
        raise RuntimeError(
            f"After download, still missing:\n"
            + "\n".join(f"  - {f}" for f in still_missing)
            + f"\n\nPlace these files in:\n  {save_dir}"
        )


# =============================================================================
# Per-Region Context Analysis (MEDIAN-based, per connected component)
# =============================================================================

def _is_region_flat(gray: np.ndarray, region_mask: np.ndarray) -> bool:
    """Determine if a single mask region sits inside a flat/white area.

    Uses MEDIAN of surrounding pixels (robust to thin bubble outlines).
    A typical speech bubble has:
      - White interior (240-255)
      - Thin black outline (0-30) — only 1-3px wide
    The MEDIAN ignores the outline and sees the white interior.

    Args:
        gray: [H, W] uint8 grayscale image
        region_mask: [H, W] boolean mask for ONE connected component

    Returns:
        True if the region is inside a flat/white area (speech bubble etc.)
    """
    mask_uint8 = region_mask.astype(np.uint8) * 255

    # Create a border ring around this specific region
    kernel_size = _BORDER_PX * 2 + 1
    kernel = imk.get_structuring_element(imk.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dilated = imk.dilate(mask_uint8, kernel, iterations=1) > 127
    border = dilated & (~region_mask)

    border_count = int(border.sum())
    if border_count < _MIN_BORDER_SAMPLES:
        # Too few border pixels → assume flat (safer for text cleaning)
        return True

    border_pixels = gray[border]
    median_val = float(np.median(border_pixels))

    return median_val > _FLAT_MEDIAN_THRESHOLD


def _fill_region_with_local_color(image: np.ndarray, region_mask: np.ndarray,
                                  gray: np.ndarray) -> None:
    """Fill a single flat region with the MEDIAN color of surrounding pixels.

    Modifies `image` in-place. Uses median instead of mean for robustness
    against bubble border outlines (thin black lines).

    Args:
        image: [H, W, C] uint8 RGB image (modified in-place)
        region_mask: [H, W] boolean mask for one region
        gray: [H, W] uint8 grayscale image
    """
    mask_uint8 = region_mask.astype(np.uint8) * 255
    kernel_size = _BORDER_PX * 2 + 1
    kernel = imk.get_structuring_element(imk.MORPH_ELLIPSE, (kernel_size, kernel_size))
    dilated = imk.dilate(mask_uint8, kernel, iterations=1) > 127
    border = dilated & (~region_mask)

    if border.sum() == 0:
        # Fallback: fill with white
        if len(image.shape) == 3:
            image[region_mask] = 255
        else:
            image[region_mask] = 255
        return

    if len(image.shape) == 3:
        for c in range(image.shape[2]):
            channel_border = image[:, :, c][border]
            fill_val = int(np.median(channel_border))
            image[:, :, c][region_mask] = fill_val
    else:
        fill_val = int(np.median(image[border]))
        image[region_mask] = fill_val


# =============================================================================
# Structural Line Extraction (aggressive noise suppression)
# =============================================================================

def _extract_structural_lines(grayscale: np.ndarray) -> np.ndarray:
    """Extract structural lines from a grayscale manga image.

    Uses aggressive noise suppression to prevent screentone from being
    misidentified as structural lines (which causes the semantic model
    to hallucinate screentone patterns).

    Args:
        grayscale: [H, W] uint8 grayscale image

    Returns:
        [H, W] uint8 binary line image (255 = line, 0 = background)
    """
    # Very strong blur to eliminate screentone patterns completely
    smoothed = imk.gaussian_blur(grayscale, radius=3.0)

    # Sobel gradients via numpy
    img_float = smoothed.astype(np.float64)
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
    ky = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float64)

    padded = np.pad(img_float, 1, mode='reflect')
    h, w = img_float.shape
    sx = np.zeros_like(img_float)
    sy = np.zeros_like(img_float)
    for dy in range(3):
        for dx in range(3):
            sx += padded[dy:dy + h, dx:dx + w] * kx[dy, dx]
            sy += padded[dy:dy + h, dx:dx + w] * ky[dy, dx]

    magnitude = np.hypot(sx, sy)
    max_val = magnitude.max()
    if max_val > 0:
        magnitude = (magnitude / max_val * 255).astype(np.uint8)
    else:
        return np.zeros_like(grayscale)

    # Very high threshold — only keep strong definitive lines
    threshold = max(60, int(np.mean(magnitude) + np.std(magnitude) * 1.5))
    edges = np.where(magnitude > threshold, np.uint8(255), np.uint8(0))

    # Morphological close to connect line fragments
    close_kernel = imk.get_structuring_element(imk.MORPH_RECT, (2, 2))
    edges = imk.morphology_ex(edges, imk.MORPH_CLOSE, close_kernel)

    return edges


# =============================================================================
# MangaInpainting Model
# =============================================================================

class MangaInpainting(TorchAutocastMixin, InpaintModel):
    """CUHK MangaInpainting — Per-Region Context-Aware Manga Inpainting.

    For each INDIVIDUAL masked region (connected component):
      - Analyzes local context using MEDIAN of surrounding pixels
      - Flat/white regions (bubbles) → filled with surrounding median color
      - Complex artwork → full 3-stage CUHK neural pipeline

    The per-region approach ensures speech bubbles get clean white fill
    regardless of what other regions on the page look like.
    """

    name = "manga_inpainting"
    pad_mod = 8
    pad_to_square = False
    preferred_backend = "torch"

    def init_model(self, device, **kwargs):
        """Initialize all three sub-networks and load pre-trained weights."""
        import torch

        missing = _get_missing_files()
        if missing:
            logger.info(f"Missing {len(missing)} checkpoint file(s), initiating download...")
            _ensure_checkpoint_dir()
            _download_checkpoints()

        from .manga_inpainting_arch import (
            build_screenvae_encoder,
            build_semantic_generator,
            build_manga_generator,
            Erosion2d,
        )

        logger.info("Building CUHK MangaInpainting models...")
        self.screenvae_enc = build_screenvae_encoder(device)
        self.semantic_gen = build_semantic_generator(device)
        self.manga_gen = build_manga_generator(device)
        self.erosion = Erosion2d(1, 1, 3, soft_max=False).to(device)

        self._load_weights(device, torch)

        for model in [self.screenvae_enc, self.semantic_gen, self.manga_gen]:
            for param in model.parameters():
                param.requires_grad = False

        self.setup_torch_autocast(torch, device)
        logger.info(f"CUHK MangaInpainting models loaded on device={device}")

    def _load_weights(self, device, torch_module):
        """Load pre-trained weights with DataParallel-aware state dict handling.

        CRITICAL: The ScreenVAE checkpoint keys have 'model.' prefix because the
        ScreenVAEEncoder wraps its Sequential in self.model. Loading into
        self.screenvae_enc (not .model) preserves the correct key alignment.
        """
        import torch

        save_dir = _CHECKPOINT_DIR

        # ScreenVAE encoder
        # Checkpoint keys: model.1.weight, model.1.bias, ...
        # screenvae_enc.state_dict() keys: model.1.weight, model.1.bias, ...  ← MATCH
        # screenvae_enc.model.state_dict() keys: 1.weight, 1.bias, ...  ← NO MATCH (wrong level!)
        enc_path = os.path.join(save_dir, _REQUIRED_FILES['screenvae_enc'])
        logger.info(f"Loading ScreenVAE encoder from: {enc_path}")
        enc_state = torch.load(enc_path, map_location='cpu', weights_only=False)
        enc_state = _strip_module_prefix(enc_state)
        missing, unexpected = self.screenvae_enc.load_state_dict(enc_state, strict=False)
        if missing:
            logger.warning(f"ScreenVAE missing keys: {len(missing)} — {missing[:3]}")
        if unexpected:
            logger.warning(f"ScreenVAE unexpected keys: {len(unexpected)} — {unexpected[:3]}")
        loaded = len(self.screenvae_enc.state_dict()) - len(missing)
        logger.info(f"ScreenVAE: {loaded}/{len(self.screenvae_enc.state_dict())} keys loaded")
        del enc_state

        # SemanticInpaintGenerator
        sem_path = os.path.join(save_dir, _REQUIRED_FILES['semantic_gen'])
        logger.info(f"Loading SemanticInpaintGenerator from: {sem_path}")
        sem_data = torch.load(sem_path, map_location='cpu', weights_only=False)
        sem_state = sem_data.get('generator', sem_data) if isinstance(sem_data, dict) else sem_data
        sem_state = _strip_module_prefix(sem_state)
        missing, unexpected = self.semantic_gen.load_state_dict(sem_state, strict=False)
        if missing:
            logger.warning(f"SemanticGen missing keys: {len(missing)} — {missing[:3]}")
        loaded = len(self.semantic_gen.state_dict()) - len(missing)
        logger.info(f"SemanticGen: {loaded}/{len(self.semantic_gen.state_dict())} keys loaded")
        del sem_data, sem_state

        # MangaInpaintGenerator
        manga_path = os.path.join(save_dir, _REQUIRED_FILES['manga_gen'])
        logger.info(f"Loading MangaInpaintGenerator from: {manga_path}")
        manga_data = torch.load(manga_path, map_location='cpu', weights_only=False)
        manga_state = manga_data.get('generator', manga_data) if isinstance(manga_data, dict) else manga_data
        manga_state = _strip_module_prefix(manga_state)
        missing, unexpected = self.manga_gen.load_state_dict(manga_state, strict=False)
        if missing:
            logger.warning(f"MangaGen missing keys: {len(missing)} — {missing[:3]}")
        loaded = len(self.manga_gen.state_dict()) - len(missing)
        logger.info(f"MangaGen: {loaded}/{len(self.manga_gen.state_dict())} keys loaded")

    @staticmethod
    def is_downloaded() -> bool:
        return len(_get_missing_files()) == 0

    def forward(self, image: np.ndarray, mask: np.ndarray, config: Config) -> np.ndarray:
        """Per-region context-aware CUHK MangaInpainting.

        Uses connected-component analysis to process each mask region
        INDEPENDENTLY:
          - Speech bubbles → clean fill with surrounding median color
          - Complex artwork → full CUHK 3-stage neural pipeline

        Args:
            image: [H, W, C] RGB uint8
            mask: [H, W] or [H, W, 1] uint8 mask (255 = inpaint region)

        Returns:
            [H, W, C] RGB uint8 inpainted result
        """
        # Normalize mask to 2D
        mask_2d = mask[:, :, 0] if len(mask.shape) == 3 else mask
        mask_bool = mask_2d > 127

        if not mask_bool.any():
            return image.copy()

        # Grayscale for analysis
        if len(image.shape) == 3 and image.shape[2] >= 3:
            gray = imk.to_gray(image)
        else:
            gray = image if len(image.shape) == 2 else image[:, :, 0]

        # =================================================================
        # PER-REGION analysis via connected components
        # =================================================================
        mask_uint8 = mask_bool.astype(np.uint8) * 255
        num_labels, labels, stats, centroids = imk.connected_components_with_stats(
            mask_uint8, connectivity=4
        )

        result = image.copy()
        neural_mask = np.zeros_like(mask_2d, dtype=np.uint8)  # regions needing neural pipeline
        flat_count = 0
        neural_count = 0

        for label_id in range(1, num_labels):  # skip background (0)
            region_mask = labels == label_id

            # Skip tiny regions (< 10 pixels — likely noise)
            region_area = int(region_mask.sum())
            if region_area < 10:
                # Fill tiny regions with surrounding color
                _fill_region_with_local_color(result, region_mask, gray)
                flat_count += 1
                continue

            if _is_region_flat(gray, region_mask):
                # FLAT — fill with median surrounding color
                _fill_region_with_local_color(result, region_mask, gray)
                flat_count += 1
            else:
                # COMPLEX — mark for neural pipeline
                neural_mask[region_mask] = 255
                neural_count += 1

        logger.info(
            f"CUHK MangaInpainting: {num_labels - 1} region(s) analyzed: "
            f"{flat_count} flat (local fill), {neural_count} complex (neural pipeline)"
        )

        # =================================================================
        # Run neural pipeline ONCE for all complex regions combined
        # =================================================================
        if neural_count > 0 and neural_mask.any():
            neural_result = self._run_cuhk_pipeline(image, gray, neural_mask, config)
            # Composite neural results into the output
            neural_bool = neural_mask > 127
            result[neural_bool] = neural_result[neural_bool]

        return result

    def _run_cuhk_pipeline(self, image: np.ndarray, gray: np.ndarray,
                           mask_2d: np.ndarray, config: Config) -> np.ndarray:
        """Run the full 3-stage CUHK MangaInpainting neural pipeline.

        Used only for complex artwork regions.

        Args:
            image: [H, W, C] RGB uint8
            gray: [H, W] uint8 grayscale
            mask_2d: [H, W] uint8 mask (255 = complex regions only)
            config: Inpainting config

        Returns:
            [H, W, C] RGB uint8 inpainted result
        """
        import torch

        device = self.device
        lines = _extract_structural_lines(gray)

        gray_norm = gray.astype(np.float32) / 127.5 - 1.0
        lines_norm = lines.astype(np.float32) / 127.5 - 1.0
        mask_norm = (mask_2d > 127).astype(np.float32)

        gray_t = torch.from_numpy(gray_norm).unsqueeze(0).unsqueeze(0).to(device)
        lines_t = torch.from_numpy(lines_norm).unsqueeze(0).unsqueeze(0).to(device)
        mask_t = torch.from_numpy(mask_norm).unsqueeze(0).unsqueeze(0).to(device)

        # Mask dilation
        from .manga_inpainting_arch import Dilation2d
        dilate = Dilation2d(1, 1, 3, soft_max=False).to(device)
        mask_t = dilate(mask_t, iterations=2)

        manga_masked = gray_t * (1 - mask_t) + mask_t
        lines_masked = lines_t * (1 - mask_t) + mask_t

        def _run_pipeline():
            # Stage 1: ScreenVAE encoding
            line_signed = torch.sign(lines_masked)
            manga_clamped = torch.clamp(manga_masked + (1 - line_signed), -1, 1)
            enc_input = torch.cat([manga_clamped, line_signed], dim=1)
            enc_output = self.screenvae_enc(enc_input)
            screen_masked, _logvar = torch.split(enc_output, 4, dim=1)

            # Stage 2: Semantic inpainting (iterative)
            lines_masked_2 = lines_t * (1 - mask_t) + mask_t
            screen_current = screen_masked.clone()
            lines_current = lines_masked_2.clone()
            noise = torch.randn_like(mask_t)

            grained = 1.0 / _SHRINK_ITERS
            erosion_masks = [mask_t.clone()]
            eroded = mask_t.clone()
            for t in range(1, _SHRINK_ITERS):
                target_area = mask_t.sum() * (1 - grained * t)
                while eroded.sum() > target_area:
                    eroded = self.erosion(eroded, iterations=3)
                erosion_masks.append(eroded.clone())

            for nmask in erosion_masks:
                combined_mask = (mask_t + nmask) / 2.0
                inputs = torch.cat([screen_current, lines_current, combined_mask, noise], dim=1)
                screen_pred, lines_pred = self.semantic_gen(inputs)
                screen_current = screen_masked * (1 - mask_t) + screen_pred * mask_t
                lines_current = lines_masked_2 * (1 - mask_t) + lines_pred * mask_t

            # Stage 3: Appearance synthesis
            hints = torch.cat([screen_current, lines_current], dim=1)
            images_masked = gray_t * (1 - mask_t).float()
            gen_input = torch.cat([images_masked, hints], dim=1)
            output = self.manga_gen(gen_input, mask_t)
            output_merged = output * mask_t + gray_t * (1 - mask_t)
            return output_merged

        result_t = self.run_with_torch_autocast(
            torch_module=torch,
            fn=_run_pipeline,
            logger=logger,
            engine_name="MangaInpainting",
        )

        result_np = result_t.squeeze().cpu().numpy()
        result_np = np.clip((result_np + 1) * 127.5, 0, 255).astype(np.uint8)
        result_rgb = np.stack([result_np] * 3, axis=-1)
        return result_rgb


def _strip_module_prefix(state_dict: dict) -> dict:
    """Strip 'module.' prefix from DataParallel state dict keys."""
    cleaned = {}
    for key, value in state_dict.items():
        new_key = key.replace('module.', '', 1) if key.startswith('module.') else key
        cleaned[new_key] = value
    return cleaned


try:
    import torch
except ImportError:
    pass
