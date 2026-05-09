import io
import math
import os
import re
import shutil
import tarfile
import tempfile
import threading
import zipfile
from PIL import Image

SUPPORTED_SAVE_AS_EXTS = {'.pdf', '.cbz', '.cb7', '.zip'}
_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
_PDF_CACHE_LOCK = threading.RLock()
_PDF_CACHE: dict[str, dict] = {}


def close_pdf_cache(file_path: str | None = None) -> None:
    """Close cached pdfplumber objects to free memory.

    If *file_path* is given, only that entry is evicted; otherwise the entire
    cache is cleared.
    """
    with _PDF_CACHE_LOCK:
        if file_path is not None:
            abs_path = os.path.abspath(file_path)
            cached = _PDF_CACHE.pop(abs_path, None)
            if cached and cached.get("pdf") is not None:
                try:
                    cached["pdf"].close()
                except Exception:
                    pass
        else:
            for cached in _PDF_CACHE.values():
                if cached.get("pdf") is not None:
                    try:
                        cached["pdf"].close()
                    except Exception:
                        pass
            _PDF_CACHE.clear()

def resolve_save_as_ext(input_archive_ext: str, save_as: str | None = None) -> str:
    """Resolve the output archive extension for auto-saved translated archives.

    Returns a dotted extension (e.g. '.zip') accepted by `make()`.
    `input_archive_ext` is ignored except for backward-compatible callers.
    """
    def _normalize_target(value: str | None) -> str | None:
        if not value:
            return None
        v = str(value).strip().lower()
        if not v:
            return None
        return v if v.startswith('.') else f'.{v}'

    forced = _normalize_target(save_as)
    if forced in SUPPORTED_SAVE_AS_EXTS:
        return forced

    # Default: zip
    return '.zip'

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', str(s))]

def is_image_file(filename):
    return filename.lower().endswith(_IMAGE_EXTENSIONS)


def _safe_ext(path: str, default: str = ".png") -> str:
    ext = os.path.splitext(os.path.basename(path))[1].lower()
    if ext in _IMAGE_EXTENSIONS:
        return ext
    return default


def _get_cached_pdf(file_path: str):
    import pdfplumber

    abs_path = os.path.abspath(file_path)
    stat = os.stat(abs_path)
    size = int(stat.st_size)
    mtime_ns = int(stat.st_mtime_ns)

    with _PDF_CACHE_LOCK:
        cached = _PDF_CACHE.get(abs_path)
        if cached and cached.get("size") == size and cached.get("mtime_ns") == mtime_ns:
            return cached["pdf"], cached["lock"]

        if cached and cached.get("pdf") is not None:
            try:
                cached["pdf"].close()
            except Exception:
                pass

        pdf = pdfplumber.open(abs_path)
        page_lock = threading.RLock()
        _PDF_CACHE[abs_path] = {
            "pdf": pdf,
            "lock": page_lock,
            "size": size,
            "mtime_ns": mtime_ns,
        }
        return pdf, page_lock


def list_archive_image_entries(file_path: str) -> list[dict]:
    file_lower = file_path.lower()
    entries: list[dict] = []

    if file_lower.endswith(('.cbz', '.zip', '.epub')):
        with zipfile.ZipFile(file_path, 'r') as archive:
            for name in archive.namelist():
                if is_image_file(name):
                    entries.append({
                        "kind": "archive_entry",
                        "entry_name": name,
                        "ext": _safe_ext(name),
                    })

    elif file_lower.endswith(('.cbr', '.rar')):
        import rarfile
        with rarfile.RarFile(file_path, 'r') as archive:
            for name in archive.namelist():
                if is_image_file(name):
                    entries.append({
                        "kind": "archive_entry",
                        "entry_name": name,
                        "ext": _safe_ext(name),
                    })

    elif file_lower.endswith(('.cbt', '.tar')):
        with tarfile.open(file_path, 'r') as archive:
            for member in archive:
                if member.isfile() and is_image_file(member.name):
                    entries.append({
                        "kind": "archive_entry",
                        "entry_name": member.name,
                        "ext": _safe_ext(member.name),
                    })

    elif file_lower.endswith(('.cb7', '.7z')):
        import py7zr
        with py7zr.SevenZipFile(file_path, 'r') as archive:
            for name in archive.getnames():
                if is_image_file(name):
                    entries.append({
                        "kind": "archive_entry",
                        "entry_name": name,
                        "ext": _safe_ext(name),
                    })

    elif file_lower.endswith('.pdf'):
        pdf, page_lock = _get_cached_pdf(file_path)
        with page_lock:
            total_pages = len(pdf.pages)
        for page_idx in range(total_pages):
            entries.append({
                "kind": "pdf_page",
                "page_index": page_idx,
                "ext": ".png",
            })

    else:
        raise ValueError("Unsupported file format")

    if entries and entries[0]["kind"] == "pdf_page":
        return entries
    return sorted(entries, key=lambda e: natural_sort_key(e.get("entry_name", "")))


