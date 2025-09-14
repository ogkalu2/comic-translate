from __future__ import annotations

from typing import List, Tuple, Optional
import numpy as np
import imkit as imk
import pyclipper
from shapely.geometry import Polygon


class DBPostProcessor:
	"""Post-process binary maps from DB detector into polygons.
	"""

	def __init__(self,
				 thresh: float = 0.3,
				 box_thresh: float = 0.5,
				 max_candidates: int = 1000,
				 unclip_ratio: float = 1.6,
				 score_mode: str = "fast",
				 use_dilation: bool = True):
		self.thresh = thresh
		self.box_thresh = box_thresh
		self.max_candidates = max_candidates
		self.unclip_ratio = unclip_ratio
		self.score_mode = score_mode
		self.dilation_kernel = np.array([[1, 1], [1, 1]], dtype=np.uint8) if use_dilation else None

	def __call__(self, pred: np.ndarray, ori_shape: Tuple[int, int]) -> Tuple[np.ndarray, List[float]]:
		H, W = ori_shape
		prob = pred[:, 0, :, :]  # N,1,h,w -> N,h,w
		seg = prob > self.thresh
		mask = seg[0]
		if self.dilation_kernel is not None:
			# imk.dilate expects a kernel; return uint8 0/255, convert back to 0/1
			dil = imk.dilate((mask.astype(np.uint8) * 255), self.dilation_kernel, iterations=1)
			mask = (dil > 0).astype(np.uint8)
		boxes, scores = self._boxes_from_bitmap(prob[0], mask, W, H)
		return self._filter(boxes, scores, H, W)

	def _boxes_from_bitmap(self, prob: np.ndarray, bitmap: np.ndarray, dest_w: int, dest_h: int) -> Tuple[np.ndarray, List[float]]:
		contours, _ = imk.find_contours((bitmap.astype(np.uint8) * 255), threshold=127)
		num = min(len(contours), self.max_candidates)
		boxes, scores = [], []
		h, w = bitmap.shape
		for i in range(num):
			c = contours[i]
			box, sside = self._min_box(c)
			if sside < 3:
				continue
			score = self._score_fast(prob, box.reshape(-1, 2)) if self.score_mode == 'fast' else self._score_slow(prob, c)
			if score < self.box_thresh:
				continue
			expanded = self._unclip(box)
			box, sside = self._min_box(expanded)
			if sside < 5:
				continue
			box[:, 0] = np.clip(np.round(box[:, 0] / w * dest_w), 0, dest_w)
			box[:, 1] = np.clip(np.round(box[:, 1] / h * dest_h), 0, dest_h)
			boxes.append(box.astype(np.int32))
			scores.append(float(score))
		return np.array(boxes, dtype=np.int32), scores

	@staticmethod
	def _min_box(contour: np.ndarray) -> Tuple[np.ndarray, float]:
		# imk expects raw points and returns rect; get box corners
		rect = imk.min_area_rect(contour)
		pts = imk.box_points(rect)
		pts = sorted(list(pts), key=lambda p: p[0])
		left = np.array(pts[:2])
		right = np.array(pts[2:])
		tl, bl = left[np.argsort(left[:, 1])]
		tr, br = right[np.argsort(right[:, 1])]
		box = np.array([tl, tr, br, bl], dtype=np.float32)
		return box, min(rect[1])

	@staticmethod
	def _score_fast(bitmap: np.ndarray, box: np.ndarray) -> float:
		h, w = bitmap.shape
		xs = box[:, 0]
		ys = box[:, 1]
		xmin = int(np.clip(np.floor(xs.min()), 0, w - 1))
		xmax = int(np.clip(np.ceil(xs.max()), 0, w - 1))
		ymin = int(np.clip(np.floor(ys.min()), 0, h - 1))
		ymax = int(np.clip(np.ceil(ys.max()), 0, h - 1))
		mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
		pts = box.copy()
		pts[:, 0] -= xmin
		pts[:, 1] -= ymin
		mask = imk.fill_poly(mask, pts.reshape(-1, 1, 2).astype(np.int32), color=1)
		region = bitmap[ymin:ymax + 1, xmin:xmax + 1]
		return imk.mean(region, mask)[0]

	@staticmethod
	def _score_slow(bitmap: np.ndarray, contour: np.ndarray) -> float:
		h, w = bitmap.shape
		pts = contour.reshape(-1, 2).astype(np.float32)
		xmin, xmax = int(np.clip(pts[:, 0].min(), 0, w - 1)), int(np.clip(pts[:, 0].max(), 0, w - 1))
		ymin, ymax = int(np.clip(pts[:, 1].min(), 0, h - 1)), int(np.clip(pts[:, 1].max(), 0, h - 1))
		mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
		pts[:, 0] -= xmin
		pts[:, 1] -= ymin
		mask = imk.fill_poly(mask, pts.reshape(-1, 1, 2).astype(np.int32), color=1)
		region = bitmap[ymin:ymax + 1, xmin:xmax + 1]
		return imk.mean(region, mask)[0]

	def _unclip(self, box: np.ndarray) -> np.ndarray:
		poly = Polygon(box)
		distance = poly.area * self.unclip_ratio / (poly.length + 1e-6)
		offset = pyclipper.PyclipperOffset()
		offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
		out = offset.Execute(distance)
		if not out:
			return box.reshape((-1, 1, 2))
		return np.array(out[0]).reshape((-1, 1, 2)).astype(np.float32)

	@staticmethod
	def _order_clockwise(pts: np.ndarray) -> np.ndarray:
		xs = pts[np.argsort(pts[:, 0])]
		left = xs[:2]
		right = xs[2:]
		tl, bl = left[np.argsort(left[:, 1])]
		tr, br = right[np.argsort(right[:, 1])]
		return np.array([tl, tr, br, bl], dtype=np.float32)

	def _filter(self, boxes: np.ndarray, scores: List[float], h: int, w: int) -> Tuple[np.ndarray, List[float]]:
		out_boxes = []
		out_scores = []
		for b, s in zip(boxes, scores):
			b = self._order_clockwise(b)
			b[:, 0] = np.clip(b[:, 0], 0, w - 1)
			b[:, 1] = np.clip(b[:, 1], 0, h - 1)
			rw = int(np.linalg.norm(b[0] - b[1]))
			rh = int(np.linalg.norm(b[0] - b[3]))
			if rw <= 3 or rh <= 3:
				continue
			out_boxes.append(b.astype(np.int32))
			out_scores.append(float(s))
		return (np.array(out_boxes, dtype=np.int32) if out_boxes else np.zeros((0, 4, 2), dtype=np.int32)), out_scores


