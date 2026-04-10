from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)


class LocalHTTPError(requests.HTTPError):
    """HTTP error raised for WSL fallback responses."""


class LocalResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            logger.error(
                "LocalResponse JSON decode failed at line %s col %s pos %s: %s | body preview: %r",
                getattr(exc, "lineno", "?"),
                getattr(exc, "colno", "?"),
                getattr(exc, "pos", "?"),
                getattr(exc, "msg", str(exc)),
                self.text[:4000],
                exc_info=True,
            )
            raise

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise LocalHTTPError(
                f"HTTP {self.status_code}: {self.text}",
                response=self,
            )


def _is_local_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in {"localhost", "127.0.0.1"}


def _wsl_distro() -> str:
    return os.environ.get("CT_WSL_DISTRO", "Ubuntu")


def _wsl_request(url: str, payload: dict[str, Any], timeout: int | float) -> LocalResponse:
    script = """
import json
import sys
import requests

url = sys.argv[1]
timeout = float(sys.argv[2])
payload = json.loads(sys.stdin.read())
response = requests.post(url, json=payload, timeout=timeout)
print(json.dumps({"status_code": response.status_code, "text": response.text}, ensure_ascii=False))
"""
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    process = subprocess.run(
        ["wsl", "-d", _wsl_distro(), "-e", "python3", "-c", script, url, str(timeout)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=max(float(timeout), 30.0) + 15.0,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr.strip() or process.stdout.strip() or "WSL request failed"
        raise RuntimeError(stderr)

    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        logger.error(
            "WSL fallback returned invalid JSON at line %s col %s pos %s: %s | stdout preview: %r",
            getattr(exc, "lineno", "?"),
            getattr(exc, "colno", "?"),
            getattr(exc, "pos", "?"),
            getattr(exc, "msg", str(exc)),
            process.stdout[:4000],
            exc_info=True,
        )
        raise RuntimeError(
            f"WSL fallback returned invalid JSON: {process.stdout[:500]}"
        ) from exc

    return LocalResponse(
        status_code=int(result["status_code"]),
        text=result["text"],
    )


def post_json_with_wsl_fallback(
    url: str,
    payload: dict[str, Any],
    timeout: int | float,
    headers: dict[str, str] | None = None,
) -> requests.Response | LocalResponse:
    try:
        return requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        if not _is_local_url(url):
            raise
        try:
            return _wsl_request(url, payload, timeout)
        except Exception as wsl_exc:
            raise requests.exceptions.ConnectionError(
                f"{exc}; WSL fallback failed: {wsl_exc}"
            ) from wsl_exc
