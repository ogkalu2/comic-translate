import os, sys, hashlib
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Dict, List, Union
from .download_file import download_url_to_file
from .paths import get_user_data_dir

logger = logging.getLogger(__name__)

# Paths / Globals
models_base_dir = os.path.join(get_user_data_dir(), "models")


_download_event_callback: Optional[Callable[[str, str], None]] = None

def set_download_callback(callback: Callable[[str, str], None]):
    """Register a global callback to be notified of model download events.

    Args:
        callback: Callable(status: str, name: str)
    """
    global _download_event_callback
    _download_event_callback = callback

def notify_download_event(status: str, name: str):
    """Notify subscribers about a download event without hard dependency on UI."""
    try:
        if _download_event_callback:
            _download_event_callback(status, name)
    except Exception:
        # Never allow UI notification failures to break downloads
        pass


def calculate_sha256_checksum(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def calculate_md5_checksum(file_path: str) -> str:
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()


class ModelID(Enum):
    MANGA_OCR_BASE = "manga-ocr-base"
    MANGA_OCR_BASE_ONNX = "manga-ocr-base-onnx"
    PORORO = "pororo"
    PORORO_ONNX = "pororo-onnx"
    LAMA_ONNX = "lama-manga-dynamic"
    AOT_JIT = "aot-traced"
    AOT_ONNX = "aot-onnx"
    AOT_TORCH = "aot-torch"
    LAMA_JIT = "anime-manga-big-lama"
    MIGAN_PIPELINE_ONNX = "migan-pipeline-v2"
    MIGAN_ONNX = "migan-onnx"
    MIGAN_JIT = "migan-traced"
    RTDETR_V2_ONNX = "rtdetr-v2-onnx"
    
    # PPOCRv5 Detection Models
    PPOCR_V5_DET_MOBILE = "ppocr-v5-det-mobile"
    PPOCR_V5_DET_SERVER = "ppocr-v5-det-server"
    PPOCR_V5_DET_MOBILE_TORCH = "ppocr-v5-det-mobile-torch"
    
    # PPOCRv5 Recognition Models - Chinese
    PPOCR_V5_REC_MOBILE = "ppocr-v5-rec-ch-mobile"
    PPOCR_V5_REC_SERVER = "ppocr-v5-rec-ch-server"
    PPOCR_V5_REC_MOBILE_TORCH = "ppocr-v5-rec-ch-mobile-torch"
    
    # PPOCRv5 Recognition Models - Other Languages
    PPOCR_V5_REC_EN_MOBILE = "ppocr-v5-rec-en-mobile"
    PPOCR_V5_REC_KOREAN_MOBILE = "ppocr-v5-rec-korean-mobile"
    PPOCR_V5_REC_LATIN_MOBILE = "ppocr-v5-rec-latin-mobile"
    PPOCR_V5_REC_ESLAV_MOBILE = "ppocr-v5-rec-eslav-mobile"

    # PPOCRv5 Recognition Models - Torch versions (if needed)
    PPOCR_V5_REC_EN_MOBILE_TORCH = "ppocr-v5-rec-en-mobile-torch"
    PPOCR_V5_REC_KOREAN_MOBILE_TORCH = "ppocr-v5-rec-korean-mobile-torch"
    PPOCR_V5_REC_LATIN_MOBILE_TORCH = "ppocr-v5-rec-latin-mobile-torch"
    PPOCR_V5_REC_ESLAV_MOBILE_TORCH = "ppocr-v5-rec-eslav-mobile-torch"

    # PPOCRv4 Classifier
    PPOCR_V4_CLS = "ppocr-v4-cls"

    # Font Detection
    FONT_DETECTOR_ONNX = "font-detector-onnx"
    FONT_DETECTOR_TORCH = "font-detector-torch"


@dataclass(frozen=True)
class ModelSpec:
    id: ModelID
    url: str
    files: List[str]
    sha256: List[Optional[str]]
    save_dir: str
    additional_urls: Optional[Dict[str, str]] = None  # dict remote filename -> url
    # Optional mapping of remote filename -> local filename to save as
    save_as: Optional[Dict[str, str]] = None

    def as_legacy_dict(self) -> Dict[str, Union[str, List[str]]]:
        """Return a dict shaped like the old module-level *_data objects."""
        return {
            'url': self.url,
            'files': list(self.files),
            'sha256_pre_calculated': list(self.sha256),
            'save_dir': self.save_dir,
        }


class ModelDownloader:
    """Central registry & download helper for model assets."""

    registry: Dict[ModelID, ModelSpec] = {}

    @classmethod
    def register(cls, spec: ModelSpec):
        cls.registry[spec.id] = spec

    @classmethod
    def get(cls, model: Union[ModelID, ModelSpec]):
        spec = cls.registry[model] if isinstance(model, ModelID) else model
        _download_spec(spec)

    @classmethod
    def ensure(cls, models: Iterable[Union[ModelID, ModelSpec]]):
        for m in models:
            cls.get(m)

    # Path Helpers
    @classmethod
    def file_paths(cls, model: Union[ModelID, ModelSpec]) -> List[str]:
        """Ensure model is present then return absolute paths to all its files."""
        spec = cls.registry[model] if isinstance(model, ModelID) else model
        cls.get(spec.id)  # ensure downloaded
        paths: List[str] = []
        for remote_name in spec.files:
            local_name = spec.save_as.get(remote_name, remote_name) if spec.save_as else remote_name
            paths.append(os.path.join(spec.save_dir, local_name))
        return paths

    @classmethod
    def primary_path(cls, model: Union[ModelID, ModelSpec]) -> str:
        """Return the first file path for a model (common for single-file specs)."""
        return cls.file_paths(model)[0]

    @classmethod
    def get_file_path(cls, model: Union[ModelID, ModelSpec], file_name: str) -> str:
        """Ensure model is present then return the absolute path for the requested file_name.

        Raises ValueError if the file_name is not part of the model spec.
        """
        spec = cls.registry[model] if isinstance(model, ModelID) else model
        # ensure downloaded
        cls.get(spec.id)
        # Accept either remote filename or local saved filename
        remote_name: Optional[str] = None
        local_name: Optional[str] = None

        if file_name in spec.files:
            remote_name = file_name
            local_name = spec.save_as.get(remote_name, remote_name) if spec.save_as else remote_name
        else:
            # Try to resolve as a local saved name
            if spec.save_as and file_name in spec.save_as.values():
                local_name = file_name
                # find corresponding remote name
                for r, l in spec.save_as.items():
                    if l == file_name:
                        remote_name = r
                        break
                if remote_name is None:
                    # Should not happen, but fallback
                    remote_name = file_name
            else:
                raise ValueError(f"File '{file_name}' is not declared for model {spec.id}")

        return os.path.join(spec.save_dir, local_name)

    @classmethod
    def file_path_map(cls, model: Union[ModelID, ModelSpec]) -> Dict[str, str]:
        """Return a dict mapping each declared filename to its absolute path (ensures download)."""
        spec = cls.registry[model] if isinstance(model, ModelID) else model
        cls.get(spec.id)
        result: Dict[str, str] = {}
        for remote_name in spec.files:
            local_name = spec.save_as.get(remote_name, remote_name) if spec.save_as else remote_name
            result[local_name] = os.path.join(spec.save_dir, local_name)
        return result

    @classmethod
    def is_downloaded(cls, model: Union[ModelID, ModelSpec]) -> bool:
        """Return True if all files for the model exist and match provided checksums (when present)."""
        spec = cls.registry[model] if isinstance(model, ModelID) else model
        for remote_name, expected_checksum in zip(spec.files, spec.sha256):
            local_name = spec.save_as.get(remote_name, remote_name) if spec.save_as else remote_name
            file_path = os.path.join(spec.save_dir, local_name)
            if not os.path.exists(file_path):
                return False
            if expected_checksum:
                # verify checksum by detecting algorithm via length
                try:
                    if len(expected_checksum) == 64:
                        calc = calculate_sha256_checksum(file_path)
                    elif len(expected_checksum) == 32:
                        calc = calculate_md5_checksum(file_path)
                    else:
                        # unknown checksum format, skip verification
                        continue
                except Exception:
                    return False
                if calc != expected_checksum:
                    return False
        return True


# Core download implementations (shared)

def _download_single_file(file_url: str, file_path: str, expected_checksum: Optional[str]):
    msg = f'Downloading: "{file_url}" to {os.path.dirname(file_path)}\n'
    if sys.stderr:
        sys.stderr.write(msg)
    else:
        logger.info(msg.strip())
    notify_download_event('start', os.path.basename(file_path))
    download_url_to_file(file_url, file_path, hash_prefix=None, progress=True)
    notify_download_event('end', os.path.basename(file_path))

    if expected_checksum:
        # Detect hash algorithm via length: 64=sha256, 32=md5
        if len(expected_checksum) == 64:
            algo = 'sha256'
            calculated_checksum = calculate_sha256_checksum(file_path)
        elif len(expected_checksum) == 32:
            algo = 'md5'
            calculated_checksum = calculate_md5_checksum(file_path)
        else:
            logger.warning(f"Unknown checksum length for {file_path} (len={len(expected_checksum)}). Skipping verification.")
            return

        if calculated_checksum == expected_checksum:
            logger.info(f"Download model success, {algo}: {calculated_checksum}")
        else:
            try:
                os.remove(file_path)
                logger.error(
                    f"Model {algo}: {calculated_checksum}, expected {algo}: {expected_checksum}, wrong model deleted. Please restart comic-translate."
                )
            except Exception:
                logger.error(
                    f"Model {algo}: {calculated_checksum}, expected {algo}: {expected_checksum}, please delete {file_path} and restart comic-translate."
                )
            raise RuntimeError(
                f"Model {algo} mismatch for {file_path}: got {calculated_checksum}, expected {expected_checksum}. "
                "Please delete the file and restart comic-translate or re-download the model."
            )


def _download_spec(spec: ModelSpec):
    if not os.path.exists(spec.save_dir):
        os.makedirs(spec.save_dir, exist_ok=True)
        logger.info(f"Created directory: {spec.save_dir}")

    for remote_name, expected_checksum in zip(spec.files, spec.sha256):
        # Determine URL for remote filename
        if spec.additional_urls and remote_name in spec.additional_urls:
            file_url = spec.additional_urls[remote_name]
        else:
            file_url = f"{spec.url}{remote_name}"

        # Determine local save name
        local_name = spec.save_as.get(remote_name, remote_name) if spec.save_as else remote_name
        file_path = os.path.join(spec.save_dir, local_name)

        if os.path.exists(file_path):
            # Skip checksum verification if no expected checksum is provided
            if expected_checksum is None:
                continue
                
            # Detect hash algorithm via length: 64=sha256, 32=md5
            try:
                if len(expected_checksum) == 64:
                    calculated = calculate_sha256_checksum(file_path)
                    algo = 'sha256'
                elif len(expected_checksum) == 32:
                    calculated = calculate_md5_checksum(file_path)
                    algo = 'md5'
                else:
                    # Unknown checksum format: force re-download
                    logger.warning(
                        f"Unknown checksum format for {remote_name} (len={len(expected_checksum)}). Redownloading..."
                    )
                    calculated = None
                    algo = None
            except Exception:
                # If checksum calculation fails, force re-download
                logger.warning(f"Failed to calculate checksum for {local_name}. Redownloading...")
                calculated = None
                algo = None

            if calculated and calculated == expected_checksum:
                continue
            else:
                if calculated:
                    logger.warning(
                        f"Checksum mismatch for {local_name}. Expected {expected_checksum}, got {calculated}. Redownloading..."
                    )

        _download_single_file(file_url, file_path, expected_checksum)


# Registry population
def _register_defaults():
    ModelDownloader.register(ModelSpec(
        id=ModelID.MANGA_OCR_BASE,
        url='https://huggingface.co/kha-white/manga-ocr-base/resolve/main/',
        files=[
            'pytorch_model.bin', 'config.json', 'preprocessor_config.json',
            'README.md', 'special_tokens_map.json', 'tokenizer_config.json', 'vocab.txt'
        ],
        sha256=[
            'c63e0bb5b3ff798c5991de18a8e0956c7ee6d1563aca6729029815eda6f5c2eb',
            '8c0e395de8fa699daaac21aee33a4ba9bd1309cfbff03147813d2a025f39f349',
            'af4eb4d79cf61b47010fc0bc9352ee967579c417423b4917188d809b7e048948',
            '32f413afcc4295151e77d25202c5c5d81ef621b46f947da1c3bde13256dc0d5f',
            '303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3',
            'd775ad1deac162dc56b84e9b8638f95ed8a1f263d0f56f4f40834e26e205e266',
            '344fbb6b8bf18c57839e924e2c9365434697e0227fac00b88bb4899b78aa594d'
        ],
        save_dir=os.path.join(models_base_dir, 'ocr', 'manga-ocr-base')
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.MANGA_OCR_BASE_ONNX,
        url='https://huggingface.co/mayocream/manga-ocr-onnx/resolve/main/',
        files=['encoder_model.onnx', 'decoder_model.onnx', 'vocab.txt'],
        sha256=[
            '15fa8155fe9bc1a7d25d9bb353debaa4def033d0174e907dbd2dd6d995def85f',
            'ef7765261e9d1cdc34d89356986c2bbc2a082897f753a89605ae80fdfa61f5e8',
            '5cb5c5586d98a2f331d9f8828e4586479b0611bfba5d8c3b6dadffc84d6a36a3',
        ],
        save_dir=os.path.join(models_base_dir, 'ocr', 'manga-ocr-base-onnx')
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PORORO,
        url='https://huggingface.co/ogkalu/pororo/resolve/main/',
        files=['craft.pt', 'brainocr.pt', 'ocr-opt.txt'],
        sha256=[
            '4a5efbfb48b4081100544e75e1e2b57f8de3d84f213004b14b85fd4b3748db17',
            '125820ba8ae4fa5d9fd8b8a2d4d4a7afe96a70c32b1aa01d4129001a6f61baec',
            'dd471474e91d78e54b179333439fea58158ad1a605df010ea0936dcf4387a8c2'
        ],
        save_dir=os.path.join(models_base_dir, 'ocr', 'pororo')
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PORORO_ONNX,
        url='https://huggingface.co/ogkalu/pororo/resolve/main/',
        files=['craft.onnx', 'brainocr.onnx', 'ocr-opt.txt'],
        sha256=[
            'e87cbb40ecb3c881971dea378ead9f80d2d607a011ccb4ca161f27823ed438ca',
            '25369c7dbeaed126dc5adb9f97134003b2d7fa7257861e0a4d90b5c5b2343d69',
            'dd471474e91d78e54b179333439fea58158ad1a605df010ea0936dcf4387a8c2'
        ],
        save_dir=os.path.join(models_base_dir, 'ocr', 'pororo-onnx')
    ))

    # Inpainting: LaMa ONNX (single file)
    ModelDownloader.register(ModelSpec(
        id=ModelID.LAMA_ONNX,
        url='https://huggingface.co/ogkalu/lama-manga-onnx-dynamic/resolve/main/',
        files=['lama-manga-dynamic.onnx'],
        sha256=['de31ffa5ba26916b8ea35319f6c12151ff9654d4261bccf0583a69bb095315f9'],
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    # Inpainting: MIGAN pipeline ONNX (single file)
    ModelDownloader.register(ModelSpec(
        id=ModelID.MIGAN_PIPELINE_ONNX,
        url='https://github.com/Sanster/models/releases/download/migan/',
        files=['migan_pipeline_v2.onnx'],
        sha256=[None],  # GitHub release no sha256 provided; could be added later
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    # Inpainting: AOT traced TorchScript
    ModelDownloader.register(ModelSpec(
        id=ModelID.AOT_JIT,
        url='https://huggingface.co/ogkalu/aot-inpainting/resolve/main/',
        files=['aot_traced.pt'],
        sha256=['552d9ad440258fa14907fc2492cf172c51983760c4619861f8b7b362a762af0b'],
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    # Inpainting: AOT ONNX
    ModelDownloader.register(ModelSpec(
        id=ModelID.AOT_ONNX,
        url='https://huggingface.co/ogkalu/aot-inpainting/resolve/main/',
        files=['aot.onnx'],
        sha256=['ffd39ed8e2a275869d3b49180d030f0d8b8b9c2c20ed0e099ecd207201f0eada'],
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    # Inpainting: AOT PyTorch
    ModelDownloader.register(ModelSpec(
        id=ModelID.AOT_TORCH,
        url='https://huggingface.co/ogkalu/aot-inpainting/resolve/main/',
        files=['inpainting.ckpt'],
        sha256=['878d541c68648969bc1b042a6e997f3a58e49b6c07c5636ad55130736977149f'],
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    # Inpainting: LaMa JIT (TorchScript)
    ModelDownloader.register(ModelSpec(
        id=ModelID.LAMA_JIT,
        url='https://github.com/Sanster/models/releases/download/AnimeMangaInpainting/',
        files=['anime-manga-big-lama.pt'],
        sha256=['29f284f36a0a510bcacf39ecf4c4d54f'],  # md5
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    # Inpainting: MIGAN traced JIT (TorchScript)
    ModelDownloader.register(ModelSpec(
        id=ModelID.MIGAN_JIT,
        url='https://github.com/Sanster/models/releases/download/migan/',
        files=['migan_traced.pt'],
        sha256=['76eb3b1a71c400ee3290524f7a11b89c'],  # md5
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.MIGAN_ONNX,
        url='',
        files=['migan.onnx'],
        sha256=[''],  # md5
        save_dir=os.path.join(models_base_dir, 'inpainting')
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.RTDETR_V2_ONNX,
        url='https://huggingface.co/ogkalu/comic-text-and-bubble-detector/resolve/main/',
        files=['detector.onnx'],
        sha256=['065744e91c0594ad8663aa8b870ce3fb27222942eded5a3cc388ce23421bd195'], 
        save_dir=os.path.join(models_base_dir, 'detection')
    ))

    # PPOCRv5 Detection Models
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_DET_MOBILE,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/det/',
        files=['ch_PP-OCRv5_mobile_det.onnx'],
        sha256=['4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae'],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx')
    ))

    # PPOCRv5 Detection/Recognition Models - Torch
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_DET_MOBILE_TORCH,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/torch/PP-OCRv5/det/',
        files=['ch_PP-OCRv5_det_mobile_infer.pth'],
        sha256=['df848ed5060bac4d0f6e58572aea97d92e909a8a87cf292849237b0e84f6ffdb'],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-torch'),
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_DET_SERVER,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/det/',
        files=['ch_PP-OCRv5_server_det.onnx'],
        sha256=['0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad'],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx')
    ))

    # PPOCRv5 Recognition Models - Chinese
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_MOBILE,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/',
        files=['ch_PP-OCRv5_rec_mobile_infer.onnx', 'ppocrv5_dict.txt'],
        sha256=['5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx'),
        additional_urls={
            'ppocrv5_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile_infer/ppocrv5_dict.txt'
        }
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_MOBILE_TORCH,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/torch/PP-OCRv5/rec/',
        files=['ch_PP-OCRv5_rec_mobile_infer.pth', 'ppocrv5_dict.txt'],
        sha256=['d20ee8dac2ca63e2d1989b02ecc42595c71d61bf8dd8c8ddc5ad2ee68e7b5be2', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-torch'),
        additional_urls={
            'ppocrv5_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile_infer/ppocrv5_dict.txt'
        }
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_SERVER,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/',
        files=['ch_PP-OCRv5_rec_server_infer.onnx', 'ppocrv5_dict.txt'],
        sha256=['e09385400eaaaef34ceff54aeb7c4f0f1fe014c27fa8b9905d4709b65746562a', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx'),
        additional_urls={
            'ppocrv5_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/ch_PP-OCRv5_rec_server_infer/ppocrv5_dict.txt'
        }
    ))

    # PPOCRv5 Recognition Models - English  
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_EN_MOBILE,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/',
        files=['en_PP-OCRv5_rec_mobile_infer.onnx', 'ppocrv5_en_dict.txt'],
        sha256=['c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx'),
        additional_urls={
            'ppocrv5_en_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile_infer/ppocrv5_en_dict.txt'
        }
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_EN_MOBILE_TORCH,
        url='https://huggingface.co/ogkalu/ppocr-v5-torch/resolve/main/',
        files=['en_PP-OCRv5_mobile_rec.pth', 'ppocrv5_en_dict.txt'],
        sha256=['4795b81d685f569e8862dc71e774aa65a6f5c06bd1e9c03459a8f2b46ad576d9', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-torch'),
        additional_urls={
            'ppocrv5_en_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile_infer/ppocrv5_en_dict.txt'
        }
    ))

    # PPOCRv5 Recognition Models - Torch versions (other languages)
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_KOREAN_MOBILE_TORCH,
        url='https://huggingface.co/ogkalu/ppocr-v5-torch/resolve/main/',
        files=['korean_PP-OCRv5_mobile_rec.pth', 'ppocrv5_korean_dict.txt'],
        sha256=['74cf26bd1c10d65812d43aadefc877f240c3f532936f912b46f27791a1e2684e', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-torch'),
        additional_urls={
            'ppocrv5_korean_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/korean_PP-OCRv5_rec_mobile_infer/ppocrv5_korean_dict.txt'
        }
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_LATIN_MOBILE_TORCH,
        url='https://huggingface.co/ogkalu/ppocr-v5-torch/resolve/main/',
        files=['latin_PP-OCRv5_mobile_rec.pth', 'ppocrv5_latin_dict.txt'],
        sha256=['bb830312c306489f20fd2f974d9c502e58b1cfe90c7c0dcc0f4871303a04d613', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-torch'),
        additional_urls={
            'ppocrv5_latin_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/latin_PP-OCRv5_rec_mobile_infer/ppocrv5_latin_dict.txt'
        }
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_ESLAV_MOBILE_TORCH,
        url='https://huggingface.co/ogkalu/ppocr-v5-torch/resolve/main/',
        files=['eslav_PP-OCRv5_mobile_rec.pth', 'ppocrv5_eslav_dict.txt'],
        sha256=['ecff6dfccf1ba1a9c0ff615f73c9504615fff4ecfed745355c957940f12f728d', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-torch'),
        additional_urls={
            'ppocrv5_eslav_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/eslav_PP-OCRv5_rec_mobile_infer/ppocrv5_eslav_dict.txt'
        }
    ))

    # PPOCRv5 Recognition Models - Korean
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_KOREAN_MOBILE,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/',
        files=['korean_PP-OCRv5_rec_mobile_infer.onnx', 'ppocrv5_korean_dict.txt'],
        sha256=['cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx'),
        additional_urls={
            'ppocrv5_korean_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/korean_PP-OCRv5_rec_mobile_infer/ppocrv5_korean_dict.txt'
        }
    ))

    # PPOCRv5 Recognition Models - Latin
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_LATIN_MOBILE,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/',
        files=['latin_PP-OCRv5_rec_mobile_infer.onnx', 'ppocrv5_latin_dict.txt'],
        sha256=['b20bd37c168a570f583afbc8cd7925603890efbcdc000a59e22c269d160b5f5a', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx'),
        additional_urls={
            'ppocrv5_latin_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/latin_PP-OCRv5_rec_mobile_infer/ppocrv5_latin_dict.txt'
        }
    ))

    # PPOCRv5 Recognition Models - East Slavic (Russian)
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V5_REC_ESLAV_MOBILE,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/',
        files=['eslav_PP-OCRv5_rec_mobile_infer.onnx', 'ppocrv5_eslav_dict.txt'],
        sha256=['08705d6721849b1347d26187f15a5e362c431963a2a62bfff4feac578c489aab', None],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx'),
        additional_urls={
            'ppocrv5_eslav_dict.txt': 'https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/paddle/PP-OCRv5/rec/eslav_PP-OCRv5_rec_mobile_infer/ppocrv5_eslav_dict.txt'
        }
    ))

    # PPOCRv4 Classifier (for text orientation)
    ModelDownloader.register(ModelSpec(
        id=ModelID.PPOCR_V4_CLS,
        url='https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv4/cls/',
        files=['ch_ppocr_mobile_v2.0_cls_infer.onnx'],
        sha256=['e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c'],
        save_dir=os.path.join(models_base_dir, 'ocr', 'ppocr-v5-onnx')
    ))

    # Font Detection
    ModelDownloader.register(ModelSpec(
        id=ModelID.FONT_DETECTOR_ONNX,
        url='https://huggingface.co/ogkalu/yuzumarker-font-detection-onnx/resolve/main/',
        files=['font-detector.onnx'],
        sha256=['99dd351e94f06e31397113602ae000a24c1d38ad76275066e844a0c836f75d4f'],
        save_dir=os.path.join(models_base_dir, 'detection', 'font')
    ))

    ModelDownloader.register(ModelSpec(
        id=ModelID.FONT_DETECTOR_TORCH,
        url='https://huggingface.co/gyrojeff/YuzuMarker.FontDetection/resolve/main/',
        files=['name%3D4x-epoch%3D84-step%3D1649340.ckpt'],
        sha256=['9053615071c31978a3988143c9a3bdec8da53e269a8f84b5908d6f15747a1a81'],
        save_dir=os.path.join(models_base_dir, 'detection', 'font'),
        save_as={'name%3D4x-epoch%3D84-step%3D1649340.ckpt': 'font-detector.ckpt'}
    ))

_register_defaults()

# List of models that should always be ensured at startup (can be ModelID items)
mandatory_models: List[Union[ModelID, ModelSpec, Dict[str, Union[str, List[str]]]]] = []

# Utility to normalize mixed mandatory_models entries at startup
def ensure_mandatory_models():
    for m in mandatory_models:
        if isinstance(m, ModelSpec):
            ModelDownloader.get(m)
        else:  # Enum
            ModelDownloader.get(m)
