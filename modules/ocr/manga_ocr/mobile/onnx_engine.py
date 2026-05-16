import logging
import re

import jaconv
import numpy as np
import onnxruntime as ort
from PIL import Image

from modules.ocr.base import OCREngine
from modules.utils.download import ModelDownloader, ModelID
from modules.utils.textblock import TextBlock, adjust_text_line_coordinates


logger = logging.getLogger(__name__)


IMAGE_SIZE = 224
MAX_SEQUENCE_LENGTH = 256
NUM_LAYERS = 4
NUM_HEADS = 4
HEAD_DIM = 64
START_TOKEN_ID = 2
END_TOKEN_ID = 3
SPECIAL_TOKEN_THRESHOLD = 5
MAX_POSITION_ID = 127


def _create_session(model_path: str) -> ort.InferenceSession:
    so = ort.SessionOptions()
    so.log_severity_level = 3
    # This decoder makes many tiny step() calls; desktop ORT is faster with one thread.
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    so.enable_cpu_mem_arena = True
    so.enable_mem_pattern = True
    return ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])


class MangaOCRMobileONNXEngine(OCREngine):
    """OCR engine for the rebuilt Manga OCR Mobile ONNX decoder path."""

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self.expansion_percentage = 5

    def initialize(self, device: str = "cpu", expansion_percentage: int = 5) -> None:
        self.device = "cpu"
        self.expansion_percentage = expansion_percentage
        if self.model is None:
            self.model = MangaOCRMobileONNX()

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        crops: list[np.ndarray] = []
        crop_indices: list[int] = []

        for idx, blk in enumerate(blk_list):
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy,
                    self.expansion_percentage,
                    self.expansion_percentage,
                    img,
                )

            if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                crops.append(img[y1:y2, x1:x2])
                crop_indices.append(idx)
            else:
                blk.text = ""

        if not crops:
            return blk_list

        try:
            texts = self.model.process_batch(crops)
        except Exception:
            logger.exception("Manga OCR Mobile ONNX failed")
            for idx in crop_indices:
                blk_list[idx].text = ""
            return blk_list

        for idx, text in zip(crop_indices, texts):
            blk_list[idx].text = text

        return blk_list


