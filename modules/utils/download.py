import os, sys, hashlib
from torch.hub import download_url_to_file
from loguru import logger

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
        os.makedirs(save_dir)
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

# Default Models
manga_ocr_data = {
    'url': 'https://huggingface.co/kha-white/manga-ocr-base/resolve/main/',
    'files': [
        'pytorch_model.bin', 'config.json', 'preprocessor_config.json',
        'README.md', 'special_tokens_map.json', 'tokenizer_config.json', 'vocab.txt'
    ],
    'sha256_pre_calculated': [
        'c63e0bb5b3ff798c5991de18a8e0956c7ee6d1563aca6729029815eda6f5c2eb', 
        '415a232fcb9d55b84fe76d859ac75c97987b76c2082c9c13d7f0c6a18c01f30d', 
        'e362a7d398be17bfee021572bfa39f8f4ba6dbbaa1ef2e9bf617448161e6bbde', 
        '2caa041b755d311daa9f7710555f5eec2346272a360f9944d6a5e806b444fd81', 
        '303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3', 
        'd775ad1deac162dc56b84e9b8638f95ed8a1f263d0f56f4f40834e26e205e266', 
        '5cb5c5586d98a2f331d9f8828e4586479b0611bfba5d8c3b6dadffc84d6a36a3'
    ],
    'save_dir': 'models/ocr/manga-ocr-base'
}

comic_text_segmenter_data = {
    'url': 'https://huggingface.co/ogkalu/comic-text-segmenter-yolov8m/resolve/main/',
    'files': [
        'comic-text-segmenter.pt'],
    'sha256_pre_calculated': [
        'f2dded0d2f5aaa25eed49f1c34a4720f1c1cd40da8bc3138fde1abb202de625e', 
        ],
    'save_dir': 'models/detection'
}

inpaint_lama_finetuned_data = {
    'url': 'https://huggingface.co/dreMaz/AnimeMangaInpainting/resolve/main/',
    'files': [
        'lama_large_512px.ckpt'
    ],
    'sha256_pre_calculated': [
        "11d30fbb3000fb2eceae318b75d9ced9229d99ae990a7f8b3ac35c8d31f2c935"
    ],
    'save_dir': 'models/inpainting'
}

comic_bubble_detector_data = {
    'url': 'https://huggingface.co/ogkalu/comic-speech-bubble-detector-yolov8m/resolve/main/',
    'files': [
        'comic-speech-bubble-detector.pt'
    ],
    'sha256_pre_calculated': [
        '10bc9f702698148e079fb4462a6b910fcd69753e04838b54087ef91d5633097b'
    ],
    'save_dir': 'models/detection'  
}

models_data = [manga_ocr_data, comic_text_segmenter_data, inpaint_lama_finetuned_data, comic_bubble_detector_data]
