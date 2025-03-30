"""
Implementazione della forma Rettangolo per il canvas.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from .shape_item import ShapeItem


class RectangleItem(ShapeItem):
    """
    Elemento rettangolare disegnabile nel canvas.
    Supporta ridimensionamento e stile personalizzabile.
    """
    
    def __init__(self, x, y, width, height, parent=None):
        super().__init__(parent)
        self._rect = QtCore.QRectF(0, 0, width, height)
        self.setPos(x, y)
        self._type = "rectangle"
        self._update_handles()
        
    def boundingRect(self):
        """Restituisce il rettangolo contenente la forma e i suoi handle"""
        if not self._is_selected:
            return self._rect
        
        # Aggiungi spazio per gli handle
        handle_margin = self._handle_size / 2
        return self._rect.adjusted(-handle_margin, -handle_margin, handle_margin, handle_margin)
        
    def paint(self, painter, option, widget):
        """Disegna il rettangolo con lo stile corrente"""
        # Disegna il rettangolo
        painter.setPen(QtGui.QPen(self._border_color, self._border_width, self._border_style))
        painter.setBrush(QtGui.QBrush(self._fill_color))
        painter.drawRect(self._rect)
        
        # Disegna gli handle se selezionato
        self._paint_handles(painter)
        
    def _update_handles(self):
        """Aggiorna la posizione degli handle di ridimensionamento"""
        if not self._is_selected:
            return
            
        s = self._handle_size
        hs = s / 2
        rect = self._rect
        
        self._handles = {
            'top_left': QtCore.QRectF(rect.left() - hs, rect.top() - hs, s, s),
            'top': QtCore.QRectF(rect.center().x() - hs, rect.top() - hs, s, s),
            'top_right': QtCore.QRectF(rect.right() - hs, rect.top() - hs, s, s),
            'right': QtCore.QRectF(rect.right() - hs, rect.center().y() - hs, s, s),
            'bottom_right': QtCore.QRectF(rect.right() - hs, rect.bottom() - hs, s, s),
            'bottom': QtCore.QRectF(rect.center().x() - hs, rect.bottom() - hs, s, s),
            'bottom_left': QtCore.QRectF(rect.left() - hs, rect.bottom() - hs, s, s),
            'left': QtCore.QRectF(rect.left() - hs, rect.center().y() - hs, s, s)
        }
        
    def _resize_by_handle(self, mouse_pos, handle):
        """Ridimensiona il rettangolo in base all'handle selezionato"""
        # Converti la posizione del mouse in coordinate locali
        pos = mouse_pos
        
        # Ottieni le dimensioni correnti
        rect = self._rect
        
        # Aggiorna il rettangolo in base al handle selezionato
        if handle == 'top_left':
            rect.setTopLeft(pos)
        elif handle == 'top':
            rect.setTop(pos.y())
        elif handle == 'top_right':
            rect.setTopRight(pos)
        elif handle == 'right':
            rect.setRight(pos.x())
        elif handle == 'bottom_right':
            rect.setBottomRight(pos)
        elif handle == 'bottom':
            rect.setBottom(pos.y())
        elif handle == 'bottom_left':
            rect.setBottomLeft(pos)
        elif handle == 'left':
            rect.setLeft(pos.x())
            
        # Normalizza il rettangolo (gestisce dimensioni negative)
        self._rect = rect.normalized()
        
        # Aggiorna gli handle
        self._update_handles()
        
        # Aggiorna la vista
        self.prepareGeometryChange()
        self.update()
        
    def to_dict(self):
        """Converte l'elemento in un dizionario per la serializzazione"""
        data = super().to_dict()
        data.update({
            'rect_x': self._rect.x(),
            'rect_y': self._rect.y(),
            'rect_width': self._rect.width(),
            'rect_height': self._rect.height()
        })
        return data
        
    @classmethod
    def from_dict(cls, data):
        """Crea un'istanza dell'elemento a partire da un dizionario"""
        item = cls(
            data.get('rect_x', 0),
            data.get('rect_y', 0),
            data.get('rect_width', 100),
            data.get('rect_height', 50)
        )
        
        # Imposta le proprietà di stile
        item.set_border_color(QtGui.QColor(data.get('border_color', '#FF000000')))
        item.set_fill_color(QtGui.QColor(data.get('fill_color', '#B4FFFFFF')))
        item.set_border_width(data.get('border_width', 2.0))
        item.set_border_style(QtCore.Qt.PenStyle(data.get('border_style', QtCore.Qt.SolidLine)))
        
        # Imposta posizione e trasformazioni
        item.setPos(data.get('pos_x', 0), data.get('pos_y', 0))
        item.setZValue(data.get('z_value', 0))
        item.setRotation(data.get('rotation', 0))
        
        return item
