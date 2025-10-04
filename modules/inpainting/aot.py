import numpy as np
import imkit as imk
from PIL import Image
import onnxruntime as ort
from modules.utils.device import get_providers

from .base import InpaintModel
from .schema import Config

from modules.utils.inpainting import (
    load_jit_model,
)
from modules.utils.download import ModelDownloader, ModelID


class AOT(InpaintModel):
    name = "aot"
    pad_mod = 8
    min_size = 128  
    max_size = 1024

    def init_model(self, device, **kwargs):
        self.backend = kwargs.get("backend")
        if self.backend == "onnx":
            ModelDownloader.get(ModelID.AOT_ONNX)
            onnx_path = ModelDownloader.primary_path(ModelID.AOT_ONNX)
            providers = get_providers(device)
            self.session = ort.InferenceSession(onnx_path, providers=providers)
        else:
            ModelDownloader.get(ModelID.AOT_JIT)
            local_path = ModelDownloader.primary_path(ModelID.AOT_JIT)
            self.model = load_jit_model(local_path, device)

    @staticmethod
    def is_downloaded() -> bool:
        return ModelDownloader.is_downloaded(ModelID.AOT_ONNX)

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
            
        backend = getattr(self, 'backend', 'torch')
        if backend == 'onnx':
            # Pure numpy preprocessing
            img_np = (image.astype(np.float32) / 127.5) - 1.0  # HWC -> later CHW
            mask_np = (mask.astype(np.float32) / 255.0)
            mask_np = (mask_np >= 0.5).astype(np.float32)
            # Apply mask (zero-out masked area like torch variant)
            img_np = img_np * (1 - mask_np[..., None])  # broadcast over channels
            # Convert to NCHW
            img_nchw = np.transpose(img_np, (2, 0, 1))[np.newaxis, ...]
            mask_nchw = mask_np[np.newaxis, np.newaxis, ...]
            ort_inputs = {
                self.session.get_inputs()[0].name: img_nchw,
                self.session.get_inputs()[1].name: mask_nchw,
            }
            out = self.session.run(None, ort_inputs)[0]  # (1,3,H,W) in [-1,1]
            img_inpainted = ((out[0].transpose(1, 2, 0) + 1.0) * 127.5)
            img_inpainted = (np.clip(np.round(img_inpainted), 0, 255)).astype(np.uint8)
        else:
            # Torch preprocessing path
            import torch  # noqa
            img_torch = torch.from_numpy(image).permute(2, 0, 1).unsqueeze_(0).float() / 127.5 - 1.0
            mask_torch = torch.from_numpy(mask).unsqueeze_(0).unsqueeze_(0).float() / 255.0
            mask_torch[mask_torch < 0.5] = 0
            mask_torch[mask_torch >= 0.5] = 1
            img_torch = img_torch.to(self.device)
            mask_torch = mask_torch.to(self.device)
            img_torch = img_torch * (1 - mask_torch)
            with torch.no_grad():
                img_inpainted_torch = self.model(img_torch, mask_torch)
            img_inpainted = ((img_inpainted_torch.cpu().squeeze_(0).permute(1, 2, 0).numpy() + 1.0) * 127.5)
            img_inpainted = (np.clip(np.round(img_inpainted), 0, 255)).astype(np.uint8)
        
        # Ensure output dimensions match input
        new_shape = img_inpainted.shape[:2]
        if new_shape[0] != im_h or new_shape[1] != im_w:
            img_inpainted = imk.resize(img_inpainted, (im_w, im_h), mode=Image.Resampling.BILINEAR)
        
        # Convert to BGR for return
        # img_inpainted is already in RGB format
        
        return img_inpainted

def resize_keep_aspect(img, target_size):
    max_dim = max(img.shape[:2])  
    scale = target_size / max_dim  
    new_size = (round(img.shape[1] * scale), round(img.shape[0] * scale))  
    return imk.resize(img, new_size, mode=Image.Resampling.BILINEAR)
    


