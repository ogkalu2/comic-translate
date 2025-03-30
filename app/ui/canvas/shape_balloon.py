"""
Implementazione della forma Fumetto (nuvoletta) per il canvas.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from .shape_item import ShapeItem


class BalloonItem(ShapeItem):
    """
    Elemento fumetto disegnabile nel canvas.
    Supporta ridimensionamento e stile personalizzabile.
    """
    
    def __init__(self, x, y, width, height, tail_direction='bottom', parent=None):
        super().__init__(parent)
        self._rect = QtCore.QRectF(0, 0, width, height)
        self._tail_direction = tail_direction  # 'top', 'right', 'bottom', 'left'
        self._tail_size = min(width, height) * 0.2  # Dimensione coda proporzionale
        self.setPos(x, y)
        self._type = "balloon"
        self._update_handles()
        
    def boundingRect(self):
        """Restituisce il rettangolo contenente la forma e i suoi handle"""
        # Ottieni il rettangolo base
        rect = self._rect.adjusted(0, 0, 0, 0)
        
        # Espandi il rettangolo per includere la coda
        if self._tail_direction == 'bottom':
            rect.setBottom(rect.bottom() + self._tail_size)
        elif self._tail_direction == 'top':
            rect.setTop(rect.top() - self._tail_size)
        elif self._tail_direction == 'right':
            rect.setRight(rect.right() + self._tail_size)
        elif self._tail_direction == 'left':
            rect.setLeft(rect.left() - self._tail_size)
        
        if not self._is_selected:
            return rect
        
        # Aggiungi spazio per gli handle
        handle_margin = self._handle_size / 2
        return rect.adjusted(-handle_margin, -handle_margin, handle_margin, handle_margin)
        
    def paint(self, painter, option, widget):
        """Disegna il fumetto con lo stile corrente"""
        painter.setPen(QtGui.QPen(self._border_color, self._border_width, self._border_style))
        painter.setBrush(QtGui.QBrush(self._fill_color))
        
        # Crea il path del fumetto
        path = QtGui.QPainterPath()
        
        # Aggiungi l'ellisse principale
        path.addEllipse(self._rect)
        
        # Aggiungi la coda
        if self._tail_direction == 'bottom':
            path.moveTo(self._rect.center().x() - self._tail_size * 0.5, self._rect.bottom())
            path.lineTo(self._rect.center().x(), self._rect.bottom() + self._tail_size)
            path.lineTo(self._rect.center().x() + self._tail_size * 0.5, self._rect.bottom())
        elif self._tail_direction == 'top':
            path.moveTo(self._rect.center().x() - self._tail_size * 0.5, self._rect.top())
            path.lineTo(self._rect.center().x(), self._rect.top() - self._tail_size)
            path.lineTo(self._rect.center().x() + self._tail_size * 0.5, self._rect.top())
        elif self._tail_direction == 'right':
            path.moveTo(self._rect.right(), self._rect.center().y() - self._tail_size * 0.5)
            path.lineTo(self._rect.right() + self._tail_size, self._rect.center().y())
            path.lineTo(self._rect.right(), self._rect.center().y() + self._tail_size * 0.5)
        elif self._tail_direction == 'left':
            path.moveTo(self._rect.left(), self._rect.center().y() - self._tail_size * 0.5)
            path.lineTo(self._rect.left() - self._tail_size, self._rect.center().y())
            path.lineTo(self._rect.left(), self._rect.center().y() + self._tail_size * 0.5)
        
        # Disegna il path
        painter.drawPath(path)
        
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
            'left': QtCore.QRectF(rect.left() - hs, rect.center().y() - hs, s, s),
            # Aggiunge un handle per la direzione della coda
            'tail': QtCore.QRectF(self._get_tail_handle_pos(), s, s)
        }
        
    def _get_tail_handle_pos(self):
        """Ottiene la posizione dell'handle della coda"""
        rect = self._rect
        if self._tail_direction == 'bottom':
            return QtCore.QPointF(rect.center().x() - self._handle_size / 2, rect.bottom() + self._tail_size - self._handle_size / 2)
        elif self._tail_direction == 'top':
            return QtCore.QPointF(rect.center().x() - self._handle_size / 2, rect.top() - self._tail_size - self._handle_size / 2)
        elif self._tail_direction == 'right':
            return QtCore.QPointF(rect.right() + self._tail_size - self._handle_size / 2, rect.center().y() - self._handle_size / 2)
        elif self._tail_direction == 'left':
            return QtCore.QPointF(rect.left() - self._tail_size - self._handle_size / 2, rect.center().y() - self._handle_size / 2)
        
    def _resize_by_handle(self, mouse_pos, handle):
        """Ridimensiona il fumetto in base all'handle selezionato"""
        # Converti la posizione del mouse in coordinate locali
        pos = mouse_pos
        
        # Ottieni le dimensioni correnti
        rect = self._rect
        
        # Se è l'handle della coda, cambia la direzione o la lunghezza
        if handle == 'tail':
            # Calcola la distanza dal centro per determinare direzione
            center = rect.center()
            dx = pos.x() - center.x()
            dy = pos.y() - center.y()
            
            # Determina la direzione della coda in base alla posizione del mouse
            if abs(dx) > abs(dy):
                # Direzione orizzontale
                if dx > 0:
                    self._tail_direction = 'right'
                    self._tail_size = abs(dx - rect.width() / 2)
                else:
                    self._tail_direction = 'left'
                    self._tail_size = abs(dx + rect.width() / 2)
            else:
                # Direzione verticale
                if dy > 0:
                    self._tail_direction = 'bottom'
                    self._tail_size = abs(dy - rect.height() / 2)
                else:
                    self._tail_direction = 'top'
                    self._tail_size = abs(dy + rect.height() / 2)
        else:
            # Altrimenti, ridimensiona il rettangolo normalmente
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
            
            # Aggiorna la dimensione della coda proporzionalmente
            self._tail_size = min(self._rect.width(), self._rect.height()) * 0.2
            
        # Aggiorna gli handle
        self._update_handles()
        
        # Aggiorna la vista
        self.prepareGeometryChange()
        self.update()
        
    def set_tail_direction(self, direction):
        """Imposta la direzione della coda del fumetto"""
        if direction in ['top', 'right', 'bottom', 'left']:
            self._tail_direction = direction
            self._update_handles()
            self.update()
        
    def to_dict(self):
        """Converte l'elemento in un dizionario per la serializzazione"""
        data = super().to_dict()
        data.update({
            'rect_x': self._rect.x(),
            'rect_y': self._rect.y(),
            'rect_width': self._rect.width(),
            'rect_height': self._rect.height(),
            'tail_direction': self._tail_direction,
            'tail_size': self._tail_size
        })
        return data
        
    @classmethod
    def from_dict(cls, data):
        """Crea un'istanza dell'elemento a partire da un dizionario"""
        item = cls(
            data.get('rect_x', 0),
            data.get('rect_y', 0),
            data.get('rect_width', 100),
            data.get('rect_height', 50),
            data.get('tail_direction', 'bottom')
        )
        
        # Imposta la dimensione della coda
        item._tail_size = data.get('tail_size', item._tail_size)
        
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
