# ZIP Extraction Performance Design

**Goal:** Fix UI freeze and slow extraction when opening ZIP/CBZ archives of any size.

**Approach:** A + B combined — Phase A ships first (QThread + extractall), Phase B layers on top (parallel extraction for large archives).

---

## Problem

Current `prepare_files()` in `modules/utils/file_handler.py` runs on the main thread and extracts files one at a time via `archive.extract(file, extract_to)` in a loop. This causes:

1. **UI freeze** — main thread blocked for the full duration of extraction
2. **Slow extraction** — serial per-file I/O instead of batch

---

## Phase A — QThread Worker + `extractall`

### What changes

**`modules/utils/file_handler.py`**
- Add `ExtractionWorker(QThread)` class
- Signals: `finished = Signal(list)`, `error = Signal(str)`
- `run()` calls `extract_archive()` (unchanged), emits `finished(image_paths)` on success or `error(msg)` on failure
- Add `prepare_files_async(file_paths, extend)` method that starts the worker and returns immediately
- Keep synchronous `prepare_files()` intact — batch processor already runs on a worker thread and uses it directly

**`modules/utils/archives.py`**
- Replace per-file `archive.extract()` loop with `archive.extractall(path=extract_to, members=image_members)` for ZIP/CBZ
- Filter image members before calling extractall (avoids extracting non-image files)

**`app/controllers/image.py`**
- `load_initial_image()` calls `prepare_files_async()` instead of `prepare_files()`
- Connect `worker.finished` → existing image loading flow
- Connect `worker.error` → existing error display pattern

### Signal flow

```
user opens file
  → image_ctrl.load_initial_image(file_paths)
      → file_handler.prepare_files_async(file_paths)
          → ExtractionWorker.start()
              → run(): extractall() on ZIP
              → finished.emit(image_paths)
      → slot: load_image(image_paths[0])
```

---

## Phase B — Parallel Extraction for Large Archives

Layered on top of Phase A. Activates when a ZIP contains **50+ image files**.

### What changes

**`modules/utils/archives.py`**
- Add `extract_zip_parallel(file_path, extract_to, max_workers=4) -> list[str]`
- Opens ZipFile once to get image namelist
- Splits list into `max_workers` chunks
- `ThreadPoolExecutor`: each worker opens its own `ZipFile` handle and calls `extractall(members=chunk)`
- Merges and natural-sorts results
- On any worker failure: falls back to sequential `extractall` automatically

**`modules/utils/file_handler.py`**
- `ExtractionWorker.run()` checks len(image_members): if >= 50, calls `extract_zip_parallel()`; else uses `extractall`

### Parallel worker model

```
ZipFile (read namelist)
  → chunk_0 → worker_0 opens own ZipFile handle → extractall(chunk_0)
  → chunk_1 → worker_1 opens own ZipFile handle → extractall(chunk_1)
  → chunk_2 → worker_2 opens own ZipFile handle → extractall(chunk_2)
  → chunk_3 → worker_3 opens own ZipFile handle → extractall(chunk_3)
  → merge + natural_sort → return image_paths
```

`max_workers=4` default — safe for both HDD and SSD, avoids thrashing.

---

## Error Handling

- Worker catches all exceptions, deletes temp dir it created, emits `error(str)`
- Parallel failure → automatic fallback to sequential `extractall`
- Controller shows error via existing `show_error` message pattern

---

## Testing

New file: `tests/utils/test_archives.py`

| Test | What it checks |
|------|---------------|
| `test_extract_zip_sequential` | < 50 files → `extractall` path, correct sorted image list |
| `test_extract_zip_parallel` | 50+ files → parallel path, same result as sequential |
| `test_extract_zip_parallel_fallback` | corrupt member in one chunk → fallback to sequential succeeds |

Tests use `zipfile.ZipFile` to create in-memory test ZIPs with synthetic image filenames — no real image data needed.

---

## What Does NOT Change

- `archive_info` structure: `{'archive_path', 'extracted_images', 'temp_dir'}`
- Temp dir location: same directory as archive (`tempfile.mkdtemp(dir=archive_dir)`)
- Natural sort order of extracted images
- RAR, 7Z, TAR, PDF extraction (future iteration)
- Batch processor path (already on worker thread, uses synchronous `prepare_files()`)

---

## Files Touched

| File | Change |
|------|--------|
| `modules/utils/archives.py` | Replace extract loop with `extractall`; add `extract_zip_parallel()` |
| `modules/utils/file_handler.py` | Add `ExtractionWorker(QThread)`; add `prepare_files_async()` |
| `app/controllers/image.py` | Use `prepare_files_async()` in `load_initial_image()` |
| `tests/utils/test_archives.py` | New — 3 tests |
