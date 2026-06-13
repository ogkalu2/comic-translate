from __future__ import annotations

from typing import Any, List, Tuple, Optional
import numpy as np
import onnxruntime as ort

from ..base import OCREngine
from modules.utils.textblock import TextBlock
from modules.utils.textblock import lists_to_blk_list
from modules.utils.language_utils import is_no_space_lang
from modules.utils.device import get_providers
from modules.utils.download import ModelDownloader, ModelID
from modules.utils.onnx import make_session
from .preprocessing import det_preprocess, crop_quad, rec_resize_norm
from .postprocessing import DBPostProcessor, CTCLabelDecoder


LANG_TO_REC_MODEL: dict[str, ModelID] = {
	'ch': ModelID.PPOCR_V6_REC_SMALL,
	'en': ModelID.PPOCR_V5_REC_EN_MOBILE,
	'ko': ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
	'latin': ModelID.PPOCR_V5_REC_LATIN_MOBILE,
	'ru': ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
	'eslav': ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
}


def _make_ppocr_session_options(threads: int = 4):
	opts = ort.SessionOptions()
	opts.log_severity_level = 3
	opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
	opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
	opts.intra_op_num_threads = threads
	opts.inter_op_num_threads = 1
	opts.enable_cpu_mem_arena = True
	opts.enable_mem_pattern = True
	return opts


