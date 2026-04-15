"""
LaMa Large 512px inpainter — uses the ``lama_large_512px.ckpt``
checkpoint from dreMaz/AnimeMangaInpainting (fine-tuned Big LaMa
on 300k anime/manga images).

Unlike the base :class:`LaMa` inpainter that loads a TorchScript JIT
model, this class instantiates the full :class:`FFCResNetGenerator`
architecture and loads weights from a raw PyTorch ``state_dict``
checkpoint.
"""

from __future__ import annotations

import logging
import os

import imkit as imk
import numpy as np
from PIL import Image

from ..utils.download import ModelDownloader, ModelID
from ..utils.inpainting import (
    boxes_from_mask,
    norm_img,
    pad_img_to_modulo,
    resize_max_size,
)
from ..utils.torch_autocast import TorchAutocastMixin
from .base import InpaintModel
from .schema import Config

logger = logging.getLogger(__name__)


class LamaLarge(TorchAutocastMixin, InpaintModel):
    """Inpainter using ``lama_large_512px.ckpt`` (PyTorch checkpoint)."""

    name = "lama_large"
    pad_mod = 8
    preferred_backend = "torch"  # No ONNX variant available

    # Per-region processing parameters for optimal quality.
    # The model was fine-tuned at 512px; processing at 1024px gives
    # excellent quality thanks to the 18-block big-lama architecture.
    max_inpaint_size = 1024
    crop_margin = 128

    @staticmethod
    def should_use_autocast(device: str) -> bool:
        """XPU devices require float32 for the FFT path."""
        return str(device).split(":", 1)[0].lower() != "xpu"

    def init_model(self, device, **kwargs):
        import torch

        self.backend = "torch"

        # Ensure checkpoint is downloaded
        ModelDownloader.get(ModelID.LAMA_LARGE_CKPT)
        ckpt_path = ModelDownloader.primary_path(ModelID.LAMA_LARGE_CKPT)

        # Build the generator architecture
        from .ffc_arch import build_lama_large_generator

        self.model = build_lama_large_generator()

        # Load checkpoint weights
        logger.info("Loading LaMa Large checkpoint from: %s", ckpt_path)
        checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)

        # Handle multiple checkpoint formats:
        # 1. BallonsTranslator / dreMaz: {'gen_state_dict': {...}}
        # 2. PyTorch Lightning: {'state_dict': {...}} with 'generator.model.' prefix
        # 3. Nested under 'model' key
        # 4. Raw state_dict (OrderedDict of tensors)
        if isinstance(checkpoint, dict) and "gen_state_dict" in checkpoint:
            state_dict = checkpoint["gen_state_dict"]
            logger.info("Checkpoint format: gen_state_dict (%d keys)", len(state_dict))
        elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
            logger.info("Checkpoint format: state_dict (%d keys)", len(state_dict))
        elif isinstance(checkpoint, dict) and "model" in checkpoint:
            state_dict = checkpoint["model"]
            logger.info("Checkpoint format: model (%d keys)", len(state_dict))
        else:
            state_dict = checkpoint
            logger.info("Checkpoint format: raw (%d keys)", len(state_dict))

        # Strip common key prefixes to match our model's parameter names
        cleaned_state_dict = self._clean_state_dict(state_dict)

        # Load into model
        missing, unexpected = self.model.load_state_dict(cleaned_state_dict, strict=False)
        if missing:
            logger.warning(
                "LaMa Large: %d missing keys: %s",
                len(missing),
                missing[:10],
            )
        if unexpected:
            logger.warning(
                "LaMa Large: %d unexpected keys: %s",
                len(unexpected),
                unexpected[:10],
            )

        # Critical integrity check: if most keys are missing, the model
        # is essentially running on random weights and will produce garbage.
        total_params = len(list(self.model.state_dict().keys()))
        if len(missing) > total_params * 0.5:
            raise RuntimeError(
                f"LaMa Large checkpoint loading failed: {len(missing)}/{total_params} "
                f"model parameters have NO learned weights (checkpoint format "
                f"mismatch?). Top-level checkpoint keys: {list(checkpoint.keys()) if isinstance(checkpoint, dict) else 'N/A'}"
            )

        self.model.to(device)
        self.model.eval()

        # Configure autocast
        self.setup_torch_autocast(torch, device)
        if not self.should_use_autocast(device):
            logger.info(
                "Disabling LaMa Large autocast on device '%s' because the FFT path requires float32.",
                device,
            )
            self.use_autocast = False

        logger.info("LaMa Large model initialized on device '%s'", device)

    @staticmethod
    def _clean_state_dict(state_dict: dict) -> dict:
        """Strip known prefixes from checkpoint keys to match local model parameter names.

        Tries the following prefix removals in order:
          1. ``generator.model.`` → ``model.``  (PyTorch Lightning full key)
          2. ``generator.``       → `` ``        (less common)

        If none of the prefixes match, returns the state_dict as-is (assume
        it already matches).
        """
        # Detect which prefix is present
        prefixes_to_try = ["generator.model.", "generator."]

        for prefix in prefixes_to_try:
            if any(k.startswith(prefix) for k in state_dict):
                # For "generator.model." -> we want "model." (our FFCResNetGenerator stores in self.model)
                if prefix == "generator.model.":
                    new_prefix = "model."
                else:
                    new_prefix = ""

                cleaned = {}
                for k, v in state_dict.items():
                    if k.startswith(prefix):
                        new_key = new_prefix + k[len(prefix):]
                        cleaned[new_key] = v
                    # Skip keys that don't start with this prefix
                    # (e.g., discriminator, optimizer, loss weights)

                if cleaned:
                    logger.info(
                        "Stripped prefix '%s' from %d checkpoint keys (skipped %d non-generator keys)",
                        prefix,
                        len(cleaned),
                        len(state_dict) - len(cleaned),
                    )
                    return cleaned

        # No prefix found — return as-is
        return state_dict

    @staticmethod
    def is_downloaded() -> bool:
        return ModelDownloader.is_downloaded(ModelID.LAMA_LARGE_CKPT)

    # -----------------------------------------------------------------
    # Override __call__ — per-region crop + resize strategy
    # -----------------------------------------------------------------

    def __call__(self, image, mask, config: Config):
        """Per-region crop+resize inpainting for production quality.

        Processing an entire 2000-3000px manga page in a single forward
        pass forces the model to work far outside its trained resolution
        (512px), producing blurry/smudged artefacts — especially over
        detailed artwork like SFX text on character illustrations.

        This override implements the same pattern used by
        :class:`MIGAN`:

        1. Detect individual mask regions  (``boxes_from_mask``)
        2. Crop each region with context margin
        3. Resize to the model's optimal resolution
        4. Inpaint each crop individually
        5. Resize back and paste only the masked pixels

        For small images (≤ ``max_inpaint_size``) the full image is
        processed directly.
        """
        import torch

        ctx = torch.no_grad()
        with ctx:
            # Small images → process directly
            if max(image.shape[:2]) <= self.max_inpaint_size:
                return self._pad_forward(image, mask, config)

            boxes = boxes_from_mask(mask)
            if not boxes:
                return self._pad_forward(image, mask, config)

            crop_results = []
            for box in boxes:
                crop_img, crop_mask, crop_box = self._crop_box(
                    image, mask, box,
                    Config(hd_strategy_crop_margin=self.crop_margin),
                )
                origin_size = crop_img.shape[:2]

                # Resize to model's optimal resolution
                resize_img = resize_max_size(
                    crop_img, size_limit=self.max_inpaint_size
                )
                resize_mask = resize_max_size(
                    crop_mask, size_limit=self.max_inpaint_size
                )

                inpaint_result = self._pad_forward(
                    resize_img, resize_mask, config
                )

                # Resize back to original crop size
                inpaint_result = imk.resize(
                    inpaint_result,
                    (origin_size[1], origin_size[0]),
                    mode=Image.Resampling.BICUBIC,
                )

                # Preserve original pixels outside the mask
                original_pixel_indices = crop_mask < 127
                inpaint_result[original_pixel_indices] = crop_img[
                    original_pixel_indices
                ]

                crop_results.append((inpaint_result, crop_box))

            inpaint_result = image.copy()
            for crop_image, crop_box in crop_results:
                x1, y1, x2, y2 = crop_box
                inpaint_result[y1:y2, x1:x2, :] = crop_image

            return inpaint_result

    # -----------------------------------------------------------------
    # forward — single-image neural inference
    # -----------------------------------------------------------------

    def forward(self, image, mask, config: Config):
        """Run LaMa Large inpainting on a single (possibly cropped) patch.

        Args:
            image: [H, W, C] RGB uint8, not normalized.
            mask:  [H, W] uint8, 255 = masked region.
            config: Inpainting configuration.

        Returns:
            [H, W, C] RGB uint8 inpainted image (already blended).
        """
        import torch

        # ------------------------------------------------------------------
        # Step 1: Conservative mask dilation (3×3, 1 iteration).
        #   Captures anti-aliased text edges without expanding into
        #   surrounding artwork (the old 5×5 / 2× dilation was too
        #   aggressive and damaged lineart near SFX areas).
        # ------------------------------------------------------------------
        mask_2d = mask.squeeze() if mask.ndim == 3 else mask
        kernel = np.ones((3, 3), np.uint8)
        mask_dilated = imk.dilate(mask_2d, kernel, iterations=1)

        # ------------------------------------------------------------------
        # Step 2: Normalize image & mask to float32 [0, 1]
        # ------------------------------------------------------------------
        image_n = norm_img(image)                            # (C, H, W)
        mask_n = norm_img(mask_dilated)                      # (1, H, W)
        mask_n = (mask_n > 0).astype("float32")

        # ------------------------------------------------------------------
        # Step 3: Build 4-channel input: concat(masked_RGB, mask)
        # ------------------------------------------------------------------
        image_t = torch.from_numpy(image_n).unsqueeze(0).to(self.device)
        mask_t = torch.from_numpy(mask_n).unsqueeze(0).to(self.device)

        masked_image = image_t * (1 - mask_t)
        input_t = torch.cat([masked_image, mask_t], dim=1)   # (1, 4, H, W)

        # ------------------------------------------------------------------
        # Step 4: Forward pass
        # ------------------------------------------------------------------
        with torch.inference_mode():
            output = self.run_with_torch_autocast(
                torch_module=torch,
                fn=lambda: self.model(input_t),
                logger=logger,
                engine_name=self.__class__.__name__,
            )

        # ------------------------------------------------------------------
        # Step 5: Float32-precision blending
        #   result = predicted * mask + original * (1 - mask)
        # ------------------------------------------------------------------
        blended = output * mask_t + image_t * (1 - mask_t)

        cur_res = blended[0].permute(1, 2, 0).detach().cpu().numpy()
        cur_res = np.clip(cur_res * 255, 0, 255).astype("uint8")
        return cur_res

    # -----------------------------------------------------------------
    # _pad_forward — padding without redundant uint8 blending
    # -----------------------------------------------------------------

    def _pad_forward(self, image, mask, config: Config):
        """Pad, forward, then un-pad — skip base-class uint8 blending."""
        origin_height, origin_width = image.shape[:2]
        pad_image = pad_img_to_modulo(
            image, mod=self.pad_mod, square=self.pad_to_square, min_size=self.min_size
        )
        pad_mask = pad_img_to_modulo(
            mask, mod=self.pad_mod, square=self.pad_to_square, min_size=self.min_size
        )

        result = self.forward(pad_image, pad_mask, config)
        result = result[0:origin_height, 0:origin_width, :]
        return result