def materialize_archive_entry(file_path: str, entry: dict, output_path: str) -> bool:
    kind = str(entry.get("kind", ""))
    if kind == "pdf_page":
        return _materialize_pdf_page(file_path, int(entry.get("page_index", 0)), output_path)
    if kind != "archive_entry":
        return False

    entry_name = str(entry.get("entry_name", ""))
    if not entry_name:
        return False

    file_lower = file_path.lower()
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if file_lower.endswith(('.cbz', '.zip', '.epub')):
        with zipfile.ZipFile(file_path, 'r') as archive:
            with archive.open(entry_name) as src, open(output_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return True

    if file_lower.endswith(('.cbr', '.rar')):
        import rarfile
        with rarfile.RarFile(file_path, 'r') as archive:
            with archive.open(entry_name) as src, open(output_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return True

    if file_lower.endswith(('.cbt', '.tar')):
        with tarfile.open(file_path, 'r') as archive:
            member = archive.getmember(entry_name)
            src = archive.extractfile(member)
            if src is None:
                return False
            with src, open(output_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return True

    if file_lower.endswith(('.cb7', '.7z')):
        import py7zr
        with tempfile.TemporaryDirectory(prefix="ct_7z_extract_") as temp_dir:
            with py7zr.SevenZipFile(file_path, 'r') as archive:
                archive.extract(targets=[entry_name], path=temp_dir)
            extracted = os.path.join(temp_dir, *entry_name.replace("\\", "/").split("/"))
            if not os.path.isfile(extracted):
                return False
            shutil.copyfile(extracted, output_path)
        return True

    return False


def materialize_archive_entries(file_path: str, items: list[tuple[dict, str]]) -> int:
    if not items:
        return 0

    file_lower = file_path.lower()
    completed = 0

    if file_lower.endswith('.pdf'):
        pdf, page_lock = _get_cached_pdf(file_path)
        with page_lock:
            for entry, output_path in items:
                page_index = int(entry.get("page_index", -1))
                if page_index < 0 or page_index >= len(pdf.pages):
                    continue
                if _materialize_pdf_page_from_page(pdf.pages[page_index], output_path):
                    completed += 1
        return completed

    if file_lower.endswith(('.cbz', '.zip', '.epub')):
        with zipfile.ZipFile(file_path, 'r') as archive:
            for entry, output_path in items:
                entry_name = str(entry.get("entry_name", ""))
                if not entry_name:
                    continue
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                try:
                    with archive.open(entry_name) as src, open(output_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    completed += 1
                except Exception:
                    continue
        return completed

    if file_lower.endswith(('.cbr', '.rar')):
        import rarfile
        with rarfile.RarFile(file_path, 'r') as archive:
            for entry, output_path in items:
                entry_name = str(entry.get("entry_name", ""))
                if not entry_name:
                    continue
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                try:
                    with archive.open(entry_name) as src, open(output_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    completed += 1
                except Exception:
                    continue
        return completed

    if file_lower.endswith(('.cbt', '.tar')):
        with tarfile.open(file_path, 'r') as archive:
            for entry, output_path in items:
                entry_name = str(entry.get("entry_name", ""))
                if not entry_name:
                    continue
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                try:
                    member = archive.getmember(entry_name)
                    src = archive.extractfile(member)
                    if src is None:
                        continue
                    with src, open(output_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    completed += 1
                except Exception:
                    continue
        return completed

    if file_lower.endswith(('.cb7', '.7z')):
        import py7zr
        targets = []
        name_to_output: dict[str, str] = {}
        for entry, output_path in items:
            entry_name = str(entry.get("entry_name", ""))
            if not entry_name:
                continue
            targets.append(entry_name)
            name_to_output[entry_name] = output_path
        if not targets:
            return 0
        with tempfile.TemporaryDirectory(prefix="ct_7z_extract_") as temp_dir:
            with py7zr.SevenZipFile(file_path, 'r') as archive:
                archive.extract(targets=targets, path=temp_dir)
            for entry_name, output_path in name_to_output.items():
                extracted = os.path.join(temp_dir, *entry_name.replace("\\", "/").split("/"))
                if not os.path.isfile(extracted):
                    continue
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                try:
                    shutil.copyfile(extracted, output_path)
                    completed += 1
                except Exception:
                    continue
        return completed

    for entry, output_path in items:
        if materialize_archive_entry(file_path, entry, output_path):
            completed += 1
    return completed


def _materialize_pdf_page(file_path: str, page_index: int, output_path: str) -> bool:
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    pdf, page_lock = _get_cached_pdf(file_path)
    with page_lock:
        if page_index < 0 or page_index >= len(pdf.pages):
            return False
        return _materialize_pdf_page_from_page(pdf.pages[page_index], output_path)


def _materialize_pdf_page_from_page(page, output_path: str) -> bool:
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if page.images:
        try:
            img = page.images[0]
            if "stream" in img:
                image_bytes = img["stream"].get_data()
                try:
                    with Image.open(io.BytesIO(image_bytes)):
                        pass
                    with open(output_path, "wb") as image_file:
                        image_file.write(image_bytes)
                    return True
                except Exception:
                    pass
        except Exception:
            pass

    try:
        page_img = page.to_image()
        page_img.save(output_path)
        return True
    except Exception:
        return False

def extract_archive(file_path: str, extract_to: str):
    image_paths = []
    entries = list_archive_image_entries(file_path)
    total = len(entries)
    digits = math.floor(math.log10(total)) + 1 if total > 0 else 1

    for index, entry in enumerate(entries, start=1):
        ext = str(entry.get("ext", ".png"))
        if not ext.startswith("."):
            ext = f".{ext}"
        image_path = os.path.join(extract_to, f"{index:0{digits}d}{ext}")
        if materialize_archive_entry(file_path, entry, image_path):
            image_paths.append(image_path)

    return image_paths

def make_cbz(input_dir, output_path='', output_dir='', output_base_name='', save_as_ext='.cbz'):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated{save_as_ext}")
    
    with zipfile.ZipFile(output_path, 'w') as archive:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if is_image_file(file):
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, input_dir))

def make_cb7(input_dir, output_path="", output_dir="", output_base_name=""):
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.cb7")

    import py7zr
    with py7zr.SevenZipFile(output_path, 'w') as archive:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if is_image_file(file):
                    file_path = os.path.join(root, file)
                    archive.write(file_path, arcname=os.path.relpath(file_path, input_dir))

def make_pdf(input_dir, output_path="", output_dir="", output_base_name=""):
    import img2pdf
    
    if not output_path:
        output_path = os.path.join(output_dir, f"{output_base_name}_translated.pdf")

    image_paths = []
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            if is_image_file(file):
                image_paths.append(os.path.join(root, file))
    
    sorted_paths = sorted(image_paths, key=lambda p: natural_sort_key(os.path.basename(p)))
    
    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(sorted_paths))

def make(input_dir, output_path="", save_as_ext="", output_dir="", output_base_name=""):
    if not output_path and (not output_dir or not output_base_name):
        raise ValueError("Either output_path or both output_dir and output_base_name must be provided")
    
    if output_path:
        save_as_ext = os.path.splitext(output_path)[1]

    if save_as_ext in ['.cbz', '.zip']:
        make_cbz(input_dir, output_path, output_dir, output_base_name, save_as_ext)
    elif save_as_ext == '.cb7':
        make_cb7(input_dir, output_path, output_dir, output_base_name)
    elif save_as_ext == '.pdf':
        make_pdf(input_dir, output_path, output_dir, output_base_name)
    else:
        raise ValueError(f"Unsupported save_as_ext: {save_as_ext}")
