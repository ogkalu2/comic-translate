from PySide6 import QtCore, QtGui, QtWidgets
import imkit as imk
import numpy as np
from app.path_materialization import ensure_path_materialized
from .text_item import TextBlockItem
from .text.text_item_properties import TextItemProperties

class ImageSaveRenderer:
    def __init__(self, image: np.ndarray):
        self.rgb_image = image
        self.scene = QtWidgets.QGraphicsScene()

        self.qimage = self.img_array_to_qimage(image)
        # Create a QGraphicsPixmapItem with the QPixmap
        self.pixmap = QtGui.QPixmap.fromImage(self.qimage)
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(self.pixmap)

        # Set scene size to match image
        self.scene.setSceneRect(0, 0, self.qimage.width(), self.qimage.height())

        # Add QGraphicsPixmapItem to the scene
        self.scene.addItem(self.pixmap_item)


    def img_array_to_qimage(self, rgb_img: np.ndarray) -> QtGui.QImage:
        height, width, channel = rgb_img.shape
        bytes_per_line = channel * width
        return QtGui.QImage(rgb_img.data, width, height, bytes_per_line, QtGui.QImage.Format.Format_RGB888)

    def add_state_to_image(self, state, page_idx=None, main_page=None):
        # Add spanning text items if we have the context to do so
        if page_idx is not None and main_page is not None:
            self.add_spanning_text_items(state, page_idx, main_page)

        for text_block in state.get('text_items_state', []):
            # Use TextItemProperties for consistent text item construction
            text_props = TextItemProperties.from_dict(text_block)
            
            text_item = TextBlockItem(
                text=text_props.text,
                source_text=getattr(text_props, "source_text", ""),
                font_family=text_props.font_family,
                font_size=text_props.font_size,
                render_color=text_props.text_color,
                alignment=text_props.alignment,
                line_spacing=text_props.line_spacing,
                outline_color=text_props.outline_color,
                outline_width=text_props.outline_width,
                second_outline=text_props.second_outline,
                second_outline_color=text_props.second_outline_color,
                second_outline_width=text_props.second_outline_width,
                text_gradient=text_props.text_gradient,
                text_gradient_start_color=text_props.text_gradient_start_color,
                text_gradient_end_color=text_props.text_gradient_end_color,
                bold=text_props.bold,
                italic=text_props.italic,
                underline=text_props.underline,
                direction=text_props.direction,
                block_uid=getattr(text_props, "block_uid", ""),
            )

            text_item.set_text(
                text_props.text,
                text_props.width,
                preserve_source_text=True,
            )
            if text_props.direction:
                text_item.set_direction(text_props.direction)
            if text_props.transform_origin:
                text_item.setTransformOriginPoint(QtCore.QPointF(*text_props.transform_origin))
            text_item.setPos(QtCore.QPointF(*text_props.position))
            text_item.setRotation(text_props.rotation)
            text_item.setScale(text_props.scale)
            text_item.set_vertical(bool(text_props.vertical))
            text_item.set_layout_box_size(text_props.width, text_props.height)
            if (
                text_props.width is not None
                and text_props.height is not None
                and text_props.width > 0
                and text_props.height > 0
                and not text_item.is_html(text_props.text)
            ):
                max_font_size = int(round(text_props.font_size)) if text_props.font_size else None
                text_item.reflow_from_source_text(
                    text_props.width,
                    text_props.height,
                    max_font_size=max_font_size,
                )
                # Keep the exact wrapped text produced by the render pass while
                # preserving the fitted font size chosen above.
                text_item.set_plain_text(text_props.text, preserve_source_text=True, update_width=False)
                text_item.set_layout_box_size(text_props.width, text_props.height)
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
        existing_text_items = viewer_state.get('text_items_state', [])

        current_image_path = main_page.image_files[page_idx]
        ensure_path_materialized(current_image_path)
        current_image = imk.read_image(current_image_path)
        current_page_height = current_image.shape[0]

        for other_page_idx, other_image_path in enumerate(main_page.image_files):
            if other_page_idx == page_idx:
                continue

            if other_image_path not in main_page.image_states:
                continue

            page_gap = page_idx - other_page_idx
            if abs(page_gap) != 1:  # Only check adjacent pages
                continue

            ensure_path_materialized(other_image_path)
            other_image = imk.read_image(other_image_path)
            other_page_height = other_image.shape[0]
            other_viewer_state = main_page.image_states[other_image_path].get('viewer_state', {})
            other_text_items = other_viewer_state.get('text_items_state', [])

            if not other_text_items:
                continue

            for text_item in other_text_items:
                pos = text_item.get('position', (0, 0))
                item_x1, item_y1 = pos
                height = text_item.get('height')
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

        # Convert QImage to RGB numpy array
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
        imk.write_image(output_path, final_rgb)

    def apply_patches(self, patches: list[dict]):
        """Apply inpainting patches to the image."""

        for patch in patches:
            # Extract data from the patch dict
            x, y, w, h = patch['bbox']
            if 'png_path' in patch:
                patch_path = patch['png_path']
                ensure_path_materialized(patch_path)
                patch_image = imk.read_image(patch_path)
            else:
                # Handle direct image data (expected to be RGB format)
                patch_image = patch['image']
            
            # Convert patch to QImage
            patch_qimage = self.img_array_to_qimage(patch_image)
            patch_pixmap = QtGui.QPixmap.fromImage(patch_qimage)
            
            # Create a pixmap item for the patch
            patch_item = QtWidgets.QGraphicsPixmapItem(patch_pixmap, self.pixmap_item)
            
            # Position the patch relative to its parent (pixmap_item)
            patch_item.setPos(x, y)
            patch_item.setZValue(self.pixmap_item.zValue() + 0.5)



