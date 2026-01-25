"""
Features:
 - Streamed download (constant memory)
 - Optional SHA256 hash prefix verification (torch.hub parity)
 - Simple stderr progress bar (no extra deps)
 - Automatic directory creation
 - Retry with exponential backoff + jitter for transient network/HTTP errors
 - Partial download resume (HTTP Range) when supported by server

Defaults are conservative; existing call sites remain valid since new parameters
have defaults appended to the signature.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import random
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Optional

CHUNK_SIZE = 64 * 1024  # 64KB per read


@contextmanager
def _open_url(url: str, *, headers: Optional[dict] = None, timeout: Optional[float] = None):
    req = urllib.request.Request(url, headers=headers or {})
    response = urllib.request.urlopen(req, timeout=timeout)  # nosec - controlled sources
    try:
        yield response
    finally:
        try:
            response.close()
        except Exception:
            pass


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 ** 2:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 ** 3:
        return f"{num_bytes / 1024 ** 2:.1f} MB"
    return f"{num_bytes / 1024 ** 3:.1f} GB"


def download_url_to_file(
    url: str,
    dst: str,
    hash_prefix: Optional[str] = None,
    progress: bool = True,
    *,
    max_retries: int = 5,
    base_delay: float = 0.75,
    timeout: float | None = 30.0,
    resume: bool = True,
):  # noqa: D401
    """Download a URL to a local file with optional retries and resume.

    Backwards compatible with the original minimal implementation. Additional
    keyword-only parameters configure robustness.

    Args:
        url: Source HTTP(S) URL.
        dst: Destination file path.
        hash_prefix: Optional SHA256 hex digest *prefix* (as torch.hub does).
        progress: Show stderr progress bar.
        max_retries: Total attempts (initial try + retries).
        base_delay: Base seconds for exponential backoff (delay = base * 2^(attempt-1) * jitter).
        timeout: Per-attempt socket timeout (seconds).
        resume: Try to resume partial .part file using HTTP Range.

    Raises:
        RuntimeError: Hash mismatch or unrecoverable error after retries.
        URLError / OSError: Propagated if non-retryable and not hash related.
    """

    # Ensure destination directory exists
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)

    tmp_dst = dst + ".part"

    retry_status_codes = {408, 425, 429, 500, 502, 503, 504}

    def is_retryable(exc) -> bool:
        if isinstance(exc, urllib.error.HTTPError):
            return exc.code in retry_status_codes
        if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError)):
            return True
        if isinstance(exc, http.client.IncompleteRead):
            return True
        return False

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        partial_size = 0
        headers = {}

        if resume and os.path.exists(tmp_dst):
            try:
                partial_size = os.path.getsize(tmp_dst)
            except OSError:
                partial_size = 0
            if partial_size > 0:
                headers["Range"] = f"bytes={partial_size}-"

        sha256 = hashlib.sha256() if hash_prefix else None
        downloaded = partial_size
        total = None

        try:
            with _open_url(url, headers=headers, timeout=timeout) as response:
                # If we requested a Range and got 200 instead of 206, server ignored resume -> restart
                if partial_size and getattr(response, 'status', getattr(response, 'code', None)) not in (206,):
                    partial_size = 0
                    downloaded = 0
                    # Truncate the temp file
                    try:
                        with open(tmp_dst, 'wb'):
                            pass
                    except Exception:
                        pass

                total_str = response.headers.get("Content-Length")
                content_range = response.headers.get("Content-Range")
                if content_range:
                    # Format: bytes start-end/total
                    try:
                        total = int(content_range.split("/")[-1])
                    except Exception:
                        total = None
                elif total_str and total_str.isdigit():
                    t = int(total_str)
                    total = t + partial_size if partial_size and headers.get("Range") else t

                # Pre-hash existing partial bytes if resuming and hash needed
                if sha256 and partial_size:
                    try:
                        with open(tmp_dst, 'rb') as existing:
                            for chunk in iter(lambda: existing.read(CHUNK_SIZE), b""):
                                sha256.update(chunk)
                    except Exception:
                        # If we fail to read partial, start over
                        sha256 = hashlib.sha256() if hash_prefix else None
                        partial_size = 0
                        downloaded = 0

                mode = 'ab' if partial_size else 'wb'
                with open(tmp_dst, mode) as f:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if sha256:
                            sha256.update(chunk)
                        if progress:
                            if total:
                                pct = min(downloaded / total * 100, 100)
                                bar_len = 30
                                filled = int(bar_len * downloaded / total)
                                bar = "#" * filled + "-" * (bar_len - filled)
                                if sys.stderr:
                                    sys.stderr.write(
                                        f"\r[{bar}] {pct:5.1f}% ({_format_size(downloaded)}/{_format_size(total)})"
                                    )
                            else:
                                if sys.stderr:
                                    sys.stderr.write(f"\rDownloaded {_format_size(downloaded)}")
                            
                            if sys.stderr:
                                sys.stderr.flush()

            if progress:
                if sys.stderr:
                    sys.stderr.write("\n")

            # Hash verification
            if sha256 and hash_prefix:
                digest = sha256.hexdigest()
                if not digest.startswith(hash_prefix):
                    try:
                        os.remove(tmp_dst)
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Downloaded file hash mismatch: expected prefix {hash_prefix}, got {digest}."
                    )

            # If total known but mismatch in size -> treat as retryable incomplete read
            if total is not None and downloaded < total:
                raise http.client.IncompleteRead(partial=downloaded)

            os.replace(tmp_dst, dst)
            return  # Success

        except KeyboardInterrupt:
            raise
        except Exception as e:  # Decide retry vs fail
            if not is_retryable(e) or attempt >= max_retries:
                # Give final newline to keep terminal sane if progress was mid-line
                if progress:
                    if sys.stderr:
                        sys.stderr.write("\n")
                raise
            # Backoff with jitter
            delay = base_delay * (2 ** (attempt - 1))
            jitter = random.uniform(0.5, 1.0)
            time.sleep(delay * jitter)

    # If loop exits without return, raise generic error (should be unreachable)
    raise RuntimeError("Failed to download file after retries without specific exception.")
