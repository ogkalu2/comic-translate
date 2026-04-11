"""
Fingerprint computation and cache lookup for multi-version comic processing.
"""

from .compute import compute_base_fp, compute_variant_fp
from .cache import (
    CacheLookup,
    CacheHitType,
    CacheResult,
    BaseCacheResult,
    MultiVersionDetector,
    VersionRelation
)

__all__ = [
    # Compute functions
    "compute_base_fp",
    "compute_variant_fp",
    # Cache classes
    "CacheLookup",
    "CacheHitType",
    "CacheResult",
    "BaseCacheResult",
    # Multi-version detection
    "MultiVersionDetector",
    "VersionRelation",
]
