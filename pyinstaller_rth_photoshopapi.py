import os
import sys


def _candidate_dirs() -> list[str]:
    roots = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(meipass)

    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    if exe_dir not in roots:
        roots.append(exe_dir)

    candidates: list[str] = []
    for root in roots:
        candidates.extend(
            [
                os.path.join(root, "photoshopapi.libs"),
                os.path.join(root, "_internal", "photoshopapi.libs"),
                os.path.join(root, "lib", "photoshopapi.libs"),
            ]
        )
    return candidates


def _add_dll_dir(path: str) -> None:
    if not os.path.isdir(path):
        return

    try:
        os.add_dll_directory(path)
    except (AttributeError, FileNotFoundError, OSError):
        pass

    current_path = os.environ.get("PATH", "")
    path_entries = current_path.split(os.pathsep) if current_path else []
    if path not in path_entries:
        os.environ["PATH"] = path + (os.pathsep + current_path if current_path else "")


for dll_dir in _candidate_dirs():
    _add_dll_dir(dll_dir)
