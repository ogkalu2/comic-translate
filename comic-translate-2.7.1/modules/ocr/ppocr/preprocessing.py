from __future__ import annotations

import numpy as np
import imkit as imk


def resize_keep_stride(img: np.ndarray, limit_side_len: int = 960, limit_type: str = "min") -> np.ndarray:
	"""Resize image so that min or max side meets threshold, snapping to multiple of 32.

	This matches the common PP-OCR DB-det precondition: H,W % 32 == 0.
	"""
	h, w = img.shape[:2]
	if limit_type == "max":
		if max(h, w) > limit_side_len:
			ratio = float(limit_side_len) / (h if h > w else w)
		else:
			ratio = 1.0
	else:
		if min(h, w) < limit_side_len:
			ratio = float(limit_side_len) / (h if h < w else w)
		else:
			ratio = 1.0

	nh = int(round((h * ratio) / 32) * 32)
	nw = int(round((w * ratio) / 32) * 32)
	nh = max(nh, 32)
	nw = max(nw, 32)
	if nh == h and nw == w:
		return img
	# imk.resize expects (w, h)
	return imk.resize(img, (nw, nh))


def det_preprocess(img: np.ndarray, mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5),
				   limit_side_len: int = 960, limit_type: str = "min") -> np.ndarray:
	"""Preprocess for DB detector: resize, normalize, CHW, NCHW float32."""
	resized = resize_keep_stride(img, limit_side_len, limit_type)
	x = resized.astype(np.float32) / 255.0
	x = (x - np.array(mean, dtype=np.float32)) / np.array(std, dtype=np.float32)
	x = x.transpose(2, 0, 1)
	x = np.expand_dims(x, 0).astype(np.float32)
	return x


def rec_resize_norm(img: np.ndarray, img_shape=(3, 48, 320), max_wh_ratio: float | None = None) -> np.ndarray:
	"""Resize and normalize for PP-OCR recognition (CTC):
	- target H=img_shape[1], W computed from ratio, padded to target width.
	- normalize to [-1,1].
	Returns CHW float32 padded array.
	"""
	c, H, W = img_shape
	assert img.shape[2] == c, "Expect BGR with 3 channels"

	if max_wh_ratio is None:
		max_wh_ratio = W / float(H)

	h, w = img.shape[:2]
	ratio = w / float(h)
	target_w = int(H * max_wh_ratio)
	resized_w = min(target_w, int(np.ceil(H * ratio)))

	resized = imk.resize(img, (resized_w, H))
	x = resized.astype(np.float32) / 255.0
	x = x.transpose(2, 0, 1)
	x = (x - 0.5) / 0.5

	out = np.zeros((c, H, target_w), dtype=np.float32)
	out[:, :, :resized_w] = x
	return out


def crop_quad(img: np.ndarray, quad: np.ndarray) -> np.ndarray:
	"""Perspective-crop a quadrilateral region. Auto-rotate tall crops."""
	pts = quad.astype(np.float32)
	w = int(max(np.linalg.norm(pts[0]-pts[1]), np.linalg.norm(pts[2]-pts[3])))
	h = int(max(np.linalg.norm(pts[0]-pts[3]), np.linalg.norm(pts[1]-pts[2])))
	dst = np.array([[0,0],[w,0],[w,h],[0,h]], dtype=np.float32)
	# imkit expects 4x2 arrays (x,y)
	M = imk.get_perspective_transform(pts, dst)
	crop = imk.warp_perspective(img, M, (w, h))
	if h > 0 and w > 0 and (h / float(w)) >= 1.5:
		crop = np.rot90(crop)
	return crop

