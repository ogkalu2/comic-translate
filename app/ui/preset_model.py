"""Tool Presets data model and persistence layer.

Each preset captures a full text-rendering configuration so typesetters
can swap between distinct font/style combos with a single click.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from modules.utils.paths import get_user_data_dir

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────
_PRESETS_DIR_NAME = "presets"
_FONTS_DIR_NAME = "fonts"


def _presets_dir() -> str:
    d = os.path.join(get_user_data_dir(), _PRESETS_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def _fonts_dir() -> str:
    d = os.path.join(get_user_data_dir(), _FONTS_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class ToolPreset:
    """A single tool preset – full text formatting snapshot."""

    name: str = ""
    font_family: str = ""
    font_size: int = 12
    bold: bool = False
    italic: bool = False
    underline: bool = False
    line_spacing: float = 1.0
    color: str = "#000000"
    outline: bool = True
    outline_color: str = "#ffffff"
    outline_width: float = 1.0
    alignment: int = 1  # 0=left, 1=center, 2=right

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ToolPreset:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


@dataclass
class PresetCategory:
    """A named group of presets (e.g. 'Manga-Fantasy')."""

    name: str = "Default"
    presets: List[ToolPreset] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "presets": [p.to_dict() for p in self.presets],
        }

    @classmethod
    def from_dict(cls, d: dict) -> PresetCategory:
        name = d.get("name", "Default")
        presets = [ToolPreset.from_dict(p) for p in d.get("presets", [])]
        return cls(name=name, presets=presets)


# ── Manager ──────────────────────────────────────────────────────────

class PresetManager:
    """Manages persistence of preset categories as JSON files.

    Directory layout::

        <user_data_dir>/presets/
            Default.json
            Manga-Fantasy.json
            Manhwa-Manhua.json
    """

    _FONT_EXTENSIONS = frozenset({".ttf", ".ttc", ".otf", ".woff", ".woff2"})

    def __init__(self) -> None:
        self._categories: dict[str, PresetCategory] = {}
        self.reload()

    # ── public API ───────────────────────────────────────────────────

    @property
    def category_names(self) -> list[str]:
        return sorted(self._categories.keys())

    def get_category(self, name: str) -> Optional[PresetCategory]:
        return self._categories.get(name)

    def reload(self) -> None:
        """Re-scan the presets directory and load all categories."""
        self._categories.clear()
        presets_dir = _presets_dir()
        for fname in os.listdir(presets_dir):
            if not fname.lower().endswith(".json"):
                continue
            fpath = os.path.join(presets_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cat = PresetCategory.from_dict(data)
                self._categories[cat.name] = cat
            except Exception:
                logger.warning("Failed to load preset file: %s", fpath, exc_info=True)

        # Ensure at least a "Default" category exists
        if not self._categories:
            self.create_category("Default")

    def save_category(self, name: str) -> None:
        cat = self._categories.get(name)
        if cat is None:
            return
        fpath = os.path.join(_presets_dir(), f"{cat.name}.json")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(cat.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception:
            logger.error("Failed to save category '%s'", name, exc_info=True)

    def create_category(self, name: str) -> PresetCategory:
        name = name.strip()
        if not name:
            name = "Default"
        if name in self._categories:
            return self._categories[name]
        cat = PresetCategory(name=name)
        self._categories[name] = cat
        self.save_category(name)
        return cat

    def delete_category(self, name: str) -> bool:
        if name not in self._categories:
            return False
        fpath = os.path.join(_presets_dir(), f"{name}.json")
        try:
            if os.path.isfile(fpath):
                os.remove(fpath)
        except OSError:
            logger.warning("Could not remove preset file: %s", fpath, exc_info=True)
        del self._categories[name]
        # Always keep at least one category
        if not self._categories:
            self.create_category("Default")
        return True

    def rename_category(self, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name or old_name not in self._categories or new_name in self._categories:
            return False
        cat = self._categories.pop(old_name)
        # Remove old file
        old_path = os.path.join(_presets_dir(), f"{old_name}.json")
        try:
            if os.path.isfile(old_path):
                os.remove(old_path)
        except OSError:
            pass
        cat.name = new_name
        self._categories[new_name] = cat
        self.save_category(new_name)
        return True

    # ── Preset CRUD ──────────────────────────────────────────────────

    def add_preset(self, category_name: str, preset: ToolPreset) -> None:
        cat = self._categories.get(category_name)
        if cat is None:
            cat = self.create_category(category_name)
        cat.presets.append(preset)
        self.save_category(category_name)

    def remove_preset(self, category_name: str, index: int) -> bool:
        cat = self._categories.get(category_name)
        if cat is None or index < 0 or index >= len(cat.presets):
            return False
        cat.presets.pop(index)
        self.save_category(category_name)
        return True

    def update_preset(self, category_name: str, index: int, preset: ToolPreset) -> bool:
        cat = self._categories.get(category_name)
        if cat is None or index < 0 or index >= len(cat.presets):
            return False
        cat.presets[index] = preset
        self.save_category(category_name)
        return True

    def rename_preset(self, category_name: str, index: int, new_name: str) -> bool:
        cat = self._categories.get(category_name)
        if cat is None or index < 0 or index >= len(cat.presets):
            return False
        cat.presets[index].name = new_name.strip()
        self.save_category(category_name)
        return True

    def move_preset(self, category_name: str, from_index: int, to_index: int) -> bool:
        cat = self._categories.get(category_name)
        if cat is None:
            return False
        presets = cat.presets
        if from_index < 0 or from_index >= len(presets) or to_index < 0 or to_index >= len(presets):
            return False
        p = presets.pop(from_index)
        presets.insert(to_index, p)
        self.save_category(category_name)
        return True

    # ── Font import helpers ──────────────────────────────────────────

    def import_fonts_to_category(
        self, category_name: str, font_paths: list[str]
    ) -> list[tuple[str, str]]:
        """Copy font files into the user fonts dir and create preset entries.

        Returns list of (font_file_basename, family_name) for each
        successfully imported font. The caller is responsible for loading
        the font into QFontDatabase before calling this, since that is a
        GUI concern.  The *family_name* reported here is just the file
        basename without extension (a best-guess display name); the
        actual family name should be resolved by the caller after loading.
        """
        results: list[tuple[str, str]] = []
        fonts_dir = _fonts_dir()

        for src in font_paths:
            ext = os.path.splitext(src)[1].lower()
            if ext not in self._FONT_EXTENSIONS:
                continue
            basename = os.path.basename(src)
            dst = os.path.join(fonts_dir, basename)
            if os.path.normcase(src) != os.path.normcase(dst):
                try:
                    shutil.copy2(src, dst)
                except OSError:
                    logger.warning("Could not copy font %s → %s", src, dst, exc_info=True)
                    continue

            display_name = os.path.splitext(basename)[0]
            results.append((basename, display_name))

        return results
