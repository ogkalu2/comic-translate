import os
import cv2
import numpy as np
import torch

from .base import InpaintModel
from .schema import Config

from ..utils.inpainting import (
    get_cache_path_by_url,
    load_jit_model,
)

AOT_MODEL_URL = os.environ.get(
    "AOT_MODEL_URL",
    "https://huggingface.co/ogkalu/aot-inpainting-jit/resolve/main/aot_traced.pt",
)
AOT_MODEL_MD5 = os.environ.get("AOT_MODEL_MD5", "5ecdac562c1d56267468fc4fbf80db27")

class AOT(InpaintModel):
    name = "aot"
    pad_mod = 8
    min_size = 128  
    max_size = 1024

    def init_model(self, device, **kwargs):
        self.model = load_jit_model(AOT_MODEL_URL, device, AOT_MODEL_MD5)
		
    @staticmethod
    def is_downloaded() -> bool:
        return os.path.exists(get_cache_path_by_url(AOT_MODEL_URL))

    def forward(self, image, mask, config: Config):
        """Input image and output image have same size
        image: [H, W, C] RGB
        mask: [H, W] or [H, W, 1]
        return: BGR IMAGE
        """
        
        # Ensure mask is 2D
        if len(mask.shape) == 3 and mask.shape[2] > 1:
            mask = mask[:, :, 0]  # Take just one channel if mask is 3D
        elif len(mask.shape) == 3:
            mask = mask[:, :, 0]
        
        # Store original dimensions
        im_h, im_w = image.shape[:2]

        if max(image.shape[0:2]) > self.max_size:
            image = resize_keep_aspect(image, self.max_size)
            mask = resize_keep_aspect(mask, self.max_size)
            
        # Convert to torch tensors with correct normalization
        img_torch = torch.from_numpy(image).permute(2, 0, 1).unsqueeze_(0).float() / 127.5 - 1.0
        mask_torch = torch.from_numpy(mask).unsqueeze_(0).unsqueeze_(0).float() / 255.0
        mask_torch[mask_torch < 0.5] = 0
        mask_torch[mask_torch >= 0.5] = 1
        
        # Move tensors to the appropriate device
        img_torch = img_torch.to(self.device)
        mask_torch = mask_torch.to(self.device)
        
        # Apply mask to input image
        img_torch = img_torch * (1 - mask_torch)
        
        # Run inference
        with torch.no_grad():
            img_inpainted_torch = self.model(img_torch, mask_torch)
        
        # Post-process result
        img_inpainted = ((img_inpainted_torch.cpu().squeeze_(0).permute(1, 2, 0).numpy() + 1.0) * 127.5)
        img_inpainted = (np.clip(np.round(img_inpainted), 0, 255)).astype(np.uint8)
        
        # Ensure output dimensions match input
        new_shape = img_inpainted.shape[:2]
        if new_shape[0] != im_h or new_shape[1] != im_w:
            img_inpainted = cv2.resize(img_inpainted, (im_w, im_h), interpolation=cv2.INTER_LINEAR)
        
        # Convert to BGR for return
        img_inpainted = cv2.cvtColor(img_inpainted, cv2.COLOR_RGB2BGR)
        
        return img_inpainted

def resize_keep_aspect(img, target_size):
    max_dim = max(img.shape[:2])  
    scale = target_size / max_dim  
    new_size = (round(img.shape[1] * scale), round(img.shape[0] * scale))  
    return cv2.resize(img, new_size, interpolation=cv2.INTER_LINEAR_EXACT)
    


