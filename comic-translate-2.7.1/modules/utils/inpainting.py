# https://github.com/Sanster/lama-cleaner/blob/main/lama_cleaner/helper.py

import io
import os
import sys
import logging
import hashlib
import numpy as np
import imkit as imk
from typing import List, Optional
from urllib.parse import urlparse
from PIL import Image, ImageOps, PngImagePlugin

from .download_file import download_url_to_file
from .download import notify_download_event, models_base_dir

logger = logging.getLogger(__name__)


def md5sum(filename):
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(128 * md5.block_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


# def switch_mps_device(model_name, device):
#     import torch
#     if model_name not in MPS_SUPPORT_MODELS and str(device) == "mps":
#         logger.info(f"{model_name} not support mps, switch to cpu")
#         return torch.device("cpu")
#     return device


def get_cache_path_by_url(url):
    parts = urlparse(url)
    model_dir = os.path.join(models_base_dir, "inpainting")
    if not os.path.isdir(model_dir):
        os.makedirs(model_dir)
    filename = os.path.basename(parts.path)
    cached_file = os.path.join(model_dir, filename)
    return cached_file


def download_model(url, model_md5: str = None):
    cached_file = get_cache_path_by_url(url)
    if not os.path.exists(cached_file):
        if sys.stderr:
            sys.stderr.write('Downloading: "{}" to {}\n'.format(url, cached_file))
        try:
            notify_download_event('start', os.path.basename(cached_file))
        except Exception:
            pass
        hash_prefix = None
        download_url_to_file(url, cached_file, hash_prefix, progress=True)
        try:
            notify_download_event('end', os.path.basename(cached_file))
        except Exception:
            pass
        if model_md5:
            _md5 = md5sum(cached_file)
            if model_md5 == _md5:
                logger.info(f"Download model success, md5: {_md5}")
            else:
                try:
                    os.remove(cached_file)
                    logger.error(
                        f"Model md5: {_md5}, expected md5: {model_md5}, wrong model deleted. Please restart comic-translate."
                        f"If you still have errors, please try download model manually first.\n"
                    )
                except:
                    logger.error(
                        f"Model md5: {_md5}, expected md5: {model_md5}, please delete {cached_file} and restart comic-translate."
                    )
                    raise RuntimeError(
                        f"Downloaded model at {cached_file} has md5 {_md5} but expected {model_md5}. File was removed; please re-run or download manually."
                    )

    return cached_file


def ceil_modulo(x, mod):
    if x % mod == 0:
        return x
    return (x // mod + 1) * mod


def handle_error(model_path, model_md5, e):
    _md5 = md5sum(model_path)
    if _md5 != model_md5:
        try:
            os.remove(model_path)
            msg = f"Model md5: {_md5}, expected md5: {model_md5}, wrong model deleted. Please restart comic-translate."
            logger.error(msg)
            raise RuntimeError(msg)
        except Exception:
            msg = f"Model md5: {_md5}, expected md5: {model_md5}, please delete {model_path} and restart comic-translate."
            logger.error(msg)
            raise RuntimeError(msg)
    else:
        msg = f"Failed to load model {model_path}: {e}"
        logger.error(msg)
        raise RuntimeError(msg)


def load_jit_model(model_path: str, device):
    """Load a TorchScript model from an existing local path.
    """
    import torch
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"JIT model file not found: {model_path}")
    logger.info(f"Loading model from: {model_path}")
    model = torch.jit.load(model_path, map_location="cpu").to(device)
    model.eval()
    return model


def load_model(model, url_or_path, device, model_md5):
    import torch
    if os.path.exists(url_or_path):
        model_path = url_or_path
    else:
        model_path = download_model(url_or_path, model_md5)

    try:
        logger.info(f"Loading model from: {model_path}")
        state_dict = torch.load(model_path, map_location="cpu")
        model.load_state_dict(state_dict, strict=True)
        model.to(device)
    except Exception as e:
        handle_error(model_path, model_md5, e)
    model.eval()
    return model


def numpy_to_bytes(image_numpy: np.ndarray, ext: str) -> bytes:
    return imk.encode_image(image_numpy, ext)


def pil_to_bytes(pil_img, ext: str, quality: int = 95, exif_infos={}) -> bytes:
    with io.BytesIO() as output:
        kwargs = {k: v for k, v in exif_infos.items() if v is not None}
        ext_lower = ext.lower()
        if ext_lower == "png" and "parameters" in kwargs:
            pnginfo_data = PngImagePlugin.PngInfo()
            pnginfo_data.add_text("parameters", kwargs["parameters"])
            kwargs["pnginfo"] = pnginfo_data

        if ext_lower in {"jpg", "jpeg"}:
            try:
                pil_img.save(output, format=ext, quality="keep", **kwargs)
            except (ValueError, OSError):
                pil_img.save(output, format=ext, **kwargs)
        else:
            pil_img.save(
                output, 
                format=ext, 
                quality=quality, 
                **kwargs
            )
        image_bytes = output.getvalue()
    return image_bytes


def load_img(img_bytes, gray: bool = False, return_exif: bool = False):
    alpha_channel = None
    image = Image.open(io.BytesIO(img_bytes))

    if return_exif:
        info = image.info or {}
        exif_infos = {"exif": image.getexif(), "parameters": info.get("parameters")}

    try:
        image = ImageOps.exif_transpose(image)
    except:
        pass

    if gray:
        image = image.convert("L")
        np_img = np.array(image)
    else:
        if image.mode == "RGBA":
            np_img = np.array(image)
            alpha_channel = np_img[:, :, -1]
            # Convert RGBA to RGB by removing alpha channel
            np_img = np_img[:, :, :3]
        else:
            image = image.convert("RGB")
            np_img = np.array(image)

    if return_exif:
        return np_img, alpha_channel, exif_infos
    return np_img, alpha_channel


def norm_img(np_img):
    if len(np_img.shape) == 2:
        np_img = np_img[:, :, np.newaxis]
    np_img = np.transpose(np_img, (2, 0, 1))
    np_img = np_img.astype("float32") / 255
    return np_img


def resize_max_size(
    np_img, size_limit: int, interpolation=Image.Resampling.BICUBIC
) -> np.ndarray:
    # Resize image's longer size to size_limit if longer size larger than size_limit
    h, w = np_img.shape[:2]
    if max(h, w) > size_limit:
        ratio = size_limit / max(h, w)
        new_w = int(w * ratio + 0.5)
        new_h = int(h * ratio + 0.5)
        return imk.resize(np_img, (new_w, new_h), mode=interpolation)
    else:
        return np_img


def pad_img_to_modulo(
    img: np.ndarray, mod: int, square: bool = False, min_size: Optional[int] = None
):
    """

    Args:
        img: [H, W, C]
        mod:
        square: 是否为正方形
        min_size:

    Returns:

    """
    if len(img.shape) == 2:
        img = img[:, :, np.newaxis]
    height, width = img.shape[:2]
    out_height = ceil_modulo(height, mod)
    out_width = ceil_modulo(width, mod)

    if min_size is not None:
        assert min_size % mod == 0
        out_width = max(min_size, out_width)
        out_height = max(min_size, out_height)

    if square:
        max_size = max(out_height, out_width)
        out_height = max_size
        out_width = max_size

    return np.pad(
        img,
        ((0, out_height - height), (0, out_width - width), (0, 0)),
        mode="symmetric",
    )


def boxes_from_mask(mask: np.ndarray) -> List[np.ndarray]:
    """
    Args:
        mask: (h, w, 1)  0~255

    Returns:

    """
    height, width = mask.shape[:2]
    _, thresh = imk.threshold(mask, 127, 255, 0)
    contours, _ = imk.find_contours(thresh)

    boxes = []
    for cnt in contours:
        x, y, w, h = imk.bounding_rect(cnt)
        box = np.array([x, y, x + w, y + h]).astype(int)

        box[::2] = np.clip(box[::2], 0, width)
        box[1::2] = np.clip(box[1::2], 0, height)
        boxes.append(box)

    return boxes


def only_keep_largest_contour(mask: np.ndarray) -> List[np.ndarray]:
    """
    Args:
        mask: (h, w)  0~255

    Returns:

    """
    _, thresh = imk.threshold(mask, 127, 255, 0)
    contours, _ = imk.find_contours(thresh)

    max_area = 0
    max_index = -1
    for i, cnt in enumerate(contours):
        area = imk.contour_area(cnt)
        if area > max_area:
            max_area = area
            max_index = i

    if max_index != -1:
        new_mask = np.zeros_like(mask)
        return imk.draw_contours(new_mask, contours, max_index, 255, -1)
    else:
        return mask
