from dataclasses import dataclass, field
from typing import Optional, List, Any
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from app.ui.canvas.text_item import OutlineType

@dataclass
class TextItemProperties:
    """Dataclass for TextBlockItem properties to reduce duplication in construction"""
    text: str = ""
    source_text: str = ""
    font_family: str = ""
    font_size: float = 20
    text_color: QColor = None
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter
    line_spacing: float = 1.2
    outline_color: Optional[QColor] = None
    outline_width: float = 1
    outline: bool = False
    second_outline: bool = False
    second_outline_color: Optional[QColor] = None
    second_outline_width: float = 0
    text_gradient: bool = False
    text_gradient_start_color: Optional[QColor] = None
    text_gradient_end_color: Optional[QColor] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    direction: Qt.LayoutDirection = Qt.LayoutDirection.LeftToRight
    
    # Position and transformation properties
    position: tuple = (0, 0)  # (x, y)
    rotation: float = 0
    scale: float = 1.0
    transform_origin: Optional[tuple] = None  # (x, y)
    
    # Layout properties
    width: Optional[float] = None
    height: Optional[float] = None
    vertical: bool = False
    block_uid: str = ""
    
    # Advanced properties
    selection_outlines: list = field(default_factory=list)
            
    @classmethod
    def from_dict(cls, data: dict) -> 'TextItemProperties':
        """Create TextItemProperties from dictionary state"""
        props = cls()
        
        # Basic text properties
        props.text = data.get('text', '')
        props.source_text = data.get('source_text', '')
        props.font_family = data.get('font_family', '')
        props.font_size = data.get('font_size', 20)
        props.line_spacing = data.get('line_spacing', 1.2)
        props.bold = data.get('bold', False)
        props.italic = data.get('italic', False)
        props.underline = data.get('underline', False)
        
        # Color properties
        if 'text_color' in data:
            if isinstance(data['text_color'], QColor):
                props.text_color = data['text_color']
            elif data['text_color'] is not None:
                props.text_color = QColor(data['text_color'])
        
        if 'outline_color' in data:
            if isinstance(data['outline_color'], QColor):
                props.outline_color = data['outline_color']
            elif data['outline_color']:
                props.outline_color = QColor(data['outline_color'])
                
        props.outline_width = data.get('outline_width', 1)
        if 'outline' in data:
            props.outline = bool(data.get('outline', False))
        else:
            props.outline = _has_full_document_outline(data.get('selection_outlines', []))
        props.second_outline = bool(data.get('second_outline', False))
        props.second_outline_color = _qcolor_from_value(data.get('second_outline_color'))
        props.second_outline_width = data.get('second_outline_width', 0)
        props.text_gradient = bool(data.get('text_gradient', False))
        props.text_gradient_start_color = _qcolor_from_value(data.get('text_gradient_start_color'))
        props.text_gradient_end_color = _qcolor_from_value(data.get('text_gradient_end_color'))
        
        # Alignment
        if 'alignment' in data:
            if isinstance(data['alignment'], int):
                props.alignment = Qt.AlignmentFlag(data['alignment'])
            else:
                props.alignment = data['alignment']
                
        # Direction – stored as Qt.LayoutDirection enum but may arrive as a plain
        # integer after JSON round-trips (RightToLeft=1, LeftToRight=0).
        if 'direction' in data:
            dir_val = data['direction']
            if isinstance(dir_val, int):
                try:
                    props.direction = Qt.LayoutDirection(dir_val)
                except (ValueError, KeyError):
                    props.direction = Qt.LayoutDirection.LeftToRight
            else:
                props.direction = dir_val
            
        # Position and transformation
        props.position = data.get('position', (0, 0))
        props.rotation = data.get('rotation', 0)
        props.scale = data.get('scale', 1.0)
        props.transform_origin = data.get('transform_origin')
        
        # Layout
        props.width = data.get('width')
        props.height = data.get('height')
        props.vertical = data.get('vertical', False)
        props.block_uid = data.get('block_uid', '')
        
        # Advanced
        props.selection_outlines = data.get('selection_outlines', [])
        
        return props
    
    @classmethod
    def from_text_item(cls, item) -> 'TextItemProperties':
        """Create TextItemProperties from an existing TextBlockItem"""
        props = cls()
        
        # Basic text properties
        props.text = item.toHtml()
        if hasattr(item, 'get_source_text'):
            props.source_text = item.get_source_text()
        else:
            props.source_text = getattr(item, 'source_text', '') or item.toPlainText()
        props.font_family = item.font_family
        props.font_size = item.font_size
        props.text_color = item.text_color
        props.alignment = item.alignment
        props.line_spacing = item.line_spacing
        props.outline_color = item.outline_color
        props.outline_width = item.outline_width
        props.outline = bool(getattr(item, 'outline', False))
        props.second_outline = bool(getattr(item, 'second_outline', False))
        props.second_outline_color = getattr(item, 'second_outline_color', None)
        props.second_outline_width = getattr(item, 'second_outline_width', 0)
        props.text_gradient = bool(getattr(item, 'text_gradient', False))
        props.text_gradient_start_color = getattr(item, 'text_gradient_start_color', None)
        props.text_gradient_end_color = getattr(item, 'text_gradient_end_color', None)
        props.bold = item.bold
        props.italic = item.italic
        props.underline = item.underline
        props.direction = item.direction
        
        # Position and transformation
        props.position = (item.pos().x(), item.pos().y())
        props.rotation = item.rotation()
        props.scale = item.scale()
        if hasattr(item, 'transformOriginPoint'):
            origin = item.transformOriginPoint()
            props.transform_origin = (origin.x(), origin.y())
        
        # Layout properties
        if hasattr(item, "get_text_box_size"):
            width, height = item.get_text_box_size()
        else:
            width = item.textWidth() if hasattr(item, 'textWidth') else -1
            if width is None or width <= 0:
                width = item.document().size().width()
            if width is None or width <= 0:
                width = item.boundingRect().width()

            height = item.document().size().height()
            if height is None or height <= 0:
                height = item.boundingRect().height()

        props.width = width
        props.height = height
        props.vertical = getattr(item, 'vertical', False)
        props.block_uid = getattr(item, 'block_uid', '')
        
        # Advanced properties
        props.selection_outlines = getattr(item, 'selection_outlines', []).copy()
        
        return props
    
    def to_dict(self) -> dict:
        """Convert TextItemProperties to dictionary"""
        return {
            'text': self.text,
            'source_text': self.source_text,
            'font_family': self.font_family,
            'font_size': self.font_size,
            'text_color': self.text_color,
            'alignment': self.alignment,
            'line_spacing': self.line_spacing,
            'outline_color': self.outline_color,
            'outline_width': self.outline_width,
            'outline': self.outline,
            'second_outline': self.second_outline,
            'second_outline_color': self.second_outline_color,
            'second_outline_width': self.second_outline_width,
            'text_gradient': self.text_gradient,
            'text_gradient_start_color': self.text_gradient_start_color,
            'text_gradient_end_color': self.text_gradient_end_color,
            'bold': self.bold,
            'italic': self.italic,
            'underline': self.underline,
            'direction': self.direction,
            'position': self.position,
            'rotation': self.rotation,
            'scale': self.scale,
            'transform_origin': self.transform_origin,
            'width': self.width,
            'height': self.height,
            'vertical': self.vertical,
            'block_uid': self.block_uid,
            'selection_outlines': self.selection_outlines,
        }


def _qcolor_from_value(value):
    if isinstance(value, QColor):
        return value
    if value:
        return QColor(value)
    return None


def _has_full_document_outline(selection_outlines: list) -> bool:
    for outline in selection_outlines or []:
        outline_type = outline.get('type') if isinstance(outline, dict) else getattr(outline, 'type', None)
        if outline_type == OutlineType.Full_Document:
            return True
        if isinstance(outline_type, str) and outline_type.lower() == "full_document":
            return True
    return False
