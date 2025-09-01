import os
from PySide6 import QtCore, QtGui, QtSvg

# Use dayu_widgets' utility to locate static resources (supports resources/static)
from ..dayu_widgets import utils as dayu_utils

rot_svg_path = dayu_utils.get_static_file('rotate-arrow-top.svg')

class RotateHandleCursors:
    def __init__(self, size=24):
        self.size = size
        self.cursors = {}
        self.initialize_cursors()

    def load_cursor_image(self, path):
        """Load either an image or SVG file and return a QImage"""
        if path.lower().endswith('.svg'):
            # Handle SVG files
            renderer = QtSvg.QSvgRenderer(path)
            if renderer.isValid():
                image = QtGui.QImage(self.size, self.size, QtGui.QImage.Format_ARGB32)
                image.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(image)
                renderer.render(painter)
                painter.end()
                return image
            return None
        else:
            # Handle regular image files
            image = QtGui.QImage(path)
            if not image.isNull():
                # Resize if needed
                if image.size() != QtCore.QSize(self.size, self.size):
                    image = image.scaled(self.size, self.size, 
                                      QtCore.Qt.KeepAspectRatio, 
                                      QtCore.Qt.SmoothTransformation)
            return image

    def initialize_cursors(self):
        # Define rotation angles for each handle
        rotations = {
            'top': 0,
            'top_right': 45,
            'right': 90,
            'bottom_right': 135,
            'bottom': 180,
            'bottom_left': 225,
            'left': 270,
            'top_left': 315
        }
        
        # Path to cursor image (can be SVG or regular image)
        image_path = rot_svg_path
        
        # Load the base image
        base_image = self.load_cursor_image(image_path)
        
        if base_image is not None:
            for handle, angle in rotations.items():
                # Create transform for rotation
                transform = QtGui.QTransform()
                transform.rotate(angle)
                
                # Apply rotation to image
                rotated_image = base_image.transformed(transform, QtCore.Qt.SmoothTransformation)
                
                # Convert to pixmap and create cursor
                pixmap = QtGui.QPixmap.fromImage(rotated_image)
                # Set hot spot to center using self.size
                self.cursors[handle] = QtGui.QCursor(pixmap, self.size//2, self.size//2)
        else:
            # Fallback to default cursors if image loading fails
            print(f"Failed to load cursor image from {image_path}")
            for handle in rotations.keys():
                self.cursors[handle] = QtGui.QCursor(QtCore.Qt.CrossCursor)

    def get_cursor(self, handle_position):
        return self.cursors.get(handle_position, QtGui.QCursor(QtCore.Qt.ArrowCursor))

