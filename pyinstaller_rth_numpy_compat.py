import sys


def _alias_module(old_name: str, new_name: str) -> None:
    try:
        module = __import__(new_name, fromlist=["*"])
    except Exception:
        return
    sys.modules.setdefault(old_name, module)


_alias_module("numpy.core.multiarray", "numpy._core.multiarray")
_alias_module("numpy.core._multiarray_umath", "numpy._core._multiarray_umath")
_alias_module("numpy.core.umath", "numpy._core.umath")
