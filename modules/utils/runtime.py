"""Runtime configuration needed by the packaged desktop application."""

from __future__ import annotations

import os
import sys


def configure_runtime() -> None:
    """Configure executable lookup before archive readers are imported.

    Finder does not load a user's shell configuration, so a macOS ``.app``
    otherwise cannot see Homebrew-installed helpers.  The certificate variables
    are intentionally not changed here: forcing a bundled CA file would hide
    certificates deliberately installed by an organisation or the user.
    """
    if sys.platform != "darwin":
        return

    candidates = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]

    current_path = os.environ.get("PATH", "")
    # Preserve a user-provided PATH's ordering.  This only extends Finder's
    # minimal PATH instead of replacing a tool selection that already works.
    path_entries = [entry for entry in current_path.split(os.pathsep) if entry]
    path_entries.extend(entry for entry in candidates if os.path.isdir(entry))
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(path_entries))
