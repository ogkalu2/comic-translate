from __future__ import annotations

import os
import numpy as np
from PIL import Image
import imkit as imk
import onnxruntime as ort
from typing import Optional

from modules.utils.download import ModelDownloader, ModelID
from modules.ocr.base import OCREngine
from modules.utils.device import get_providers
from modules.utils.textblock import adjust_text_line_coordinates
from .pororo.models.brainOCR.brainocr import Reader
from .pororo.models.brainOCR.detection import (
    resize_aspect_ratio,
    normalize_mean_variance,
    get_det_boxes,
    adjust_result_coordinates,
)
from .pororo.models.brainOCR.recognition import CTCLabelConverter, adjust_contrast_grey
from .pororo.models.brainOCR.utils import group_text_box
from .pororo.models.brainOCR.utils import get_image_list
from .pororo.models.brainOCR.utils import reformat_input, get_paragraph, diff


class PororoOCREngineONNX(OCREngine):  # type: ignore
    """Runs Pororo OCR fully with ONNXRuntime."""

    def __init__(self):
        opt_file = ModelDownloader.get_file_path(ModelID.PORORO_ONNX, "ocr-opt.txt")
        self.opt2val = Reader.parse_options(opt_file)
        self.opt2val["vocab"] = Reader.build_vocab(self.opt2val["character"])  # type: ignore
        self.opt2val["vocab_size"] = len(self.opt2val["vocab"])
        self.converter = CTCLabelConverter(self.opt2val["vocab"])  # type: ignore

    def initialize(self, lang: str = 'ko', expansion_percentage: int = 5, device: Optional[str] = None):  # match signature style of torch engine
        """Initialize engine runtime options and create ONNX sessions with device hint.

        device: optional device hint (e.g. 'cpu' or 'cuda') that controls ONNX provider selection.
        """
        ModelDownloader.get(ModelID.PORORO_ONNX)
        self.lang = lang
        self.expansion_percentage = expansion_percentage

        if device:
            self.opt2val["device"] = device

        sess_opts = ort.SessionOptions()
        providers = get_providers(self.opt2val.get("device"))
        self.det_path = ModelDownloader.get_file_path(ModelID.PORORO_ONNX, "craft.onnx")
        self.rec_path = ModelDownloader.get_file_path(ModelID.PORORO_ONNX, "brainocr.onnx")
        self.det_sess = ort.InferenceSession(self.det_path, sess_options=sess_opts, providers=providers)
        self.rec_sess = ort.InferenceSession(self.rec_path, sess_options=sess_opts, providers=providers)
        return None

    # Detection
    def _detect(self, image: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
        opt = self.opt2val
        canvas_size = opt.get("canvas_size", 2560)
        mag_ratio = opt.get("mag_ratio", 1.0)
        text_threshold = opt.get("text_threshold", 0.7)
        link_threshold = opt.get("link_threshold", 0.4)
        low_text = opt.get("low_text", 0.4)
        img_resized, target_ratio, _ = resize_aspect_ratio(
            image,
            canvas_size,
            interpolation=Image.Resampling.BILINEAR,
            mag_ratio=mag_ratio,
        )
        ratio_h = ratio_w = 1 / target_ratio
        x = normalize_mean_variance(img_resized)
        # Convert HWC numpy array -> NCHW float32 for ONNXRuntime (no torch required)
        x_np = np.transpose(x, (2, 0, 1))[np.newaxis, ...].astype(np.float32)
        y, feature = self.det_sess.run(None, {self.det_sess.get_inputs()[0].name: x_np})
        score_text = y[0, :, :, 0]
        score_link = y[0, :, :, 1]
        boxes, polys = get_det_boxes(
            score_text, score_link, text_threshold, link_threshold, low_text
        )
        boxes = adjust_result_coordinates(boxes, ratio_w, ratio_h)
        polys = adjust_result_coordinates(polys, ratio_w, ratio_h)
        for k in range(len(polys)):
            if polys[k] is None:
                polys[k] = boxes[k]
        return boxes, polys

    # Recognition
    def _prepare_recognition_crops(self, img_cv_grey: np.ndarray, horizontal_list, free_list):
        imgH = self.opt2val.get("imgH", 64)
        if (horizontal_list is None) and (free_list is None):
            y_max, x_max = img_cv_grey.shape
            ratio = x_max / y_max
            max_width = int(imgH * ratio)
            crop_img = imk.resize(img_cv_grey, (max_width, imgH), mode=Image.Resampling.LANCZOS)
            image_list = [([[0, 0], [x_max, 0], [x_max, y_max], [0, y_max]], crop_img)]
        else:
            image_list, _ = get_image_list(horizontal_list, free_list, img_cv_grey, model_height=imgH)
        return image_list

    def _recognize(self, image_list):
        opt = self.opt2val
        imgH = opt.get("imgH", 64)
        imgW = opt.get("imgW", 640)
        adjust_contrast = opt.get("adjust_contrast", 0.5)
        batch_size = opt.get("batch_size", 1)

        import math
        # We'll implement a small numpy-based normalize+pad to avoid torch dependency
        def normalize_pad_numpy(pil_image: Image.Image, max_size=(1, imgH, imgW)) -> np.ndarray:
            # pil_image is mode 'L'
            arr = np.asarray(pil_image).astype(np.float32) / 255.0  # [H,W]
            # torchvision ToTensor + (sub 0.5 div 0.5) => map [0,1] -> [-1,1]
            arr = arr * 2.0 - 1.0
            H, W = arr.shape
            C, target_H, target_W = max_size
            assert H == target_H, "unexpected image height"
            out = np.zeros((C, target_H, target_W), dtype=np.float32)
            out[0, :, :W] = arr
            if target_W != W:
                # replicate last column to the right as in original implementation
                last_col = arr[:, W - 1:W]
                out[0, :, W:] = np.repeat(last_col, target_W - W, axis=1)
            return out
        coord = [item[0] for item in image_list]
        img_list = [item[1] for item in image_list]

        def _resize(image):
            pil = Image.fromarray(image, "L")
            w, h = pil.size
            if adjust_contrast > 0:
                arr = np.array(pil.convert("L"))
                arr = adjust_contrast_grey(arr, target=adjust_contrast)
                pil = Image.fromarray(arr, "L")
            ratio = w / float(h)
            if math.ceil(imgH * ratio) > imgW:
                resized_w = imgW
            else:
                resized_w = math.ceil(imgH * ratio)
            return pil.resize((resized_w, imgH), Image.BICUBIC)

        tensors = []
        for im in img_list:
            resized = _resize(im)
            t = normalize_pad_numpy(resized, max_size=(1, imgH, imgW))  # (1,H,Wpad)
            tensors.append(t[np.newaxis, ...])
        # batch_tensor shape: (N,1,H,W)
        batch_tensor = np.concatenate(tensors, axis=0).astype(np.float32)

        results = []
        converter = self.converter
        for start in range(0, batch_tensor.shape[0], batch_size):
            chunk = batch_tensor[start:start+batch_size]
            preds = self.rec_sess.run(None, {self.rec_sess.get_inputs()[0].name: chunk})[0]
            # preds: (N, length, num_classes)
            # compute softmax along classes axis
            exp = np.exp(preds - np.max(preds, axis=2, keepdims=True))
            probs = exp / exp.sum(axis=2, keepdims=True)
            preds_lengths = np.full((probs.shape[0],), probs.shape[1], dtype=np.int32)
            max_indices = probs.argmax(axis=2)  # (N, length)
            flat = max_indices.reshape(-1)
            strings = converter.decode_greedy(flat, preds_lengths)
            max_prob = probs.max(axis=2)
            cumprods = np.cumprod(max_prob, axis=1)
            confs = cumprods[:, -1]
            for s, conf in zip(strings, confs.tolist()):
                results.append([s, float(conf)])

        out = []
        for coord_box, (text, score) in zip(coord, results):
            out.append((coord_box, text, score))
        return out

    # Public API
    def read(self, image):  # type: ignore
        opt = self.opt2val
        opt.setdefault("batch_size", 1)
        opt.setdefault("skip_details", False)
        opt.setdefault("paragraph", False)
        opt.setdefault("min_size", 20)
        # thresholds (defaults match Reader.__call__)
        slope_ths = opt.setdefault("slope_ths", 0.1)
        ycenter_ths = opt.setdefault("ycenter_ths", 0.5)
        height_ths = opt.setdefault("height_ths", 0.5)
        width_ths = opt.setdefault("width_ths", 0.5)
        add_margin = opt.setdefault("add_margin", 0.1)

        _, img_cv_grey = reformat_input(image)
        boxes, polys = self._detect(image if isinstance(image, np.ndarray) else img_cv_grey)

        # Reconstruct text_box list (flattened polys) as expected by group_text_box
        text_box = []
        for p in polys:
            flat = np.array(p).astype(np.int32).reshape(-1)
            if flat.size == 8:
                text_box.append(flat)

        # Group into horizontal_list / free_list like original pipeline
        horizontal_list, free_list = group_text_box(
            text_box,
            slope_ths,
            ycenter_ths,
            height_ths,
            width_ths,
            add_margin,
        )

        min_size = opt["min_size"]
        if min_size:
            horizontal_list = [i for i in horizontal_list if max(i[1]-i[0], i[3]-i[2]) > min_size]
            free_list = [
                i for i in free_list
                if max(diff([c[0] for c in i]), diff([c[1] for c in i])) > min_size
            ]

        # Fallback: if no boxes detected / retained, treat whole image
        if not horizontal_list and not free_list:
            image_list = self._prepare_recognition_crops(img_cv_grey, None, None)
        else:
            image_list = self._prepare_recognition_crops(img_cv_grey, horizontal_list, free_list)

        # Guard against empty image list (shouldn't happen after fallback)
        if not image_list:
            return [] if opt["skip_details"] else []
        result = self._recognize(image_list)
        if opt["paragraph"]:
            result = get_paragraph(result, mode="ltr")  # type: ignore
        if opt["skip_details"]:
            return [item[1] for item in result]  # type: ignore
        return result  # type: ignore

    # OCREngine interface
    def process_image(self, img: np.ndarray, blk_list: list):  # list[TextBlock] but no direct import to avoid cycle
        # ensure defaults present
        self.opt2val.setdefault("batch_size", 1)
        self.opt2val.setdefault("skip_details", False)
        self.opt2val.setdefault("paragraph", False)
        self.opt2val.setdefault("min_size", 20)

        for blk in blk_list:
            if getattr(blk, 'bubble_xyxy', None) is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy,
                    getattr(self, 'expansion_percentage', 5),
                    getattr(self, 'expansion_percentage', 5),
                    img,
                )
            if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                cropped = img[y1:y2, x1:x2]
                # run full pipeline on cropped region
                # detection+recognition expects color or grey; keep as is
                res = self.read(cropped)
                # res is list of (box,text,score); join texts
                if isinstance(res, list) and len(res) > 0 and isinstance(res[0], tuple):
                    blk.text = ' '.join([r[1] for r in res])
                elif isinstance(res, list):
                    blk.text = ' '.join(res)
                else:
                    blk.text = ''
            else:
                blk.text = ''
        return blk_list
