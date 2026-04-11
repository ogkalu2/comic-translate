from .noop import NoopApplicator
from .json_patch import JsonPatchApplicator

__all__ = ["NoopApplicator", "JsonPatchApplicator"]

# CacheApplicator (requires pipeline.cache_v2 module)
try:
    from .cache_applicator import CacheApplicator
    __all__.append("CacheApplicator")
except ImportError:
    pass
