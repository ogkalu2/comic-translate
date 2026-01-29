import numpy as np
import onnxruntime as ort
from ..utils.device import get_providers

from ..utils.inpainting import (
    norm_img,
    load_jit_model,
)
from ..utils.download import ModelDownloader, ModelID
from .base import InpaintModel
from .schema import Config


class LaMa(InpaintModel):
    name = "lama"
    pad_mod = 8

    def init_model(self, device, **kwargs):
        self.backend = kwargs.get("backend")
        if self.backend == "onnx":
            ModelDownloader.get(ModelID.LAMA_ONNX)
            onnx_path = ModelDownloader.primary_path(ModelID.LAMA_ONNX)
            providers = get_providers(device)
            self.session = ort.InferenceSession(onnx_path, providers=providers)
        else:
            ModelDownloader.get(ModelID.LAMA_JIT)
            local_path = ModelDownloader.primary_path(ModelID.LAMA_JIT) 
            self.model = load_jit_model(local_path, device)

    @staticmethod
    def is_downloaded() -> bool:
        return ModelDownloader.is_downloaded(ModelID.LAMA_JIT)

    def forward(self, image, mask, config: Config):
        """Input image and output image have same size
        image: [H, W, C] RGB
        mask: [H, W]
        return: BGR IMAGE
        """
        image_n = norm_img(image)
        mask_n = norm_img(mask)
        # mask_n = (mask_n > 0) * 1
        mask_n = (mask_n > 0).astype('float32')
        backend = getattr(self, 'backend', 'torch')
        if backend == 'onnx':
            image_tensor = image_n[np.newaxis, ...]
            mask_tensor = mask_n[np.newaxis, ...]
            ort_inputs = {self.session.get_inputs()[0].name: image_tensor,
                          self.session.get_inputs()[1].name: mask_tensor}
            inpainted = self.session.run(None, ort_inputs)[0]
            cur_res = inpainted[0].transpose(1, 2, 0)
            cur_res = np.clip(cur_res * 255, 0, 255).astype("uint8")
            # cur_res is already in RGB format
            return cur_res
        else:
            import torch  # noqa
            image_t = torch.from_numpy(image_n).unsqueeze(0).to(self.device)
            mask_t = torch.from_numpy(mask_n).unsqueeze(0).to(self.device)
            inpainted_image = self.model(image_t, mask_t)
            cur_res = inpainted_image[0].permute(1, 2, 0).detach().cpu().numpy()
            cur_res = np.clip(cur_res * 255, 0, 255).astype("uint8")
            # cur_res is already in RGB format
            return cur_res
    
