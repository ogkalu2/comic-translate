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

import io
import json
import logging
import platform
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

Enhancer = Callable[[np.ndarray], np.ndarray]


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
        def _enhance(img: np.ndarray, *, _cfg: Waifu2xConfig = cfg) -> np.ndarray:
            return enhance_waifu2x_ncnn(img, _cfg)

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


def enhance_waifu2x_ncnn(img: np.ndarray, cfg: Waifu2xConfig) -> np.ndarray:
    """Run the official ``waifu2x-ncnn-vulkan`` CLI with the given settings."""

    binary = _ensure_waifu2x_binary()
    if not binary:
        return img

    arr = _ensure_uint8(img)
    pil_img = Image.fromarray(arr, mode="RGB")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        input_path = tmp_dir / "input.png"
        output_path = tmp_dir / "output.png"
        pil_img.save(input_path, format="PNG")

        cmd = [
            binary,
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

        try:
            completed = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(binary).parent,
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


def _ensure_waifu2x_binary() -> Optional[str]:
    """Return a usable waifu2x binary, attempting an automatic install if needed."""

    binary = shutil.which("waifu2x-ncnn-vulkan") or shutil.which("waifu2x-ncnn-vulkan.exe")
    if binary:
        return binary

    tag = "20250915"
    cache_dir = Path.home() / ".cache" / "comic-translater" / "waifu2x" / tag
    cache_dir.mkdir(parents=True, exist_ok=True)

    binary_name = "waifu2x-ncnn-vulkan.exe" if platform.system().lower().startswith("win") else "waifu2x-ncnn-vulkan"
    cached_binary = _find_cached_binary(cache_dir, binary_name)
    if cached_binary:
        return str(cached_binary)

    asset_url = _select_waifu2x_asset(tag)
    if not asset_url:
        logger.error(
            "waifu2x-ncnn-vulkan executable not available. Please install it from %s manually.",
            f"https://github.com/nihui/waifu2x-ncnn-vulkan/releases/tag/{tag}",
        )
        return None

    try:
        with urllib.request.urlopen(asset_url, timeout=60) as response:
            payload = response.read()
    except urllib.error.URLError as exc:
        logger.error("Failed to download waifu2x-ncnn-vulkan from %s: %s", asset_url, exc)
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(cache_dir)
    except zipfile.BadZipFile as exc:
        logger.error("Failed to unpack waifu2x-ncnn-vulkan archive: %s", exc)
        return None

    cached_binary = _find_cached_binary(cache_dir, binary_name)
    if not cached_binary:
        logger.error(
            "Downloaded waifu2x-ncnn-vulkan archive did not contain %s", binary_name
        )
        return None

    try:
        cached_binary.chmod(cached_binary.stat().st_mode | 0o111)
    except OSError:
        logger.debug("Unable to update execute permissions for %s", cached_binary)

    logger.info("Installed waifu2x-ncnn-vulkan to %s", cached_binary)
    return str(cached_binary)


def _find_cached_binary(root: Path, binary_name: str) -> Optional[Path]:
    """Locate a previously extracted waifu2x binary inside ``root``."""

    direct_path = root / binary_name
    if direct_path.exists():
        return direct_path

    for path in root.rglob(binary_name):
        if path.is_file():
            return path

    return None


def _select_waifu2x_asset(tag: str) -> Optional[str]:
    """Select the appropriate waifu2x asset download URL for the current system."""

    api_url = f"https://api.github.com/repos/nihui/waifu2x-ncnn-vulkan/releases/tags/{tag}"
    try:
        with urllib.request.urlopen(api_url, timeout=30) as response:
            release_data = json.load(response)
    except urllib.error.URLError as exc:
        logger.error("Failed to query waifu2x release metadata: %s", exc)
        return None

    assets = release_data.get("assets") or []
    if not assets:
        logger.error("No downloadable waifu2x assets found in release %s", tag)
        return None

    system = platform.system().lower()
    machine = platform.machine().lower()

    def _matches(asset_name: str) -> bool:
        name = asset_name.lower()
        if name.endswith(".zip"):
            if system.startswith("win") and "windows" in name:
                return True
            if system == "darwin" and "mac" in name:
                return True
            if system == "linux" and ("linux" in name or "ubuntu" in name):
                if "arm" in machine:
                    return "arm" in name
                return "arm" not in name
        return False

    for asset in assets:
        asset_name = asset.get("name") or ""
        if _matches(asset_name):
            return asset.get("browser_download_url")

    return None


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
