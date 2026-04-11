import hashlib
import logging
from typing import List
from pathlib import Path
from PIL import Image
import imagehash

logger = logging.getLogger(__name__)

def compute_base_fp(pages: List[str], title: str, artist: str) -> str:
    """
    Compute base fingerprint from perceptual hashes of all pages + normalized metadata.
    
    base_fp = sha256(perceptual_hash_all_pages + normalized_title + artist)
    
    Args:
        pages: List of page image paths. Will be sorted for deterministic ordering.
        title: Comic title (will be normalized to lowercase, stripped).
        artist: Artist name (will be normalized to lowercase, stripped).
    
    Returns:
        Hex digest of SHA256 hash.
    
    Raises:
        ValueError: If no pages could be hashed (all images corrupted/unreadable).
    """
    # Sort pages for deterministic ordering - base_fp represents the work,
    # not a specific ordering of pages
    sorted_pages = sorted(pages)
    
    # Compute perceptual hashes for all pages
    phashes = []
    failed_pages = []
    for page_path in sorted_pages:
        try:
            img = Image.open(page_path)
            phash = str(imagehash.phash(img))
            phashes.append(phash)
        except Exception as e:
            failed_pages.append((page_path, str(e)))
            continue
    
    # Warn about failed pages
    if failed_pages:
        logger.warning(f"Failed to hash {len(failed_pages)} page(s): {failed_pages}")
    
    # If ALL pages failed, we can't compute a meaningful fingerprint
    if not phashes:
        raise ValueError(
            f"Cannot compute base_fp: all {len(pages)} page images failed to hash. "
            f"Last errors: {failed_pages[-3:] if failed_pages else 'none'}"
        )
    
    # Normalize title and artist
    normalized_title = title.strip().lower()
    normalized_artist = artist.strip().lower()
    
    # Combine all components
    combined = "".join(phashes) + normalized_title + normalized_artist
    
    # SHA256 hash
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def file_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    """
    Compute SHA256 hash of a file using chunked reading.
    
    Avoids loading entire file into memory - safe for large archives (hundreds of MB).
    
    Args:
        path: Path to the file.
        chunk_size: Read chunk size in bytes (default 1MB).
    
    Returns:
        Hex digest of SHA256 hash.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_variant_fp(file_path: str, page_count: int, censor_signature: str, source: str) -> str:
    """
    Compute variant fingerprint from file hash + metadata.
    
    variant_fp = sha256(raw_file_hash + page_count + censor_signature + source)
    
    Uses chunked hashing to avoid memory spikes on large archive files.
    """
    # Compute file hash using chunked reading (safe for large files)
    file_hash = file_sha256(file_path)
    
    # Combine components
    combined = f"{file_hash}{page_count}{censor_signature}{source}"
    
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()
