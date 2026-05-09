from __future__ import annotations

from app.projects.project_state import ensure_project_blob_materialized
from modules.utils.file_handler import ensure_prepared_path_materialized


def ensure_path_materialized(path: str) -> bool:
    return ensure_project_blob_materialized(path) or ensure_prepared_path_materialized(path)
