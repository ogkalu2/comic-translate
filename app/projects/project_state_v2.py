from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import tempfile
import threading
from typing import TYPE_CHECKING

import msgpack

from .parsers import ProjectDecoder, ProjectEncoder, ensure_string_keys
from modules.utils.file_handler import ensure_prepared_path_materialized

if TYPE_CHECKING:
    from controller import ComicTranslate


_SQLITE_HEADER = b"SQLite format 3\x00"
_CONN_CACHE_LOCK = threading.RLock()
_CONN_CACHE: dict[str, tuple[sqlite3.Connection, threading.RLock]] = {}
_LAZY_BLOB_LOCK = threading.RLock()
_LAZY_BLOBS_BY_PATH: dict[str, tuple[str, str]] = {}
logger = logging.getLogger(__name__)


def is_sqlite_project_file(file_name: str) -> bool:
    if not os.path.isfile(file_name):
        return False
    try:
        with open(file_name, "rb") as fh:
            return fh.read(16) == _SQLITE_HEADER
    except Exception:
        return False


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_manifest (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            manifest_blob BLOB NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS page_state (
            page_path TEXT PRIMARY KEY,
            row_blob BLOB NOT NULL
        )
        """
    )
    # Keep legacy interim table for backward local compatibility.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_blob BLOB NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blobs (
            hash TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            ext TEXT NOT NULL,
            size INTEGER NOT NULL,
            data BLOB NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cache_blob BLOB NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS source_fingerprints (
            path TEXT PRIMARY KEY,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            hash TEXT NOT NULL
        )
        """
    )


def _configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")


def _get_cached_connection(file_name: str) -> tuple[sqlite3.Connection, threading.RLock]:
    db_key = os.path.abspath(file_name)
    with _CONN_CACHE_LOCK:
        cached = _CONN_CACHE.get(db_key)
        if cached is not None:
            return cached

        conn = sqlite3.connect(db_key, check_same_thread=False, timeout=30.0)
        _configure_connection(conn)
        _init_schema(conn)
        lock = threading.RLock()
        _CONN_CACHE[db_key] = (conn, lock)
        return conn, lock


def close_cached_connection(file_name: str | None = None) -> None:
    with _CONN_CACHE_LOCK:
        if file_name:
            db_key = os.path.abspath(file_name)
            cached = _CONN_CACHE.pop(db_key, None)
            if cached is not None:
                conn, _ = cached
                conn.close()
            with _LAZY_BLOB_LOCK:
                stale_paths = [p for p, (mapped_db, _) in _LAZY_BLOBS_BY_PATH.items() if mapped_db == db_key]
                for path in stale_paths:
                    _LAZY_BLOBS_BY_PATH.pop(path, None)
            return

        for conn, _ in _CONN_CACHE.values():
            conn.close()
        _CONN_CACHE.clear()
    with _LAZY_BLOB_LOCK:
        _LAZY_BLOBS_BY_PATH.clear()


def register_lazy_blob_path(project_file: str, output_path: str, blob_hash: str) -> None:
    if not output_path or not blob_hash:
        return
    abs_path = os.path.abspath(output_path)
    db_key = os.path.abspath(project_file)
    # Avoid stale collisions when loading multiple projects into the same temp_dir.
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass
    with _LAZY_BLOB_LOCK:
        _LAZY_BLOBS_BY_PATH[abs_path] = (db_key, str(blob_hash))


def remap_lazy_blob_paths(path_mapping: dict[str, str]) -> None:
    if not path_mapping:
        return

    with _LAZY_BLOB_LOCK:
        updates: dict[str, tuple[str, str]] = {}
        for old_path, new_path in path_mapping.items():
            mapped = _LAZY_BLOBS_BY_PATH.pop(os.path.abspath(old_path), None)
            if mapped is not None:
                updates[os.path.abspath(new_path)] = mapped
        _LAZY_BLOBS_BY_PATH.update(updates)


