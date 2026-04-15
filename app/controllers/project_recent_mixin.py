from __future__ import annotations

import os

from PySide6.QtCore import QSettings


class ProjectRecentMixin:
    MAX_RECENT = 15

    def add_recent_project(self, path: str) -> None:
        if not path or not os.path.isfile(path):
            return
        path = os.path.normpath(os.path.abspath(path))
        entries = self.get_recent_projects()
        existing = next((entry for entry in entries if os.path.normpath(entry["path"]) == path), None)
        pinned = existing.get("pinned", False) if existing else False
        entries = [entry for entry in entries if os.path.normpath(entry["path"]) != path]
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        entries.insert(0, {"path": path, "mtime": mtime, "pinned": pinned})
        entries = entries[: self.MAX_RECENT]
        self._save_entries(entries)

    def get_recent_projects(self) -> list:
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("recent_projects")
        paths = settings.value("paths", []) or []
        mtimes = settings.value("mtimes", []) or []
        pinneds = settings.value("pinned", []) or []
        settings.endGroup()
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(mtimes, list):
            mtimes = [mtimes]
        if not isinstance(pinneds, list):
            pinneds = [pinneds]

        result = []
        for index, (path, mtime) in enumerate(zip(paths, mtimes)):
            try:
                resolved_mtime = float(mtime)
            except (TypeError, ValueError):
                resolved_mtime = 0.0
            try:
                if os.path.isfile(path):
                    resolved_mtime = float(os.path.getmtime(path))
            except OSError:
                pass
            try:
                pinned = str(pinneds[index]).lower() == "true" if index < len(pinneds) else False
            except Exception:
                pinned = False
            result.append({"path": str(path), "mtime": resolved_mtime, "pinned": pinned})

        result.sort(key=lambda entry: float(entry.get("mtime", 0.0) or 0.0), reverse=True)
        return result

    def remove_recent_project(self, path: str) -> None:
        path = os.path.normpath(os.path.abspath(path))
        entries = [
            entry
            for entry in self.get_recent_projects()
            if os.path.normpath(entry["path"]) != path
        ]
        self._save_entries(entries)

    def toggle_pin_project(self, path: str, pinned: bool) -> None:
        path = os.path.normpath(os.path.abspath(path))
        entries = self.get_recent_projects()
        for entry in entries:
            if os.path.normpath(entry["path"]) == path:
                entry["pinned"] = pinned
                break
        self._save_entries(entries)

    def clear_recent_projects(self) -> None:
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("recent_projects")
        settings.remove("")
        settings.endGroup()

    @staticmethod
    def _save_entries(entries: list) -> None:
        settings = QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup("recent_projects")
        settings.setValue("paths", [entry["path"] for entry in entries])
        settings.setValue("mtimes", [entry["mtime"] for entry in entries])
        settings.setValue("pinned", [entry.get("pinned", False) for entry in entries])
        settings.endGroup()
