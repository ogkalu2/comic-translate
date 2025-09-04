"""Lightweight monkey-patches to surface third-party model/file downloads.

This wraps common download entry points so we can emit UI notifications via
modules.utils.download.notify_download_event without coupling to those libs.

Idempotent and optional: patches only apply if the target libraries are present.
"""

from __future__ import annotations

import os
from typing import Callable

_installed = False
_active_names: set[str] = set()


def _basename_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return os.path.basename(urlparse(url).path) or url
    except Exception:
        return url


def _notify_start(notify: Callable[[str, str], None], name: str) -> bool:
    """Notify start if not already active; returns True if we should send end later."""
    try:
        if name in _active_names:
            return False
        _active_names.add(name)
        notify("start", name)
        return True
    except Exception:
        return False


def _notify_end(notify: Callable[[str, str], None], name: str, started: bool) -> None:
    if not started:
        return
    try:
        notify("end", name)
    except Exception:
        pass
    finally:
        _active_names.discard(name)


def install_third_party_download_hooks(notify: Callable[[str, str], None]) -> None:
    """Install monkey-patches into common third-party download functions.

    Safe to call multiple times; patches only once.
    """
    global _installed
    if _installed:
        return

    # 1) Hugging Face Hub (transformers often uses this under the hood)
    try:
        import huggingface_hub as hf

        if hasattr(hf, "hf_hub_download") and not getattr(hf.hf_hub_download, "__ct_patched__", False):
            _orig_hf_hub_download = hf.hf_hub_download

            def _hf_hub_download_wrapper(*args, **kwargs):
                filename = kwargs.get("filename")
                if filename is None and len(args) >= 2:
                    filename = args[1]
                short = os.path.basename(filename) if filename else "huggingface-file"
                _started = _notify_start(notify, short)
                try:
                    return _orig_hf_hub_download(*args, **kwargs)
                finally:
                    _notify_end(notify, short, _started)

            _hf_hub_download_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            hf.hf_hub_download = _hf_hub_download_wrapper  # type: ignore[assignment]

        if hasattr(hf, "snapshot_download") and not getattr(hf.snapshot_download, "__ct_patched__", False):
            _orig_snapshot_download = hf.snapshot_download

            def _snapshot_download_wrapper(*args, **kwargs):
                name = "huggingface-snapshot"
                _started = _notify_start(notify, name)
                try:
                    return _orig_snapshot_download(*args, **kwargs)
                finally:
                    _notify_end(notify, name, _started)

            _snapshot_download_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            hf.snapshot_download = _snapshot_download_wrapper  # type: ignore[assignment]
    except Exception:
        pass

    # 1b) Some call sites import from huggingface_hub.file_download directly
    try:
        import huggingface_hub.file_download as hffd

        if hasattr(hffd, "hf_hub_download") and not getattr(hffd.hf_hub_download, "__ct_patched__", False):
            _orig_hffd_hf = hffd.hf_hub_download

            def _hffd_hf_wrapper(*args, **kwargs):
                filename = kwargs.get("filename")
                if filename is None and len(args) >= 2:
                    filename = args[1]
                short = os.path.basename(filename) if filename else "huggingface-file"
                _started = _notify_start(notify, short)
                try:
                    return _orig_hffd_hf(*args, **kwargs)
                finally:
                    _notify_end(notify, short, _started)

            _hffd_hf_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            hffd.hf_hub_download = _hffd_hf_wrapper  # type: ignore[assignment]

        if hasattr(hffd, "snapshot_download") and not getattr(hffd.snapshot_download, "__ct_patched__", False):
            _orig_hffd_snap = hffd.snapshot_download

            def _hffd_snap_wrapper(*args, **kwargs):
                name = "huggingface-snapshot"
                _started = _notify_start(notify, name)
                try:
                    return _orig_hffd_snap(*args, **kwargs)
                finally:
                    _notify_end(notify, name, _started)

            _hffd_snap_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            hffd.snapshot_download = _hffd_snap_wrapper  # type: ignore[assignment]
    except Exception:
        pass

    # 1c) Newer huggingface_hub splits snapshot_download into a private module
    try:
        import importlib
        hfsnap = importlib.import_module("huggingface_hub._snapshot_download")
        if hasattr(hfsnap, "snapshot_download") and not getattr(hfsnap.snapshot_download, "__ct_patched__", False):
            _orig_hfsnap = hfsnap.snapshot_download

            def _hfsnap_wrapper(*args, **kwargs):
                name = "huggingface-snapshot"
                _started = _notify_start(notify, name)
                try:
                    return _orig_hfsnap(*args, **kwargs)
                finally:
                    _notify_end(notify, name, _started)

            _hfsnap_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            hfsnap.snapshot_download = _hfsnap_wrapper  # type: ignore[assignment]
    except Exception:
        pass

    # 2) torch.hub.download_url_to_file
    try:
        import torch.hub as th

        if hasattr(th, "download_url_to_file") and not getattr(th.download_url_to_file, "__ct_patched__", False):
            _orig_th_download = th.download_url_to_file

            def _th_download_wrapper(url, *args, **kwargs):
                short = _basename_from_url(url)
                _started = _notify_start(notify, short)
                try:
                    return _orig_th_download(url, *args, **kwargs)
                finally:
                    _notify_end(notify, short, _started)

            _th_download_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            th.download_url_to_file = _th_download_wrapper  # type: ignore[assignment]
    except Exception:
        pass

    # 3) DocTR (python-doctr) download helper
    #    DocTR uses doctr.utils.data.download_from_url to fetch weights/assets.
    try:
        import importlib
        dd = importlib.import_module("doctr.utils.data")

        if hasattr(dd, "download_from_url") and not getattr(dd.download_from_url, "__ct_patched__", False):
            _orig_doctr_download = dd.download_from_url

            def _doctr_download_wrapper(*args, **kwargs):
                # Extract a friendly name: prefer provided file_name, else derive from URL
                file_name = kwargs.get("file_name")
                if file_name is None and len(args) >= 2:
                    file_name = args[1]
                url = kwargs.get("url") if "url" in kwargs else (args[0] if args else None)

                if isinstance(file_name, str) and file_name:
                    short = os.path.basename(file_name)
                else:
                    short = _basename_from_url(url) if isinstance(url, str) else "doctr-file"

                _started = _notify_start(notify, short)
                try:
                    return _orig_doctr_download(*args, **kwargs)
                finally:
                    _notify_end(notify, short, _started)

            _doctr_download_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            dd.download_from_url = _doctr_download_wrapper  # type: ignore[assignment]

            # Also update modules that imported it by name so they use our wrapper
            for _mod_name in (
                "doctr.models.utils.pytorch",
                "doctr.datasets.datasets.base",
                "doctr.contrib.base",
            ):
                try:
                    _mod = importlib.import_module(_mod_name)
                    _attr = getattr(_mod, "download_from_url", None)
                    # Only replace if they still point to the original function
                    if _attr is _orig_doctr_download:
                        setattr(_mod, "download_from_url", dd.download_from_url)
                except Exception:
                    pass
    except Exception:
        pass

    # 4) Transformers-level helpers (cached_file/snapshot_download)
    try:
        import transformers.utils.hub as thub

        if hasattr(thub, "cached_file") and not getattr(thub.cached_file, "__ct_patched__", False):
            _orig_cached_file = thub.cached_file

            def _cached_file_wrapper(repo_id, filename, *args, **kwargs):
                short = os.path.basename(filename) if isinstance(filename, str) else "transformers-file"
                _started = _notify_start(notify, short)
                try:
                    return _orig_cached_file(repo_id, filename, *args, **kwargs)
                finally:
                    _notify_end(notify, short, _started)

            _cached_file_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            thub.cached_file = _cached_file_wrapper  # type: ignore[assignment]

        if hasattr(thub, "snapshot_download") and not getattr(thub.snapshot_download, "__ct_patched__", False):
            _orig_thub_snap = thub.snapshot_download

            def _thub_snap_wrapper(*args, **kwargs):
                name = "transformers-snapshot"
                _started = _notify_start(notify, name)
                try:
                    return _orig_thub_snap(*args, **kwargs)
                finally:
                    _notify_end(notify, name, _started)

            _thub_snap_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            thub.snapshot_download = _thub_snap_wrapper  # type: ignore[assignment]
    except Exception:
        pass

    # 4b) Older Transformers path (cached_path in transformers.file_utils)
    try:
        import transformers.file_utils as tfu

        if hasattr(tfu, "cached_path") and not getattr(tfu.cached_path, "__ct_patched__", False):
            _orig_cached_path = tfu.cached_path

            def _cached_path_wrapper(url_or_filename, *args, **kwargs):
                # Only show for remote URLs; skip local paths
                name = None
                try:
                    if isinstance(url_or_filename, str) and (url_or_filename.startswith("http://") or url_or_filename.startswith("https://")):
                        name = _basename_from_url(url_or_filename)
                except Exception:
                    name = None
                _started = _notify_start(notify, name) if name else False
                try:
                    return _orig_cached_path(url_or_filename, *args, **kwargs)
                finally:
                    if name:
                        _notify_end(notify, name, _started)

            _cached_path_wrapper.__ct_patched__ = True  # type: ignore[attr-defined]
            tfu.cached_path = _cached_path_wrapper  # type: ignore[assignment]
    except Exception:
        pass

    # 5) RapidOCR model/file downloader
    # RapidOCR uses a custom DownloadFile classmethod(run) which many submodules call.
    # We wrap it to emit start/end events for the target filename.
    try:
        import importlib
        rudf = importlib.import_module("rapidocr.utils.download_file")

        if hasattr(rudf, "DownloadFile") and hasattr(rudf.DownloadFile, "run"):
            _orig_cm = rudf.DownloadFile.run
            # classmethod descriptors expose underlying function via __func__
            _orig_func = getattr(_orig_cm, "__func__", _orig_cm)
            if not getattr(_orig_func, "__ct_patched__", False):

                def _rapidocr_run_wrapper(cls, input_params):  # type: ignore[no-redef]
                    # input_params is DownloadFileInput with fields: file_url, save_path, logger, sha256, verbose
                    try:
                        name = None
                        # Prefer the final save filename if provided
                        try:
                            from pathlib import Path
                            save_path = getattr(input_params, "save_path", None)
                            if save_path is not None:
                                name = Path(save_path).name
                        except Exception:
                            name = None
                        if not name:
                            # Fallback to URL basename
                            file_url = getattr(input_params, "file_url", None)
                            name = _basename_from_url(file_url) if file_url else "rapidocr-file"
                    except Exception:
                        name = "rapidocr-file"

                    _started = _notify_start(notify, name)
                    try:
                        return _orig_func(cls, input_params)
                    finally:
                        _notify_end(notify, name, _started)

                # Mark as patched and rebind as classmethod
                setattr(_rapidocr_run_wrapper, "__ct_patched__", True)
                rudf.DownloadFile.run = classmethod(_rapidocr_run_wrapper)  # type: ignore[assignment]
    except Exception:
        pass

    _installed = True