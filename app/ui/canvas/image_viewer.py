import numpy as np
from typing import List, Dict, Tuple

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QGraphicsView, QGraphicsPixmapItem, QGraphicsScene
from PySide6.QtCore import Signal, Qt, QRectF, QPointF

from .text_item import TextBlockItem
from .text.text_item_properties import TextItemProperties
from .rectangle import MoveableRectItem
from .rotate_cursor import RotateHandleCursors
from .drawing_manager import DrawingManager
from .webtoons.webtoon_manager import LazyWebtoonManager
from .interaction_manager import InteractionManager
from .event_handler import EventHandler


class ImageViewer(QGraphicsView):
    # Signals
    rectangle_created = Signal(MoveableRectItem)
    rectangle_selected = Signal(QRectF)
    rectangle_deleted = Signal(QRectF)
    command_emitted = Signal(QtGui.QUndoCommand)
    connect_rect_item = Signal(MoveableRectItem)
    connect_text_item =  Signal(TextBlockItem)
    page_changed = Signal(int)
    clear_text_edits = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        
        # Core Setup
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.photo = QGraphicsPixmapItem()
        self.photo.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
        self._scene.addItem(self.photo)

        # Managers using Composition
        self.drawing_manager = DrawingManager(self)
        self.webtoon_manager = LazyWebtoonManager(self)
        self.interaction_manager = InteractionManager(self)
        self.event_handler = EventHandler(self)

        # Viewer Properties
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.viewport().grabGesture(Qt.GestureType.PanGesture)
        # Default to NoDrag; only enable ScrollHandDrag when explicit 'pan' tool is active
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # State
        self.empty = True
        self.zoom = 0
        self.current_tool = None
        self.panning = False
        self.pan_start_pos = None
        self.last_pan_pos = QtCore.QPoint()
        self.total_scale_factor = 0.2 
        self.rotate_cursors = RotateHandleCursors()
        self.webtoon_view_state = {}

        # Page detection state (used by webtoon and event handlers)
        self._programmatic_scroll = False
        
        # Item lists
        self.rectangles: list[MoveableRectItem] = []
        self.text_items: list[TextBlockItem] = []
        self.selected_rect: MoveableRectItem = None
        
        # Box drawing state
        self.start_point: QPointF = None
        self.current_rect: MoveableRectItem = None

    # Properties to maintain public API
    @property
    def webtoon_mode(self):
        """Read-only proxy to check if webtoon mode is active."""
        return self.webtoon_manager.is_active()

    # Public API
    def hasPhoto(self) -> bool:
        if self.webtoon_mode:
            return not self.empty and len(self.webtoon_manager.loaded_pages) > 0
        return not self.empty
    
    def load_images_webtoon(self, file_paths: List[str], current_page: int = 0) -> bool:
        """Load images using lazy loading strategy."""
        return self.webtoon_manager.load_images_lazy(file_paths, current_page)

    def scroll_to_page(self, page_index: int, position='top'):
        if self.webtoon_mode:
            self.webtoon_manager.scroll_to_page(page_index, position)

    def fitInView(self):
        # Handle lazy webtoon manager
        if self.webtoon_mode:
            if not self.empty and self.webtoon_manager.image_items:
                # Use first loaded image or fallback to first position
                first_item = None
                for i in range(len(self.webtoon_manager.image_file_paths)):
                    if i in self.webtoon_manager.image_items:
                        first_item = self.webtoon_manager.image_items[i]
                        break
                
                if first_item:
                    image_rect = QRectF(first_item.pos(), first_item.boundingRect().size())
                else:
                    # Fallback to estimated first page bounds
                    y_pos = self.webtoon_manager.image_positions[0] if self.webtoon_manager.image_positions else 100
                    height = self.webtoon_manager.image_heights[0] if self.webtoon_manager.image_heights else 1000
                    width = self.webtoon_manager.webtoon_width
                    image_rect = QRectF(0, y_pos, width, height)
                
                if not image_rect.isNull():
                    padding = 20
                    padded_rect = image_rect.adjusted(-padding, -padding, padding, padding)
                    
                    self.setSceneRect(padded_rect)
                    unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                    self.scale(1 / unity.width(), 1 / unity.height())
                    viewrect = self.viewport().rect()
                    scenerect = self.transform().mapRect(padded_rect)
                    factor = min(viewrect.width() / scenerect.width(),
                                 viewrect.height() / scenerect.height())
                    self.scale(factor, factor)
                    self.centerOn(image_rect.center())
                    
                    # Set the full scene rect for scrolling
                    self.setSceneRect(0, 0, self.webtoon_manager.webtoon_width, self.webtoon_manager.total_height)

        elif self.hasPhoto():
            rect = self.photo.boundingRect()
            if not rect.isNull():
                self.setSceneRect(rect)
                unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())
                viewrect = self.viewport().rect()
                scenerect = self.transform().mapRect(rect)
                factor = min(viewrect.width() / scenerect.width(),
                             viewrect.height() / scenerect.height())
                self.scale(factor, factor)
                self.centerOn(rect.center())

    def set_tool(self, tool: str):
        self.current_tool = tool
        if tool == 'pan':
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        elif tool in ['brush', 'eraser']:
            self.setDragMode(QGraphicsView.NoDrag)
            if tool == 'brush':
                cursor = self.drawing_manager.brush_cursor
            else:
                cursor =  self.drawing_manager.eraser_cursor
            self.setCursor(cursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)

    @property
    def brush_size(self):
        return self.drawing_manager.brush_size

    @brush_size.setter
    def brush_size(self, size: int):
        try:
            self.drawing_manager.set_brush_size(size, size)
        except Exception:
            self.drawing_manager.brush_size = size

    @property
    def eraser_size(self):
        return self.drawing_manager.eraser_size

    @eraser_size.setter
    def eraser_size(self, size: int):
        try:
            self.drawing_manager.set_eraser_size(size, size)
        except Exception:
            self.drawing_manager.eraser_size = size

    # Event Handler Methods (Delegated to EventHandler)
    def mousePressEvent(self, event):
        self.event_handler.handle_mouse_press(event)

    def mouseMoveEvent(self, event):
        self.event_handler.handle_mouse_move(event)

    def mouseReleaseEvent(self, event):
        self.event_handler.handle_mouse_release(event)

    def wheelEvent(self, event):
        self.event_handler.handle_wheel(event)

    def viewportEvent(self, event):
        return self.event_handler.handle_viewport_event(event)

    def set_br_er_size(self, size, scaled_size):
        if self.current_tool == 'brush':
            self.drawing_manager.set_brush_size(size, scaled_size)
            self.setCursor(self.drawing_manager.brush_cursor)
        elif self.current_tool == 'eraser':
            self.drawing_manager.set_eraser_size(size, scaled_size)
            self.setCursor(self.drawing_manager.eraser_cursor)

    def constrain_point(self, point: QPointF) -> QPointF:
        if self.webtoon_mode:
            return QPointF(
                max(0, min(point.x(), self.webtoon_manager.webtoon_width)),
                max(0, min(point.y(), self.webtoon_manager.total_height))
            )

        elif self.hasPhoto():
            return QPointF(
                max(0, min(point.x(), self.photo.pixmap().width())),
                max(0, min(point.y(), self.photo.pixmap().height()))
            )
        return point

    def get_image_array(self, paint_all=False, include_patches=True):
        """
        Get image array data. In webtoon mode, returns the visible area image.
        In regular mode, returns the single photo image with optional patches/scene items.
        """
        if not self.hasPhoto():
            return None

        # Handle webtoon mode using the webtoon manager's specialized logic
        if self.webtoon_mode:
            result, _ = self.webtoon_manager.get_visible_area_image(paint_all, include_patches)
            return result

        # Handle regular single image mode
        if self.photo.pixmap() is None:
            return None

        qimage = None
        if paint_all:
            # Create a high-resolution QImage
            scale_factor = 2 # Increase this for higher resolution
            pixmap = self.photo.pixmap()
            original_size = pixmap.size()
            scaled_size = original_size * scale_factor

            qimage = QtGui.QImage(scaled_size, QtGui.QImage.Format_ARGB32)
            qimage.fill(Qt.transparent)

            # Create a QPainter with antialiasing
            painter = QtGui.QPainter(qimage)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
            painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
            

            original_transform = self.transform()
            self._scene.views()[0].resetTransform()
            self._scene.setSceneRect(0, 0, original_size.width(), original_size.height())
            self._scene.render(painter)
            painter.end()


            # Scale down the image to the original size
            qimage = qimage.scaled(
                original_size, 
                QtCore.Qt.AspectRatioMode.KeepAspectRatio, 
                QtCore.Qt.TransformationMode.SmoothTransformation
            )

            # Restore the original transformation
            self._scene.views()[0].setTransform(original_transform)
        
        elif include_patches:
            pixmap = self.photo.pixmap()
            qimage = QtGui.QImage(pixmap.size(), QtGui.QImage.Format_ARGB32)
            qimage.fill(Qt.transparent)
            painter = QtGui.QPainter(qimage)
            painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(0, 0, pixmap)
            
            # Updated patch detection logic - patches are now added directly to scene
            for item in self._scene.items():
                if isinstance(item, QGraphicsPixmapItem) and item != self.photo:
                    # Check if this is a patch item (has the hash key data)
                    if item.data(0) is not None:  # HASH_KEY = 0 from PatchCommandBase
                        pos = item.pos()
                        painter.drawPixmap(int(pos.x()), int(pos.y()), item.pixmap())
            painter.end()
        else:
            qimage = self.photo.pixmap().toImage()

        # Convert QImage to image
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
    
    def qimage_from_array(self, img_array: np.ndarray):
        height, width, channel = img_array.shape
        bytes_per_line = 3 * width
        qimage = QtGui.QImage(img_array.data, width, height, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        return qimage

    def display_image_array(self, img_array: np.ndarray, fit: bool = True):
        qimage = self.qimage_from_array(img_array)
        pixmap = QtGui.QPixmap.fromImage(qimage)
        self.clear_scene()
        self.setPhoto(pixmap, fit=fit)

    def clear_scene(self):
        self.webtoon_manager.clear() 
        self._scene.clear()
        self.rectangles.clear()
        self.text_items.clear()
        self.selected_rect = None
        self.photo = QGraphicsPixmapItem()
        self.photo.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
        self._scene.addItem(self.photo)

    def setPhoto(self, pixmap: QtGui.QPixmap = None, fit: bool = True):
        if pixmap and not pixmap.isNull():
            self.empty = False
            self.photo.setPixmap(pixmap)
            if fit:
                self.fitInView()
        else:
            self.empty = True
            self.photo.setPixmap(QtGui.QPixmap())
        self.zoom = 0

    def get_mask_for_inpainting(self):
        mask = self.drawing_manager.generate_mask_from_strokes()
        return mask
    
    def create_rect_item(self, rect: QRectF, scene_pos: QPointF = None) -> MoveableRectItem:
        rect_item = MoveableRectItem(rect, None)
        self._scene.addItem(rect_item)
        return rect_item

    def add_rectangle(self, rect: QRectF, position: QPointF, rotation: float = 0, origin: QPointF = None) -> MoveableRectItem:
        rect_item = self.create_rect_item(rect)
        rect_item.setPos(position)
        rect_item.setRotation(rotation)
        if origin:
            rect_item.setTransformOriginPoint(origin)
        self.connect_rect_item.emit(rect_item)
        self.rectangles.append(rect_item)
        return rect_item
    
    def add_text_item(self, properties) -> TextBlockItem:
        """
        Create and add a TextBlockItem to the scene using TextItemProperties.
        
        Args:
            properties: TextItemProperties dataclass containing all text item settings
            
        Returns:
            TextBlockItem: The created text item
        """
        
        # If properties is a dict, convert to TextItemProperties
        if isinstance(properties, dict):
            properties = TextItemProperties.from_dict(properties)
        
        # Create the TextBlockItem with the most up-to-date construction logic
        # Based on the load_state function which has the most complete setup
        item = TextBlockItem(
            text=properties.text, 
            font_family=properties.font_family,
            font_size=properties.font_size, 
            render_color=properties.text_color,
            alignment=properties.alignment, 
            line_spacing=properties.line_spacing,
            outline_color=properties.outline_color, 
            outline_width=properties.outline_width,
            bold=properties.bold, 
            italic=properties.italic, 
            underline=properties.underline,
            direction=properties.direction,
        )
        
        # Apply width if specified
        if properties.width is not None:
            item.set_text(properties.text, properties.width)
        
        # Set direction if specified
        item.set_direction(properties.direction)
        
        # Set transform origin if specified
        if properties.transform_origin:
            item.setTransformOriginPoint(QPointF(*properties.transform_origin))
        
        # Set position, rotation, and scale
        item.setPos(QPointF(*properties.position))
        item.setRotation(properties.rotation)
        item.setScale(properties.scale)

        item.set_vertical(bool(properties.vertical))
        item.set_color(properties.text_color)
            
        # Set selection outlines
        item.selection_outlines = properties.selection_outlines.copy()
        
        # Update the item
        item.update()

        # Add to scene and track
        self._scene.addItem(item)
        self.text_items.append(item)
        
        # Emit the connect signal for the text item
        self.connect_text_item.emit(item)
        
        return item
    
    # InteractionManager proxy methods
    def sel_rot_item(self):
        return self.interaction_manager.sel_rot_item()
    
    def select_rectangle(self, rect: MoveableRectItem):
        return self.interaction_manager.select_rectangle(rect)
    
    def deselect_rect(self, rect: MoveableRectItem):
        return self.interaction_manager.deselect_rect(rect)
    
    def deselect_all(self):
        return self.interaction_manager.deselect_all()
    
    def clear_rectangles(self, page_switch=False):
        return self.interaction_manager.clear_rectangles(page_switch)
        
    def clear_rectangles_in_visible_area(self):
        """Clear rectangles that are within the currently visible viewport area."""
        return self.interaction_manager.clear_rectangles_in_visible_area()
    
    def clear_text_items(self, delete=True):
        return self.interaction_manager.clear_text_items(delete)
    
    # DrawingManager proxy methods
    def clear_brush_strokes(self, page_switch=False):
        self.drawing_manager.clear_brush_strokes(page_switch)

    def load_brush_strokes(self, strokes: List[Dict]):
        self.drawing_manager.load_brush_strokes(strokes)

    def save_brush_strokes(self) -> List[Dict]:
        return self.drawing_manager.save_brush_strokes()

    def draw_segmentation_lines(self, bboxes):
        self.drawing_manager.draw_segmentation_lines(bboxes)

    def has_drawn_elements(self) -> bool:
        return self.drawing_manager.has_drawn_elements()

    def scene_to_page_coordinates(self, scene_pos: QPointF) -> Tuple[int, QPointF]:
        if self.webtoon_mode:
            return self.webtoon_manager.layout_manager.scene_to_page_coordinates(scene_pos)

    def page_to_scene_coordinates(self, page_index: int, local_pos: QPointF) -> QPointF:
        if self.webtoon_mode:
            return self.webtoon_manager.layout_manager.page_to_scene_coordinates(page_index, local_pos)

    def get_visible_area_image(self, paint_all=False, include_patches=True) -> Tuple[np.ndarray, list]:
        if self.webtoon_mode:
            return self.webtoon_manager.get_visible_area_image(paint_all, include_patches)
        
    # State Management
    def save_state(self) -> Dict:
        transform = self.transform()
        center = self.mapToScene(self.viewport().rect().center())
        
        rectangles_state = []
        for item in self._scene.items():
            if isinstance(item, MoveableRectItem):
                rectangles_state.append({
                    'rect': (item.pos().x(), item.pos().y(), item.boundingRect().width(), item.boundingRect().height()),
                    'rotation': item.rotation(),
                    'transform_origin': (item.transformOriginPoint().x(), item.transformOriginPoint().y())
                })
            
        text_items_state = []
        for item in self._scene.items():
            if isinstance(item, TextBlockItem):
                # Use TextItemProperties for consistent serialization
                text_props = TextItemProperties.from_text_item(item)
                text_items_state.append(text_props.to_dict())

        return {
            'rectangles': rectangles_state,
            'transform': (transform.m11(), transform.m12(), transform.m13(),
                          transform.m21(), transform.m22(), transform.m23(),
                          transform.m31(), transform.m32(), transform.m33()),
            'center': (center.x(), center.y()),
            'scene_rect': (self.sceneRect().x(), self.sceneRect().y(), 
                           self.sceneRect().width(), self.sceneRect().height()),
            'text_items_state': text_items_state
        }

    def load_state(self, state: Dict):
        self.setTransform(QtGui.QTransform(*state['transform']))
        self.centerOn(QPointF(*state['center']))
        self.setSceneRect(QRectF(*state['scene_rect']))

        for data in state['rectangles']:
            x, y, w, h = data['rect']
            origin = QPointF(*data.get('transform_origin', (0,0))) if 'transform_origin' in data else None
            self.add_rectangle(QRectF(0,0,w,h), QPointF(x,y), data.get('rotation', 0), origin)

        for data in state.get('text_items_state', []):
            # Use the new add_text_item function for consistency
            self.add_text_item(data)