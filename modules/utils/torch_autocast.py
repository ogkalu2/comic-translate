from __future__ import annotations

from contextlib import nullcontext
from typing import Any, Callable


def configure_torch_autocast(torch_module: Any, device: str) -> tuple[str, Any, bool]:
    device_type = str(device).split(":", 1)[0].lower()
    use_autocast = (
        device_type != "cpu"
        and torch_module.amp.autocast_mode.is_autocast_available(device_type)
    )
    dtype = torch_module.float16
    if device_type == "xpu" and hasattr(torch_module, "bfloat16"):
        # Intel XPU TorchScript paths may reject Half for FFT-backed models like LaMa.
        dtype = torch_module.bfloat16
    return device_type, dtype, use_autocast


def autocast_context(torch_module: Any, enabled: bool, device_type: str, dtype: Any):
    if not enabled:
        return nullcontext()
    return torch_module.autocast(device_type=device_type, dtype=dtype)


def run_with_optional_autocast(
    *,
    torch_module: Any,
    fn: Callable[[], Any],
    enabled: bool,
    device_type: str,
    dtype: Any,
    logger: Any,
    engine_name: str,
) -> tuple[Any, bool]:
    try:
        with autocast_context(torch_module, enabled, device_type, dtype):
            return fn(), enabled
    except Exception:
        if not enabled:
            raise
        logger.warning(
            "Disabling %s autocast for device '%s' after runtime failure.",
            engine_name,
            device_type,
            exc_info=True,
        )
        return fn(), False


class TorchAutocastMixin:
    autocast_device_type: str = "cpu"
    autocast_dtype: Any = None
    use_autocast: bool = False

    def setup_torch_autocast(self, torch_module: Any, device: str) -> None:
        (
            self.autocast_device_type,
            self.autocast_dtype,
            self.use_autocast,
        ) = configure_torch_autocast(torch_module, device)

    def run_with_torch_autocast(
        self,
        *,
        torch_module: Any,
        fn: Callable[[], Any],
        logger: Any,
        engine_name: str,
    ) -> Any:
        result, self.use_autocast = run_with_optional_autocast(
            torch_module=torch_module,
            fn=fn,
            enabled=self.use_autocast,
            device_type=self.autocast_device_type,
            dtype=self.autocast_dtype,
            logger=logger,
            engine_name=engine_name,
        )
        return result
