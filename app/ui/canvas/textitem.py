from PySide6.QtWidgets import QGraphicsTextItem
from PySide6.QtGui import QPen, QFont, QCursor, QColor, \
     QTextCharFormat, QTextBlockFormat, QTextCursor, QFontMetrics
from PySide6.QtCore import Qt, QRectF, Signal


class TextBlockItem(QGraphicsTextItem):
    textChanged = Signal(str)
    itemSelected = Signal(object)
    itemDeselected = Signal()

    def __init__(self, 
             text = "", 
             parent_item = None, 
             text_block = None, 
             font_family = "", 
             font_size = 20, 
             render_color = QColor(0, 0, 0), 
             alignment = Qt.AlignmentFlag.AlignCenter, 
             line_spacing = 1.2, 
             outline_color = QColor(255, 255, 255), 
             outline_width = 1,
             bold=False, 
             italic=False, 
             underline=False):

        super().__init__(text)
        self.parent_item = parent_item
        if text_block:
            self.setPos(text_block.xyxy[0], text_block.xyxy[1]) 
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

        # if text:
        self.apply_all_attributes()
            
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.handle_size = 30
        self.selected = False

        self.resizing = False
        self.resize_handle = None
        self._resize_start = None

        self.editing_mode = False

        self.text_block = text_block
        self.document().contentsChanged.connect(self._on_text_changed)

    def set_font(self, font_family, font_size):
        if not self.textCursor().hasSelection():
            self.font_family = font_family
            self.font_size = font_size

        font = QFont(font_family, font_size)
        self.update_text_format('font', font)

    def set_font_size(self, font_size):
        if not self.textCursor().hasSelection():
            self.font_size = font_size
        self.update_text_format('size', font_size)

    def update_text_width(self):
        fm = QFontMetrics(self.font())
        max_width = max(fm.horizontalAdvance(line) for line in self.toPlainText().split('\n'))
        self.setTextWidth(max_width)

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
            'outline': lambda cf, v: cf.setTextOutline(QPen(v[0], v[1]) if v[0] else Qt.NoPen)
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

    def set_outline(self, outline_color, outline_width):
        if not self.textCursor().hasSelection():
            self.outline_color = outline_color
            self.outline = True if outline_color else False
            self.outline_width = outline_width
        self.update_text_format('outline', (outline_color, outline_width))

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
        super().mouseDoubleClickEvent(event)

    def enter_editing_mode(self):
        self.editing_mode = True
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        self.setFocus()

    def exit_editing_mode(self):
        self.editing_mode = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clearFocus()

    def _on_text_changed(self):
        new_text = self.toPlainText()
        self.textChanged.emit(new_text)

    def mousePressEvent(self, event):
        if not self.editing_mode:
            scene_pos = self.mapToScene(event.pos().toPoint())
            local_pos = self.mapFromScene(scene_pos)
            self.selected = self.boundingRect().contains(local_pos)
            
            if self.selected:
                self.itemSelected.emit(self)  
            
            if event.button() == Qt.LeftButton:
                self.resize_handle = self.get_handle_at_position(local_pos, self.boundingRect())
                if self.resize_handle:
                    self.resizing = True
                    self._resize_start = scene_pos
                else:
                    self.setCursor(QCursor(Qt.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.editing_mode:
            if event.button() == Qt.LeftButton:
                self.resizing = False
                self.resize_handle = None
                self._resize_start = None
                self.update_cursor(event.pos())
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not self.editing_mode:
            if self.resizing and self.resize_handle:
                self.resize_item(event.pos())
            else:
                self.update_cursor(event.pos())
                if self.parent_item:
                    # Calculate the difference between the current mouse position and the previous one
                    delta = event.pos() - event.lastPos()
                    
                    # Update the position based on the delta
                    new_pos = self.pos() + delta
                    
                    # Ensure the new position is within the parent's bounds
                    parent_rect = self.parent_item.boundingRect()
                    new_pos.setX(max(0, min(new_pos.x(), parent_rect.width() - self.boundingRect().width())))
                    new_pos.setY(max(0, min(new_pos.y(), parent_rect.height() - self.boundingRect().height())))
                    
                    self.setPos(new_pos)
                else:
                    super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def hoverMoveEvent(self, event):
        if self.selected:
            self.update_cursor(event.pos())
            super().hoverMoveEvent(event)
    
    def handleDeselection(self):
        if self.selected:
            self.setSelected(False)
            self.selected = False
            self.itemDeselected.emit()
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if self.editing_mode:
                self.exit_editing_mode()
            self.update()

    def focusOutEvent(self, event):
        # Only exit editing mode if we're not in a text selection
        if not self.textCursor().hasSelection():
            self.handleDeselection()
        super().focusOutEvent(event)

    def update_cursor(self, pos):
        if not self.editing_mode:
            cursor = self.get_cursor_for_position(pos)
            self.setCursor(QCursor(cursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.IBeamCursor))

    def get_cursor_for_position(self, pos):
        rect = self.boundingRect()
        handle = self.get_handle_at_position(pos, rect)
        
        cursors = {
            'top_left': Qt.CursorShape.SizeFDiagCursor,
            'top_right': Qt.CursorShape.SizeBDiagCursor,
            'bottom_left': Qt.CursorShape.SizeBDiagCursor,
            'bottom_right': Qt.CursorShape.SizeFDiagCursor,
            'top': Qt.CursorShape.SizeVerCursor,
            'bottom': Qt.CursorShape.SizeVerCursor,
            'left': Qt.CursorShape.SizeHorCursor,
            'right': Qt.CursorShape.SizeHorCursor,
        }
        
        if handle:
            return cursors.get(handle, Qt.CursorShape.ArrowCursor)
        elif rect.contains(pos):
            return Qt.CursorShape.SizeAllCursor
        else:
            return Qt.CursorShape.PointingHandCursor

    def get_handle_at_position(self, pos, rect):
        handle_size = self.handle_size
        rect_rect = rect.toRect()
        top_left = rect_rect.topLeft()
        bottom_right = rect_rect.bottomRight()

        handles = {
            'top_left': QRectF(top_left.x() - handle_size/2, top_left.y() - handle_size/2, handle_size, handle_size),
            'top_right': QRectF(bottom_right.x() - handle_size/2, top_left.y() - handle_size/2, handle_size, handle_size),
            'bottom_left': QRectF(top_left.x() - handle_size/2, bottom_right.y() - handle_size/2, handle_size, handle_size),
            'bottom_right': QRectF(bottom_right.x() - handle_size/2, bottom_right.y() - handle_size/2, handle_size, handle_size),
            'top': QRectF(top_left.x(), top_left.y() - handle_size/2, rect_rect.width(), handle_size),
            'bottom': QRectF(top_left.x(), bottom_right.y() - handle_size/2, rect_rect.width(), handle_size),
            'left': QRectF(top_left.x() - handle_size/2, top_left.y(), handle_size, rect_rect.height()),
            'right': QRectF(bottom_right.x() - handle_size/2, top_left.y(), handle_size, rect_rect.height()),
        }

        for handle, handle_rect in handles.items():
            if handle_rect.contains(pos):
                return handle

        return None
    
    def resize_item(self, pos):
        if not self._resize_start:
            return

        scene_pos = self.mapToScene(pos.toPoint())
        delta = scene_pos - self._resize_start
        rect = self.boundingRect()
        new_rect = QRectF(rect)
        original_height = rect.height()

        if self.resize_handle in ['left', 'top_left', 'bottom_left']:
            new_rect.setLeft(rect.left() + delta.x())
        if self.resize_handle in ['right', 'top_right', 'bottom_right']:
            new_rect.setRight(rect.right() + delta.x())
        if self.resize_handle in ['top', 'top_left', 'top_right']:
            new_rect.setTop(rect.top() + delta.y())
        if self.resize_handle in ['bottom', 'bottom_left', 'bottom_right']:
            new_rect.setBottom(rect.bottom() + delta.y())

        # Ensure minimum size
        min_size = 10
        if new_rect.width() < min_size:
            if 'left' in self.resize_handle:
                new_rect.setLeft(new_rect.right() - min_size)
            else:
                new_rect.setRight(new_rect.left() + min_size)
        if new_rect.height() < min_size:
            if 'top' in self.resize_handle:
                new_rect.setTop(new_rect.bottom() - min_size)
            else:
                new_rect.setBottom(new_rect.top() + min_size)

        # Constrain to parent item
        if self.parent_item:
            parent_rect = self.parent_item.boundingRect()
            new_pos = self.mapToParent(new_rect.topLeft() - rect.topLeft())
            
            # Constrain position
            new_pos.setX(max(0, min(new_pos.x(), parent_rect.width() - new_rect.width())))
            new_pos.setY(max(0, min(new_pos.y(), parent_rect.height() - new_rect.height())))
            
            # Constrain size
            new_rect.setWidth(min(new_rect.width(), parent_rect.width() - new_pos.x()))
            new_rect.setHeight(min(new_rect.height(), parent_rect.height() - new_pos.y()))
            
            self.setPos(new_pos)
        else:
            self.setPos(self.mapToParent(new_rect.topLeft() - rect.topLeft()))

        # Update size and font
        self.setTextWidth(new_rect.width())
        height_ratio = new_rect.height() / original_height
        new_font_size = self.font_size * height_ratio
        self.set_font_size(new_font_size)

        x1 = new_pos.x()
        y1 = new_pos.y()
        x2 = x1 + new_rect.width()
        y2 = y1 + self.boundingRect().height()
        self.text_block.xyxy[:] = [x1, y1, x2, y2]

        # Update the resize start position
        self._resize_start = scene_pos

        self.update()





