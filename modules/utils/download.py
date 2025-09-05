import os, sys, hashlib
from torch.hub import download_url_to_file
from loguru import logger

# Get the directory of the current file
current_file_dir = os.path.dirname(os.path.abspath(__file__))

# Navigate up two levels to reach the project root
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))

# Define the base directory for all models
models_base_dir = os.path.join(project_root, 'models')

# Simple download event callback to integrate with UI if available.
# The callback signature is: callback(status: str, name: str)
# status is one of: 'start', 'end'
_download_event_callback = None

def set_download_callback(callback):
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

def calculate_sha256_checksum(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_models(data):
    """
    Ensure required model files exist locally; download missing or mismatched files.
    data keys: url, files, sha256_pre_calculated, save_dir
    """
    save_dir = data['save_dir']
    if not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
        print(f"Created directory: {save_dir}")

    for i, file_name in enumerate(data['files']):
        file_url = f"{data['url']}{file_name}"
        file_path = os.path.join(save_dir, file_name)
        expected_checksum = data['sha256_pre_calculated'][i]

        # If file exists and checksum matches (when given), skip
        if os.path.exists(file_path) and expected_checksum is not None:
            calculated_checksum = calculate_sha256_checksum(file_path)
            if calculated_checksum == expected_checksum:
                continue
            else:
                print(f"Checksum mismatch for {file_name}. Expected {expected_checksum}, got {calculated_checksum}. Redownloading...")

        # Download the file
        sys.stderr.write('Downloading: "{}" to {}\n'.format(file_url, save_dir))
        notify_download_event('start', file_name)
        download_url_to_file(file_url, file_path, hash_prefix=None, progress=True)
        notify_download_event('end', file_name)

        # Verify checksum if provided
        if expected_checksum is not None:
            calculated_checksum = calculate_sha256_checksum(file_path)
            if calculated_checksum == expected_checksum:
                logger.info(f"Download model success, sha256: {calculated_checksum}")
            else:
                try:
                    os.remove(file_path)
                    logger.error(
                        f"Model sha256: {calculated_checksum}, expected sha256: {expected_checksum}, wrong model deleted. Please restart comic-translate."
                    )
                except Exception:
                    logger.error(
                        f"Model sha256: {calculated_checksum}, expected sha256: {expected_checksum}, please delete {file_path} and restart comic-translate."
                    )
                    
                    raise RuntimeError(
                        f"Model sha256 mismatch for {file_path}: got {calculated_checksum}, expected {expected_checksum}. "
                        "Please delete the file and restart comic-translate or re-download the model."
                    )

# Model Download Data
manga_ocr_data = {
    'url': 'https://huggingface.co/kha-white/manga-ocr-base/resolve/main/',
    'files': [
        'pytorch_model.bin', 'config.json', 'preprocessor_config.json',
        'README.md', 'special_tokens_map.json', 'tokenizer_config.json', 'vocab.txt'
    ],
    'sha256_pre_calculated': [
        'c63e0bb5b3ff798c5991de18a8e0956c7ee6d1563aca6729029815eda6f5c2eb', 
        '8c0e395de8fa699daaac21aee33a4ba9bd1309cfbff03147813d2a025f39f349', 
        'af4eb4d79cf61b47010fc0bc9352ee967579c417423b4917188d809b7e048948', 
        '32f413afcc4295151e77d25202c5c5d81ef621b46f947da1c3bde13256dc0d5f', 
        '303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3', 
        'd775ad1deac162dc56b84e9b8638f95ed8a1f263d0f56f4f40834e26e205e266', 
        '344fbb6b8bf18c57839e924e2c9365434697e0227fac00b88bb4899b78aa594d'
    ],
    'save_dir': os.path.join(models_base_dir, 'ocr', 'manga-ocr-base')
}

manga_ocr_onnx_data = {
    'url': 'https://huggingface.co/mayocream/manga-ocr-onnx/resolve/main/',
    'files': [
        'encoder_model.onnx', 'decoder_model.onnx', 'vocab.txt'
    ],
    'sha256_pre_calculated': [
        '15fa8155fe9bc1a7d25d9bb353debaa4def033d0174e907dbd2dd6d995def85f', 
        'ef7765261e9d1cdc34d89356986c2bbc2a082897f753a89605ae80fdfa61f5e8', 
        '5cb5c5586d98a2f331d9f8828e4586479b0611bfba5d8c3b6dadffc84d6a36a3', 
    ],
    'save_dir': os.path.join(models_base_dir, 'ocr', 'manga-ocr-base-onnx')
}

pororo_data = {
    'url': 'https://huggingface.co/ogkalu/pororo/resolve/main/',
    'files': ['craft.pt', 'brainocr.pt', 'ocr-opt.txt'],
    'sha256_pre_calculated': [
        '4a5efbfb48b4081100544e75e1e2b57f8de3d84f213004b14b85fd4b3748db17',
        '125820ba8ae4fa5d9fd8b8a2d4d4a7afe96a70c32b1aa01d4129001a6f61baec',
        'dd471474e91d78e54b179333439fea58158ad1a605df010ea0936dcf4387a8c2'
    ],
    'save_dir': os.path.join(models_base_dir, 'ocr', 'pororo')
}

mandatory_models = []