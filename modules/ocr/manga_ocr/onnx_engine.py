import os
import re
import jaconv
import numpy as np
from PIL import Image
from onnxruntime import InferenceSession
import onnxruntime as ort
from modules.utils.device import get_providers

from modules.ocr.base import OCREngine
from modules.utils.textblock import TextBlock, adjust_text_line_coordinates
from modules.utils.download import ModelDownloader, ModelID


class MangaOCREngineONNX(OCREngine):
    """OCR engine using ONNX-exported MangaOCR models.
    """

    def __init__(self):
        self.model = None
        self.device = 'cpu'
        self.expansion_percentage = 5

    def initialize(self, device: str = 'cpu', expansion_percentage: int = 5) -> None:
        """Initialize the ONNX Manga OCR engine.

        Args:
            device: 'cpu' or a device string containing 'cuda' to attempt GPU provider.
            expansion_percentage: bounding box expansion percentage used when cropping.
        """

        self.device = device
        self.expansion_percentage = expansion_percentage

        if self.model is None:
            ModelDownloader.get(ModelID.MANGA_OCR_BASE_ONNX)
            self.model = MangaOCRONNX(device=device)

    def process_image(self, img: np.ndarray, blk_list: list[TextBlock]) -> list[TextBlock]:
        for blk in blk_list:
            # Get box coordinates
            if blk.bubble_xyxy is not None:
                x1, y1, x2, y2 = blk.bubble_xyxy
            else:
                x1, y1, x2, y2 = adjust_text_line_coordinates(
                    blk.xyxy,
                    self.expansion_percentage,
                    self.expansion_percentage,
                    img,
                )

            # Validate coordinates
            if x1 < x2 and y1 < y2 and x1 >= 0 and y1 >= 0 and x2 <= img.shape[1] and y2 <= img.shape[0]:
                cropped_img = img[y1:y2, x1:x2]
                try:
                    blk.text = self.model(cropped_img)
                except Exception:
                    blk.text = ""
            else:
                blk.text = ""

        return blk_list


class MangaOCRONNX:
    """Wrapper around ONNX encoder/decoder sessions for Manga OCR.

    The implementation is intentionally defensive: input and output names
    are discovered from the ONNX graphs so the wrapper is robust to small
    naming differences. The model expects images resized to 224x224.
    """

    def __init__(self, device: str = 'cpu'):
        self.device = device

        encoder_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_BASE_ONNX, "encoder_model.onnx")
        decoder_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_BASE_ONNX, "decoder_model.onnx")
        vocab_path = ModelDownloader.get_file_path(ModelID.MANGA_OCR_BASE_ONNX, "vocab.txt")

        providers = get_providers(self.device)
        self.encoder = InferenceSession(encoder_path, providers=providers)
        self.decoder = InferenceSession(decoder_path, providers=providers)

        self.vocab = self._load_vocab(vocab_path)

        # discover useful input/output names
        self.encoder_image_input = self._find_input_name(self.encoder, candidates=('image', 'pixel_values', 'input'))
        self.encoder_output_name = self.encoder.get_outputs()[0].name

        self.decoder_token_input = self._find_input_name(self.decoder, candidates=('token_ids', 'input_ids', 'input'))
        # decoder likely accepts encoder hidden states under a name; prefer common ones
        self.decoder_encoder_input = self._find_input_name(self.decoder, candidates=('encoder_hidden_states', 'encoder_outputs', 'encoder_last_hidden_state'))

    def _find_input_name(self, session: InferenceSession, candidates=('input',)) -> str:
        names = [inp.name for inp in session.get_inputs()]
        for cand in candidates:
            for n in names:
                if cand in n:
                    return n
        # fallback to first input name
        return names[0]

    def _load_vocab(self, vocab_file: str) -> list:
        with open(vocab_file, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        return lines

    def __call__(self, img: np.ndarray) -> str:
        img_in = self._preprocess(img)
        token_ids = self._generate(img_in)
        text = self._decode(token_ids)
        text = self._postprocess(text)
        return text

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        # Expecting BGR (OpenCV) numpy array from cropping logic used elsewhere.
        if img is None or img.size == 0:
            raise ValueError('Empty image passed to MangaOCRONNX')

        # convert BGR->RGB and to PIL
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)  # img is already in RGB format
        elif isinstance(img, Image.Image):
            img = img
        else:
            img = Image.fromarray(np.array(img))

        # convert to grayscale and back to RGB to match training preproc
        img = img.convert('L').convert('RGB')
        img = img.resize((224, 224), resample=Image.BILINEAR)

        arr = np.array(img, dtype=np.float32)
        arr /= 255.0
        arr = (arr - 0.5) / 0.5
        # (H, W, C) -> (C, H, W)
        arr = arr.transpose((2, 0, 1)).astype(np.float32)
        # add batch
        arr = arr[None]

        return arr

    def _generate(self, image: np.ndarray) -> list:
        # Run encoder once
        encoder_feed = {self.encoder_image_input: image}
        encoder_outs = self.encoder.run(None, encoder_feed)
        encoder_hidden = encoder_outs[0]

        token_ids = [2]

        for _ in range(300):
            # prepare decoder inputs
            decoder_feed = {
                self.decoder_token_input: np.array([token_ids], dtype=np.int64),
                self.decoder_encoder_input: encoder_hidden,
            }

            outs = self.decoder.run(None, decoder_feed)
            # assume logits are first output
            logits = outs[0]
            # pick last timestep logits
            next_token = int(np.argmax(logits[0, -1, :]))
            token_ids.append(next_token)

            if next_token == 3:
                break

        return token_ids

    def _decode(self, token_ids: list) -> str:
        text = ''
        for tid in token_ids:
            if tid < 5:
                continue
            if tid < len(self.vocab):
                text += self.vocab[tid]
        return text

    def _postprocess(self, text: str) -> str:
        text = ''.join(text.split())
        text = text.replace('…', '...')
        text = re.sub('[・.]{2,}', lambda x: (x.end() - x.start()) * '.', text)
        text = jaconv.h2z(text, ascii=True, digit=True)
        return text
