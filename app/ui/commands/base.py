import numpy as np
from typing import TypedDict
from PySide6.QtGui import QColor, QBrush, QPen, QPainterPath, Qt
from PySide6.QtWidgets import QGraphicsPathItem
from PySide6.QtCore import QRectF, QPointF

from modules.utils.textblock import TextBlock
from ..canvas.rectangle import MoveableRectItem
from ..canvas.text_item import TextBlockItem


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
    def create_rect_item(properties, photo):
        """Create a new rect item with given properties"""
        rect = QRectF(0, 0, properties['width'], properties['height'])
        rect_item = MoveableRectItem(rect, photo)
        rect_item.setTransformOriginPoint(QPointF(*properties['transform_origin']))
        rect_item.setPos(*properties['pos'])
        rect_item.setRotation(properties['rotation'])
        rect_item.setZValue(1)        
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
                
                # If the value is a numpy array, use np.array_equal for comparison
                if isinstance(value1, np.ndarray) and isinstance(value2, np.ndarray):
                    if not np.array_equal(value1, value2):
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
        prp = {
                'text': item.toHtml(),
                'font_family': item.font_family,
                'font_size': item.font_size,
                'text_color': item.text_color,
                'alignment': item.alignment,
                'line_spacing': item.line_spacing,
                'outline_color': item.outline_color,
                'outline_width': item.outline_width,
                'bold': item.bold,
                'italic': item.italic,
                'underline': item.underline,
                'position': (item.pos().x(), item.pos().y()),
                'rotation': item.rotation(),
                'scale': item.scale(),
                'transform_origin': (item.transformOriginPoint().x(), 
                                     item.transformOriginPoint().y()),
                'width': item.boundingRect().width()
            }
        return prp
    
    @staticmethod
    def create_new_txt_item(properties, photo):  
        text_item = TextBlockItem(
            text=properties['text'],
            parent_item = photo,
            font_family=properties['font_family'],
            font_size=properties['font_size'],
            render_color=properties['text_color'],
            alignment=properties['alignment'],
            line_spacing=properties['line_spacing'],
            outline_color=properties['outline_color'],
            outline_width=properties['outline_width'],
            bold=properties['bold'],
            italic=properties['italic'],
            underline=properties['underline'],
            )
        text_item.set_text(properties['text'], properties['width'])
        text_item.setTransformOriginPoint(QPointF(*properties['transform_origin']))
        text_item.setPos(QPointF(*properties['position']))
        text_item.setRotation(properties['rotation'])
        text_item.setScale(properties['scale'])

        return text_item
    
    @staticmethod
    def find_matching_txt_item(scene, properties):
        """Find a TextBlockItem in the scene matching the given properties"""
        for item in scene.items():
            if isinstance(item, TextBlockItem):
                # Compare all relevant properties with is_close for numerical values
                if (item.font_family == properties['font_family'] and
                    is_close(item.font_size, properties['font_size']) and
                    item.text_color == properties['text_color'] and
                    item.alignment == properties['alignment'] and
                    is_close(item.line_spacing, properties['line_spacing']) and
                    item.outline_color == properties['outline_color'] and
                    is_close(item.outline_width, properties['outline_width']) and
                    item.bold == properties['bold'] and
                    item.italic == properties['italic'] and
                    item.underline == properties['underline'] and
                    is_close(item.pos().x(), properties['position'][0]) and
                    is_close(item.pos().y(), properties['position'][1]) and
                    is_close(item.rotation(), properties['rotation']) and
                    is_close(item.scale(), properties['scale']) and
                    is_close(item.transformOriginPoint().x(), properties['transform_origin'][0]) and
                    is_close(item.transformOriginPoint().y(), properties['transform_origin'][1]) and
                    is_close(item.boundingRect().width(), properties['width'])):
                    return item
        return None

    
def is_close(value1, value2, tolerance=2):
    return abs(value1 - value2) <= tolerance