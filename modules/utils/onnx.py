from __future__ import annotations

from typing import Any, Optional
import onnxruntime as ort


def make_session_options(
    *, 
    log_severity_level: int = 3,
    low_mem: bool = True
) -> Any:
    """Create ONNXRuntime SessionOptions with optional low-memory toggles."""

    so = ort.SessionOptions()
    try:
        so.log_severity_level = int(log_severity_level)
    except Exception:
        pass

    # Default to low-memory mode (reduces peak RSS for large batches).
    if low_mem:
        # These options trade memory for speed; useful for huge batches.
        try:
            so.enable_mem_pattern = False
        except Exception:
            pass
        try:
            so.enable_cpu_mem_arena = False
        except Exception:
            pass

    return so


def make_session(
    model_path: str,
    *,
    providers: list[Any],
    sess_options: Optional[Any] = None,
) -> Any:
    """Create an ONNXRuntime InferenceSession honoring CT_ORT_* toggles."""
    so = sess_options if sess_options is not None else make_session_options()
    return ort.InferenceSession(model_path, sess_options=so, providers=providers)
