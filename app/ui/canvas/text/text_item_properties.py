from dataclasses import dataclass, field
from typing import Optional, List, Any
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

@dataclass
class TextItemProperties:
    """Dataclass for TextBlockItem properties to reduce duplication in construction"""
    text: str = ""
    font_family: str = ""
    font_size: float = 20
    text_color: QColor = None
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter
    line_spacing: float = 1.2
    outline_color: Optional[QColor] = None
    outline_width: float = 1
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
    vertical: bool = False
    
    # Advanced properties
    selection_outlines: list = field(default_factory=list)
            
    @classmethod
    def from_dict(cls, data: dict) -> 'TextItemProperties':
        """Create TextItemProperties from dictionary state"""
        props = cls()
        
        # Basic text properties
        props.text = data.get('text', '')
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
        
        # Alignment
        if 'alignment' in data:
            if isinstance(data['alignment'], int):
                props.alignment = Qt.AlignmentFlag(data['alignment'])
            else:
                props.alignment = data['alignment']
                
        # Direction
        if 'direction' in data:
            props.direction = data['direction']
            
        # Position and transformation
        props.position = data.get('position', (0, 0))
        props.rotation = data.get('rotation', 0)
        props.scale = data.get('scale', 1.0)
        props.transform_origin = data.get('transform_origin')
        
        # Layout
        props.width = data.get('width')
        props.vertical = data.get('vertical', False)
        
        # Advanced
        props.selection_outlines = data.get('selection_outlines', [])
        
        return props
    
    @classmethod
    def from_text_item(cls, item) -> 'TextItemProperties':
        """Create TextItemProperties from an existing TextBlockItem"""
        props = cls()
        
        # Basic text properties
        props.text = item.toHtml()
        props.font_family = item.font_family
        props.font_size = item.font_size
        props.text_color = item.text_color
        props.alignment = item.alignment
        props.line_spacing = item.line_spacing
        props.outline_color = item.outline_color
        props.outline_width = item.outline_width
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
        props.width = item.boundingRect().width()
        props.vertical = getattr(item, 'vertical', False)
        
        # Advanced properties
        props.selection_outlines = getattr(item, 'selection_outlines', []).copy()
        
        return props
    
    def to_dict(self) -> dict:
        """Convert TextItemProperties to dictionary"""
        return {
            'text': self.text,
            'font_family': self.font_family,
            'font_size': self.font_size,
            'text_color': self.text_color,
            'alignment': self.alignment,
            'line_spacing': self.line_spacing,
            'outline_color': self.outline_color,
            'outline_width': self.outline_width,
            'bold': self.bold,
            'italic': self.italic,
            'underline': self.underline,
            'direction': self.direction,
            'position': self.position,
            'rotation': self.rotation,
            'scale': self.scale,
            'transform_origin': self.transform_origin,
            'width': self.width,
            'vertical': self.vertical,
            'selection_outlines': self.selection_outlines,
        }
