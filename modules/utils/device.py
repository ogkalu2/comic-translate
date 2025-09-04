from __future__ import annotations

from typing import Any, Mapping
import torch


def resolve_device(use_gpu: bool) -> str:
    """Return the best available device string.

    Priority when use_gpu is True:
    1) CUDA (NVIDIA)
    2) MPS (Apple Silicon)
    3) XPU (Intel GPU)
    Fallback: CPU
    """
    if not use_gpu:
        return "cpu"

    # CUDA (NVIDIA)
    try:
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass

    # MPS (Apple)
    try:
        if getattr(torch.backends, "mps", None) is not None:
            if torch.backends.mps.is_available():
                return "mps"
    except Exception:
        pass

    # XPU (Intel)
    try:
        if hasattr(torch, "xpu") and callable(getattr(torch.xpu, "is_available", None)):
            if torch.xpu.is_available():
                return "xpu"
    except Exception:
        pass

    return "cpu"


def tensors_to_device(data: Any, device: str) -> Any:
    """Move tensors in nested containers to device; returns the same structure.

    Supports dict, list/tuple, and tensors. Other objects are returned as-is.
    """
    import torch

    if isinstance(data, torch.Tensor):
        return data.to(device)
    if isinstance(data, Mapping):
        return {k: tensors_to_device(v, device) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        seq = [tensors_to_device(v, device) for v in data]
        return type(data)(seq) if isinstance(data, tuple) else seq
    return data
