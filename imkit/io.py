"""Image I/O operations for the imkit module."""

from __future__ import annotations
from io import BytesIO
import numpy as np
from PIL import Image
from .utils import ensure_uint8


def read_image(path: str) -> np.ndarray:
    """Read an image file and return as RGB numpy array."""
    im = Image.open(path)
    if im.mode in ("RGBA", "P"):  # convert palette/alpha
        im = im.convert("RGB")
    elif im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    arr = np.array(im)
    return arr


def write_image(path: str, array: np.ndarray) -> None:
    """Write a numpy array as an image file."""
    im = Image.fromarray(ensure_uint8(array))
    im.save(path)


def encode_image(array: np.ndarray, ext: str = ".png", **kwargs) -> bytes:
    """Encode a numpy array as image bytes."""
    if not ext.startswith('.'):
        ext = '.' + ext
    fmt = ext.lstrip('.').upper()
    im = Image.fromarray(ensure_uint8(array))
    buf = BytesIO()
    save_kwargs = {}
    if fmt in ("JPEG", "JPG"):
        save_kwargs.setdefault("quality", kwargs.get("quality", 95))
        save_kwargs.setdefault("optimize", True)
        # PIL only recognizes 'JPEG', not 'JPG'
        fmt = "JPEG" if fmt == "JPG" else fmt
    if fmt == "PNG":
        # Pillow uses 0 (no compression) to 9. Mirror cv2.IMWRITE_PNG_COMPRESSION default 3.
        save_kwargs.setdefault("compress_level", kwargs.get("compress_level", 3))
    im.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def decode_image(data: bytes) -> np.ndarray:
    """Decode image bytes to numpy array."""
    im = Image.open(BytesIO(data))
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    arr = np.array(im)
    # Preserve single-channel grayscale arrays (ndim == 2).
    return arr
