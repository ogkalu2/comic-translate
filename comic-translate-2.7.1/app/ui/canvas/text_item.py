from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem, \
     QApplication, QWidget, QStyleOptionGraphicsItem
from PySide6.QtGui import QFont, QCursor, QColor, \
     QTextCharFormat, QTextBlockFormat, QTextCursor, QPainter
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
import math, copy
from dataclasses import dataclass
from enum import Enum
from .text.vertical_layout import VerticalTextDocumentLayout


@dataclass
class TextBlockState:
    rect: tuple  
    rotation: float
    transform_origin: QPointF

    @classmethod
    def from_item(cls, item: QGraphicsTextItem):
        """Create TextBlockState from a TextBlockItem"""
        rect = QRectF(item.pos(), item.boundingRect().size()).getCoords()
        return cls(
            rect=rect,
            rotation=item.rotation(),
            transform_origin=item.transformOriginPoint()
        )
    
class OutlineType(Enum):
    Full_Document = 'full_document'
    Selection = 'selection'
    
@dataclass
class OutlineInfo:
    start: int
    end: int
    color: QColor
    width: float
    type: OutlineType

class TextBlockItem(QGraphicsTextItem):
    text_changed = Signal(str)
    item_selected = Signal(object)
    item_deselected = Signal()
    text_highlighted = Signal(dict)
    change_undo = Signal(TextBlockState, TextBlockState)
    
    def __init__(self, 
             text = "", 
             font_family = "", 
             font_size = 20, 
             render_color = QColor(0, 0, 0), 
             alignment = Qt.AlignmentFlag.AlignCenter, 
             line_spacing = 1.2, 
             outline_color = QColor(255, 255, 255), 
             outline_width = 1,
             bold=False, 
             italic=False, 
             underline=False,
             direction=Qt.LayoutDirection.LeftToRight):

        super().__init__(text)
        self.text_color = render_color
        self.outline = True if outline_color else False
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.font_family = font_family
        self.font_size = font_size
        self.alignment = alignment
        self.line_spacing = line_spacing
        self.direction = direction

        self.layout = None
        self.vertical = False

        self.selected = False
        self.resizing = False
        self.resize_handle = None
        self.resize_start = None
        self.editing_mode = False
        self.last_selection = None 
        self._drag_selecting = False
        self._drag_select_anchor = None

        # Rotation properties
        self.rot_handle = None
        self.rotating = False
        self.last_rotation_angle = 0
        self.rotation_smoothing = 1.0  # rotation sensitivity
        self.center_scene_pos = None  

        self.old_state = None

        self.selection_outlines = []

        self.setAcceptHoverEvents(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.document().contentsChanged.connect(self._on_text_changed)
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)

        # Set the initial text direction
        self._apply_text_direction()

    def set_vertical(self, vertical: bool):
        doc = self.document()
        is_already_vertical = isinstance(doc.documentLayout(), VerticalTextDocumentLayout)

        if vertical == is_already_vertical:
            return

        self.vertical = vertical

        # Disconnect signals from the old layout if it's our custom one
        if is_already_vertical:
            old_layout = doc.documentLayout()
            if old_layout:
                try:
                    old_layout.size_enlarged.disconnect(self.on_document_enlarged)
                    old_layout.documentSizeChanged.disconnect(self.setCenterTransform)
                except (TypeError, RuntimeError): # Already disconnected
                    pass
        
        # Inform the graphics system that the geometry will change
        self.prepareGeometryChange()
        current_rect = self.boundingRect()

        # Disable text interaction while changing layout
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        
        if doc.documentLayout():
            doc.documentLayout().blockSignals(True)

        if vertical:
            layout = VerticalTextDocumentLayout(
                document=doc,
                line_spacing=self.line_spacing,
            )
            self.layout = layout
            doc.setDocumentLayout(layout)
            
            # Connect signals for the new layout
            layout.size_enlarged.connect(self.on_document_enlarged)
            layout.documentSizeChanged.connect(self.setCenterTransform)
            
            # Initialize layout with the item's current size.
            # set_max_size enforces the dimensions, but a text item with no 
            # set text has negligible size, so this can collapse the layout.
            # Only uncomment if set_vertical runs after plain text is set.
            # layout.set_max_size(current_rect.width(), current_rect.height())
            # layout.update_layout()

        else:  # Switching back to horizontal
            self.layout = None
            doc.setDocumentLayout(None)  # Qt will restore the default layout.
            self.setTextWidth(current_rect.width())
        
        # After setting the new layout, update the item's state
        self.setCenterTransform()
        self.update()

    def setCenterTransform(self):
        center = self.boundingRect().center()
        self.setTransformOriginPoint(center)

    def on_document_enlarged(self):
        self.prepareGeometryChange()
        self.setCenterTransform()

    def _apply_text_direction(self):
        text_option = self.document().defaultTextOption()
        text_option.setTextDirection(self.direction)
        self.document().setDefaultTextOption(text_option)

    def set_direction(self, direction):
        if self.direction != direction:
            self.direction = direction
            self._apply_text_direction()
            self.update()

    def set_text(self, text, width):
        if self.is_html(text):
            self.setHtml(text)
            self.setTextWidth(width)
            self.set_outline(self.outline_color, self.outline_width)
        else:
            self.set_plain_text(text)

    def set_plain_text(self, text):
        self.setPlainText(text)
        self.apply_all_attributes()

    def is_html(self, text):
        import re
        # Simple check for HTML tags
        return bool(re.search(r'<[^>]+>', text))

    def set_font(self, font_family, font_size):
        if not self.textCursor().hasSelection():
            self.font_family = font_family
            self.font_size = font_size

        # Ensure minimum font size.
        font_size = max(1, font_size)

        # Fallback to application default font family if none provided
        effective_family = font_family.strip() if isinstance(font_family, str) and font_family.strip() else QApplication.font().family()
        font = QFont(effective_family, font_size)
        self.update_text_format('font', font)

    def set_font_size(self, font_size):
        font_size = max(1, font_size)
        if not self.textCursor().hasSelection():
            self.font_size = font_size
        self.update_text_format('size', font_size)

    def update_text_width(self):
        width = self.document().size().width()
        self.setTextWidth(width)

    def set_alignment(self, alignment):
        if not self.textCursor().hasSelection():
            self.alignment = alignment
        self.update_alignment(alignment)

    def update_alignment(self, alignment):
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()
        block_format = cursor.blockFormat()
        block_format.setAlignment(alignment)

        if has_selection:
            cursor.beginEditBlock()
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            cursor.mergeBlockFormat(block_format)
            cursor.endEditBlock()
        else:
            doc = self.document()
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.mergeBlockFormat(block_format)

        self.update()

    def update_text_format(self, attribute, value):
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()

        format_operations = {
            'color': lambda cf, v: cf.setForeground(v),
            'font': lambda cf, v: cf.setFont(v),
            'size': lambda cf, v: cf.setFontPointSize(v),
            'bold': lambda cf, v: cf.setFontWeight(QFont.Bold if v else QFont.Normal),
            'italic': lambda cf, v: cf.setFontItalic(v),
            'underline': lambda cf, v: cf.setFontUnderline(v),
        }

        if attribute not in format_operations:
            print(f"Unsupported attribute: {attribute}")
            return

        char_format = QTextCharFormat()
        format_operations[attribute](char_format, value)

        if not has_selection:
            cursor.select(QTextCursor.SelectionType.Document)    
  
        cursor.mergeCharFormat(char_format)

        # Update the document's default format
        doc_format = self.document().defaultTextOption()
        if attribute == 'color':
            self.setDefaultTextColor(value)
        elif attribute == 'font':
            self.document().setDefaultFont(value)
        elif attribute == 'size':
            font = self.document().defaultFont()
            font.setPointSize(value)
            self.document().setDefaultFont(font)
        
        # Clear the selection by moving the cursor to the end of the document
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.End)

        self.setTextCursor(cursor)
        self.document().setDefaultTextOption(doc_format)
        self.update()

    def set_line_spacing(self, spacing):
        self.line_spacing = spacing
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = QTextBlockFormat()
        spacing = spacing * 100
        spacing = float(spacing)
        block_format.setLineHeight(spacing, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cursor.mergeBlockFormat(block_format)

    def set_color(self, color):
        if not self.textCursor().hasSelection():
            self.text_color = color
        self.update_text_format('color', color)

    def update_outlines(self):
        """Update the selection outlines when text changes"""
        if self.outline:
            # Create an outline for the entire document
            doc = self.document()
            char_count = doc.characterCount()
            
            # Create an outline info for the entire document
            new_outline = OutlineInfo(  
                start = 0,
                end = max(0, char_count - 1),
                color = self.outline_color,  
                width = self.outline_width,
                type = OutlineType.Full_Document
            )
            
            # Remove any existing full document outline
            self.selection_outlines = [outline for outline in self.selection_outlines 
                                     if outline.type != OutlineType.Full_Document]
            # Add the new one
            self.selection_outlines.append(new_outline)
        else:
            # Remove only the full document outline
            self.selection_outlines = [outline for outline in self.selection_outlines 
                                     if outline.type != OutlineType.Full_Document]

        self.update() 

    def set_outline(self, outline_color, outline_width):
        # Initialize start and end variables
        start = 0
        end = 0

        if self.textCursor().hasSelection():
            # Store outline properties for the current selection
            start = self.textCursor().selectionStart()
            end = self.textCursor().selectionEnd()
        else:
            # Set global outline properties only when there's no selection
            self.outline = True if outline_color else False

            if self.outline:
                # enabling global outline: store color/width and target whole document
                self.outline_color = outline_color
                self.outline_width = outline_width

                char_count = self.document().characterCount()
                start = 0
                end = max(0, char_count - 1)

        # When disabling outlines (outline_color is falsy), remove the relevant outlines
        if not outline_color:
            if self.textCursor().hasSelection():
                # Remove any outlines that contain the current selection range
                self.selection_outlines = [
                    outline for outline in self.selection_outlines
                    if not (outline.start <= start and outline.end >= end)
                ]
            else:
                # No selection: remove only full-document outlines
                self.selection_outlines = [
                    outline for outline in self.selection_outlines
                    if outline.type != OutlineType.Full_Document
                ]
        else:
            # Adding/updating an outline for the selection or whole document
            type = OutlineType.Selection if self.textCursor().hasSelection() else OutlineType.Full_Document

            # Remove any existing outline for this exact selection range
            self.selection_outlines = [
                outline for outline in self.selection_outlines 
                if not (outline.start == start and outline.end == end)
            ]

            # Add new outline info
            self.selection_outlines.append(
                OutlineInfo(start, end, outline_color, outline_width, type)
            )
        
        self.update()

    def paint(   
        self, 
        painter: QPainter, 
        option: QStyleOptionGraphicsItem, 
        widget: QWidget = None
    ):

        # Then handle any selection outlines
        if self.selection_outlines:
            doc = self.document().clone()
            
            # Preserve vertical layout if in vertical mode
            if self.vertical and self.layout:
                vertical_layout = VerticalTextDocumentLayout(
                    document=doc,
                    line_spacing=self.layout.line_spacing,
                )
                doc.setDocumentLayout(vertical_layout)
                vertical_layout.set_max_size(self.layout.max_width, self.layout.max_height)

            painter.save()
            
            # Clear the document first to only show outlined parts
            cursor = QTextCursor(doc)
            cursor.select(QTextCursor.SelectionType.Document)
            fmt = cursor.charFormat()
            fmt.setForeground(QColor(0, 0, 0, 0))  # Transparent
            cursor.mergeCharFormat(fmt)

            # Apply outline colors only to selected regions
            for outline_info in self.selection_outlines:
                cursor.setPosition(outline_info.start)
                cursor.setPosition(outline_info.end, QTextCursor.KeepAnchor)
                fmt = cursor.charFormat()
                fmt.setForeground(outline_info.color)
                cursor.mergeCharFormat(fmt)

                # Draw the outline for this selection
                offsets = [(dx, dy) 
                    for dx in (-outline_info.width, 0, outline_info.width)
                    for dy in (-outline_info.width, 0, outline_info.width)
                    if dx != 0 or dy != 0
                ]
                
                for dx, dy in offsets:
                    painter.save()
                    painter.translate(dx, dy)
                    doc.drawContents(painter)
                    painter.restore()

            painter.restore()

        # Draw the normal text on top
        super().paint(painter, option, widget)

    def set_bold(self, state):
        if not self.textCursor().hasSelection():
            self.bold = state
        self.update_text_format('bold', state)

    def set_italic(self, state):
        if not self.textCursor().hasSelection():
            self.italic = state
        self.update_text_format('italic', state)

    def set_underline(self, state):
        if not self.textCursor().hasSelection():
            self.underline = state
        self.update_text_format('underline', state)

    def apply_all_attributes(self):
        self.set_font(self.font_family, self.font_size)
        self.set_color(self.text_color)
        self.set_outline(self.outline_color, self.outline_width)
        self.set_bold(self.bold)
        self.set_italic(self.italic)
        self.set_underline(self.underline)
        self.set_line_spacing(self.line_spacing)
        self.update_text_width()
        self.set_alignment(self.alignment)

    def mouseDoubleClickEvent(self, event):
        if not self.editing_mode:
            self.enter_editing_mode()
            if self.layout:
                hit = self.layout.hitTest(event.pos(), None)
                cursor = self.textCursor()
                cursor.setPosition(hit)
                self.setTextCursor(cursor)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        # Handle single clicks in editing mode for vertical text
        if self.editing_mode and self.layout and event.button() == Qt.MouseButton.LeftButton:
            hit = self.layout.hitTest(event.pos(), None)
            cursor = self.textCursor()
            
            # Check if shift is pressed for selection
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._drag_select_anchor = cursor.anchor()
                cursor.setPosition(hit, QTextCursor.MoveMode.KeepAnchor)
            else:
                cursor.setPosition(hit)
                self._drag_select_anchor = hit
            
            self._drag_selecting = True
            self.setTextCursor(cursor)
            self.setFocus()
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):

        if self.editing_mode and self.vertical:
            key = event.key()
            modifiers = event.modifiers()
            
            if key == Qt.Key.Key_Down:
                # Down arrow in vertical text = move to next character
                cursor = self.textCursor()
                move_mode = QTextCursor.MoveMode.KeepAnchor if (modifiers & Qt.KeyboardModifier.ShiftModifier) else QTextCursor.MoveMode.MoveAnchor
                cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, move_mode)
                self.setTextCursor(cursor)
                event.accept()
                return
            elif key == Qt.Key.Key_Up:
                # Up arrow in vertical text = move to previous character
                cursor = self.textCursor()
                move_mode = QTextCursor.MoveMode.KeepAnchor if (modifiers & Qt.KeyboardModifier.ShiftModifier) else QTextCursor.MoveMode.MoveAnchor
                cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter, move_mode)
                self.setTextCursor(cursor)
                event.accept()
                return
            elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and not (
                modifiers & (
                    Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )
            ):
                # Left/Right arrow in vertical text = move between paragraphs (visual columns),
                # keeping the same in-block offset when possible.
                cursor = self.textCursor()
                move_mode = QTextCursor.MoveMode.KeepAnchor if (modifiers & Qt.KeyboardModifier.ShiftModifier) else QTextCursor.MoveMode.MoveAnchor

                # Prefer layout-aware movement (handles wrapped columns).
                if self.layout and hasattr(self.layout, "move_cursor_between_columns"):
                    column_delta = 1 if key == Qt.Key.Key_Left else -1
                    new_pos = self.layout.move_cursor_between_columns(cursor.position(), column_delta)
                    if new_pos is not None and new_pos != cursor.position():
                        cursor.setPosition(new_pos, move_mode)
                        self.setTextCursor(cursor)
                        event.accept()
                        return

                # Fallback: treat each QTextBlock as a vertical "line" and move between them.
                block = cursor.block()
                target_block = block.next() if key == Qt.Key.Key_Left else block.previous()
                if target_block.isValid():
                    offset_in_block = cursor.position() - block.position()
                    target_offset = min(offset_in_block, max(0, target_block.length() - 1))
                    new_pos = target_block.position() + target_offset
                    if new_pos != cursor.position():
                        cursor.setPosition(new_pos, move_mode)
                        self.setTextCursor(cursor)
                        event.accept()
                        return
            
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Use the current character format as the new block's char format so empty paragraphs
                # keep the same font metrics (Qt can otherwise fall back to a tiny default).
                # Currently only necessary for vertical text layouts.
                cursor = self.textCursor()
                inherited_char_format = QTextCharFormat(cursor.charFormat())
                inherited_block_format = cursor.blockFormat()
                inherited_block_char_format = QTextCharFormat(inherited_char_format)

                # Ensure we always carry a valid point size/font for layout metrics.
                if inherited_block_char_format.fontPointSize() <= 0:
                    inherited_block_char_format.setFontPointSize(max(1, float(self.font_size)))
                font = inherited_block_char_format.font()
                if font.pointSizeF() <= 0:
                    font = self.document().defaultFont()
                    if font.pointSizeF() <= 0:
                        font.setPointSizeF(max(1.0, float(self.font_size)))
                    inherited_block_char_format.setFont(font)

                cursor.beginEditBlock()
                if cursor.hasSelection():
                    cursor.removeSelectedText()

                # Create a new paragraph that keeps the current paragraph + char formatting.
                cursor.insertBlock(inherited_block_format, inherited_block_char_format)
                cursor.setCharFormat(inherited_char_format)

                cursor.endEditBlock()
                self.setTextCursor(cursor)
                event.accept()
                return
        
        # Default handling for all other cases
        super().keyPressEvent(event)

    def enter_editing_mode(self):
        self.editing_mode = True
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.setFocus()

    def exit_editing_mode(self):
        self.editing_mode = False
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clearFocus()

    def _on_text_changed(self):
        new_text = self.toPlainText()
        self.text_changed.emit(new_text)
        self.update_outlines()

    def mouseMoveEvent(self, event):
        # Resize/rotate/move logic is now handled by EventHandler and QGraphicsView
        if self.editing_mode and self.layout and (event.buttons() & Qt.MouseButton.LeftButton) and self._drag_selecting:
            hit = self.layout.hitTest(event.pos(), None)
            anchor = self._drag_select_anchor
            if anchor is None:
                anchor = self.textCursor().anchor()

            cursor = self.textCursor()
            cursor.setPosition(anchor)
            cursor.setPosition(hit, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            event.accept()
            return

        if self.editing_mode:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.editing_mode and self.layout and event.button() == Qt.MouseButton.LeftButton:
            self._drag_selecting = False
            self._drag_select_anchor = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        super().contextMenuEvent(event)
        if self.editing_mode:
            self.enter_editing_mode()
    
    def handleDeselection(self):
        if self.selected:
            self.setSelected(False)
            self.selected = False
            self.item_deselected.emit()
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if self.editing_mode:
                self.exit_editing_mode()
            self.update()

    def init_resize(self, scene_pos: QPointF):
        self.resizing = True
        self.resize_start = scene_pos

    def init_rotation(self, scene_pos):
        self.rotating = True
        center = self.boundingRect().center()
        self.center_scene_pos = self.mapToScene(center)
        self.last_rotation_angle = math.degrees(math.atan2(
            scene_pos.y() - self.center_scene_pos.y(),
            scene_pos.x() - self.center_scene_pos.x()
        ))

    def move_item(self, local_pos: QPointF, last_local_pos: QPointF):
        delta = self.mapToParent(local_pos) - self.mapToParent(last_local_pos)
        new_pos = self.pos() + delta
        
        # Calculate the bounding rect of the rotated rectangle in scene coordinates
        scene_rect = self.mapToScene(self.boundingRect())
        bounding_rect = scene_rect.boundingRect()
        
        # Get constraint bounds
        parent_rect = None
        
        # Check if we're in webtoon mode by looking for the lazy webtoon manager
        scene = self.scene()
        if scene and scene.views():
            parent_rect = scene.sceneRect()
        
        # Constrain the movement
        if bounding_rect.left() + delta.x() < parent_rect.left():
            new_pos.setX(self.pos().x() - (bounding_rect.left() - parent_rect.left()))
        elif bounding_rect.right() + delta.x() > parent_rect.right():
            new_pos.setX(self.pos().x() + parent_rect.right() - bounding_rect.right())
        
        if bounding_rect.top() + delta.y() < parent_rect.top():
            new_pos.setY(self.pos().y() - (bounding_rect.top() - parent_rect.top()))
        elif bounding_rect.bottom() + delta.y() > parent_rect.bottom():
            new_pos.setY(self.pos().y() + parent_rect.bottom() - bounding_rect.bottom())
        
        self.setPos(new_pos)

    def rotate_item(self, scene_pos):
        self.setTransformOriginPoint(self.boundingRect().center())
        current_angle = math.degrees(math.atan2(
            scene_pos.y() - self.center_scene_pos.y(),
            scene_pos.x() - self.center_scene_pos.x()
        ))
        
        angle_diff = current_angle - self.last_rotation_angle
        
        if angle_diff > 180:
            angle_diff -= 360
        elif angle_diff < -180:
            angle_diff += 360
        
        smoothed_angle = angle_diff / self.rotation_smoothing
        
        new_rotation = self.rotation() + smoothed_angle
        self.setRotation(new_rotation)
        self.last_rotation_angle = current_angle

    def resize_item(self, scene_pos: QPointF):
        if not self.resize_start:
            return

        # Calculate delta from start position in scene coordinates
        scene_start = self.resize_start
        scene_delta = scene_pos - scene_start

        # Counter-rotate the delta to align it with the item's unrotated coordinate system
        angle_rad = math.radians(-self.rotation())
        rotated_delta_x = scene_delta.x() * math.cos(angle_rad) - scene_delta.y() * math.sin(angle_rad)
        rotated_delta_y = scene_delta.x() * math.sin(angle_rad) + scene_delta.y() * math.cos(angle_rad)
        rotated_delta = QPointF(rotated_delta_x, rotated_delta_y)

        # Get the current rect and create a new one to modify
        rect = self.boundingRect()
        new_rect = QRectF(rect)
        original_height = rect.height()

        # Apply the delta based on which handle is being dragged
        if self.resize_handle in ['left', 'top_left', 'bottom_left']:
            new_rect.setLeft(rect.left() + rotated_delta.x())
        if self.resize_handle in ['right', 'top_right', 'bottom_right']:
            new_rect.setRight(rect.right() + rotated_delta.x())
        if self.resize_handle in ['top', 'top_left', 'top_right']:
            new_rect.setTop(rect.top() + rotated_delta.y())
        if self.resize_handle in ['bottom', 'bottom_left', 'bottom_right']:
            new_rect.setBottom(rect.bottom() + rotated_delta.y())

        # Ensure minimum size
        min_size = 10
        if new_rect.width() < min_size:
            if 'left' in self.resize_handle: new_rect.setLeft(new_rect.right() - min_size)
            else: new_rect.setRight(new_rect.left() + min_size)
        if new_rect.height() < min_size:
            if 'top' in self.resize_handle: new_rect.setTop(new_rect.bottom() - min_size)
            else: new_rect.setBottom(new_rect.top() + min_size)

        # Determine constraint bounds
        constraint_rect = None
        scene = self.scene()
        
        if scene and scene.views():
            constraint_rect = scene.sceneRect()
        
        if constraint_rect:
            # Map the proposed new local rect to the scene to get its final footprint
            prospective_scene_rect = self.mapRectToScene(new_rect)

            # Check if the resize would push the item outside the constraint bounds
            if (prospective_scene_rect.left() < constraint_rect.left() or
                prospective_scene_rect.right() > constraint_rect.right() or
                prospective_scene_rect.top() < constraint_rect.top() or
                prospective_scene_rect.bottom() > constraint_rect.bottom()):
                return  # Abort the resize operation

        # Calculate the required shift in the parent's coordinate system.
        pos_delta = self.mapToParent(new_rect.topLeft()) - self.mapToParent(rect.topLeft())
        new_pos = self.pos() + pos_delta

        self.setPos(new_pos)

        if self.vertical:
            if self.layout:
                self.layout.set_max_size(new_rect.width(), new_rect.height())
        else: # Horizontal logic
            self.setTextWidth(new_rect.width())
            if original_height > 0:
                height_ratio = new_rect.height() / original_height
                if height_ratio > 0:
                    new_font_size = self.font_size * height_ratio
                    # Ensure minimum font size of 1pt.
                    if new_font_size >= 1:
                        self.font_size = new_font_size
                        self.set_font_size(new_font_size)
                    else:
                        # If font would become invalid, stop the resize.
                        return

        self.resize_start = scene_pos

    def on_selection_changed(self):
        cursor = self.textCursor()
        properties = self.get_selected_text_properties(cursor)
        if self.editing_mode:
            self.text_highlighted.emit(properties)

    def get_selected_text_properties(self, cursor: QTextCursor):
        if not cursor.hasSelection():
            return {
                'font_family': self.font_family,
                'font_size': self.font_size,
                'bold': False,
                'italic': False,
                'underline': False,
                'text_color': self.text_color.name(),
                'alignment': self.alignment,
                'outline': self.outline,
                'outline_color': self.outline_color.name() if self.outline_color else None,
                'outline_width': self.outline_width,
            }

        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        # Find all selections that completely contain the current selection
        containing_outlines = [
            outline for outline in self.selection_outlines
            if outline.start <= start and outline.end >= end
        ]

        # Get outline properties from the last (most recent) containing selection
        outline_properties = None
        if containing_outlines:
            latest_outline = containing_outlines[-1]  # Get the last one from the list
            outline_properties = {
                'outline': True,
                'outline_color': latest_outline.color.name(),
                'outline_width': latest_outline.width
            }
        else:
            outline_properties = {
                'outline': False,
                'outline_color': None,
                'outline_width': None
            }

        # Create a new cursor for traversing the selection
        format_cursor = QTextCursor(cursor)

        # Initialize properties with default values
        properties = {
            'font_family': set(),
            'font_size': set(),
            'bold': True,
            'italic': True,
            'underline': True,
            'text_color': set(),
            'alignment': None,
        }

        # Get initial block format for alignment
        format_cursor.setPosition(start)
        properties['alignment'] = format_cursor.blockFormat().alignment()

        # Iterate through the selection one character at a time
        for pos in range(start, end):
            format_cursor.setPosition(pos)
            format_cursor.setPosition(pos + 1, QTextCursor.KeepAnchor)
            char_format = format_cursor.charFormat()

            # Update properties
            properties['font_family'].add(char_format.font().family())
            properties['font_size'].add(char_format.fontPointSize())
            properties['bold'] &= char_format.font().bold()
            properties['italic'] &= char_format.font().italic()
            properties['underline'] &= char_format.font().underline()
            properties['text_color'].add(char_format.foreground().color().name())

        # Convert sets to single values if all elements are the same, otherwise set to None
        for key, value in properties.items():
            if isinstance(value, set):
                properties[key] = list(value)[0] if len(value) == 1 else None

        # Merge outline properties with other properties
        properties.update(outline_properties)

        return properties
    
    def __copy__(self):
        cls = self.__class__
        new_instance = cls(
            text=self.toHtml(),
            font_family=self.font_family,
            font_size=self.font_size,
            render_color=self.text_color,
            alignment=self.alignment,
            line_spacing=self.line_spacing,
            outline_color=self.outline_color,
            outline_width=self.outline_width,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline
        )
        
        new_instance.set_text(self.toHtml(), self.boundingRect().width())
        new_instance.setTransformOriginPoint(self.transformOriginPoint())
        new_instance.setPos(self.pos())
        new_instance.setRotation(self.rotation())
        new_instance.setScale(self.scale())
        new_instance.__dict__.update(copy.copy(self.__dict__))
        return new_instance

