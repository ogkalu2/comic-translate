import bisect
from dataclasses import dataclass, field
from functools import cached_property
from typing import Iterator

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSizeF
from PySide6.QtGui import QTextDocument, QTransform, QPainter, \
                           QTextFrame, QTextBlock, QTextOption, \
                           QAbstractTextDocumentLayout, QTextLine

from .metrics import CharacterStyle, GlyphPlacement, PlacementRule

def iter_blocks(doc: QTextDocument) -> Iterator[QTextBlock]:
    """Provides a Pythonic iterator over the blocks in a QTextDocument."""
    block = doc.firstBlock()
    while block.isValid():
        yield block
        block = block.next()


@dataclass
class CharLayoutInfo:
    """Stores the calculated line width for a character."""
    line_width: float

@dataclass
class LayoutContext:
    """All the information needed for a single layout pass."""
    document: QTextDocument
    available_size: QSizeF
    line_spacing: float
    letter_spacing: float

    @cached_property
    def doc_margin(self) -> float:
        return self.document.documentMargin()

    @cached_property
    def available_height(self) -> float:
        return max(self.available_size.height() - self.doc_margin * 2, 0)


@dataclass
class LayoutState:
    """Holds the result of a single layout pass."""
    nodes: list['BlockLayoutNode'] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    content_width: float = 0.0
    content_height: float = 0.0
    content_left_x: float = 0.0
    min_required_height: float = 0.0

    # Caches for hit-testing, generated on-demand
    @cached_property
    def hittest_x_rights(self) -> list[float]:
        return [node.x_right for node in self.nodes]

    @cached_property
    def hittest_y_tops(self) -> list[list[float]]:
        return [[line.y_boundary[0] for line in node.lines] for node in self.nodes]

