from __future__ import annotations

from typing import List, Tuple, Optional
import numpy as np
import onnxruntime as ort
import re
from ..base import OCREngine
from modules.utils.textblock import TextBlock
from modules.utils.textblock import lists_to_blk_list
from modules.utils.device import get_providers
from modules.utils.download import ModelDownloader, ModelID
from .preprocessing import det_preprocess, crop_quad, rec_resize_norm
from .postprocessing import DBPostProcessor, CTCLabelDecoder
import base64
import json
import requests
from io import BytesIO
from PIL import Image, ImageOps
import base64
import json
from io import BytesIO
from pathlib import Path

class VLLMOcrClient:
    def __init__(self, url: str, model: str = "tencent/HunyuanOCR", timeout: int = 300):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
    def _img_to_data_url(self, pil_img: Image.Image, fmt: str = "PNG") -> str:
        buf = BytesIO()
        pil_img.save(buf, format=fmt)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/{fmt.lower()};base64,{b64}"

    def _extract_json_or_text(self, content: str) -> str:
        if content is None:
            return ""
        s = content.strip()
        if not s:
            return ""

        # убрать ```json ... ``` / ``` ... ```
        if s.startswith("```"):
            s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE | re.DOTALL).strip()

        # если уже валидный JSON
        if s.startswith("{") and s.endswith("}"):
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    v = obj.get("text", "")
                    return v.strip() if isinstance(v, str) else str(v)
            except json.JSONDecodeError:
                pass

        # попытка вытащить первый JSON-объект внутри текста
        m = re.search(r"\{.*\}", s, flags=re.DOTALL)
        if m:
            cand = m.group(0)
            try:
                obj = json.loads(cand)
                if isinstance(obj, dict):
                    v = obj.get("text", "")
                    return v.strip() if isinstance(v, str) else str(v)
            except json.JSONDecodeError:
                pass

        # fallback: считаем что модель вернула просто текст OCR
        return s

    def _prep(self, img: Image.Image, pad: int = 16, min_h: int = 96) -> Image.Image:
        img = img.convert("RGB")
        # img = ImageOps.expand(img, border=pad, fill=(255, 255, 255))
        # w, h = img.size
        # # if h < min_h:
        # s = float(h) / float(min_h)
        # img = img.resize((int(w // s), int(h // s)), Image.Resampling.LANCZOS)
        return img
    
    def ocr_one(self, pil_img: Image.Image) -> str:
        pil_img = self._prep(pil_img, pad=16, min_h=24)  # если у тебя есть _prep

        data_url = self._img_to_data_url(pil_img, "PNG")
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": ""},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": "Extract text."},
                ]},
            ],
            "top_k": 1,
            "max_tokens" : 64,
            "repetition_penalty": 1.0,
        }
        r = requests.post(f"{self.url}/chat/completions", json=payload, timeout=self.timeout)
        if r.status_code != 200:
           raise RuntimeError(f"vLLM HTTP {r.status_code}: {r.text}")
        
        content = r.json()["choices"][0]["message"]["content"]
        return (content or "").strip()		

LANG_TO_REC_MODEL: dict[str, ModelID] = {
    'ch': ModelID.PPOCR_V5_REC_MOBILE,
    'en': ModelID.PPOCR_V5_REC_EN_MOBILE,
    'ko': ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
    'latin': ModelID.PPOCR_V5_REC_LATIN_MOBILE,
    'ru': ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
    'eslav': ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
}


class PPOCRv5Engine(OCREngine):
    """Lightweight PP-OCRv5 ONNX pipeline (det + rec).
    """

    def __init__(self):
        self.det_sess: Optional[ort.InferenceSession] = None
        self.rec_sess: Optional[ort.InferenceSession] = None
        self.vllm = VLLMOcrClient(
        url="http://127.0.0.1:8001/v1",
        model="hunyuanocr",
        timeout=300
    )
        self.dbg_dir = Path(r"G:\CT\comic-translate\_debug_crops")
        self.dbg_dir.mkdir(parents=True, exist_ok=True)
        self.det_post = DBPostProcessor(
            thresh=0.3, 
            box_thresh=0.5, 
            unclip_ratio=2.0, 
            use_dilation=False
        )
        self.decoder: Optional[CTCLabelDecoder] = None
        self.rec_img_shape = (3, 48, 320)


    
    def initialize(
        self, 
        lang: str = 'ch', 
        device: str = 'cpu', 
        det_model: str = 'mobile'
    ) -> None:
        # Ensure models present
        det_id = ModelID.PPOCR_V5_DET_MOBILE if det_model == 'mobile' else ModelID.PPOCR_V5_DET_SERVER
        rec_id = LANG_TO_REC_MODEL.get(lang, ModelID.PPOCR_V5_REC_LATIN_MOBILE)
        ModelDownloader.ensure([det_id, rec_id])

        # Load ONNX sessions
        det_path = ModelDownloader.primary_path(det_id)
        rec_paths = ModelDownloader.file_path_map(rec_id)
        rec_model = [p for n, p in rec_paths.items() if n.endswith('.onnx')][0]
        # dict file name can vary per lang
        dict_file = [p for n, p in rec_paths.items() if n.endswith('.txt')]
        dict_path = dict_file[0] if dict_file else None

        providers = get_providers(device)
        sess_opt = ort.SessionOptions()
        sess_opt.log_severity_level = 3
        self.det_sess = ort.InferenceSession(det_path, sess_options=sess_opt, providers=providers)
        self.rec_sess = ort.InferenceSession(rec_model, sess_options=sess_opt, providers=providers)

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
        assert self.det_sess is not None
        inp = det_preprocess(img, limit_side_len=2, limit_type='min')
        input_name = self.det_sess.get_inputs()[0].name
        output_name = self.det_sess.get_outputs()[0].name
        pred = self.det_sess.run([output_name], {input_name: inp})[0]
        boxes, scores = self.det_post(pred, (img.shape[0], img.shape[1]))
        return boxes, scores

    def _rec_infer(self, crops):
        # crops: список кропов (обычно PIL.Image или np.ndarray)
        texts = []
        confs = []

        for c in crops:
            if not isinstance(c, Image.Image):
                c = Image.fromarray(c)
            t = self.vllm.ocr_one(c)
            texts.append(t)
            confs.append(1.0 if t else 0.0)  # HunyuanOCR не даёт уверенность; ставим суррогат

        return texts, confs

    def process_image(self, img: np.ndarray, blk_list: List[TextBlock]) -> List[TextBlock]:
        if self.det_sess is None or self.rec_sess is None or self.decoder is None:
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