class CTCLabelDecoder:
	"""Simple CTC greedy decoder for Paddle-style dictionaries."""

	def __init__(self, charset: Optional[List[str]] = None, dict_path: Optional[str] = None):
		if charset is None and dict_path:
			with open(dict_path, 'r', encoding='utf-8') as f:
				charset = [line.strip('\n') for line in f]
		if charset is None:
			raise ValueError("CTCLabelDecoder requires charset or dict_path")
		# Store raw dict characters (without blank/space); vocab is derived at runtime
		self.dict_chars: List[str] = list(charset)

	def __call__(self, logits: np.ndarray, prob_threshold: float = 0.3) -> Tuple[List[str], List[float]]:
		"""Greedy decode.
		logits: (N, T, C) or (T, C) ndarray with softmax probabilities or raw logits.
		Returns: (texts, avg_confidence)
		"""
		if logits.ndim == 2:
			logits = logits[None, ...]
		num_classes = logits.shape[-1]
		dict_len = len(self.dict_chars)
		# Build vocab to align with model classes
		if num_classes == dict_len + 2:
			vocab = [''] + self.dict_chars + [' ']
		elif num_classes == dict_len + 1:
			vocab = [''] + self.dict_chars
		elif num_classes == dict_len:
			pad = np.zeros((*logits.shape[:-1], 1), dtype=logits.dtype)
			logits = np.concatenate([pad, logits], axis=-1)
			num_classes = logits.shape[-1]
			vocab = [''] + self.dict_chars
		else:
			if num_classes >= dict_len + 2:
				extra = num_classes - (dict_len + 2)
				vocab = [''] + self.dict_chars + [' '] + ([''] * extra)
			elif num_classes == dict_len + 1:
				vocab = [''] + self.dict_chars
			else:
				keep = max(0, num_classes - 1)
				vocab = [''] + self.dict_chars[:keep]
		# Softmax if needed
		if np.max(logits) > 1.0 or np.min(logits) < 0.0:
			e = np.exp(logits - logits.max(axis=-1, keepdims=True))
			probs = e / e.sum(axis=-1, keepdims=True)
		else:
			probs = logits
		texts: List[str] = []
		confs: List[float] = []
		blank = 0
		for n in range(probs.shape[0]):
			seq = probs[n]  # (T,C)
			idxs = seq.argmax(axis=-1)
			last = -1
			decoded_chars: List[str] = []
			scores: List[float] = []
			for t, i in enumerate(idxs):
				if i != blank and i != last:
					p = float(seq[t, int(i)])
					if p < prob_threshold:
						last = int(i)
						continue
					if int(i) < 0 or int(i) >= len(vocab):
						last = int(i)
						continue
					ch = vocab[int(i)]
					if not ch or any(ord(c) < 32 for c in ch):
						last = int(i)
						continue
					decoded_chars.append(ch)
					scores.append(p)
				last = int(i)
			text = ''.join(decoded_chars)
			conf = float(np.mean(scores)) if scores else 0.0
			texts.append(text)
			confs.append(conf)
		return texts, confs

