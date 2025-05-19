from PySide6 import QtCore, QtGui, QtWidgets
import cv2
from PIL import Image
import numpy as np
from .text_item import TextBlockItem

class ImageSaveRenderer:
    def __init__(self, cv2_image):
        self.cv2_image = cv2_image
        self.scene = QtWidgets.QGraphicsScene()

        self.qimage = self.cv2_to_qimage(cv2_image)
        # Create a QGraphicsPixmapItem with the QPixmap
        self.pixmap = QtGui.QPixmap.fromImage(self.qimage)
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(self.pixmap)

        # Set scene size to match image
        self.scene.setSceneRect(0, 0, self.qimage.width(), self.qimage.height())

        # Add QGraphicsPixmapItem to the scene
        self.scene.addItem(self.pixmap_item)


    def cv2_to_qimage(self, cv2_img):
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb_image.shape
        bytes_per_line = channel * width
        return QtGui.QImage(rgb_image.data, width, height, bytes_per_line, QtGui.QImage.Format.Format_RGB888)

    def add_state_to_image(self, state):

        for text_block in state.get('text_items_state', []):
            text_item = TextBlockItem(
                text=text_block['text'],
                parent_item = self.pixmap_item,
                font_family=text_block['font_family'],
                font_size=text_block['font_size'],
                render_color=text_block['text_color'],
                alignment=text_block['alignment'],
                line_spacing=text_block['line_spacing'],
                outline_color=text_block['outline_color'],
                outline_width=text_block['outline_width'],
                bold=text_block['bold'],
                italic=text_block['italic'],
                underline=text_block['underline'],
            )

            text_item.set_text(text_block['text'], text_block['width'])
            if 'direction' in text_block:
                text_item.set_direction(text_block['direction'])
            if text_block['transform_origin']:
                text_item.setTransformOriginPoint(QtCore.QPointF(*text_block['transform_origin']))
            text_item.setPos(QtCore.QPointF(*text_block['position']))
            text_item.setRotation(text_block['rotation'])
            text_item.setScale(text_block['scale'])
            text_item.selection_outlines = text_block['selection_outlines']
            text_item.update()

            self.scene.addItem(text_item)

    def render_to_image(self):
        # Create a high-resolution QImage
        scale_factor = 2  # Increase this for higher resolution
        original_size = self.pixmap.size()
        scaled_size = original_size * scale_factor
        
        qimage = QtGui.QImage(scaled_size, QtGui.QImage.Format.Format_ARGB32)
        qimage.fill(QtCore.Qt.transparent)

        # Create a QPainter with antialiasing
        painter = QtGui.QPainter(qimage)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)

        # Render the scene
        self.scene.render(painter)
        painter.end()

        # Scale down the image to the original size
        qimage = qimage.scaled(original_size, 
                            QtCore.Qt.AspectRatioMode.KeepAspectRatio, 
                            QtCore.Qt.TransformationMode.SmoothTransformation)

        # Convert QImage to cv2 image
        qimage = qimage.convertToFormat(QtGui.QImage.Format.Format_RGB888)
        width = qimage.width()
        height = qimage.height()
        bytes_per_line = qimage.bytesPerLine()

        byte_count = qimage.sizeInBytes()
        expected_size = height * bytes_per_line  # bytes per line can include padding

        if byte_count != expected_size:
            print(f"QImage sizeInBytes: {byte_count}, Expected size: {expected_size}")
            print(f"Image dimensions: ({width}, {height}), Format: {qimage.format()}")
            raise ValueError(f"Byte count mismatch: got {byte_count} but expected {expected_size}")

        ptr = qimage.bits()

        # Convert memoryview to a numpy array considering the complete data with padding
        arr = np.array(ptr).reshape((height, bytes_per_line))
        # Exclude the padding bytes, keeping only the relevant image data
        arr = arr[:, :width * 3]
        # Reshape to the correct dimensions without the padding bytes
        arr = arr.reshape((height, width, 3))

        return arr

    def save_image(self, output_path: str):
        final_bgr = self.render_to_image()
        final_rgb = cv2.cvtColor(final_bgr, cv2.COLOR_BGR2RGB)
        pil_img   = Image.fromarray(final_rgb)
        pil_img.save(output_path)

    def apply_patches(self, patches: list[dict]):
        """Apply inpainting patches to the image."""

        for patch in patches:
            # Extract data from the patch dict
            x, y, w, h = patch['bbox']
            patch_image = cv2.imread(patch['png_path']) if 'png_path' in patch else patch['cv2_img']
            
            # Convert patch to QImage
            patch_qimage = self.cv2_to_qimage(patch_image)
            patch_pixmap = QtGui.QPixmap.fromImage(patch_qimage)
            
            # Create a pixmap item for the patch
            patch_item = QtWidgets.QGraphicsPixmapItem(patch_pixmap, self.pixmap_item)
            
            # Position the patch relative to its parent (pixmap_item)
            patch_item.setPos(x, y)
            patch_item.setZValue(self.pixmap_item.zValue() + 0.5)



