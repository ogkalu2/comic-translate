from __future__ import annotations

from typing import Any, Mapping, Optional
import onnxruntime as ort


def torch_available() -> bool:
    """Check if torch is available without raising import errors."""
    try:
        import torch
        return True
    except ImportError:
        return False


def resolve_device(use_gpu: bool, backend: str = "onnx") -> str:
    """Return the best available device string for the specified backend.

    Args:
        use_gpu: Whether to use GPU acceleration
        backend: Backend to use ('onnx' or 'torch')

    Returns:
        Device string compatible with the specified backend
    """
    if not use_gpu:
        return "cpu"

    if backend.lower() == "torch":
        return _resolve_torch_device(fallback_to_onnx=True)
    else:
        return _resolve_onnx_device()


def _resolve_torch_device(fallback_to_onnx: bool = False) -> str:
    """Resolve the best available PyTorch device."""
    try:
        import torch
    except ImportError:
        # Torch not available, fallback to ONNX resolution if requested
        if fallback_to_onnx:
            return _resolve_onnx_device()
        return "cpu"

    # Check for MPS (Apple Silicon)
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"

    # Check for CUDA
    if torch.cuda.is_available():
        return "cuda"

    # Check for XPU (Intel GPU)
    try:
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            return "xpu"
    except Exception:
        pass

    # Fallback to CPU
    return "cpu"


def _resolve_onnx_device() -> str:
    """Resolve the best available ONNX device."""
    providers = ort.get_available_providers() 

    if not providers:
        return "cpu"

    if "CUDAExecutionProvider" in providers:
        return "cuda"

    if "CoreMLExecutionProvider" in providers:
        return "coreml"
    
    if "ROCMExecutionProvider" in providers:
        return "rocm"

    if "XnnpackExecutionProvider" in providers:
        return "xnnpack"

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
    - If device is 'cpu', return ['CPUExecutionProvider']
    - If device specifies a GPU type, prioritize the corresponding provider
    - Otherwise return all available providers
    """
    try:
        available = ort.get_available_providers()
    except Exception:
        available = []

    if not available:
        return ['CPUExecutionProvider']

    if not device:
        return available

    device_lower = device.lower()
    
    # Force CPU
    if device_lower == 'cpu':
        return ['CPUExecutionProvider']
    
    # Map device types to their corresponding ONNX providers
    device_provider_map = {
        'cuda': 'CUDAExecutionProvider',
        'coreml': 'CoreMLExecutionProvider',
        'rocm': 'ROCMExecutionProvider',
    }
    
    # Prioritize the provider for the specified device
    target_provider = device_provider_map.get(device_lower)
    if target_provider and target_provider in available:
        # Put target provider first, then add others as fallback
        return [target_provider] + [p for p in available if p != target_provider]

    return available