class PPOCRv5Engine(OCREngine):
	"""Lightweight PP-OCRv5 ONNX pipeline (det + rec).
	"""

	def __init__(self):
		# Sessions are created lazily in initialize(); keep startup light.
		self.det_sess: Optional[Any] = None
		self.rec_sess: Optional[Any] = None
		self.use_text_lines = True
		self.det_model = 'mobile'
		self.device = 'cpu'
		self.det_post = DBPostProcessor(
			thresh=0.3, 
			box_thresh=0.5, 
			unclip_ratio=2.0, 
			use_dilation=False
		)
		self.decoder: Optional[CTCLabelDecoder] = None
		self.rec_img_shape = (3, 48, 320)
		self.rec_batch_size = 8
		self.rec_threads = 4

	def initialize(
		self, 
		lang: str = 'ch', 
		device: str = 'cpu', 
		det_model: str = 'mobile',
		use_text_lines: bool = True
	) -> None:
		self.det_model = det_model
		self.device = device
		self.use_text_lines = use_text_lines
		self.rec_batch_size = 1 if lang == 'latin' else 8
		if lang == 'latin':
			self.rec_threads = 3
		elif lang == 'ko':
			self.rec_threads = 6
		else:
			self.rec_threads = 4
		rec_id = LANG_TO_REC_MODEL.get(lang, ModelID.PPOCR_V6_REC_SMALL)
		ModelDownloader.ensure([rec_id])

		rec_paths = ModelDownloader.file_path_map(rec_id)
		rec_model = [p for n, p in rec_paths.items() if n.endswith('.onnx')][0]
		# dict file name can vary per lang
		dict_file = [p for n, p in rec_paths.items() if n.endswith('.txt')]
		dict_path = dict_file[0] if dict_file else None

		providers = get_providers(device)
		sess_opt = _make_ppocr_session_options(self.rec_threads)
		self.rec_sess = make_session(rec_model, sess_options=sess_opt, providers=providers)

		# Prepare CTC decoder
		if dict_path:
			self.decoder = CTCLabelDecoder(dict_path=dict_path)
		else:
			# try pull embedded vocab from model metadata
			meta = self.rec_sess.get_modelmeta().custom_metadata_map
			if 'character' in meta:
				chars = meta['character'].splitlines()
				self.decoder = CTCLabelDecoder(charset=chars)
			else:
				raise RuntimeError('Recognition dictionary not found')

	def _det_infer(self, img: np.ndarray) -> Tuple[np.ndarray, List[float]]:
		self._ensure_det_session()
		assert self.det_sess is not None
		inp = det_preprocess(img, limit_side_len=960, limit_type='min')
		input_name = self.det_sess.get_inputs()[0].name
		output_name = self.det_sess.get_outputs()[0].name
		pred = self.det_sess.run([output_name], {input_name: inp})[0]
		boxes, scores = self.det_post(pred, (img.shape[0], img.shape[1]))
		return boxes, scores

	def _ensure_det_session(self) -> None:
		if self.det_sess is not None:
			return
		det_id = ModelID.PPOCR_V5_DET_MOBILE if self.det_model == 'mobile' else ModelID.PPOCR_V5_DET_SERVER
		ModelDownloader.ensure([det_id])
		det_path = ModelDownloader.primary_path(det_id)
		providers = get_providers(self.device)
		sess_opt = ort.SessionOptions()
		sess_opt.log_severity_level = 3
		self.det_sess = make_session(det_path, sess_options=sess_opt, providers=providers)

	def _rec_infer(self, crops: List[np.ndarray]) -> Tuple[List[str], List[float]]:
		assert self.rec_sess is not None and self.decoder is not None
		if not crops:
			return [], []
		# Batch by exact padded recognition width to reduce wasted padding.
		target_widths = [_rec_target_width(crop, self.rec_img_shape) for crop in crops]
		texts = [""] * len(crops)
		confs = [0.0] * len(crops)
		buckets: dict[int, list[int]] = {}
		for crop_index, target_w in enumerate(target_widths):
			buckets.setdefault(target_w, []).append(crop_index)
		inp_name = self.rec_sess.get_inputs()[0].name
		out_name = self.rec_sess.get_outputs()[0].name
		for target_w, idxs in buckets.items():
			max_ratio = target_w / float(self.rec_img_shape[1])
			batch = [
				rec_resize_norm(crops[crop_index], self.rec_img_shape, max_ratio)[None, ...]
				for crop_index in idxs
			]
			x = np.concatenate(batch, axis=0).astype(np.float32)
			logits = self.rec_sess.run([out_name], {inp_name: x})[0]  # (N, T, C) or (N, C, T)
			if logits.ndim == 3 and logits.shape[1] > logits.shape[2]:
				# If output is (N, C, T), transpose to (N, T, C)
				logits = np.transpose(logits, (0, 2, 1))
			# Match PaddleOCR behavior: do not drop characters by per-step prob threshold
			dec_texts, dec_confs = self.decoder(logits, prob_threshold=0.0)
			for oi, t, s in zip(idxs, dec_texts, dec_confs):
				texts[oi] = t
				confs[oi] = float(s)
		return texts, confs

	def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
		if self.rec_sess is None or self.decoder is None:
			return blk_list
		if self.use_text_lines and any(getattr(blk, 'lines', None) for blk in blk_list):
			# Batch all blocks' line crops together so width-bucketing happens
			# across the whole page, not once per block (fewer ORT calls).
			block_crops: list[list[np.ndarray]] = []
			all_crops: list[np.ndarray] = []
			for blk in blk_list:
				lines = getattr(blk, 'lines', None) or [blk.xyxy]
				crops = [_crop_line(img, line) for line in lines]
				crops = [crop for crop in crops if crop is not None and crop.size > 0]
				block_crops.append(crops)
				all_crops.extend(crops)

			all_texts, _ = self._rec_infer(all_crops)

			offset = 0
			for blk, crops in zip(blk_list, block_crops):
				texts = all_texts[offset:offset + len(crops)]
				offset += len(crops)
				texts = [text.strip() for text in texts if text and text.strip()]
				blk.texts = texts
				blk.text = ''.join(texts) if is_no_space_lang(getattr(blk, 'source_lang', '')) else ' '.join(texts)
			return blk_list
		boxes, _ = self._det_infer(img)
		if boxes is None or len(boxes) == 0:
			return blk_list
		crops = [crop_quad(img, quad.astype(np.float32)) for quad in boxes]
		texts, _ = self._rec_infer(crops)
		# map quads -> axis-aligned boxes
		bboxes = []
		for quad in boxes:
			xs = quad[:, 0]
			ys = quad[:, 1]
			x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
			bboxes.append((x1, y1, x2, y2))
		return lists_to_blk_list(blk_list, bboxes, texts)


def _crop_line(img: np.ndarray, line) -> np.ndarray | None:
	arr = np.asarray(line)
	if arr.ndim == 2 and arr.shape[0] >= 4 and arr.shape[1] == 2:
		return crop_quad(img, arr.astype(np.float32))
	if arr.size != 4:
		return None
	x1, y1, x2, y2 = [int(round(float(v))) for v in arr.reshape(-1)[:4]]
	x1 = max(0, min(img.shape[1], x1))
	x2 = max(0, min(img.shape[1], x2))
	y1 = max(0, min(img.shape[0], y1))
	y2 = max(0, min(img.shape[0], y2))
	if x2 <= x1 or y2 <= y1:
		return None
	crop = img[y1:y2, x1:x2]
	h, w = crop.shape[:2]
	if h > 0 and w > 0 and h / float(w) >= 1.5:
		crop = np.rot90(crop)
	return crop


def _rec_target_width(img: np.ndarray, img_shape=(3, 48, 320)) -> int:
	_, H, W = img_shape
	h, w = img.shape[:2]
	ratio = w / float(max(1, h))
	return max(W, int(np.ceil(H * ratio)))

