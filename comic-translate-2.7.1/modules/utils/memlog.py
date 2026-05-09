from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Any


def _rss_mb() -> float:
    """Return RSS in MB (best-effort)."""
    # Prefer psutil if available (it is in the dev venv).
    try:
        import psutil  # type: ignore

        p = psutil.Process(os.getpid())
        return float(p.memory_info().rss) / 1024.0 / 1024.0
    except Exception:
        pass

    # Fallback to Windows API (ctypes). Keep it optional and quiet on failure.
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("psapi")
        kernel32 = ctypes.WinDLL("kernel32")
        get_current_process = kernel32.GetCurrentProcess
        get_process_memory_info = psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        get_process_memory_info.restype = wintypes.BOOL

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ok = get_process_memory_info(get_current_process(), ctypes.byref(counters), counters.cb)
        if ok:
            return float(counters.WorkingSetSize) / 1024.0 / 1024.0
    except Exception:
        pass

    return -1.0


def _memory_maps_top(*, top_n: int = 12) -> list[dict[str, Any]]:
    """Return top memory-mapped modules by RSS (best-effort).

    This is expensive; only call for occasional deep snapshots.
    """
    try:
        import psutil  # type: ignore

        p = psutil.Process(os.getpid())
        maps = p.memory_maps(grouped=True)  # type: ignore[arg-type]
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for m in maps or []:
        try:
            rss = float(getattr(m, "rss", 0.0))
            path = str(getattr(m, "path", "") or "")
            if not path:
                continue
            items.append({"path": path, "rss_mb": round(rss / 1024.0 / 1024.0, 1)})
        except Exception:
            continue

    items.sort(key=lambda x: float(x.get("rss_mb") or 0.0), reverse=True)
    return items[: max(1, int(top_n))]


def _sum_numpy_nbytes(value: Any, *, max_items: int = 200_000) -> int:
    """Best-effort recursive sum of numpy array nbytes inside common containers."""
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None

    seen: set[int] = set()
    total = 0
    scanned = 0

    def _walk(v: Any) -> None:
        nonlocal total, scanned
        if v is None:
            return
        scanned += 1
        if scanned > max_items:
            return

        vid = id(v)
        if vid in seen:
            return
        seen.add(vid)

        if np is not None and isinstance(v, getattr(np, "ndarray")):
            try:
                total += int(v.nbytes)
            except Exception:
                pass
            return

        if isinstance(v, dict):
            for k, vv in v.items():
                _walk(k)
                _walk(vv)
            return

        if isinstance(v, (list, tuple, set)):
            for item in v:
                _walk(item)
            return

    _walk(value)
    return total


