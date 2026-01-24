import logging
import base64
import io
from typing import Optional

import numpy as np
from PIL import Image

from .base import InpaintModel
from .schema import Config

logger = logging.getLogger(__name__)

# Import guard for replicate
try:
    import replicate
    REPLICATE_AVAILABLE = True
except ImportError:
    replicate = None
    REPLICATE_AVAILABLE = False


class ReplicateInpaint(InpaintModel):
    name = "replicate"
    pad_mod = 8

    def __init__(self, device, **kwargs):
        self.api_key: Optional[str] = kwargs.get('api_key')
        super().__init__(device, **kwargs)

    def init_model(self, device, **kwargs):
        """Initialize the Replicate API client."""
        # Set backend to 'onnx' to avoid torch import in base class __call__
        self.backend = kwargs.get("backend", "onnx")

        if not REPLICATE_AVAILABLE:
            raise ImportError("replicate package is not installed. Install it with: pip install replicate")

        if not self.api_key:
            raise ValueError("Replicate API key is required. Configure it in Settings > Credentials.")

        # Set the API token for the replicate client
        import os
        os.environ["REPLICATE_API_TOKEN"] = self.api_key

    @staticmethod
    def is_downloaded() -> bool:
        """API-based model is always 'available' if replicate is installed."""
        return REPLICATE_AVAILABLE

    def forward(self, image, mask, config: Config):
        """
        Run inpainting via Replicate API.

        Args:
            image: [H, W, C] RGB numpy array
            mask: [H, W] numpy array, 255 = mask area

        Returns:
            RGB numpy array
        """
        # Convert image to base64 PNG
        img_pil = Image.fromarray(image.astype(np.uint8))
        img_buffer = io.BytesIO()
        img_pil.save(img_buffer, format='PNG')
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        img_data_uri = f"data:image/png;base64,{img_base64}"

        # Convert mask to base64 PNG (ensure it's proper format)
        # Squeeze mask to 2D if it has shape (H, W, 1)
        if mask.ndim == 3:
            mask = mask.squeeze(axis=-1)
        mask_pil = Image.fromarray(mask.astype(np.uint8), mode='L')
        mask_buffer = io.BytesIO()
        mask_pil.save(mask_buffer, format='PNG')
        mask_base64 = base64.b64encode(mask_buffer.getvalue()).decode('utf-8')
        mask_data_uri = f"data:image/png;base64,{mask_base64}"

        logger.info("Calling Replicate LaMa inpainting API...")

        try:
            # Call Replicate API - using twn39/lama model with full version ID
            output = replicate.run(
                "twn39/lama:2b91ca2340801c2a5be745612356fac36a17f698354a07f48a62d564d3b3a7a0",
                input={
                    "image": img_data_uri,
                    "mask": mask_data_uri,
                }
            )

            # Output is a URL to the result image
            # Download and convert to numpy array
            import requests
            response = requests.get(output, timeout=60)
            response.raise_for_status()

            result_pil = Image.open(io.BytesIO(response.content))
            result_array = np.array(result_pil)

            # Ensure RGB format (result should already be RGB)
            if result_array.ndim == 2:
                result_array = np.stack([result_array] * 3, axis=-1)
            elif result_array.shape[-1] == 4:
                result_array = result_array[:, :, :3]

            logger.info("Replicate inpainting completed successfully")
            return result_array

        except Exception as e:
            logger.error(f"Replicate API error: {e}")
            raise RuntimeError(f"Replicate inpainting failed: {e}")
