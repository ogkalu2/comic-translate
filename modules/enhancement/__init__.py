"""
Image enhancement utilities for Comic Translate.

This package exposes helper functions to improve the quality of images before
running text detection. Enhancement can include denoising, sharpening and
super‑resolution.  The default implementation uses only the Python standard
library and Pillow to avoid introducing heavy dependencies.  Additional
enhancers such as waifu2x or nunif can be added in the future by defining a
new function and mapping it in ``get_enhancer``.
"""

from .enhancers import get_enhancer

__all__ = ["get_enhancer"]