class MangaOCRMobileONNX:
    def __init__(self):
        ModelDownloader.get(ModelID.MANGA_OCR_MOBILE_ONNX)
        encoder_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_MOBILE_ONNX, "encoder.onnx")
        decoder_init_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_MOBILE_ONNX, "decoder_init.onnx")
        decoder_step_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_MOBILE_ONNX, "decoder_step.onnx")
        vocab_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_MOBILE_ONNX, "vocab.txt")

        self.encoder = _create_session(encoder_path)
        self.decoder_init = _create_session(decoder_init_path)
        self.decoder_step = _create_session(decoder_step_path)
        self.vocab = self._load_vocab(vocab_path)
        self.vocab_size = len(self.vocab)

        self.encoder_input = self.encoder.get_inputs()[0].name
        self.decoder_init_inputs = [inp.name for inp in self.decoder_init.get_inputs()]
        self.decoder_step_inputs = [inp.name for inp in self.decoder_step.get_inputs()]

        self.image_buffer = np.empty((1, 3, IMAGE_SIZE, IMAGE_SIZE), dtype=np.float32)
        self.token_buffer = np.empty((1, 1), dtype=np.int64)
        self.position_buffer = np.empty((1, 1), dtype=np.int64)
        self.self_k_cache = np.zeros((NUM_LAYERS, 1, NUM_HEADS, MAX_SEQUENCE_LENGTH, HEAD_DIM), dtype=np.float32)
        self.self_v_cache = np.zeros((NUM_LAYERS, 1, NUM_HEADS, MAX_SEQUENCE_LENGTH, HEAD_DIM), dtype=np.float32)

    def _load_vocab(self, vocab_file: str) -> list[str]:
        with open(vocab_file, "r", encoding="utf-8") as handle:
            return handle.read().splitlines()

    def process_batch(self, imgs: list[np.ndarray]) -> list[str]:
        texts: list[str] = []
        for img in imgs:
            texts.append(self.process_single(img))
        return texts

    def process_single(self, img: np.ndarray) -> str:
        self._preprocess_into(img)
        encoder_hidden = self.encoder.run(None, {self.encoder_input: self.image_buffer})[0]

        self.self_k_cache.fill(0)
        self.self_v_cache.fill(0)
        self.token_buffer[0, 0] = START_TOKEN_ID

        init_out = self.decoder_init.run(
            None,
            {
                self.decoder_init_inputs[0]: encoder_hidden,
                self.decoder_init_inputs[1]: self.token_buffer,
            },
        )

        self.self_k_cache[:, :, :, :1, :] = init_out[1]
        self.self_v_cache[:, :, :, :1, :] = init_out[2]
        cross_k_cache = init_out[3]
        cross_v_cache = init_out[4]

        token_ids: list[int] = [START_TOKEN_ID]
        next_token = int(np.argmax(init_out[0][0][:self.vocab_size]))
        if next_token != END_TOKEN_ID:
            token_ids.append(next_token)
            cache_len = 1
            current_token = next_token

            while len(token_ids) < MAX_SEQUENCE_LENGTH and cache_len < MAX_SEQUENCE_LENGTH:
                self.token_buffer[0, 0] = current_token
                self.position_buffer[0, 0] = min(cache_len + 1, MAX_POSITION_ID)
                step_out = self.decoder_step.run(
                    None,
                    {
                        self.decoder_step_inputs[0]: encoder_hidden,
                        self.decoder_step_inputs[1]: self.token_buffer,
                        self.decoder_step_inputs[2]: self.position_buffer,
                        self.decoder_step_inputs[3]: self.self_k_cache,
                        self.decoder_step_inputs[4]: self.self_v_cache,
                        self.decoder_step_inputs[5]: cross_k_cache,
                        self.decoder_step_inputs[6]: cross_v_cache,
                    },
                )

                self.self_k_cache[:, :, :, cache_len : cache_len + 1, :] = step_out[1]
                self.self_v_cache[:, :, :, cache_len : cache_len + 1, :] = step_out[2]
                cache_len += 1

                next_token = int(np.argmax(step_out[0][0][:self.vocab_size]))
                if next_token == END_TOKEN_ID:
                    break

                token_ids.append(next_token)
                current_token = next_token

        return self._postprocess(self._decode(token_ids))

    def _preprocess_into(self, img: np.ndarray) -> None:
        if img is None or getattr(img, "size", 0) == 0:
            raise ValueError("Empty image passed to MangaOCRMobileONNX")

        image = Image.fromarray(img).convert("RGB")
        src_w, src_h = image.size
        scale = min(IMAGE_SIZE / src_w, IMAGE_SIZE / src_h)
        dst_w = max(1, int(src_w * scale))
        dst_h = max(1, int(src_h * scale))

        resized = image.resize((dst_w, dst_h), resample=Image.Resampling.BILINEAR)
        canvas = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), (255, 255, 255))
        canvas.paste(resized, ((IMAGE_SIZE - dst_w) // 2, (IMAGE_SIZE - dst_h) // 2))

        arr = np.asarray(canvas, dtype=np.float32) / 255.0
        np.copyto(self.image_buffer[0], arr.transpose((2, 0, 1)))

    def _decode(self, token_ids: list[int]) -> str:
        pieces: list[str] = []
        for token_id in token_ids:
            if token_id < SPECIAL_TOKEN_THRESHOLD:
                continue
            if token_id < self.vocab_size:
                pieces.append(self.vocab[token_id])
        return "".join(pieces)

    def _postprocess(self, text: str) -> str:
        text = "".join(text.split())
        text = text.replace("ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦", "...")
        text = re.sub("[ÃƒÂ£Ã†â€™Ã‚Â».]{2,}", lambda x: (x.end() - x.start()) * ".", text)
        text = jaconv.h2z(text, ascii=True, digit=True)
        if self._is_pathological_punctuation_run(text):
            return ""
        return re.sub(r"([.\uFF0E\u30FB\uFF65])\1{3,}", r"\1\1\1", text)

    def _is_pathological_punctuation_run(self, text: str) -> bool:
        if len(text) < 12:
            return False
        if not re.fullmatch(r"[.\uFF0E\u30FB\uFF65\u3002,\u2026\u30FC\u2014\-~\u301C\u300C\u300D\u300E\u300F\uFF08\uFF09()\uFF3B\uFF3D\[\]!?\uFF01\uFF1F\s]+", text):
            return False
        dot_like_count = sum(1 for char in text if re.fullmatch(r"[.\uFF0E\u30FB\uFF65\u3002,\u2026]", char))
        return dot_like_count / len(text) >= 0.85

