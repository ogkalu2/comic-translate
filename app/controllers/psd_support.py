"""Deferred loading for the optional native PhotoshopAPI dependency."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from types import ModuleType
from typing import Any


class PsdSupportUnavailableError(RuntimeError):
    """Raised when Photoshop import/export cannot be used on this system."""


@lru_cache(maxsize=1)
def _load_photoshopapi() -> ModuleType:
    return import_module("photoshopapi")


def require_photoshopapi() -> ModuleType:
    """Load PhotoshopAPI only when a PSD operation is requested."""
    try:
        return _load_photoshopapi()
    except Exception as exc:
        details = str(exc) or type(exc).__name__
        raise PsdSupportUnavailableError(
            "PSD import and export are unavailable because PhotoshopAPI could not be loaded. "
            "Other Comic Translate features can still be used. "
            f"Details: {details}"
        ) from exc


class _DeferredPhotoshopApi:
    """Proxy that preserves the existing PSD code while deferring the DLL import."""

    def __getattr__(self, name: str) -> Any:
        return getattr(require_photoshopapi(), name)


photoshopapi = _DeferredPhotoshopApi()