class LineLayoutNode:
    """Represents and calculates the layout for a single line of vertical text."""
    def __init__(
            self, 
            qt_line: QTextLine, 
            start_index_in_block: int, 
            parent_block: 'BlockLayoutNode', 
            context: 'LayoutContext'
        ):
        self.qt_line = qt_line
        self.start_char_index_in_block = start_index_in_block
        self.parent_block = parent_block
        self.context = context
        self.text_len = qt_line.textLength()

        # Properties calculated on initialization, used for column breaking
        self.char_style: CharacterStyle = None
        self.char_width: float = 0
        self.space_width: float = 0
        self.left_spaces: int = 0
        self.right_spaces: int = 0
        self.effective_char_idx: int = -1
        self.calculated_height: float = 0
        self.letter_spacing_offset: float = 0

        # Properties calculated in the final geometry pass
        self.char_y_offsets: list[float] = []
        self.y_boundary: list[float] = [0, 0]
        self.draw_offset: QPointF = QPointF()

        self._calculate_initial_properties()

    def _calculate_initial_properties(self):
        """Calculates a preliminary line height for column-breaking decisions."""
        blk_text = self.parent_block.qt_block.text()
        blk_text_len = len(blk_text)

        # Find the first non-space character to determine the line's properties
        text = blk_text[self.start_char_index_in_block : self.start_char_index_in_block + self.text_len].replace('\n', '')
        self.right_spaces = self.text_len - len(text.rstrip())
        self.left_spaces = self.text_len - len(text.lstrip())
        self.effective_char_idx = self.start_char_index_in_block + self.left_spaces

        tbr_h = 0
        if self.effective_char_idx < blk_text_len:
            # Get the character style and the primary character driving this line's layout
            self.char_style = self.parent_block.get_char_fontfmt(self.effective_char_idx)
            char = blk_text[self.effective_char_idx]

            # Basic properties needed for all cases
            self.space_width = self.char_style.space_width
            self.char_width = self.char_style.tight_char_bounds.width()
            self.letter_spacing_offset = self.char_style.tight_char_bounds.height() * (self.context.letter_spacing - 1)

            # Get the placement rule from our new, independent logic class
            rule, _, _ = GlyphPlacement.get_rule(char)
            
            base_h = 0
            # Dispatch based on the placement rule 
            if rule == PlacementRule.ROTATE_EDGE_ALIGNED or rule == PlacementRule.ROTATE_CENTERED:
                base_h = self.qt_line.naturalTextWidth()
                # Account for leading spaces that don't contribute to the rotated height.
                if self.left_spaces > 0:
                    base_h -= self.left_spaces * self.space_width

            elif rule == PlacementRule.UPRIGHT_CENTERED:
                # For centered punctuation, a good estimate is the tight bounding box plus the descent,
                # which accounts for characters that sit on or below the baseline.
                tbr, _ = self.char_style.get_char_bounds(char)
                base_h = tbr.height() + self.char_style.font_metrics.descent()

            else:  # Default case: PlacementRule.UPRIGHT
                base_h = self.char_style.tight_char_bounds.height()
            
            # Apply letter spacing offset to the calculated base height
            tbr_h = base_h + self.letter_spacing_offset

        elif self.start_char_index_in_block < blk_text_len:
            # This handles lines that contain only spaces or are empty but still part of a block
            self.char_style = self.parent_block.get_char_fontfmt(self.start_char_index_in_block)
            tbr_h = self.char_style.tight_char_bounds.height() + self.char_style.font_metrics.descent()
            self.space_width = self.char_style.space_width
            self.char_width = self.char_style.tight_char_bounds.width()

        self.calculated_height = max(0, tbr_h)

    def calculate_final_geometry(self, y_offset: float, available_height: float) -> float:
        """Calculates final y-offsets for characters based on the line's starting y_offset."""
        self.char_y_offsets = [y_offset]
        for _ in range(self.left_spaces):
            self.char_y_offsets.append(min(available_height - self.calculated_height, self.char_y_offsets[-1] + self.space_width))

        char_bottom = self.char_y_offsets[-1] + self.calculated_height
        self.char_y_offsets.append(char_bottom)

        for _ in range(self.right_spaces):
            self.char_y_offsets.append(min(self.char_y_offsets[-1] + self.space_width, available_height))

        line_bottom = self.char_y_offsets[-1]
        self.y_boundary = [self.char_y_offsets[self.left_spaces], line_bottom]
        return line_bottom

    def update_draw_offset(self, line_width: float):
        """Calculates the precise drawing offset to align glyphs correctly."""
        if not self.char_style or self.text_len == 0: return

        blk_text = self.parent_block.qt_block.text()
        char_idx = self.effective_char_idx
        char = blk_text[char_idx]

        space_shift = self.left_spaces * self.char_style.space_width if self.left_spaces > 0 else 0
        line_start = self.qt_line.textStart()
        line_len = self.qt_line.textLength()
        line_text = blk_text[line_start : line_start + line_len]
        act_rect = self.char_style.get_precise_bounds(line_text, self.qt_line, space_shift=space_shift)

        rule, is_open, is_close = GlyphPlacement.get_rule(char)
        xoff, yoff = 0, 0

        if rule == PlacementRule.ROTATE_EDGE_ALIGNED or rule == PlacementRule.ROTATE_CENTERED:
            yoff = -act_rect[1] - act_rect[3] # Base y-offset for rotation
            xoff = -act_rect[0] # Base x-offset
            
            # Now, adjust based on the sub-rule
            if rule == PlacementRule.ROTATE_EDGE_ALIGNED:
                if is_open: # Right-aligned in vertical (e.g., '「')
                    yoff -= (line_width - act_rect[3])
                # For close brackets, no special y-shift is needed, they align to the left edge by default.
            else: # ROTATE_CENTERED
                yoff -= (line_width - act_rect[3]) / 2
                
            if char.isalpha(): # Specific override for rotated latin chars
                yoff = -self.qt_line.ascent() - (line_width - self.char_style.font_metrics.capHeight()) / 2
                xoff = 0 # Reset xoff for alpha chars

        elif rule == PlacementRule.UPRIGHT_CENTERED:
            yoff = -act_rect[1]
            xoff = -act_rect[0] + (line_width - act_rect[2]) / 2
            
            # Handle specific centered punctuation alignment nuances
            if char in GlyphPlacement._FORCE_CENTERED_PUNCTUATION and char not in {'！', '？'}:
                tbr, _ = self.char_style.get_char_bounds(char)
                yoff += (tbr.height() + self.char_style.font_metrics.descent() - act_rect[3]) / 2

        else: # Default UPRIGHT rule
            yoff = min(self.char_style.standard_char_bounds.top() - self.char_style.tight_char_bounds.top(), -self.char_style.tight_char_bounds.top() - self.qt_line.ascent())
            xoff = -act_rect[0] + (line_width - act_rect[2]) / 2

        # handle space_shift offset
        self.draw_offset = QPointF(xoff, yoff)

    def set_position(self, pos: QPointF):
        self.qt_line.setPosition(pos)

    def draw(self, painter: QPainter, selection: QAbstractTextDocumentLayout.Selection):
        """Draws this single line of text, handling rotation and selection."""
        if self.text_len == 0:
            return

        block = self.parent_block.qt_block
        blpos = block.position()
        blk_text = block.text()

        if self.effective_char_idx < 0:
            # Fallback for lines that don't map to an effective character (e.g., empty lines).
            # Draw the raw line at (0,0) relative to its calculated position.
            self.qt_line.draw(painter, QPointF(0, 0))
            return

        xoff, yoff = self.draw_offset.x(), self.draw_offset.y()
        char = blk_text[self.effective_char_idx]
        char_style = self.char_style

        # Determine if this character is selected
        selected = False
        if selection:
            sel_start = selection.cursor.selectionStart() - blpos
            sel_end = selection.cursor.selectionEnd() - blpos
            if sel_start <= self.effective_char_idx < sel_end:
                selected = True

        line_width = self.parent_block.chars.get(self.effective_char_idx, CharLayoutInfo(char_style.tight_char_bounds.width())).line_width
        line_text = blk_text[self.qt_line.textStart(): self.qt_line.textStart() + self.qt_line.textLength()]

        rule, _, _ = GlyphPlacement.get_rule(char)
        is_rotated = (rule == PlacementRule.ROTATE_EDGE_ALIGNED or rule == PlacementRule.ROTATE_CENTERED)
        if is_rotated:
            line_x, line_y = self.qt_line.x(), self.qt_line.y()
            transform = QTransform(0, 1, -1, 0, line_x + line_y, line_y - line_x)
            painter.setTransform(transform, True)
            
            # Embedded line_draw logic for rotated text
            if selected and selection:
                painter.save()
                overlay_rect = QRectF(self.qt_line.x() + xoff, self.qt_line.y() + yoff, self.qt_line.naturalTextWidth(), self.qt_line.height())
                painter.fillRect(overlay_rect, selection.format.background())
                painter.setPen(selection.format.foreground().color())
                self.qt_line.draw(painter, QPointF(xoff, yoff))
                painter.restore()
            else:
                self.qt_line.draw(painter, QPointF(xoff, yoff))
            
            painter.setTransform(transform.inverted()[0], True)
        else:
            # Embedded line_draw logic for non-rotated text
            if selected and selection:
                painter.save()
                
                if char_style is None:
                    overlay_rect = QRectF(self.qt_line.x() + xoff, self.qt_line.y() + yoff, self.qt_line.naturalTextWidth(), self.qt_line.height())
                else:
                    bound_rect = char_style.get_precise_bounds(line_text, self.qt_line)
                    bound_rect = QRectF(0, bound_rect[1], line_width, bound_rect[3])
                    overlay_rect = QRectF(self.qt_line.x() + xoff, self.qt_line.y() + yoff + bound_rect.y(), line_width, bound_rect.height())

                painter.fillRect(overlay_rect, selection.format.background())
                painter.setPen(selection.format.foreground().color())
                self.qt_line.draw(painter, QPointF(xoff, yoff))
                painter.restore()
            else:
                self.qt_line.draw(painter, QPointF(xoff, yoff))