def ensure_lazy_blob_materialized(path: str) -> bool:
    if not path:
        return False
    abs_path = os.path.abspath(path)
    try:
        if os.path.isfile(abs_path) and os.path.getsize(abs_path) > 0:
            return True
    except Exception:
        pass

    with _LAZY_BLOB_LOCK:
        mapped = _LAZY_BLOBS_BY_PATH.get(abs_path)
        if mapped is None:
            return os.path.isfile(abs_path)
        db_key, blob_hash = mapped
        conn, conn_lock = _get_cached_connection(db_key)
        with conn_lock:
            row = conn.execute("SELECT data FROM blobs WHERE hash = ?", (blob_hash,)).fetchone()
        if row is None or row[0] is None:
            return False

        target_dir = os.path.dirname(abs_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".blob_tmp_", dir=target_dir or None)
        os.close(fd)
        try:
            with open(temp_path, "wb") as fh:
                fh.write(row[0])
            os.replace(temp_path, abs_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
    return True


def save_state_to_proj_file_v2(comic_translate: "ComicTranslate", file_name: str) -> None:
    encoder = ProjectEncoder()

    target_dir = os.path.dirname(os.path.abspath(file_name))
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    existing_is_sqlite = is_sqlite_project_file(file_name)
    use_temp_and_replace = os.path.exists(file_name) and not existing_is_sqlite
    if use_temp_and_replace:
        fd, temp_db_path = tempfile.mkstemp(prefix=".ctprv2_tmp_", suffix=".ctpr", dir=target_dir or None)
        os.close(fd)
        db_path = temp_db_path
    else:
        temp_db_path = None
        db_path = file_name

    if use_temp_and_replace:
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        _configure_connection(conn)
        _init_schema(conn)
        conn_lock = threading.RLock()
    else:
        conn, conn_lock = _get_cached_connection(db_path)

    blob_rows: dict[str, tuple[str, str, int, bytes]] = {}
    fingerprint_updates: dict[str, tuple[int, int, str]] = {}
    image_id_counter = 0
    image_path_to_id: dict[str, int] = {}
    unique_images: dict[int, dict[str, str]] = {}

    image_data_references: dict[str, int] = {}
    image_files_references: dict[str, int] = {}
    in_memory_history_references: dict[str, list[int]] = {}
    image_history_references: dict[str, list[int]] = {}
    image_patches_references: dict[str, list[dict]] = {}

    def add_blob_if_needed(path: str, kind: str) -> str:
        if not ensure_lazy_blob_materialized(path):
            ensure_prepared_path_materialized(path)
        stat = os.stat(path)
        size = int(stat.st_size)
        mtime_ns = int(stat.st_mtime_ns)

        cached = conn.execute(
            """
            SELECT hash FROM source_fingerprints
            WHERE path = ? AND size = ? AND mtime_ns = ?
            """,
            (path, size, mtime_ns),
        ).fetchone()
        if cached and cached[0]:
            blob_hash = str(cached[0])
            blob_exists = conn.execute(
                "SELECT 1 FROM blobs WHERE hash = ? LIMIT 1",
                (blob_hash,),
            ).fetchone()
            if blob_exists:
                return blob_hash

        payload = _read_file_bytes(path)
        blob_hash = _sha256_bytes(payload)
        if blob_hash not in blob_rows:
            ext = os.path.splitext(path)[1].lower()
            blob_rows[blob_hash] = (kind, ext, len(payload), payload)
        fingerprint_updates[path] = (size, mtime_ns, blob_hash)
        return blob_hash

    def assign_image_id(path: str) -> int:
        nonlocal image_id_counter
        if path in image_path_to_id:
            return image_path_to_id[path]

        image_id = image_id_counter
        image_id_counter += 1
        image_path_to_id[path] = image_id
        blob_hash = add_blob_if_needed(path, "image")
        unique_images[image_id] = {"hash": blob_hash, "name": os.path.basename(path)}
        return image_id

    for file_path, history in comic_translate.in_memory_history.items():
        in_memory_history_references[file_path] = []
        for idx, _img in enumerate(history):
            path = comic_translate.image_history[file_path][idx]
            image_id = assign_image_id(path)
            if idx == comic_translate.current_history_index.get(file_path, 0):
                image_data_references[file_path] = image_id
            in_memory_history_references[file_path].append(image_id)

    for file_path in comic_translate.image_files:
        image_id = assign_image_id(file_path)
        image_files_references[file_path] = image_id

        if file_path in comic_translate.image_history:
            image_history_references[file_path] = []
            for history_path in comic_translate.image_history[file_path]:
                hist_id = assign_image_id(history_path)
                image_history_references[file_path].append(hist_id)

    for page_path, patch_list in comic_translate.image_patches.items():
        image_patches_references[page_path] = []
        for patch in patch_list:
            src_png = patch["png_path"]
            blob_hash = add_blob_if_needed(src_png, "patch")
            patch_entry = {"bbox": patch["bbox"], "png_hash": blob_hash, "hash": patch["hash"]}
            if patch.get("group_id"):
                patch_entry["group_id"] = patch["group_id"]
            if "scene_pos" in patch:
                patch_entry["scene_pos"] = patch["scene_pos"]
            if "page_index" in patch:
                patch_entry["page_index"] = patch["page_index"]
            image_patches_references[page_path].append(patch_entry)

    page_paths = list(
        dict.fromkeys(
            list(comic_translate.image_files)
            + list(comic_translate.image_states.keys())
            + list(image_history_references.keys())
            + list(in_memory_history_references.keys())
            + list(image_patches_references.keys())
        )
    )

    page_rows: dict[str, bytes] = {}
    for page_path in page_paths:
        row_payload = {
            "image_state": comic_translate.image_states.get(page_path, {}),
            "image_file_ref": image_files_references.get(page_path),
            "image_data_ref": image_data_references.get(page_path),
            "image_history_refs": image_history_references.get(page_path, []),
            "in_memory_history_refs": in_memory_history_references.get(page_path, []),
            "patches": image_patches_references.get(page_path, []),
        }
        page_rows[page_path] = msgpack.packb(row_payload, default=encoder.encode, use_bin_type=True)

    manifest = {
        "current_image_index": comic_translate.curr_img_idx,
        "original_image_files": comic_translate.image_files,
        "current_history_index": comic_translate.current_history_index,
        "displayed_images": list(comic_translate.displayed_images),
        "loaded_images": comic_translate.loaded_images,
        "llm_extra_context": comic_translate.settings_page.get_llm_settings().get("extra_context", ""),
        "target_language": comic_translate.lang_mapping.get(
            comic_translate.t_combo.currentText(),
            comic_translate.t_combo.currentText(),
        ),
        "webtoon_mode": comic_translate.webtoon_mode,
        "webtoon_view_state": comic_translate.image_viewer.webtoon_view_state,
        "unique_images": ensure_string_keys(unique_images),
    }
    manifest_blob = msgpack.packb(manifest, default=encoder.encode, use_bin_type=True)

    cache_manager = getattr(getattr(comic_translate, "pipeline", None), "cache_manager", None)
    cache_blob = None
    if cache_manager is not None:
        cache_state = cache_manager.export_state()
        if cache_state.get("ocr_cache") or cache_state.get("translation_cache"):
            cache_blob = msgpack.packb(cache_state, default=encoder.encode, use_bin_type=True)

    try:
        with conn_lock:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                    ("project_format_version", "2"),
                )

                current_manifest_row = conn.execute(
                    "SELECT manifest_blob FROM project_manifest WHERE id = 1"
                ).fetchone()
                if not current_manifest_row or current_manifest_row[0] != manifest_blob:
                    conn.execute(
                        "INSERT OR REPLACE INTO project_manifest(id, manifest_blob) VALUES(1, ?)",
                        (sqlite3.Binary(manifest_blob),),
                    )

                if cache_blob is not None:
                    current_cache_row = conn.execute(
                        "SELECT cache_blob FROM cache_state WHERE id = 1"
                    ).fetchone()
                    if not current_cache_row or current_cache_row[0] != cache_blob:
                        conn.execute(
                            "INSERT OR REPLACE INTO cache_state(id, cache_blob) VALUES(1, ?)",
                            (sqlite3.Binary(cache_blob),),
                        )
                else:
                    conn.execute("DELETE FROM cache_state WHERE id = 1")

                existing_rows = {
                    row[0]: row[1]
                    for row in conn.execute("SELECT page_path, row_blob FROM page_state")
                }
                new_keys = set(page_rows.keys())
                old_keys = set(existing_rows.keys())
                for removed in old_keys - new_keys:
                    conn.execute("DELETE FROM page_state WHERE page_path = ?", (removed,))

                for page_path, row_blob in page_rows.items():
                    old_blob = existing_rows.get(page_path)
                    if old_blob != row_blob:
                        conn.execute(
                            "INSERT OR REPLACE INTO page_state(page_path, row_blob) VALUES(?, ?)",
                            (page_path, sqlite3.Binary(row_blob)),
                        )

                for blob_hash, (kind, ext, size, payload) in blob_rows.items():
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO blobs(hash, kind, ext, size, data)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (blob_hash, kind, ext, size, sqlite3.Binary(payload)),
                    )

                for src_path, (size, mtime_ns, blob_hash) in fingerprint_updates.items():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO source_fingerprints(path, size, mtime_ns, hash)
                        VALUES(?, ?, ?, ?)
                        """,
                        (src_path, size, mtime_ns, blob_hash),
                    )

    finally:
        if use_temp_and_replace:
            conn.close()
    if use_temp_and_replace and temp_db_path is not None:
        os.replace(temp_db_path, file_name)


def _materialize_from_manifest_and_pages(
    comic_translate: "ComicTranslate",
    project_file: str,
    manifest: dict,
    page_rows: dict[str, dict],
):
    if not hasattr(comic_translate, "temp_dir"):
        comic_translate.temp_dir = tempfile.mkdtemp()

    image_data = comic_translate.image_data
    temp_dir = comic_translate.temp_dir
    in_memory_history = comic_translate.in_memory_history
    image_history = comic_translate.image_history
    original_to_temp: dict[str, str] = {}

    os.makedirs(temp_dir, exist_ok=True)
    unique_images_dir = os.path.join(temp_dir, "unique_images")
    unique_patches_dir = os.path.join(temp_dir, "unique_patches")
    os.makedirs(unique_images_dir, exist_ok=True)
    os.makedirs(unique_patches_dir, exist_ok=True)

    unique_images = manifest.get("unique_images", {})

    img_id_to_usage: dict[int, list[tuple]] = {}
    for page_path, row in page_rows.items():
        img_data_ref = row.get("image_data_ref")
        if img_data_ref is not None:
            img_id_to_usage.setdefault(int(img_data_ref), []).append(("image_data", page_path))

        img_file_ref = row.get("image_file_ref")
        if img_file_ref is not None:
            img_id_to_usage.setdefault(int(img_file_ref), []).append(("image_files", page_path))

        for idx, img_id in enumerate(row.get("in_memory_history_refs", []) or []):
            img_id_to_usage.setdefault(int(img_id), []).append(("in_memory_history", page_path, idx))

        for idx, img_id in enumerate(row.get("image_history_refs", []) or []):
            img_id_to_usage.setdefault(int(img_id), []).append(("image_history", page_path, idx))

    for img_id_str, meta in unique_images.items():
        img_id = int(img_id_str)
        if img_id not in img_id_to_usage:
            continue

        if isinstance(meta, dict):
            blob_hash = str(meta.get("hash", ""))
            file_name_hint = str(meta.get("name", f"{img_id}.img"))
        else:
            blob_hash = str(meta)
            file_name_hint = f"{img_id}.img"

        # Preserve user-facing base names (no numeric prefix) while avoiding collisions
        # by isolating each materialized image into its own id-specific subdirectory.
        safe_name = os.path.basename(file_name_hint) or f"{img_id}.img"
        img_dir = os.path.join(unique_images_dir, str(img_id))
        os.makedirs(img_dir, exist_ok=True)
        img_disk_path = os.path.join(img_dir, safe_name)
        register_lazy_blob_path(project_file, img_disk_path, blob_hash)

        for usage in img_id_to_usage[img_id]:
            usage_type = usage[0]
            if usage_type == "image_data":
                file_path = usage[1]
                # Keep image_data lazy on project load; load_image() reads from
                # image_history/current path when needed.
                image_data[file_path] = None
            elif usage_type == "image_files":
                file_path = usage[1]
                original_to_temp[file_path] = img_disk_path
            elif usage_type == "in_memory_history":
                file_path, idx = usage[1], usage[2]
                in_memory_history.setdefault(file_path, [])
                history = in_memory_history[file_path]
                while len(history) <= idx:
                    history.append(None)
                # Keep history cache lazy (None placeholders). Undo/redo already
                # falls back to reading from image_history paths on demand.
                history[idx] = None
            elif usage_type == "image_history":
                file_path, idx = usage[1], usage[2]
                image_history.setdefault(file_path, [])
                history = image_history[file_path]
                while len(history) <= idx:
                    history.append(None)
                history[idx] = img_disk_path

    comic_translate.curr_img_idx = manifest.get("current_image_index", 0)
    comic_translate.webtoon_mode = manifest.get("webtoon_mode", False)
    comic_translate.image_viewer.webtoon_view_state = manifest.get("webtoon_view_state", {})

    target_language = manifest.get("target_language", "English")
    try:
        comic_translate.t_combo.blockSignals(True)
        comic_translate.t_combo.setCurrentText(
            comic_translate.reverse_lang_mapping.get(target_language, comic_translate.tr("English"))
        )
    finally:
        comic_translate.t_combo.blockSignals(False)

    original_image_files = manifest.get("original_image_files", [])
    comic_translate.image_files = [original_to_temp.get(file, file) for file in original_image_files]

    comic_translate.image_states = {
        original_to_temp.get(page, page): (row.get("image_state", {}) or {})
        for page, row in page_rows.items()
    }
    current_target = comic_translate.t_combo.currentText()
    for state in comic_translate.image_states.values():
        target_render_states = state.get("target_render_states") or {}
        if not isinstance(target_render_states, dict):
            target_render_states = {}
        if state.get("viewer_state") and current_target and current_target not in target_render_states:
            target_render_states[current_target] = state["viewer_state"]
        state["target_render_states"] = target_render_states
        state.setdefault("target_lang", current_target)
    # Ensure every image state has a pipeline_state dict
    default_pipeline_state = {
        'completed_stages': [],
        'target_lang': '',
        'inpaint_hash': '',
        'translator_key': '',
        'extra_context_hash': '',
    }
    for state in comic_translate.image_states.values():
        if 'pipeline_state' not in state:
            state['pipeline_state'] = dict(default_pipeline_state)

    current_history_index = manifest.get("current_history_index", {})
    comic_translate.current_history_index = {
        original_to_temp.get(file, file): index for file, index in current_history_index.items()
    }

    displayed_images = manifest.get("displayed_images", [])
    comic_translate.displayed_images = set(original_to_temp.get(i, i) for i in displayed_images)

    loaded_images = manifest.get("loaded_images", [])
    comic_translate.loaded_images = [original_to_temp.get(file, file) for file in loaded_images]

    comic_translate.image_data = {
        original_to_temp.get(file, file): img for file, img in image_data.items()
    }

    comic_translate.in_memory_history = {
        original_to_temp.get(file, file): imgs for file, imgs in in_memory_history.items()
    }

    comic_translate.image_history = {
        original_to_temp.get(file_path, file_path): history_list
        for file_path, history_list in image_history.items()
    }

    reconstructed: dict[str, list[dict]] = {}
    for page_path, row in page_rows.items():
        patch_list = row.get("patches") or []
        if not patch_list:
            continue

        new_list: list[dict] = []
        page_folder = os.path.join(unique_patches_dir, os.path.basename(page_path))
        os.makedirs(page_folder, exist_ok=True)
        for idx, patch in enumerate(patch_list):
            png_hash = patch.get("png_hash")
            if not png_hash:
                continue

            ext = ".png"
            if not str(ext).startswith("."):
                ext = f".{ext}"
            patch_disk_path = os.path.join(page_folder, f"{idx}_{png_hash[:12]}{ext}")
            register_lazy_blob_path(project_file, patch_disk_path, str(png_hash))

            patch_entry = {"bbox": patch["bbox"], "png_path": patch_disk_path, "hash": patch["hash"]}
            if patch.get("group_id"):
                patch_entry["group_id"] = patch["group_id"]
            if "scene_pos" in patch:
                patch_entry["scene_pos"] = patch["scene_pos"]
            if "page_index" in patch:
                patch_entry["page_index"] = patch["page_index"]
            new_list.append(patch_entry)

        if new_list:
            reconstructed[page_path] = new_list

    comic_translate.image_patches = {
        original_to_temp.get(page, page): plist for page, plist in reconstructed.items()
    }
    for page_path, state_val in comic_translate.image_states.items():
        if not state_val.get("inpaint_cache") and comic_translate.image_patches.get(page_path):
            state_val["inpaint_cache"] = [
                dict(patch) for patch in comic_translate.image_patches.get(page_path, [])
            ]

    return manifest.get("llm_extra_context", "")


def _load_from_legacy_state_blob(
    comic_translate: "ComicTranslate",
    file_name: str,
    conn: sqlite3.Connection,
    decoder: ProjectDecoder,
):
    row = conn.execute("SELECT state_blob FROM project_state WHERE id = 1").fetchone()
    if row is None or row[0] is None:
        raise ValueError("Invalid v2 project: missing project manifest/state")

    state = msgpack.unpackb(row[0], object_hook=decoder.decode, strict_map_key=True)

    page_rows: dict[str, dict] = {}
    image_states = state.get("image_states", {})
    image_patches = state.get("image_patches", {})
    for page_path in set(image_states.keys()) | set(image_patches.keys()):
        page_rows[page_path] = {
            "image_state": image_states.get(page_path, {}),
            "image_file_ref": state.get("image_files_references", {}).get(page_path),
            "image_data_ref": state.get("image_data_references", {}).get(page_path),
            "image_history_refs": state.get("image_history_references", {}).get(page_path, []),
            "in_memory_history_refs": state.get("in_memory_history_references", {}).get(page_path, []),
            "patches": image_patches.get(page_path, []),
        }

    manifest = {
        "current_image_index": state.get("current_image_index", 0),
        "original_image_files": state.get("original_image_files", []),
        "current_history_index": state.get("current_history_index", {}),
        "displayed_images": state.get("displayed_images", []),
        "loaded_images": state.get("loaded_images", []),
        "llm_extra_context": state.get("llm_extra_context", ""),
        "target_language": state.get("target_language", "English"),
        "webtoon_mode": state.get("webtoon_mode", False),
        "webtoon_view_state": state.get("webtoon_view_state", {}),
        "unique_images": state.get("unique_images", {}),
    }

    return _materialize_from_manifest_and_pages(comic_translate, file_name, manifest, page_rows)


def load_state_from_proj_file_v2(comic_translate: "ComicTranslate", file_name: str):
    decoder = ProjectDecoder()
    conn, conn_lock = _get_cached_connection(file_name)
    with conn_lock:
        manifest_row = conn.execute("SELECT manifest_blob FROM project_manifest WHERE id = 1").fetchone()
        if manifest_row is None or manifest_row[0] is None:
            return _load_from_legacy_state_blob(comic_translate, file_name, conn, decoder)

        manifest = msgpack.unpackb(manifest_row[0], object_hook=decoder.decode, strict_map_key=True)
        page_rows = {
            row[0]: msgpack.unpackb(row[1], object_hook=decoder.decode, strict_map_key=True)
            for row in conn.execute("SELECT page_path, row_blob FROM page_state")
        }
        saved_ctx = _materialize_from_manifest_and_pages(comic_translate, file_name, manifest, page_rows)

        page_rows_with_blocks = [
            page_path
            for page_path, row in page_rows.items()
            if (row.get("image_state", {}) or {}).get("blk_list")
        ]
        pages_missing_viewer_state = [
            page_path
            for page_path in page_rows_with_blocks
            if not (page_rows.get(page_path, {}).get("image_state", {}) or {}).get("viewer_state")
        ]
        if page_rows_with_blocks:
            logger.info(
                "Loaded project state: %d pages with blocks, %d without viewer_state.",
                len(page_rows_with_blocks),
                len(pages_missing_viewer_state),
            )
            if pages_missing_viewer_state:
                preview = ", ".join(os.path.basename(p) for p in pages_missing_viewer_state[:5])
                if len(pages_missing_viewer_state) > 5:
                    preview += ", ..."
                logger.debug(
                    "Pages missing viewer_state but keeping blk_list: %s",
                    preview,
                )

        cache_row = conn.execute("SELECT cache_blob FROM cache_state WHERE id = 1").fetchone()
        if cache_row is not None and cache_row[0] is not None:
            cache_state = msgpack.unpackb(cache_row[0], object_hook=decoder.decode, strict_map_key=True)
            cache_manager = getattr(getattr(comic_translate, "pipeline", None), "cache_manager", None)
            if cache_manager is not None:
                cache_manager.import_state(cache_state)
                logger.info(
                    "Project cache restored: %d OCR entries, %d translation entries.",
                    len(cache_manager.ocr_cache),
                    len(cache_manager.translation_cache),
                )
        else:
            logger.info("Project cache restored: 0 OCR entries, 0 translation entries.")

        return saved_ctx
