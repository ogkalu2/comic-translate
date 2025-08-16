from PySide6 import QtCore, QtGui, QtWidgets
import cv2
from PIL import Image
import numpy as np
import os
from .text_item import TextBlockItem
from .text.text_item_properties import TextItemProperties

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

    def add_state_to_image(self, state, page_idx=None, main_page=None):
        # Add spanning text items if we have the context to do so
        if page_idx is not None and main_page is not None:
            self.add_spanning_text_items(state, page_idx, main_page)

        for text_block in state.get('text_items_state', []):
            # Use TextItemProperties for consistent text item construction
            text_props = TextItemProperties.from_dict(text_block)
            
            text_item = TextBlockItem(
                text=text_props.text,
                font_family=text_props.font_family,
                font_size=text_props.font_size,
                render_color=text_props.text_color,
                alignment=text_props.alignment,
                line_spacing=text_props.line_spacing,
                outline_color=text_props.outline_color,
                outline_width=text_props.outline_width,
                bold=text_props.bold,
                italic=text_props.italic,
                underline=text_props.underline,
                direction=text_props.direction,
            )

            text_item.set_text(text_props.text, text_props.width)
            if text_props.direction:
                text_item.set_direction(text_props.direction)
            if text_props.transform_origin:
                text_item.setTransformOriginPoint(QtCore.QPointF(*text_props.transform_origin))
            text_item.setPos(QtCore.QPointF(*text_props.position))
            text_item.setRotation(text_props.rotation)
            text_item.setScale(text_props.scale)
            text_item.selection_outlines = text_props.selection_outlines
            text_item.update()

            self.scene.addItem(text_item)

    def add_spanning_text_items(self, viewer_state, page_idx, main_page):
        """
        Add text items from spanning blocks that should appear on this page.
        This function uses 'positional clipping': it places the full text item
        on the render canvas but adjusts its position so that the parts outside
        the intended visible area are positioned off-canvas and are clipped by
        the renderer.
        """
        import cv2  # Import here to avoid circular imports

        existing_text_items = viewer_state.get('text_items_state', [])

        current_image_path = main_page.image_files[page_idx]
        current_image = cv2.imread(current_image_path)
        if current_image is None:
            return
        current_page_height = current_image.shape[0]

        for other_page_idx, other_image_path in enumerate(main_page.image_files):
            if other_page_idx == page_idx:
                continue

            if other_image_path not in main_page.image_states:
                continue

            page_gap = page_idx - other_page_idx
            if abs(page_gap) != 1:  # Only check adjacent pages
                continue

            other_image = cv2.imread(other_image_path)
            if other_image is None:
                continue
            other_page_height = other_image.shape[0]
            other_viewer_state = main_page.image_states[other_image_path].get('viewer_state', {})
            other_text_items = other_viewer_state.get('text_items_state', [])

            if not other_text_items:
                continue

            for text_item in other_text_items:
                pos = text_item.get('position', (0, 0))
                item_x1, item_y1 = pos
                height = text_item.get('height', 0)
                item_y2 = item_y1 + height

                new_pos = None

                if page_gap == 1:  # Current page is BELOW other page
                    # Check if text from the page above extends below its bottom boundary
                    if item_y2 > other_page_height:
                        # Position the item on the current page's canvas such that its top is
                        # shifted up by the height of the portion visible on the page above.
                        # This makes the renderer clip the top and show only the overflowing bottom part.
                        new_y = -(other_page_height - item_y1)
                        new_pos = (item_x1, new_y)

                elif page_gap == -1:  # Current page is ABOVE other page
                    # Check if text from the page below extends above its top boundary (i.e., has a negative y)
                    if item_y1 < 0:
                        # Position the item on the current page's canvas so its top aligns with where
                        # it should appear at the bottom of the current page. The renderer will clip the
                        # rest of the text block that falls below the page's bottom boundary.
                        new_y = current_page_height + item_y1
                        new_pos = (item_x1, new_y)

                if new_pos:
                    # Create a new text item state for the spanning portion.
                    # It's a full copy, but its position causes clipping.
                    spanning_text_item = text_item.copy()
                    spanning_text_item['position'] = new_pos
                    existing_text_items.append(spanning_text_item)

        viewer_state['text_items_state'] = existing_text_items

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
        final_rgb = self.render_to_image()
        pil_img   = Image.fromarray(final_rgb)
        
        settings = QtCore.QSettings("ComicLabs", "ComicTranslate")
        settings.beginGroup('export')
        jpeg_quality = settings.value('jpeg_quality', 95, type=int)
        settings.endGroup()
        
        file_ext = os.path.splitext(output_path)[1].lower()
        if file_ext in ['.jpg', '.jpeg']:
            pil_img.save(output_path, quality=jpeg_quality, optimize=True)
        else:
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



