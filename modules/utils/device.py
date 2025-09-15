from __future__ import annotations
from typing import Any, Mapping, Optional
import os
import onnxruntime as ort
from dotenv import load_dotenv
# Options:DEVICE= cpu, gpu0, gpu1, gpu2, cuda, coreml, rocm, xnnpack, openvino
load_dotenv()

def resolve_device(use_gpu: bool = None) -> str:
    """Return the best available device string.
    
    Priority:
    1. DEVICE environment variable (cpu, gpu0, gpu1, etc.)
    2. use_gpu parameter
    3. Automatic detection based on available providers
    """
    device_env = os.getenv('DEVICE', '').lower()
    
    if device_env:
        if device_env == 'cpu':
            return "cpu"
        elif device_env.startswith('gpu'):
            gpu_id = device_env.replace('gpu', '') or '0'
            return f"cuda:{gpu_id}" if _is_cuda_available() else "cpu"
        elif device_env in ['cuda', 'coreml', 'rocm', 'xnnpack', 'openvino']:
            return device_env
    
    if use_gpu is False:
        return "cpu"
    
    if use_gpu is None:
        use_gpu = True
    
    if not use_gpu:
        return "cpu"
    
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
    
    return "cpu"

def _is_cuda_available() -> bool:
    """Check if CUDA is available in ONNX Runtime providers."""
    try:
        providers = ort.get_available_providers()
        return "CUDAExecutionProvider" in providers
    except Exception:
        return False

def tensors_to_device(data: Any, device: str) -> Any:
    """Move tensors in nested containers to device; returns the same structure.
    Supports dict, list/tuple, and tensors. Other objects are returned as-is.
    """
    try:
        import torch
    except Exception:
        return data
    
    torch_device = _map_device_to_torch(device)
    
    if isinstance(data, torch.Tensor):
        return data.to(torch_device)
    if isinstance(data, Mapping):
        return {k: tensors_to_device(v, device) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        seq = [tensors_to_device(v, device) for v in data]
        return type(data)(seq) if isinstance(data, tuple) else seq
    return data

def _map_device_to_torch(device: str) -> str:
    """Map ONNX device strings to torch-compatible device strings."""
    if isinstance(device, str):
        low = device.lower()
        if low in ("cpu", "mps", "xpu"):
            return low
        elif low == "cuda" or low.startswith("cuda:"):
            return device
        else:
            return "cpu"
    return "cpu"

def get_providers(device: Optional[str] = None) -> list[str]:
    """Return a provider list for ONNXRuntime.
    
    Rules:
    - If device is 'cpu' -> return ['CPUExecutionProvider']
    - If device is 'cuda' or 'cuda:X' -> return CUDA provider with device_id
    - Otherwise return available providers or fallback to CPU
    """
    try:
        available = ort.get_available_providers()
    except Exception:
        available = []
    
    if device and isinstance(device, str):
        device_lower = device.lower()
        
        if device_lower == 'cpu':
            return ['CPUExecutionProvider']
        
        if device_lower == 'cuda' or device_lower.startswith('cuda:'):
            if 'CUDAExecutionProvider' in available:
                gpu_id = 0
                if ':' in device_lower:
                    try:
                        gpu_id = int(device_lower.split(':')[1])
                    except (ValueError, IndexError):
                        gpu_id = 0
                
                return [('CUDAExecutionProvider', {'device_id': gpu_id}), 'CPUExecutionProvider']
            else:
                return ['CPUExecutionProvider']
        
        if device_lower == 'coreml' and 'CoreMLExecutionProvider' in available:
            return ['CoreMLExecutionProvider', 'CPUExecutionProvider']
        
        if device_lower == 'rocm' and 'ROCMExecutionProvider' in available:
            return ['ROCMExecutionProvider', 'CPUExecutionProvider']
        
        if device_lower == 'xnnpack' and 'XnnpackExecutionProvider' in available:
            return ['XnnpackExecutionProvider', 'CPUExecutionProvider']
        
        if device_lower == 'openvino' and 'OpenVINOExecutionProvider' in available:
            return ['OpenVINOExecutionProvider', 'CPUExecutionProvider']
    
    return available if available else ['CPUExecutionProvider']

def get_current_device() -> str:
    """Get the currently configured device."""
    return resolve_device()

def list_available_devices() -> dict[str, bool]:
    """List all available devices and their availability status."""
    providers = ort.get_available_providers()
    
    devices = {
        'cpu': True,
        'cuda': 'CUDAExecutionProvider' in providers,
        'coreml': 'CoreMLExecutionProvider' in providers,
        'rocm': 'ROCMExecutionProvider' in providers,
        'xnnpack': 'XnnpackExecutionProvider' in providers,
        'openvino': 'OpenVINOExecutionProvider' in providers,
    }
    
    if devices['cuda']:
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                for i in range(gpu_count):
                    devices[f'gpu{i}'] = True
        except Exception:
            pass
    
    return devices