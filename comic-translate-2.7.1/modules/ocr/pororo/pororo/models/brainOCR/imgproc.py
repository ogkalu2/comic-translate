"""
This is adapted from https://github.com/clovaai/CRAFT-pytorch/blob/master/imgproc.py
Copyright (c) 2019-present NAVER Corp.
MIT License
"""

import numpy as np
import imkit as imk


def load_image(img_file):
    img = imk.read_image(img_file)

    if img is None:
        raise IOError(f"Could not read image file: {img_file}")

    if img.shape[0] == 2: 
        img = img[0]
    if len(img.shape) == 2: # Convert grayscale to RGB
        img = np.stack([img, img, img], axis=2)
    if img.shape[2] == 4: # cv2.imread strips the alpha channel by default
        img = img[:, :, :3]
    
    return img

def normalize_mean_variance(
    in_img,
    mean=(0.485, 0.456, 0.406),
    variance=(0.229, 0.224, 0.225),
):
    # should be RGB order
    img = in_img.copy().astype(np.float32)

    img -= np.array([mean[0] * 255.0, mean[1] * 255.0, mean[2] * 255.0],
                    dtype=np.float32)
    img /= np.array(
        [variance[0] * 255.0, variance[1] * 255.0, variance[2] * 255.0],
        dtype=np.float32,
    )
    return img


def denormalize_mean_variance(
        in_img,
        mean=(0.485, 0.456, 0.406),
        variance=(0.229, 0.224, 0.225),
):
    # should be RGB order
    img = in_img.copy()
    img *= variance
    img += mean
    img *= 255.0
    img = np.clip(img, 0, 255).astype(np.uint8)
    return img


def resize_aspect_ratio(
    img: np.ndarray,
    square_size: int,
    interpolation: int,
    mag_ratio: float = 1.0,
):
    height, width, channel = img.shape

    # magnify image size
    target_size = mag_ratio * max(height, width)

    # set original image size
    if target_size > square_size:
        target_size = square_size

    ratio = target_size / max(height, width)

    target_h, target_w = int(height * ratio), int(width * ratio)
    proc = imk.resize(img, (target_w, target_h), mode=interpolation)

    # make canvas and paste image
    target_h32, target_w32 = target_h, target_w
    if target_h % 32 != 0:
        target_h32 = target_h + (32 - target_h % 32)
    if target_w % 32 != 0:
        target_w32 = target_w + (32 - target_w % 32)
    resized = np.zeros((target_h32, target_w32, channel), dtype=np.float32)
    resized[0:target_h, 0:target_w, :] = proc
    target_h, target_w = target_h32, target_w32

    size_heatmap = (int(target_w / 2), int(target_h / 2))

    return resized, ratio, size_heatmap
