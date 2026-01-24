from __future__ import annotations

import os
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
    
    if "TensorrtExecutionProvider" in providers:
        return "tensorrt"

    if "CoreMLExecutionProvider" in providers:
        return "coreml"
    
    if "ROCMExecutionProvider" in providers:
        return "rocm"

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

def get_providers(device: Optional[str] = None) -> list[Any]:
    """Return a providers list for ONNXRuntime (optionally with provider options).

    Rules:
    - If device is the string 'cpu' (case-insensitive) -> return ['CPUExecutionProvider']
    - Otherwise return available providers with options for certain GPU providers
    - If no providers are available, fall back to ['CPUExecutionProvider']
    """
    try:
        available = ort.get_available_providers()
    except Exception:
        available = []

    if device and isinstance(device, str) and device.lower() == 'cpu':
        return ['CPUExecutionProvider']

    if not available:
        return ['CPUExecutionProvider']

    
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_file_dir, '..', '..'))
    
    # OpenVINO cache
    ov_cache_dir = os.path.join(project_root, 'models', 'onnx-gpu-cache', 'openvino')
    os.makedirs(ov_cache_dir, exist_ok=True)

    # TensorRT cache
    trt_cache_dir = os.path.join(project_root, 'models', 'onnx-gpu-cache', 'tensorrt')
    os.makedirs(trt_cache_dir, exist_ok=True)

    # CoreML cache
    coreml_cache_dir = os.path.join(project_root, 'models', 'onnx-gpu-cache', 'coreml')
    os.makedirs(coreml_cache_dir, exist_ok=True)

    provider_options = {
        'OpenVINOExecutionProvider': {
            'device_type': 'GPU',
            'precision': 'FP32',
            'cache_dir': ov_cache_dir,
        },
        'TensorrtExecutionProvider': {
            'trt_engine_cache_enable': True,
            'trt_engine_cache_path': trt_cache_dir,
        },
        'CoreMLExecutionProvider': {
            'ModelCacheDirectory': coreml_cache_dir,
        }
    }

    configured: list[Any] = []
    for p in available:
        if p in provider_options:
            configured.append((p, provider_options[p]))
        else:
            configured.append(p)

    return configured


def is_gpu_available() -> bool:
    """Check if a valid GPU provider is available.
    
    Returns False if only AzureExecutionProvider and/or CPUExecutionProvider are present.
    Returns True if any other provider (CUDA, CoreML, etc.) is found.
    """
    try:
        providers = ort.get_available_providers()
    except Exception:
        return False

    ignored_providers = {'AzureExecutionProvider', 'CPUExecutionProvider'}
    available = set(providers)
    
    # If the only available providers are in the ignored list, return False
    # logic: if available is a subset of ignored_providers, then we have nothing else.
    if available.issubset(ignored_providers):
        return False
        
    return True
