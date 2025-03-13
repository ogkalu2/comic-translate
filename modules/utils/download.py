import os, sys, hashlib
from torch.hub import download_url_to_file
from loguru import logger

# Get the directory of the current file
current_file_dir = os.path.dirname(os.path.abspath(__file__))

# Navigate up two levels to reach the project root
project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))

# Define the base directory for all models
models_base_dir = os.path.join(project_root, 'models')

def calculate_sha256_checksum(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_models(data):
    # Check if the save directory exists; if not, create it
    save_dir = data['save_dir']
    if not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
        print(f"Created directory: {save_dir}")

    for i, file_name in enumerate(data['files']):
        file_url = f"{data['url']}{file_name}"

        file_path = os.path.join(data['save_dir'], file_name)
        expected_checksum = data['sha256_pre_calculated'][i]

        # Check if the file already exists
        if os.path.exists(file_path):

            # If there's an expected checksum, verify it
            if expected_checksum is not None:
                calculated_checksum = calculate_sha256_checksum(file_path)
                if calculated_checksum == expected_checksum:
                    continue
                else:
                    print(f"Checksum mismatch for {file_name}. Expected {expected_checksum}, got {calculated_checksum}. Redownloading...")

        sys.stderr.write('Downloading: "{}" to {}\n'.format(file_url, save_dir))
        download_url_to_file(file_url, file_path, hash_prefix=None, progress=True)

        if expected_checksum:
            calculated_checksum = calculate_sha256_checksum(file_path)
            if calculated_checksum == expected_checksum:
                    logger.info(f"Download model success, sha256: {calculated_checksum}")
            else:
                try:
                    os.remove(file_path)
                    logger.error(
                        f"Model sha256: {calculated_checksum}, expected sha256: {expected_checksum}, wrong model deleted. Please restart comic-translate."
                    )
                except:
                    logger.error(
                        f"Model sha256: {calculated_checksum}, expected sha256: {expected_checksum}, please delete {file_path} and restart comic-translate."
                    )
                exit(-1)

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

pororo_data = {
    'url': 'https://twg.kakaocdn.net/pororo/ko/models/misc/',
    'files': ['craft.pt', 'brainocr.pt', 'ocr-opt.txt'],
    'sha256_pre_calculated': [
        '4a5efbfb48b4081100544e75e1e2b57f8de3d84f213004b14b85fd4b3748db17',
        '125820ba8ae4fa5d9fd8b8a2d4d4a7afe96a70c32b1aa01d4129001a6f61baec',
        'dd471474e91d78e54b179333439fea58158ad1a605df010ea0936dcf4387a8c2'
    ],
    'save_dir': os.path.join(models_base_dir, 'ocr', 'pororo')
}

mandatory_models = []