class BlockLayoutNode:
    """Represents and calculates the layout for a QTextBlock."""
    def __init__(
            self, 
            qt_block: QTextBlock, 
            block_number: int, 
            context: 'LayoutContext'
        ):
        self.qt_block = qt_block
        self.block_number = block_number
        self.context = context

        self.char_style_list: list[CharacterStyle] = []
        self.map_charidx2frag: dict[int, int] = {}
        self.ideal_width: float = -1
        self._precalculate_formats()

        self.x_right: float = 0
        self.x_left: float = 0
        self.lines: list[LineLayoutNode] = []
        self.chars: dict[int, CharLayoutInfo] = {} # Maps char index in block to its calculated line width
        self.min_required_height: float = 0
        self._max_line_y: float = 0

    # Method to handle pre-calculation for this block only.
    def _precalculate_formats(self):
        """Caches font formats and ideal dimensions for this specific block."""
        char_idx = 0
        it = self.qt_block.begin()
        frag_idx = 0
        while not it.atEnd():
            fragment = it.fragment()
            char_style = CharacterStyle(fragment.charFormat())
            self.char_style_list.append(char_style)

            w_ = char_style.standard_char_bounds.width()
            if self.ideal_width < w_:
                self.ideal_width = w_

            for _ in range(fragment.length()):
                self.map_charidx2frag[char_idx] = frag_idx
                char_idx += 1
            it += 1
            frag_idx += 1

    def get_char_fontfmt(self, char_idx: int) -> CharacterStyle:
        """Gets the CharacterStyle for a character index within this block."""
        if not self.map_charidx2frag:
            # Fallback for empty blocks
            return self.char_style_list[0] if self.char_style_list else CharacterStyle(self.qt_block.charFormat())
        if char_idx not in self.map_charidx2frag:
            # Fallback for positions at the very end of the block
            char_idx = len(self.map_charidx2frag) - 1
        frag_idx = self.map_charidx2frag[char_idx]
        return self.char_style_list[frag_idx]

    def layout(self, x_offset: float, available_height: float, is_first_line_in_doc: bool) -> dict[float, float, bool]:
        self.x_right = x_offset
        self.qt_block.clearLayout()
        doc_margin = self.context.doc_margin

        tl = self.qt_block.layout()
        tl.beginLayout()
        option = self.context.document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAnywhere)
        tl.setTextOption(option)

        blk_text = self.qt_block.text()
        blk_text_len = len(blk_text)
        block_width = self.ideal_width if blk_text_len > 0 else CharacterStyle(self.qt_block.charFormat()).tight_char_bounds.width()
        char_idx_in_block = 0

        y_offset = doc_margin
        lines_in_current_column = []
        is_first_block_in_doc = self.qt_block == self.context.document.firstBlock()

        while char_idx_in_block <= blk_text_len:
            line = tl.createLine()
            if not line.isValid(): break

            line.setLineWidth(block_width)
            line.setNumColumns(1)
            line_node = LineLayoutNode(line, char_idx_in_block, self, self.context)

            char_bottom = y_offset + line_node.calculated_height
            end_of_block = char_idx_in_block + line_node.text_len >= blk_text_len
            out_of_vspace = char_bottom - max(line_node.letter_spacing_offset, 0) > available_height

            if out_of_vspace:
                if char_idx_in_block == 0 and is_first_block_in_doc:
                    self.min_required_height = doc_margin + line_node.calculated_height

                actual_height_needed = char_bottom + doc_margin
                self.min_required_height = max(self.min_required_height, actual_height_needed)

                x_offset = self._finalize_column(lines_in_current_column, x_offset, available_height, is_first_line_in_doc)
                lines_in_current_column = [line_node]
                y_offset = doc_margin
                is_first_line_in_doc = False
            else:
                lines_in_current_column.append(line_node)

            y_offset += line_node.calculated_height

            char_idx_in_block += line_node.text_len
            if end_of_block: break

        x_offset = self._finalize_column(lines_in_current_column, x_offset, available_height, is_first_line_in_doc)

        tl.endLayout()
        self.x_left = x_offset
        return x_offset, self.min_required_height, False

    def _finalize_column(self, lines: list[LineLayoutNode], x_offset: float, available_height: float, is_first_line: bool):
        if not lines:
            return x_offset
        doc_margin = self.context.doc_margin

        width_list = [l.char_width for l in lines if l.char_style]
        if not width_list:
            width_list = [self.ideal_width]
        idea_line_width = max(width_list)

        line_spacing = 1.0 if is_first_line else self.context.line_spacing
        x_offset -= idea_line_width * line_spacing

        y_pos = doc_margin
        for line_node in lines:
            line_node.set_position(QPointF(x_offset, y_pos))
            y_pos = line_node.calculate_final_geometry(y_pos, available_height)
            self._max_line_y = max(self._max_line_y, y_pos)
            self.lines.append(line_node)

            if line_node.effective_char_idx != -1:
                self.chars[line_node.effective_char_idx] = CharLayoutInfo(idea_line_width)

        return x_offset

    def update_draw_offsets(self, is_painting_stroke: bool):
        """Delegates draw offset calculation to child lines."""
        if is_painting_stroke and self.lines:
            return
        for line in self.lines:
            line_width = self.chars.get(line.effective_char_idx, CharLayoutInfo(line.char_width)).line_width
            line.update_draw_offset(line_width)

    def set_x_shift(self, shift: float):
        """Applies a horizontal shift to the block and its lines."""
        self.x_right += shift
        self.x_left += shift
        for line in self.lines:
            pos = line.qt_line.position()
            line.set_position(pos + QPointF(shift, 0))

    def height(self):
        return self._max_line_y

    def width(self):
        return self.x_right - self.x_left

    def hit_test(self, point: QPointF, line_y_tops: list[float]) -> int:
        """Performs a hit test within this block."""
        line_idx = bisect.bisect_right(line_y_tops, point.y()) - 1

        if not (0 <= line_idx < len(self.lines)):
            # Return start of block for positions before first line, end for positions after last line
            if line_idx < 0:
                return 0  # Return relative position 0 for before first line
            else:
                # Return the last valid position in this block
                return max(0, self.qt_block.length() - 1)

        line_info = self.lines[line_idx]
        line_top, line_bottom = line_info.y_boundary
        y = point.y()

        off = 0
        if y < line_top:
            off = line_info.qt_line.textStart()
        elif y > line_bottom:
            off = line_info.qt_line.textStart() + line_info.qt_line.textLength()
        else:
            if line_info.left_spaces > 0 or line_info.right_spaces > 0:
                y_offsets = line_info.char_y_offsets
                for i, (ytop, ybottom) in enumerate(zip(y_offsets[:-1], y_offsets[1:])):
                    if ytop <= y < ybottom:
                        dis_top, dis_bottom = y - ytop, ybottom - y
                        off = i if dis_top < dis_bottom else i + 1
                        break
                else:
                    off = len(y_offsets) - 1
                off += line_info.start_char_index_in_block
            else:
                qt_line = line_info.qt_line
                off = qt_line.textStart()
                if qt_line.textLength() != 1:
                    if line_bottom - y < y - line_top:
                        off += 2
                    elif qt_line.naturalTextRect().right() - point.x() < point.x() - qt_line.naturalTextRect().left():
                        off += 1
                elif line_bottom - y < y - line_top:
                    off += 1

        # Ensure offset is within valid range for this block
        off = max(0, min(off, self.qt_block.length() - 1))
        return off  # Return relative offset, not absolute position

    def draw(self, painter: QPainter, selection: QAbstractTextDocumentLayout.Selection):
        """Delegates drawing to child LineLayoutNode instances."""
        for line_node in self.lines:
            line_node.draw(painter, selection)



