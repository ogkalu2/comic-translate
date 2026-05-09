import os

from PySide6 import QtGui, QtWidgets
from PySide6.QtGui import QFontDatabase

from .constants import user_font_path


class ToolStateMixin:
    def toggle_pan_tool(self):
        if self.pan_button.isChecked():
            self.set_tool("pan")
        else:
            self.set_tool(None)

    def toggle_box_tool(self):
        if self.box_button.isChecked():
            self.set_tool("box")
        else:
            self.set_tool(None)

    def toggle_brush_tool(self):
        if self.brush_button.isChecked():
            self.set_tool("brush")
            size = self.image_viewer.brush_size
            self.set_slider_size(size)
        else:
            self.set_tool(None)

    def toggle_eraser_tool(self):
        if self.eraser_button.isChecked():
            self.set_tool("eraser")
            size = self.image_viewer.eraser_size
            self.set_slider_size(size)
        else:
            self.set_tool(None)

    def set_slider_size(self, size: int):
        self.brush_eraser_slider.blockSignals(True)
        self.brush_eraser_slider.setValue(size)
        self.brush_eraser_slider.blockSignals(False)

    def set_tool(self, tool_name: str):
        self.image_viewer.unsetCursor()
        self.image_viewer.set_tool(tool_name)

        for name, button in self.tool_buttons.items():
            if name != tool_name:
                button.setChecked(False)
            elif tool_name is not None:
                button.setChecked(True)

        if not tool_name:
            for button in self.tool_buttons.values():
                button.setChecked(False)
            self.image_viewer.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)

    def set_brush_eraser_size(self, size: int):
        try:
            current_tool = self.image_viewer.current_tool
        except Exception:
            current_tool = None

        if current_tool == "brush":
            self.image_viewer.brush_size = size
        elif current_tool == "eraser":
            self.image_viewer.eraser_size = size
        else:
            self.image_viewer.brush_size = size
            self.image_viewer.eraser_size = size

        if self.image_viewer.hasPhoto():
            image = self.image_viewer.get_image_array()
            if image is not None:
                h, w = image.shape[:2]
                scaled_size = self.scale_size(size, w, h)

                if current_tool in {"brush", "eraser"}:
                    self.image_viewer.set_br_er_size(size, scaled_size)
                else:
                    self.image_viewer.drawing_manager.set_brush_size(size, scaled_size)
                    self.image_viewer.drawing_manager.set_eraser_size(size, scaled_size)

    def scale_size(self, base_size, image_width, image_height):
        image_diagonal = (image_width**2 + image_height**2) ** 0.5
        reference_diagonal = 1000
        scaling_factor = image_diagonal / reference_diagonal
        scaled_size = base_size * scaling_factor
        return scaled_size

    def _ensure_custom_font_caches(self) -> None:
        if not hasattr(self, "_custom_font_path_to_family"):
            self._custom_font_path_to_family = {}
        if not hasattr(self, "_custom_font_family_cache"):
            self._custom_font_family_cache = {}
        if not hasattr(self, "_custom_font_miss_cache"):
            self._custom_font_miss_cache = set()

    def _load_custom_font_file(self, font_path: str) -> str | None:
        self._ensure_custom_font_caches()
        if not font_path or not os.path.isfile(font_path):
            return None

        font_path = os.path.normpath(font_path)
        if font_path in self._custom_font_path_to_family:
            return self._custom_font_path_to_family[font_path]

        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            return None

        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            return None

        primary = families[0]
        self._custom_font_path_to_family[font_path] = primary
        for family in families:
            self._custom_font_family_cache[family.casefold()] = family
        return primary

    def ensure_custom_font_loaded(self, font_input: str) -> str:
        if not isinstance(font_input, str):
            return font_input

        requested = font_input.strip()
        if not requested:
            return requested

        self._ensure_custom_font_caches()
        lower = requested.casefold()
        if lower in self._custom_font_family_cache:
            return self._custom_font_family_cache[lower]
        if lower in self._custom_font_miss_cache:
            return requested

        ext = os.path.splitext(requested)[1].lower()
        if ext in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            loaded = self._load_custom_font_file(requested)
            return loaded or requested

        for family in QFontDatabase().families():
            if family.casefold() == lower:
                self._custom_font_family_cache[lower] = family
                return family

        if os.path.isdir(user_font_path):
            for name in os.listdir(user_font_path):
                if os.path.splitext(name)[1].lower() not in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
                    continue
                path = os.path.join(user_font_path, name)
                loaded = self._load_custom_font_file(path)
                if loaded and loaded.casefold() == lower:
                    return loaded

        self._custom_font_miss_cache.add(lower)
        return requested

    def get_font_family(self, font_input: str) -> str:
        return self.ensure_custom_font_loaded(font_input)

    def add_custom_font(self, font_input: str):
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            self._load_custom_font_file(font_input)

    def get_color(self):
        default_color = QtGui.QColor("#000000")
        color_dialog = QtWidgets.QColorDialog()
        color_dialog.setCurrentColor(default_color)
        if color_dialog.exec() == QtWidgets.QDialog.Accepted:
            return color_dialog.selectedColor()

    def set_font(self, font_family: str):
        resolved_family = self.ensure_custom_font_loaded(font_family)
        self.font_dropdown.setCurrentFont(QtGui.QFont(resolved_family))
        if self.font_dropdown.currentText() != resolved_family:
            self.font_dropdown.setCurrentText(resolved_family)