@dataclass
class MemLogger:
    """Memory logger for diagnosing RAM growth in long batch runs.

    Writes JSON lines to `<user_data_dir>/logs/memlog_<timestamp>_<pid>.jsonl`.

    Notes:
    - This is intentionally best-effort: failures must never break the app.
    - Interval can be overridden via env var `CT_MEMLOG_INTERVAL_SEC` (optional).
    """

    main: Any
    interval_sec: float = 5.0
    max_file_bytes: int = 50 * 1024 * 1024  # rotate after ~50MB per run

    def __post_init__(self) -> None:
        self._timer = None
        self._path = None
        self._run_id = None
        self._deep_emitted: set[str] = set()

    def _resolve_log_path(self) -> str:
        try:
            from modules.utils.paths import get_user_data_dir

            base = os.path.join(get_user_data_dir(), "logs")
        except Exception:
            base = os.path.join(getattr(self.main, "temp_dir", ""), "logs") or os.getcwd()
        os.makedirs(base, exist_ok=True)
        if not self._run_id:
            # Local time is fine; this is purely diagnostic.
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._run_id = f"{ts}_{os.getpid()}"
        return os.path.join(base, f"memlog_{self._run_id}.jsonl")

    def _rotate_if_needed(self) -> None:
        if not self._path:
            return
        try:
            if os.path.isfile(self._path) and os.path.getsize(self._path) > int(self.max_file_bytes):
                rotated = f"{self._path}.old"
                try:
                    if os.path.exists(rotated):
                        os.remove(rotated)
                except Exception:
                    pass
                try:
                    os.replace(self._path, rotated)
                except Exception:
                    pass
        except Exception:
            pass

    def _snapshot(self, tag: str) -> dict[str, Any]:
        ct = self.main

        image_data = getattr(ct, "image_data", None)
        in_mem_hist = getattr(ct, "in_memory_history", None)
        in_mem_patches = getattr(ct, "in_memory_patches", None)

        pipeline = getattr(ct, "pipeline", None)

        snap: dict[str, Any] = {
            "ts": time.time(),
            "tag": tag,
            "rss_mb": round(_rss_mb(), 1),
            "py": sys.version.split()[0],
            "onnxruntime_loaded": "onnxruntime" in sys.modules,
            "torch_loaded": "torch" in sys.modules,
            "modules_loaded": len(sys.modules),
            "cv2_loaded": "cv2" in sys.modules,
            "imkit_loaded": "imkit" in sys.modules,
            "image_files": len(getattr(ct, "image_files", []) or []),
            "image_states": len(getattr(ct, "image_states", {}) or {}),
            "image_data_slots": len(image_data or {}) if isinstance(image_data, dict) else None,
            "image_data_np_mb": round(_sum_numpy_nbytes(image_data) / 1024.0 / 1024.0, 1),
            "in_memory_history_np_mb": round(_sum_numpy_nbytes(in_mem_hist) / 1024.0 / 1024.0, 1),
            "in_memory_patches_np_mb": round(_sum_numpy_nbytes(in_mem_patches) / 1024.0 / 1024.0, 1),
        }

        try:
            cache_mgr = getattr(pipeline, "cache_manager", None) if pipeline else None
            if cache_mgr:
                snap["cache_ocr_keys"] = len(getattr(cache_mgr, "ocr_cache", {}) or {})
                snap["cache_translation_keys"] = len(getattr(cache_mgr, "translation_cache", {}) or {})
        except Exception:
            pass

        # Handler-level model caches (should not import anything).
        try:
            inpaint = getattr(pipeline, "inpainting", None) if pipeline else None
            snap["inpainting_cached"] = bool(getattr(inpaint, "inpainter_cache", None) is not None)
        except Exception:
            pass
        try:
            bd = getattr(pipeline, "block_detection", None) if pipeline else None
            snap["block_detector_cached"] = bool(getattr(bd, "block_detector_cache", None) is not None)
        except Exception:
            pass

        # Factory-level caches: only inspect if already imported to avoid inflating RSS.
        try:
            m = sys.modules.get("modules.detection.factory")
            if m and hasattr(m, "DetectionEngineFactory"):
                snap["detection_factory_engines"] = len(getattr(m.DetectionEngineFactory, "_engines", {}) or {})
        except Exception:
            pass
        try:
            m = sys.modules.get("modules.ocr.factory")
            if m and hasattr(m, "OCRFactory"):
                snap["ocr_factory_engines"] = len(getattr(m.OCRFactory, "_engines", {}) or {})
        except Exception:
            pass
        try:
            m = sys.modules.get("modules.translation.factory")
            if m and hasattr(m, "TranslationFactory"):
                snap["translation_factory_engines"] = len(getattr(m.TranslationFactory, "_engines", {}) or {})
        except Exception:
            pass

        return snap

    def emit(self, tag: str) -> None:
        if self._path is None:
            self._path = self._resolve_log_path()
        self._rotate_if_needed()
        payload = self._snapshot(tag)
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            # Never let diagnostics break the app.
            pass

    def emit_deep(self, tag: str, *, top_n: int = 12) -> None:
        """Emit a deep snapshot (includes top memory-mapped modules)."""
        # De-dupe per tag so accidental repeated calls don't spam logs.
        if tag in self._deep_emitted:
            return
        self._deep_emitted.add(tag)

        if self._path is None:
            self._path = self._resolve_log_path()
        self._rotate_if_needed()

        payload = self._snapshot(tag)
        try:
            payload["maps_top"] = _memory_maps_top(top_n=top_n)
        except Exception:
            pass

        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def start(self) -> None:
        # Import Qt lazily so tools/tests can import this module without PySide6.
        try:
            from PySide6 import QtCore  # type: ignore
        except Exception:
            return

        interval = os.environ.get("CT_MEMLOG_INTERVAL_SEC")
        if interval:
            try:
                self.interval_sec = max(0.5, float(interval))
            except Exception:
                pass

        self.emit("memlog_start")
        # One-shot deep snapshot shortly after startup to attribute idle RSS to DLLs.
        try:
            self.emit_deep("memlog_start_deep")
        except Exception:
            pass

        self._timer = QtCore.QTimer(self.main)
        self._timer.setSingleShot(False)
        self._timer.setInterval(int(self.interval_sec * 1000))
        self._timer.timeout.connect(lambda: self.emit("tick"))
        self._timer.start()

        # Another deep snapshot after the app has been idle for a bit.
        try:
            QtCore.QTimer.singleShot(15000, lambda: self.emit_deep("idle_15s_deep"))
        except Exception:
            pass
