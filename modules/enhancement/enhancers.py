"""Waifu2x-backed image enhancement helpers.

This module mirrors the configuration surface of popular waifu2x front-ends
such as https://www.waifu2x.net/, https://unlimited.waifu2x.net/ and the
official `waifu2x-ncnn-vulkan` utility.  Rather than approximating the
behaviour with simple filters, the helpers here delegate directly to the
reference implementations so users obtain the same quality improvements that
those tools provide.  The primary integration relies on the
``waifu2x-ncnn-vulkan`` CLI, with optional hooks for Python bindings and web
APIs when available.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

Enhancer = Callable[[np.ndarray], np.ndarray]

_WAIFU2X_NCNN_PATH: Optional[str] = None
_WAIFU2X_NCNN_RESOLVED = False
_WAIFU2X_NCNN_MISSING_WARNED = False
_WAIFU2X_DOWNLOAD_ATTEMPTED = False

_WAIFU2X_RELEASE_API = "https://api.github.com/repos/nihui/waifu2x-ncnn-vulkan/releases/latest"
_CACHE_ENV_OVERRIDE = "COMIC_TRANSLATER_CACHE_DIR"
_DEFAULT_CACHE_ROOT = Path.home() / ".cache" / "comic_translater" / "waifu2x"


@dataclass(frozen=True)
class Waifu2xConfig:
    """Normalized configuration for waifu2x engines."""

    engine: str = "disabled"
    model: str = "models-cunet"
    noise: int = 1
    scale: int = 2
    tta: bool = False
    keep_size: bool = True
    tile_size: int = 0
    format: str = "png"

    @staticmethod
    def from_raw(raw: Any) -> "Waifu2xConfig":
        """Convert raw user data into a ``Waifu2xConfig`` instance."""

        if raw is None:
            return Waifu2xConfig()
        if isinstance(raw, Waifu2xConfig):
            return raw
        if isinstance(raw, str):
            return Waifu2xConfig(engine=raw)
        if isinstance(raw, dict):
            engine = str(raw.get("engine", "disabled"))
            model = str(raw.get("model", "models-cunet"))
            noise = _coerce_noise(raw.get("noise", 1))
            scale = _coerce_scale(raw.get("scale", 2))
            tta = bool(raw.get("tta", False))
            keep_size = bool(raw.get("keep_size", True))
            tile_size = _coerce_int(raw.get("tile_size", 0), default=0, minimum=0, maximum=4096)
            fmt = str(raw.get("format", "png") or "png")
            return Waifu2xConfig(
                engine=engine,
                model=model,
                noise=noise,
                scale=scale,
                tta=tta,
                keep_size=keep_size,
                tile_size=tile_size,
                format=fmt,
            )
        return Waifu2xConfig(engine=str(raw))


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        if isinstance(value, str) and value.endswith("x"):
            value = value[:-1]
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, coerced))


def _coerce_noise(value: Any) -> int:
    return _coerce_int(value, default=1, minimum=-1, maximum=3)


def _coerce_scale(value: Any) -> int:
    return _coerce_int(value, default=2, minimum=1, maximum=32)


def _ensure_uint8(img: np.ndarray) -> np.ndarray:
    if img.dtype != np.uint8:
        return img.astype(np.uint8)
    return img


def _resolve_waifu2x_ncnn_binary() -> Optional[str]:
    """Locate the waifu2x-ncnn-vulkan executable once per process."""

    global _WAIFU2X_NCNN_PATH, _WAIFU2X_NCNN_RESOLVED

    if not _WAIFU2X_NCNN_RESOLVED:
        binary = shutil.which("waifu2x-ncnn-vulkan") or shutil.which("waifu2x-ncnn-vulkan.exe")
        if not binary:
            binary = _ensure_downloaded_waifu2x_ncnn()
        _WAIFU2X_NCNN_PATH = binary
        _WAIFU2X_NCNN_RESOLVED = True
        if binary:
            logger.debug("Resolved waifu2x-ncnn-vulkan binary at %s", binary)

    return _WAIFU2X_NCNN_PATH


def _waifu2x_cache_root() -> Path:
    override = os.getenv(_CACHE_ENV_OVERRIDE)
    if override:
        return Path(override).expanduser()
    return _DEFAULT_CACHE_ROOT


def _detect_platform_asset() -> Optional[tuple[str, str]]:
    system = platform.system().lower()
    if system.startswith("linux"):
        return "linux", "waifu2x-ncnn-vulkan"
    if system.startswith("windows"):
        return "windows", "waifu2x-ncnn-vulkan.exe"
    if system.startswith("darwin") or system.startswith("mac"):
        return "macos", "waifu2x-ncnn-vulkan"
    logger.warning("Automatic waifu2x download is not supported on platform '%s'", platform.system())
    return None


def _find_cached_binary(root: Path, binary_name: str) -> Optional[Path]:
    if not root.exists():
        return None
    for candidate in root.rglob(binary_name):
        if candidate.is_file():
            return candidate
    return None


def _ensure_downloaded_waifu2x_ncnn() -> Optional[str]:
    global _WAIFU2X_DOWNLOAD_ATTEMPTED

    platform_info = _detect_platform_asset()
    if not platform_info:
        return None

    platform_suffix, binary_name = platform_info
    cache_root = _waifu2x_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)

    cached = _find_cached_binary(cache_root, binary_name)
    if cached:
        return str(cached)

    if _WAIFU2X_DOWNLOAD_ATTEMPTED:
        return None

    _WAIFU2X_DOWNLOAD_ATTEMPTED = True

    release = _fetch_latest_release()
    if not release:
        return None

    asset = _select_release_asset(release, platform_suffix)
    if not asset:
        logger.error("No waifu2x asset available for platform '%s'", platform_suffix)
        return None

    version_tag = str(release.get("tag_name") or "latest")
    target_dir = cache_root / version_tag
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        archive_bytes = _download_asset(asset)
    except Exception as exc:  # pragma: no cover - network errors
        logger.error("Failed to download waifu2x package: %s", exc)
        return None

    if not archive_bytes:
        return None

    try:
        _extract_archive(archive_bytes, target_dir)
    except Exception as exc:  # pragma: no cover - archive errors
        logger.error("Failed to extract waifu2x package: %s", exc)
        return None

    cached = _find_cached_binary(target_dir, binary_name)
    if cached:
        _make_executable(cached)
        return str(cached)

    logger.error("Downloaded waifu2x package did not contain '%s'", binary_name)
    return None


def _fetch_latest_release() -> Optional[dict[str, Any]]:
    try:
        with urllib.request.urlopen(_WAIFU2X_RELEASE_API, timeout=15) as response:
            data = response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network errors
        logger.error("Unable to query waifu2x releases: %s", exc)
        return None

    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode waifu2x release metadata: %s", exc)
        return None


def _select_release_asset(release: dict[str, Any], platform_suffix: str) -> Optional[dict[str, Any]]:
    assets = release.get("assets") or []
    suffix = f"{platform_suffix}.zip"
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.endswith(suffix):
            return asset
    return None


def _download_asset(asset: dict[str, Any]) -> Optional[bytes]:
    url = asset.get("browser_download_url")
    name = asset.get("name")
    if not url or not name:
        return None

    logger.info("Downloading waifu2x package %s", name)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network errors
        logger.error("Failed to download %s: %s", url, exc)
        return None

    return data


def _extract_archive(archive_bytes: bytes, target_dir: Path) -> None:
    with zipfile.ZipFile(BytesIO(archive_bytes)) as zf:
        zf.extractall(target_dir)


def _make_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:  # pragma: no cover - permission issues
        logger.debug("Unable to adjust permissions for %s", path)


def _warn_missing_waifu2x() -> None:
    """Emit a user-facing warning once when the CLI cannot be located."""

    global _WAIFU2X_NCNN_MISSING_WARNED

    if not _WAIFU2X_NCNN_MISSING_WARNED:
        logger.warning(
            "waifu2x-ncnn-vulkan executable not available. Automatic download failed; install it manually from %s and ensure it is on the PATH.",
            "https://github.com/nihui/waifu2x-ncnn-vulkan/releases",
        )
        _WAIFU2X_NCNN_MISSING_WARNED = True


def get_enhancer(config: Any) -> Optional[Enhancer]:
    """Return an enhancer callable based on the supplied configuration."""

    cfg = Waifu2xConfig.from_raw(config)
    engine = cfg.engine.strip().lower()

    if engine in {"", "disabled", "none", "off"}:
        return None

    if engine in {
        "waifu2x-ncnn-vulkan",
        "waifu2x ncnn vulkan",
        "waifu2x_ncnn_vulkan",
    }:
        binary = _resolve_waifu2x_ncnn_binary()
        if not binary:
            _warn_missing_waifu2x()
            return None

        def _enhance(img: np.ndarray, *, _cfg: Waifu2xConfig = cfg) -> np.ndarray:
            return enhance_waifu2x_ncnn(img, _cfg, binary=binary)

        return _enhance

    if engine in {"waifu2x-converter", "waifu2x python", "waifu2x (python)"}:
        def _enhance_python(img: np.ndarray, *, _cfg: Waifu2xConfig = cfg) -> np.ndarray:
            return enhance_waifu2x_python(img, _cfg)

        return _enhance_python

    if engine in {"waifu2x-unlimited", "waifu2x unlimited", "waifu2x (web api)"}:
        def _enhance_api(img: np.ndarray, *, _cfg: Waifu2xConfig = cfg) -> np.ndarray:
            return enhance_waifu2x_unlimited(img, _cfg)

        return _enhance_api

    logger.warning("Unknown image enhancer engine '%s'; enhancement disabled.", cfg.engine)
    return None


def enhance_waifu2x_ncnn(
    img: np.ndarray,
    cfg: Waifu2xConfig,
    *,
    binary: Optional[str] = None,
) -> np.ndarray:
    """Run the official ``waifu2x-ncnn-vulkan`` CLI with the given settings."""

    binary_path = binary or _resolve_waifu2x_ncnn_binary()
    if not binary_path:
        _warn_missing_waifu2x()
        return img

    arr = _ensure_uint8(img)
    pil_img = Image.fromarray(arr, mode="RGB")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        input_path = tmp_dir / "input.png"
        output_path = tmp_dir / "output.png"
        pil_img.save(input_path, format="PNG")

        cmd = [
            binary_path,
            "-i",
            str(input_path),
            "-o",
            str(output_path),
            "-n",
            str(cfg.noise),
            "-s",
            str(cfg.scale),
        ]

        if cfg.tile_size:
            cmd.extend(["-t", str(cfg.tile_size)])
        if cfg.model:
            cmd.extend(["-m", cfg.model])
        if cfg.tta:
            cmd.append("-x")
        if cfg.format:
            cmd.extend(["-f", cfg.format])

        logger.debug("Executing waifu2x-ncnn-vulkan: %s", " ".join(cmd))

        cwd = str(Path(binary_path).parent)

        try:
            completed = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
            )
            if completed.stdout:
                logger.debug("waifu2x stdout: %s", completed.stdout.strip())
            if completed.stderr:
                logger.debug("waifu2x stderr: %s", completed.stderr.strip())
        except FileNotFoundError:
            logger.error("waifu2x-ncnn-vulkan binary disappeared while executing.")
            return arr
        except subprocess.CalledProcessError as exc:
            logger.error(
                "waifu2x-ncnn-vulkan failed with exit code %s: %s",
                exc.returncode,
                exc.stderr.strip(),
            )
            return arr

        if not output_path.exists():
            logger.error("waifu2x-ncnn-vulkan did not create an output image at %s", output_path)
            return arr

        enhanced = Image.open(output_path).convert("RGB")
        if cfg.keep_size and enhanced.size != pil_img.size:
            enhanced = enhanced.resize(pil_img.size, Image.LANCZOS)

        return np.array(enhanced)


def enhance_waifu2x_python(img: np.ndarray, cfg: Waifu2xConfig) -> np.ndarray:
    """Attempt to call a Python waifu2x binding, falling back to the CLI."""

    try:
        from waifu2x import Waifu2x  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency path
        logger.warning("Python waifu2x bindings unavailable: %s", exc)
        return enhance_waifu2x_ncnn(img, cfg)

    arr = _ensure_uint8(img)
    try:
        engine = Waifu2x(
            scale=cfg.scale,
            noise=cfg.noise,
            model=cfg.model,
            tta=cfg.tta,
        )
    except TypeError as exc:  # pragma: no cover - depends on third party API
        logger.error("Unsupported waifu2x Python binding arguments: %s", exc)
        return enhance_waifu2x_ncnn(img, cfg)

    try:
        enhanced = engine.process(arr)
    except Exception as exc:  # pragma: no cover - depends on third party API
        logger.error("waifu2x Python processing failed: %s", exc)
        return enhance_waifu2x_ncnn(img, cfg)

    if cfg.keep_size and (
        enhanced.shape[0] != arr.shape[0] or enhanced.shape[1] != arr.shape[1]
    ):
        enhanced_img = Image.fromarray(enhanced.astype(np.uint8), mode="RGB")
        enhanced_img = enhanced_img.resize((arr.shape[1], arr.shape[0]), Image.LANCZOS)
        return np.array(enhanced_img)

    return enhanced.astype(np.uint8)


def enhance_waifu2x_unlimited(img: np.ndarray, cfg: Waifu2xConfig) -> np.ndarray:
    """Proxy to the waifu2x Unlimited web API when ``requests`` is available."""

    try:
        import requests
    except Exception as exc:  # pragma: no cover - optional dependency path
        logger.warning("The requests library is required for waifu2x Unlimited: %s", exc)
        return enhance_waifu2x_ncnn(img, cfg)

    arr = _ensure_uint8(img)
    pil_img = Image.fromarray(arr, mode="RGB")

    with tempfile.NamedTemporaryFile(suffix=".png") as tmp_in, tempfile.NamedTemporaryFile(suffix=".png") as tmp_out:
        pil_img.save(tmp_in.name, format="PNG")
        tmp_in.flush()

        files = {"file": ("image.png", open(tmp_in.name, "rb"), "image/png")}
        data = {
            "noise": str(cfg.noise),
            "scale": str(cfg.scale),
            "tta": "1" if cfg.tta else "0",
        }

        try:
            response = requests.post(
                "https://api.waifu2x.net/",
                data=data,
                files=files,
                timeout=120,
            )
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failures
            logger.error("waifu2x Unlimited request failed: %s", exc)
            return arr
        finally:
            files["file"][1].close()

        tmp_out.write(response.content)
        tmp_out.flush()

        try:
            enhanced = Image.open(tmp_out.name).convert("RGB")
        except Exception as exc:  # pragma: no cover - network failures
            logger.error("Failed to decode waifu2x Unlimited response: %s", exc)
            return arr
        if cfg.keep_size and enhanced.size != pil_img.size:
            enhanced = enhanced.resize(pil_img.size, Image.LANCZOS)

        return np.array(enhanced)
