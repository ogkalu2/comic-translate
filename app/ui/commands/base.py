from __future__ import annotations

import numpy as np
from typing import TypedDict, TYPE_CHECKING
from PySide6.QtGui import QColor, QBrush, QPen, QPainterPath, Qt
from PySide6.QtWidgets import QGraphicsPathItem
from PySide6.QtCore import QRectF, QPointF
from PySide6 import QtGui, QtWidgets
import imkit as imk

from ..canvas.text.text_item_properties import TextItemProperties
from modules.utils.textblock import TextBlock
from ..canvas.rectangle import MoveableRectItem
from ..canvas.text_item import TextBlockItem
from modules.utils.common_utils import is_close

if TYPE_CHECKING:
    from app.ui.canvas.image_viewer import ImageViewer

class PenSettings(TypedDict):
    color: QColor
    width: int
    style: Qt.PenStyle
    cap: Qt.PenCapStyle
    join: Qt.PenJoinStyle

class PathProperties(TypedDict):
    path: QPainterPath
    pen: str  # HexArgb color string
    brush: str  # HexArgb color string
    width: int
    pen_settings: PenSettings

class PathCommandBase:
    """Base class with shared functionality for path-related commands"""
    
    @staticmethod
    def save_path_properties(path_item) -> PathProperties:
        """Save properties of a path item"""
        return {
            'path': path_item.path(),
            'pen': path_item.pen().color().name(QColor.HexArgb),
            'brush': path_item.brush().color().name(QColor.HexArgb),
            'width': path_item.pen().width(),
            'pen_settings': {
                'color': path_item.pen().color(),
                'width': path_item.pen().width(),
                'style': path_item.pen().style(),
                'cap': path_item.pen().capStyle(),
                'join': path_item.pen().joinStyle()
            }
        }

    @staticmethod
    def create_path_item(properties):
        """Create a new path item with given properties"""
        pen = QPen()
        pen_settings = properties['pen_settings']
        pen.setColor(pen_settings['color'])
        pen.setWidth(pen_settings['width'])
        pen.setStyle(pen_settings['style'])
        pen.setCapStyle(pen_settings['cap'])
        pen.setJoinStyle(pen_settings['join'])

        path_item = QGraphicsPathItem()
        path_item.setPath(properties['path'])
        path_item.setPen(pen)
        
        if properties['brush'] == "#80ff0000":
            brush_color = QColor(properties['brush'])
            path_item.setBrush(QBrush(brush_color))
            
        return path_item

    @staticmethod
    def find_matching_item(scene, properties):
        """Find an item in the scene matching the given properties"""
        for item in scene.items():
            if isinstance(item, QGraphicsPathItem):
                if (item.path() == properties['path'] and
                    item.pen().color().name(QColor.HexArgb) == properties['pen'] and
                    item.brush().color().name(QColor.HexArgb) == properties['brush'] and
                    item.pen().width() == properties['width']):
                    return item
        return None

