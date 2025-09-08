from __future__ import annotations

from typing import Any, Mapping, Optional
import onnxruntime as ort


def resolve_device(use_gpu: bool) -> str:
    """Return the best available device string.

    Priority when use_gpu is True:
    We resolve device without by inspecting available
    ONNXRuntime providers.
    """
    if not use_gpu:
        return "cpu"

    providers = ort.get_available_providers() 

    if not providers:
        return "cpu"

    # Prefer CUDA when available
    if "CUDAExecutionProvider" in providers:
        return "cuda"

    # CoreML (Apple) - available as 'CoreMLExecutionProvider'
    if "CoreMLExecutionProvider" in providers:
        return "coreml"
    
    if "ROCMExecutionProvider" in providers:
        return "rocm"

    # XNNPACK (mobile/CPU optimized) - appear as 'XnnpackExecutionProvider'
    if "XnnpackExecutionProvider" in providers:
        return "xnnpack"

    # OpenVINO / other accelerators
    if "OpenVINOExecutionProvider" in providers:
        return "openvino"

    # Fallback to CPU
    return "cpu"

def tensors_to_device(data: Any, device: str) -> Any:
    """Move tensors in nested containers to device; returns the same structure.
    Supports dict, list/tuple, and tensors. Other objects are returned as-is.
    """
    try:
        import torch
    except Exception:
        # Torch is not available; return data unchanged
        return data

    # Map unknown device strings (onnx-driven) to torch-compatible device
    torch_device = device
    if isinstance(device, str):
        low = device.lower()
        if low in ("cpu", "cuda", "mps", "xpu"):
            torch_device = low
        else:
            # Unknown or ONNX-specific device -> fallback to cpu for torch tensors
            torch_device = "cpu"

    if isinstance(data, torch.Tensor):
        return data.to(torch_device)
    if isinstance(data, Mapping):
        return {k: tensors_to_device(v, device) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        seq = [tensors_to_device(v, device) for v in data]
        return type(data)(seq) if isinstance(data, tuple) else seq
    return data

def get_providers(device: Optional[str] = None) -> list[str]:
    """Return a provider list for ONNXRuntime.

    Rules:
    - If device is the string 'cpu' (case-insensitive) -> return ['CPUExecutionProvider']
    - Otherwise return ort.get_available_providers() if non-empty, else fall back to ['CPUExecutionProvider']
    """
    try:
        available = ort.get_available_providers()
    except Exception:
        available = []

    if device and isinstance(device, str) and device.lower() == 'cpu':
        return ['CPUExecutionProvider']

    return available if available else ['CPUExecutionProvider']
