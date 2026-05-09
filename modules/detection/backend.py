from ..utils.device import torch_available


DEFAULT_DETECTION_BACKEND = "onnx"


def resolve_detection_backend(backend: str | None = None) -> str:
    effective_backend = (backend or DEFAULT_DETECTION_BACKEND).lower()
    if effective_backend == "torch" and not torch_available():
        return "onnx"
    return effective_backend
