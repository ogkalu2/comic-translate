from __future__ import annotations

from typing import Any, List, Tuple, Optional
import numpy as np
import onnxruntime as ort

from modules.ocr.base import OCREngine
from modules.utils.textblock import TextBlock
from modules.utils.textblock import lists_to_blk_list
from modules.utils.language_utils import is_no_space_lang, normalize_script
from modules.utils.device import get_providers
from modules.utils.download import ModelDownloader, ModelID
from modules.utils.onnx import make_session
from .preprocessing import det_preprocess, crop_quad, rec_resize_norm
from .postprocessing import DBPostProcessor, CTCLabelDecoder


LANG_TO_REC_MODEL: dict[str, ModelID] = {
	'ch': ModelID.PPOCR_V6_REC_SMALL,
	'ja': ModelID.PPOCR_V6_REC_SMALL,
	'en': ModelID.PPOCR_V5_REC_EN_MOBILE,
	'ko': ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
	'latin': ModelID.PPOCR_V5_REC_LATIN_MOBILE,
	'ru': ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
	'eslav': ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
}

JA_SMALL_LINE_THICKNESS_RATIO = 0.7
JA_SMALL_LINE_AREA_RATIO = 0.75


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
			block_lines: list[list[Any]] = []
			all_crops: list[np.ndarray] = []
			for blk in blk_list:
				lines = getattr(blk, 'lines', None) or [blk.xyxy]
				crops = [_crop_line(img, line) for line in lines]
				valid_lines: list[Any] = []
				valid_crops: list[np.ndarray] = []
				for line, crop in zip(lines, crops):
					if crop is None or crop.size == 0:
						continue
					valid_lines.append(line)
					valid_crops.append(crop)
				crops = valid_crops
				block_crops.append(crops)
				block_lines.append(valid_lines)
				all_crops.extend(crops)

			all_texts, _ = self._rec_infer(all_crops)

			offset = 0
			for blk, lines, crops in zip(blk_list, block_lines, block_crops):
				texts = all_texts[offset:offset + len(crops)]
				offset += len(crops)
				texts = [text.strip() if text else "" for text in texts]
				blk.texts, blk.skipped_small_texts = _split_japanese_small_line_texts(blk, lines, texts)
				blk.text = ''.join(blk.texts) if is_no_space_lang(getattr(blk, 'source_lang', '')) else ' '.join(blk.texts)
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


def _split_japanese_small_line_texts(
	blk: TextBlock,
	lines: List[Any],
	texts: List[str],
) -> tuple[list[str], list[dict[str, Any]]]:
	cleaned = [text.strip() for text in texts if text and text.strip()]
	if not _should_filter_japanese_small_lines(blk, texts):
		return cleaned, []
	if len(lines) < 2 or len(lines) != len(texts):
		return cleaned, []

	line_infos: list[dict[str, Any]] = []
	for index, (line, text) in enumerate(zip(lines, texts)):
		box = _line_axis_box(line)
		if box is None:
			continue
		x1, y1, x2, y2 = box
		width = max(1.0, float(x2 - x1))
		height = max(1.0, float(y2 - y1))
		line_infos.append(
			{
				"line_index": index,
				"line": line,
				"text": (text or "").strip(),
				"width": width,
				"height": height,
				"area": width * height,
			}
		)

	if len(line_infos) < 2:
		return cleaned, []

	direction = (getattr(blk, "direction", "") or "").strip().lower()
	use_width_as_thickness = direction == "vertical"
	median_thickness = float(
		np.median([info["width"] if use_width_as_thickness else info["height"] for info in line_infos])
	)
	median_area = float(np.median([info["area"] for info in line_infos]))
	kept_infos: list[dict[str, Any]] = []
	skipped_infos: list[dict[str, Any]] = []

	for info in line_infos:
		thickness = info["width"] if use_width_as_thickness else info["height"]
		thickness_ratio = thickness / max(1.0, median_thickness)
		area_ratio = info["area"] / max(1.0, median_area)
		info["thickness_ratio_to_block_median"] = thickness_ratio
		info["height_ratio_to_block_median"] = info["height"] / max(1.0, float(np.median([entry["height"] for entry in line_infos])))
		info["width_ratio_to_block_median"] = info["width"] / max(1.0, float(np.median([entry["width"] for entry in line_infos])))
		info["area_ratio_to_block_median"] = area_ratio
		is_small = (
			thickness_ratio < JA_SMALL_LINE_THICKNESS_RATIO
			and area_ratio < JA_SMALL_LINE_AREA_RATIO
		)
		if is_small:
			skipped_infos.append(info)
		else:
			kept_infos.append(info)

	if not kept_infos:
		return cleaned, []

	kept_texts = [info["text"] for info in kept_infos if info["text"]]
	skipped_texts = [info for info in skipped_infos if info["text"]]
	return kept_texts, skipped_texts


def _line_axis_box(line: Any) -> tuple[int, int, int, int] | None:
	arr = np.asarray(line)
	if arr.ndim == 2 and arr.shape[0] >= 4 and arr.shape[1] == 2:
		xs = arr[:, 0]
		ys = arr[:, 1]
		return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
	if arr.size != 4:
		return None
	x1, y1, x2, y2 = [int(round(float(v))) for v in arr.reshape(-1)[:4]]
	return x1, y1, x2, y2


def _is_japanese_source_lang(lang_code: str | None) -> bool:
	return (lang_code or "").strip().lower().startswith("ja")


def _should_filter_japanese_small_lines(blk: TextBlock, texts: List[str]) -> bool:
	if _is_japanese_source_lang(getattr(blk, "source_lang", "")):
		return True
	if normalize_script(getattr(blk, "script", "")) == "Japanese":
		return True
	return False