class RectCommandBase:
    """Base class with shared functionality for rect-related commands"""
    
    @staticmethod
    def save_rect_properties(item):
        """Save properties of a path item"""
        return {
            'pos':(item.pos().x(), item.pos().y()),
            'rotation': item.rotation(),
            'width': item.boundingRect().width(),
            'height': item.boundingRect().height(),
            'transform_origin': (item.transformOriginPoint().x(), 
                                     item.transformOriginPoint().y()),
        }

    @staticmethod
    def create_rect_item(properties, viewer: ImageViewer):
        """Create a new rect item with given properties using the viewer's method"""
        rect = QRectF(0, 0, properties['width'], properties['height'])
        transform_origin = QPointF(*properties['transform_origin'])
        position = QPointF(*properties['pos'])
        rotation = properties['rotation']
        
        # Use the viewer's add_rectangle method for consistent handling
        rect_item = viewer.add_rectangle(rect, position, rotation, transform_origin)
        return rect_item


    @staticmethod
    def find_matching_rect(scene, properties):
        """Find an item in the scene matching the given properties"""
        for item in scene.items():
            if isinstance(item, MoveableRectItem):
                if (is_close(item.pos().x(), properties['pos'][0]) and
                    is_close(item.pos().y(), properties['pos'][1]) and
                    is_close(item.boundingRect().width(), properties['width']) and
                    is_close(item.boundingRect().height(), properties['height']) and
                    is_close(item.rotation(), properties['rotation']) and
                    is_close(item.transformOriginPoint().x(), properties['transform_origin'][0]) and
                    is_close(item.transformOriginPoint().y(), properties['transform_origin'][1])):
                    return item
        return None
    
    @staticmethod
    def save_blk_properties(blk):
        prp = blk.__dict__
        return prp
    
    @staticmethod
    def find_matching_blk(blk_list, properties):
        for blk in blk_list:
            # Get current block's properties
            current_props = blk.__dict__.copy()
            
            # Check if all properties match
            match = True
            for key in properties:
                value1 = current_props.get(key)
                value2 = properties.get(key)
                
                # Handle numpy arrays properly
                if isinstance(value1, np.ndarray) or isinstance(value2, np.ndarray):
                    # Convert both to numpy arrays if needed for comparison
                    try:
                        arr1 = np.array(value1) if not isinstance(value1, np.ndarray) else value1
                        arr2 = np.array(value2) if not isinstance(value2, np.ndarray) else value2
                        if not np.array_equal(arr1, arr2):
                            match = False
                            break
                    except (ValueError, TypeError):
                        # If conversion fails, fall back to regular comparison
                        if value1 != value2:
                            match = False
                            break
                else:
                    # Use standard equality for non-numpy values
                    if value1 != value2:
                        match = False
                        break
            
            if match:
                return blk

        # Return None if no match is found
        return None
    
    @staticmethod
    def create_new_blk(properties):
        blk = TextBlock()  
        blk.__dict__.update(properties)  
        return blk  
    
    @staticmethod
    def save_txt_item_properties(item):
        """Save TextBlockItem properties using the centralized TextItemProperties"""
        return TextItemProperties.from_text_item(item)
    
    @staticmethod
    def create_new_txt_item(properties, viewer: ImageViewer):  
        """Create a new TextBlockItem using the centralized add_text_item method"""
        
        # Convert properties dict to TextItemProperties if needed
        if isinstance(properties, dict):
            text_props = TextItemProperties.from_dict(properties)
        else:
            text_props = properties
            
        # Use the viewer's add_text_item method for consistent creation
        text_item = viewer.add_text_item(text_props)
        
        return text_item
    
    @staticmethod
    def find_matching_txt_item(scene, properties):
        """Find a TextBlockItem in the scene matching the given properties"""
        for item in scene.items():
            if isinstance(item, TextBlockItem):
                # Compare all relevant properties with is_close for numerical values
                if (item.font_family == properties.font_family and
                    is_close(item.font_size, properties.font_size) and
                    item.text_color == properties.text_color and
                    item.alignment == properties.alignment and
                    is_close(item.line_spacing, properties.line_spacing) and
                    item.outline_color == properties.outline_color and
                    is_close(item.outline_width, properties.outline_width) and
                    item.bold == properties.bold and
                    item.italic == properties.italic and
                    item.underline == properties.underline and
                    is_close(item.pos().x(), properties.position[0]) and
                    is_close(item.pos().y(), properties.position[1]) and
                    is_close(item.rotation(), properties.rotation) and
                    is_close(item.scale(), properties.scale) and
                    is_close(item.transformOriginPoint().x(), properties.transform_origin[0]) and
                    is_close(item.transformOriginPoint().y(), properties.transform_origin[1]) and
                    is_close(item.boundingRect().width(), properties.width)):
                    return item
        return None


class PatchProperties(TypedDict):
    bbox: tuple            # (x, y, w, h)
    png_path: str          # absolute path to the patch PNG on disk
    hash: str             # hash of the patch image + bbox

class PatchCommandBase:
    """Shared helpers for pixmap patch commands"""

    HASH_KEY = 0

    @staticmethod
    def create_patch_item(properties, viewer: ImageViewer):
        x, y, w, h = properties['bbox']
        img = imk.read_image(properties['png_path']) if 'png_path' in properties else properties['image']
        qimg = QtGui.QImage(img.data, w, h, img.strides[0],
                            QtGui.QImage.Format.Format_RGB888)
        pix  = QtGui.QPixmap.fromImage(qimg)
        item = QtWidgets.QGraphicsPixmapItem(pix)
        
        # Handle webtoon mode with scene coordinates
        if 'scene_pos' in properties and viewer.webtoon_mode:
            scene_x, scene_y = properties['scene_pos']
            item.setPos(scene_x, scene_y)
            item.setZValue(0.5)  # Above images but below text
        else:
            item.setPos(x, y)
            item.setZValue(0.5)
        item.setData(PatchCommandBase.HASH_KEY, properties['hash'])
        viewer._scene.addItem(item)
        viewer._scene.update()
        return item

    @staticmethod
    def find_matching_item(scene, properties):
        x, y, w, h = properties['bbox']
        want_hash = properties['hash']
        
        # Check if we have scene position (webtoon mode)
        if 'scene_pos' in properties:
            scene_x, scene_y = properties['scene_pos']
        else:
            scene_x, scene_y = x, y

        for itm in scene.items():
            if not isinstance(itm, QtWidgets.QGraphicsPixmapItem):
                continue

            # Check hash first for efficiency
            stored_hash = itm.data(PatchCommandBase.HASH_KEY)
            if stored_hash != want_hash:
                continue

            # Check size
            if (itm.pixmap().width() != w or itm.pixmap().height() != h):
                continue
                
            # Check position (try both scene and bbox coordinates)
            item_x, item_y = int(itm.pos().x()), int(itm.pos().y())
            if ((item_x == int(scene_x) and item_y == int(scene_y)) or 
                (item_x == x and item_y == y)):
                return itm
                
        return None
