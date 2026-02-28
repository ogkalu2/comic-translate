import os

from PySide6 import QtGui, QtWidgets
from PySide6.QtGui import QFont, QFontDatabase


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

    def get_font_family(self, font_input: str) -> QFont:
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            font_id = QFontDatabase.addApplicationFont(font_input)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    return font_families[0]

        return font_input

    def add_custom_font(self, font_input: str):
        if os.path.splitext(font_input)[1].lower() in [".ttf", ".ttc", ".otf", ".woff", ".woff2"]:
            QFontDatabase.addApplicationFont(font_input)

    def get_color(self):
        default_color = QtGui.QColor("#000000")
        color_dialog = QtWidgets.QColorDialog()
        color_dialog.setCurrentColor(default_color)
        if color_dialog.exec() == QtWidgets.QDialog.Accepted:
            return color_dialog.selectedColor()

    def set_font(self, font_family: str):
        self.font_dropdown.setCurrentFont(font_family)
