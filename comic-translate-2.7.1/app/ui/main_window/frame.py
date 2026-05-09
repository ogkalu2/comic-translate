from PySide6 import QtCore, QtWidgets

from ..title_bar import RESIZE_MARGIN

_EDGE_CURSORS: dict = {
    frozenset({QtCore.Qt.Edge.LeftEdge}): QtCore.Qt.CursorShape.SizeHorCursor,
    frozenset({QtCore.Qt.Edge.RightEdge}): QtCore.Qt.CursorShape.SizeHorCursor,
    frozenset({QtCore.Qt.Edge.TopEdge}): QtCore.Qt.CursorShape.SizeVerCursor,
    frozenset({QtCore.Qt.Edge.BottomEdge}): QtCore.Qt.CursorShape.SizeVerCursor,
    frozenset({QtCore.Qt.Edge.TopEdge, QtCore.Qt.Edge.LeftEdge}): QtCore.Qt.CursorShape.SizeFDiagCursor,
    frozenset({QtCore.Qt.Edge.BottomEdge, QtCore.Qt.Edge.RightEdge}): QtCore.Qt.CursorShape.SizeFDiagCursor,
    frozenset({QtCore.Qt.Edge.TopEdge, QtCore.Qt.Edge.RightEdge}): QtCore.Qt.CursorShape.SizeBDiagCursor,
    frozenset({QtCore.Qt.Edge.BottomEdge, QtCore.Qt.Edge.LeftEdge}): QtCore.Qt.CursorShape.SizeBDiagCursor,
}


def _edges_at(win: QtWidgets.QMainWindow, gpos: QtCore.QPoint, margin: int = RESIZE_MARGIN):
    """Return a Qt.Edges flag for whichever window edges *gpos* is within *margin* pixels of."""
    geo = win.geometry()
    x = gpos.x() - geo.x()
    y = gpos.y() - geo.y()
    w = geo.width()
    h = geo.height()

    edges = QtCore.Qt.Edge(0)
    if x <= margin:
        edges |= QtCore.Qt.Edge.LeftEdge
    if x >= w - margin:
        edges |= QtCore.Qt.Edge.RightEdge
    if y <= margin:
        edges |= QtCore.Qt.Edge.TopEdge
    if y >= h - margin:
        edges |= QtCore.Qt.Edge.BottomEdge
    return edges


class EdgeResizer(QtCore.QObject):
    """Event filter that provides edge resize cursors and startSystemResize for frameless windows."""

    MARGIN = RESIZE_MARGIN

    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        super().__init__(window)
        self._win = window
        QtWidgets.QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        etype = event.type()
        if etype not in (QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonPress):
            return False

        win = self._win

        if isinstance(watched, QtWidgets.QWidget) and watched.window() is not win:
            return False

        if win.isMaximized() or win.isFullScreen():
            if etype == QtCore.QEvent.Type.MouseMove:
                win.unsetCursor()
            return False

        gpos = event.globalPosition().toPoint()
        geo = win.geometry()
        m = self.MARGIN
        if not geo.adjusted(-m, -m, m, m).contains(gpos):
            if etype == QtCore.QEvent.Type.MouseMove:
                win.unsetCursor()
            return False

        edges = _edges_at(win, gpos, m)

        if etype == QtCore.QEvent.Type.MouseMove:
            key = frozenset(e for e in QtCore.Qt.Edge if e & edges)
            cursor_shape = _EDGE_CURSORS.get(key)
            if cursor_shape is not None:
                win.setCursor(cursor_shape)
            else:
                win.unsetCursor()
            return False

        if event.button() == QtCore.Qt.MouseButton.LeftButton and edges:
            handle = win.windowHandle()
            if handle:
                handle.startSystemResize(edges)
            return True

        return False
