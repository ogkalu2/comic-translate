import os
import cv2
import onnxruntime as ort
import numpy as np

from ..utils.inpainting import (
    load_jit_model,
    boxes_from_mask,
    resize_max_size,
    norm_img,
)
from modules.utils.download import ModelDownloader, ModelID
from modules.utils.device import get_providers
from .base import InpaintModel
from .schema import Config


class MIGAN(InpaintModel):
    name = "migan"
    min_size = 512
    pad_mod = 512
    pad_to_square = True
    is_erase_model = True
    use_pipeline_for_onnx = False

    def init_model(self, device, **kwargs):
        self.backend = kwargs.get("backend")
        if self.backend == "onnx":
            model_id = ModelID.MIGAN_PIPELINE_ONNX if self.use_pipeline_for_onnx else ModelID.MIGAN_ONNX
            ModelDownloader.get(model_id)
            onnx_path = ModelDownloader.primary_path(model_id)
            providers = get_providers(device)
            self.session = ort.InferenceSession(onnx_path, providers=providers)
        else:
            ModelDownloader.get(ModelID.MIGAN_JIT)
            local_path = ModelDownloader.primary_path(ModelID.MIGAN_JIT)
            self.model = load_jit_model(local_path, device)

    @staticmethod
    def is_downloaded() -> bool:
        return ModelDownloader.is_downloaded(ModelID.MIGAN_JIT)

    def __call__(self, image, mask, config: Config):
        """
        images: [H, W, C] RGB, not normalized
        masks: [H, W]
        return: BGR IMAGE
        """
        import torch  # noqa
        with torch.no_grad():
            if image.shape[0] == 512 and image.shape[1] == 512:
                return self._pad_forward(image, mask, config)

            boxes = boxes_from_mask(mask)
            crop_result = []
            config.hd_strategy_crop_margin = 128
            for box in boxes:
                crop_image, crop_mask, crop_box = self._crop_box(image, mask, box, config)
                origin_size = crop_image.shape[:2]
                resize_image = resize_max_size(crop_image, size_limit=512)
                resize_mask = resize_max_size(crop_mask, size_limit=512)
                inpaint_result = self._pad_forward(resize_image, resize_mask, config)

                # only paste masked area result
                inpaint_result = cv2.resize(
                    inpaint_result,
                    (origin_size[1], origin_size[0]),
                    interpolation=cv2.INTER_CUBIC,
                )

                original_pixel_indices = crop_mask < 127
                inpaint_result[original_pixel_indices] = crop_image[:, :, ::-1][
                    original_pixel_indices
                ]

                crop_result.append((inpaint_result, crop_box))

            inpaint_result = image[:, :, ::-1].copy()
            for crop_image, crop_box in crop_result:
                x1, y1, x2, y2 = crop_box
                inpaint_result[y1:y2, x1:x2, :] = crop_image

            return inpaint_result

    def forward(self, image, mask, config: Config):
        """Input images and output images have same size
        images: [H, W, C] RGB
        masks: [H, W] mask area == 255
        return: BGR IMAGE
        """

        backend = getattr(self, 'backend', 'torch')
        if backend == 'onnx' and getattr(self, 'use_pipeline', False):
            print('Pipeline onnx')
            # Pipeline model expects uint8 RGB image and uint8 grayscale mask
            # Convert mask to binary (255 for known, 0 for masked)
            binary_mask = np.where(mask > 120, 0, 255).astype(np.uint8)  # Invert: 0=masked, 255=known
            
            # Inspect expected input shapes (may contain symbolic dims)
            inps = self.session.get_inputs()
            img_nchw = np.transpose(image, (2, 0, 1))[np.newaxis, ...]  # (1, 3, H, W) uint8
            # Ensure mask is 2D before adding batch/channel (pad utility may have added a trailing channel)
            if binary_mask.ndim == 3 and binary_mask.shape[2] == 1:
                binary_mask_2d = binary_mask[:, :, 0]
            else:
                binary_mask_2d = binary_mask
            mask_nchw = binary_mask_2d[np.newaxis, np.newaxis, ...]  # (1, 1, H, W)

            ort_inputs = {
                inps[0].name: img_nchw,
                inps[1].name: mask_nchw
            }
            # Optional quick shape debug (can be silenced later)
            if os.environ.get('MIGAN_DEBUG_SHAPES') == '1':
                print(f"[MIGAN ONNX] Feeding image shape {img_nchw.shape} mask shape {mask_nchw.shape} orig mask shape {mask.shape}")
            out = self.session.run(None, ort_inputs)[0]  # Should be (1, 3, H, W) uint8 RGB
            out_img = np.transpose(out[0], (1, 2, 0))  # Convert to (H, W, 3)
            cur_res = cv2.cvtColor(out_img, cv2.COLOR_RGB2BGR)
            return cur_res
        elif backend == 'onnx':
            # Original exported model path (preprocessing required)
            img_norm = norm_img(image)  # C,H,W float32 [0,1]
            img_norm = img_norm * 2 - 1
            m = (mask > 120).astype(np.uint8) * 255
            m_norm = norm_img(m)
            img_np = img_norm[np.newaxis, ...]  # (1,C,H,W)
            mask_np = m_norm[np.newaxis, ...]
            erased = img_np * (1 - mask_np)
            concat = np.concatenate([0.5 - mask_np, erased], axis=1)  # (1,4,H,W)
            ort_inputs = {self.session.get_inputs()[0].name: concat}
            out = self.session.run(None, ort_inputs)[0]  # (1,3,H,W) in [-1,1]
            out_img = np.clip((out.transpose(0, 2, 3, 1) * 127.5 + 127.5).round(), 0, 255).astype(np.uint8)[0]
            cur_res = cv2.cvtColor(out_img, cv2.COLOR_RGB2BGR)
            return cur_res
        else:
            # Torch path
            import torch  # noqa
            img_norm = norm_img(image)  # C,H,W float32 [0,1]
            img_norm = img_norm * 2 - 1
            m = (mask > 120).astype(np.uint8) * 255
            m_norm = norm_img(m)
            image_t = torch.from_numpy(img_norm).unsqueeze(0).to(self.device)
            mask_t = torch.from_numpy(m_norm).unsqueeze(0).to(self.device)
            erased_img = image_t * (1 - mask_t)
            input_image = torch.cat([0.5 - mask_t, erased_img], dim=1)
            output = self.model(input_image)
            output = (
                (output.permute(0, 2, 3, 1) * 127.5 + 127.5)
                .round()
                .clamp(0, 255)
                .to(torch.uint8)
            )
            output = output[0].cpu().numpy()
            cur_res = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
            return cur_res