class VerticalTextDocumentLayout(QAbstractTextDocumentLayout):
    size_enlarged = Signal()
    def __init__(
            self, 
            document: QTextDocument, 
            line_spacing: float, 
            letter_spacing: float = 1.15, 
        ):
        super().__init__(document)
        # Core layout configuration
        self.line_spacing = line_spacing
        self.letter_spacing = letter_spacing

        # Document dimensions
        self.max_width = 0
        self.max_height = 0
        self.user_set_width = 0
        self.user_set_height = 0
        self.auto_height_mode = True

        # The single source of truth for the calculated layout result
        self._layout_state = LayoutState()

        # Control flags and other state
        self.update_layout_on_changed = True
        self._is_painting_stroke = False
        self.has_selection = False

    @property
    def doc_margin(self) -> float:
        return self.document().documentMargin()

    def set_max_size(self, max_width: int, max_height: int, relayout=True):
        self.user_set_width = max_width
        self.user_set_height = max_height
        if max_height > 0:
            self.auto_height_mode = False

        self.max_height = max_height
        self.max_width = max_width
        if relayout:
            self.update_layout()

    def set_line_spacing(self, line_spacing: float):
        if self.line_spacing != line_spacing:
            self.line_spacing = line_spacing
            self.update_layout()

    def set_line_spacing_type(self, linespacing_type: int):
        if self.linespacing_type != linespacing_type:
            self.linespacing_type = linespacing_type
            self.update_layout()

    def set_letter_spacing(self, letter_spacing: float):
        if self.letter_spacing != letter_spacing:
            self.letter_spacing = letter_spacing
            self.update_layout()

    def update_layout(self):
        # This loop allows the layout to be re-run if it discovers it
        # needs more space.
        max_iterations = 5  
        for _ in range(max_iterations):
            # 1. Create the context for this layout pass
            context = LayoutContext(
                document=self.document(),
                available_size=QSizeF(self.max_width, self.max_height),
                line_spacing=self.line_spacing,
                letter_spacing=self.letter_spacing,
            )

            # 2. Run the stateless layout engine to get a potential layout state
            current_state = self.calculate_layout(context)

            # 3. Analyze the result and decide if resizing is needed
            enlarged = False
            doc_margin = context.doc_margin

            content_width_needed = self.max_width - current_state.content_left_x + doc_margin
            min_width_needed = max(content_width_needed + doc_margin, self.user_set_width)

            # Width Contraction: Shrink if oversized
            if self.max_width > min_width_needed * 1.2 and self.max_width > self.user_set_width:
                self.max_width = min_width_needed
                enlarged = True
            # Width Expansion: Grow if content overflows
            elif current_state.content_left_x < doc_margin:
                self.max_width += (doc_margin - current_state.content_left_x)
                enlarged = True

            # Height Expansion: Grow if content overflows and in auto-height mode
            if current_state.min_required_height > context.available_height + doc_margin:
                if self.auto_height_mode:
                    self.max_height = current_state.min_required_height + doc_margin
                    enlarged = True

            if enlarged:
                self.size_enlarged.emit()
                continue  # Re-run the layout with new dimensions
            else:
                # Success! Commit the temporary state to the real state.
                self._layout_state = current_state
                break  # Layout fits, exit the loop

        self._update_all_draw_offsets()
        self.documentSizeChanged.emit(self.documentSize())

    def _update_all_draw_offsets(self):
        for node in self._layout_state.nodes:
            node.update_draw_offsets(is_painting_stroke=self._is_painting_stroke)

    def calculate_layout(self, context: LayoutContext) -> LayoutState:
        """
        Calculates the layout for the entire document based on the given context.
        This is a stateless operation that returns a new LayoutState.
        """
        state = LayoutState(
            width=context.available_size.width(), 
            height=context.available_size.height()
        )

        doc = context.document
        doc_margin = context.doc_margin
        x_offset = context.available_size.width() - doc_margin
        min_doc_height = 0
        is_first_line_in_doc = True

        current_available_height = context.available_height + doc_margin

        for block_no, block in enumerate(iter_blocks(doc)):
            node = BlockLayoutNode(block, block_no, context)
            x_offset, block_min_height, is_first_line_in_doc = node.layout(
                x_offset, current_available_height, is_first_line_in_doc
            )
            state.nodes.append(node)

            min_doc_height = max(min_doc_height, block_min_height)
            actual_height_needed = node.height() + doc_margin
            min_doc_height = max(min_doc_height, actual_height_needed)

            if node.height() > current_available_height - doc_margin:
                min_doc_height = max(min_doc_height, node.height() + doc_margin * 2)

        state.content_left_x = x_offset
        state.content_height = max((node.height() for node in state.nodes), default=doc_margin) - doc_margin
        state.content_width = context.available_size.width() - state.content_left_x - doc_margin
        state.min_required_height = min_doc_height

        return state

    def draw(self, painter: QPainter, context: QAbstractTextDocumentLayout.PaintContext) -> None:
        painter.save()
        context_sel = context.selections
        has_selection = len(context_sel) > 0
        selection = context_sel[0] if has_selection else None
        cursor_block = self.document().findBlock(context.cursorPosition)

        # Delegate drawing to the hierarchical layout nodes
        for block_node in self._layout_state.nodes:
            block_node.draw(painter, selection)

        # Draw the cursor, which is a layout-level concern
        if cursor_block.isValid() and cursor_block.isVisible():
            blk_no = cursor_block.blockNumber()
            if blk_no < len(self._layout_state.nodes):
                block_node = self._layout_state.nodes[blk_no]
                layout = cursor_block.layout()
                cpos_in_block = context.cursorPosition - cursor_block.position()
                line = layout.lineForTextPosition(cpos_in_block)
                if line.isValid():
                    pos = line.position()
                    x, y = pos.x(), pos.y()

                    line_width = 0
                    line_idx = line.lineNumber()
                    if line_idx < len(block_node.lines):
                        line_info = block_node.lines[line_idx]
                        char_info = block_node.chars.get(line_info.effective_char_idx)
                        if char_info: line_width = char_info.line_width

                        y_idx = cpos_in_block - line_info.start_char_index_in_block
                        if 0 <= y_idx < len(line_info.char_y_offsets):
                            y = line_info.char_y_offsets[y_idx]

                    if line_width == 0:
                        line_width = CharacterStyle(cursor_block.charFormat()).tight_char_bounds.width()

                    painter.setCompositionMode(QPainter.CompositionMode.RasterOp_NotDestination)
                    painter.fillRect(QRectF(x, y, line_width, 2), painter.pen().brush())

        if context.cursorPosition != -1 or has_selection:
            self.update.emit()
        if self.has_selection != has_selection:
            self.update.emit()
        else:
            self.update.emit()
        self.has_selection = has_selection
        painter.restore()

    def hitTest(self, point: QPointF, accuracy: Qt.HitTestAccuracy) -> int:
        if not self._layout_state.nodes:
            return 0

        rev_x_rights = self._layout_state.hittest_x_rights[::-1]
        rev_idx = bisect.bisect_left(rev_x_rights, point.x())
        block_idx = len(self._layout_state.hittest_x_rights) - 1 - rev_idx

        if not (0 <= block_idx < len(self._layout_state.nodes)):
            return 0

        block_node = self._layout_state.nodes[block_idx]

        if point.x() < block_node.x_left:
            return block_node.qt_block.position() + block_node.qt_block.length() - 1

        line_y_tops = self._layout_state.hittest_y_tops[block_idx]
        relative_offset = block_node.hit_test(point, line_y_tops)
        
        # Convert relative offset to absolute position
        result = block_node.qt_block.position() + relative_offset
        
        # Final safety check to ensure result is within document bounds
        doc_length = self.document().characterCount()
        return max(0, min(result, doc_length - 1))

    def documentSize(self) -> QSizeF:
        return QSizeF(self.max_width, self.max_height)

    def documentChanged(self, position: int, charsRemoved: int, charsAdded: int) -> None:
        if not self.update_layout_on_changed:
            return
        self.update_layout()

    def blockBoundingRect(self, block: QTextBlock) -> QRectF:
        if not block.isValid():
            return QRectF()
        block_no = block.blockNumber()
        if block_no < len(self._layout_state.nodes):
            node = self._layout_state.nodes[block_no]
            return QRectF(node.x_left, 0, node.width(), node.height())
        return QRectF()

    def frameBoundingRect(self, frame: QTextFrame):
        return QRectF(0, 0, max(self.document().pageSize().width(), self.max_width), 2147483647)

    def max_font_size(self) -> float:
        max_fs = self.document().defaultFont().pointSizeF()
        if self._layout_state and self._layout_state.nodes:
            for node in self._layout_state.nodes:
                for char_style in node.char_style_list:
                    max_fs = max(max_fs, char_style.font.pointSizeF())
        return max_fs

    def min_size(self):
        return (self._layout_state.content_height, self._layout_state.content_width)

    def update_document_margin(self, margin):
        old_doc_margin = self.doc_margin
        # Preserve the content area size when changing margins
        self.max_height = self.max_height - old_doc_margin * 2 + margin * 2
        self.max_width = self.max_width - old_doc_margin * 2 + margin * 2
        self.document().setDocumentMargin(margin)
        self.update_layout()
