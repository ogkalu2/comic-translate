"""
Classe base per gli elementi di forma disegnabili nell'editor di immagini.
Gestisce proprietà comuni come colore del bordo, colore di riempimento, e z-index.
"""

from PySide6 import QtCore, QtGui, QtWidgets


class ShapeItem(QtWidgets.QGraphicsObject):
    """
    Classe base per tutti gli elementi di forma nel canvas.
    Gestisce proprietà comuni e comportamenti come selezione, movimenti e stile.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
        # Stile di default
        self._border_color = QtGui.QColor(0, 0, 0, 255)  # Nero opaco
        self._fill_color = QtGui.QColor(255, 255, 255, 180)  # Bianco semitrasparente
        self._border_width = 2.0
        self._border_style = QtCore.Qt.SolidLine
        
        # Stato attuale
        self._is_selected = False
        self._handle_size = 8.0
        self._handles = {}  # Punti di controllo per ridimensionamento
        self._handle_cursors = {
            'top_left': QtCore.Qt.SizeFDiagCursor,
            'top': QtCore.Qt.SizeVerCursor,
            'top_right': QtCore.Qt.SizeBDiagCursor,
            'right': QtCore.Qt.SizeHorCursor,
            'bottom_right': QtCore.Qt.SizeFDiagCursor,
            'bottom': QtCore.Qt.SizeVerCursor,
            'bottom_left': QtCore.Qt.SizeBDiagCursor,
            'left': QtCore.Qt.SizeHorCursor
        }
        self._handle_being_dragged = None
        
        # Per la serializzazione
        self._type = "shape"  # Da sovrascrivere nelle sottoclassi
        
    def type(self):
        """Restituisce il tipo di forma per l'identificazione"""
        return self._type
        
    def boundingRect(self):
        """
        Rettangolo che contiene la forma e i suoi handle.
        Da implementare nelle sottoclassi.
        """
        raise NotImplementedError("Metodo da implementare nelle sottoclassi")
        
    def paint(self, painter, option, widget):
        """
        Dipinge la forma e i suoi handle se selezionata.
        Da implementare nelle sottoclassi per la forma specifica, poi
        richiamare _paint_handles se appropriato.
        """
        raise NotImplementedError("Metodo da implementare nelle sottoclassi")
        
    def _update_handles(self):
        """
        Aggiorna la posizione degli handle basandosi sul boundingRect.
        Da implementare nelle sottoclassi.
        """
        raise NotImplementedError("Metodo da implementare nelle sottoclassi")
        
    def _paint_handles(self, painter):
        """Dipinge gli handle di ridimensionamento se l'oggetto è selezionato"""
        if self._is_selected:
            # Rendi le maniglie più visibili con un bordo più scuro
            painter.setPen(QtGui.QPen(QtCore.Qt.black, 1.5, QtCore.Qt.SolidLine))
            painter.setBrush(QtGui.QBrush(QtCore.Qt.cyan))
            for handle_pos in self._handles.values():
                # Rendi le maniglie leggermente più grandi
                enlarged_rect = handle_pos.adjusted(-1, -1, 1, 1)
                painter.drawRect(enlarged_rect)
                
    def handle_at(self, point):
        """Restituisce il tipo di handle alla posizione specificata, o None"""
        if not self._is_selected:
            return None
            
        for handle_name, handle_rect in self._handles.items():
            if handle_rect.contains(point):
                return handle_name
        return None
        
    def set_border_color(self, color):
        """Imposta il colore del bordo"""
        self._border_color = color
        self.update()
        
    def border_color(self):
        """Restituisce il colore del bordo"""
        return self._border_color
        
    def set_fill_color(self, color):
        """Imposta il colore di riempimento"""
        self._fill_color = color
        self.update()
        
    def fill_color(self):
        """Restituisce il colore di riempimento"""
        return self._fill_color
        
    def set_border_width(self, width):
        """Imposta lo spessore del bordo"""
        self._border_width = width
        self.update()
        
    def border_width(self):
        """Restituisce lo spessore del bordo"""
        return self._border_width
        
    def set_border_style(self, style):
        """Imposta lo stile del bordo (solido, tratteggiato, ecc.)"""
        self._border_style = style
        self.update()
        
    def border_style(self):
        """Restituisce lo stile del bordo"""
        return self._border_style
        
    def mousePressEvent(self, event):
        """Gestisce l'evento di pressione del mouse sull'elemento"""
        self._handle_being_dragged = self.handle_at(event.pos())
        if self._handle_being_dragged:
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        """Gestisce l'evento di movimento del mouse"""
        if self._handle_being_dragged:
            self._resize_by_handle(event.pos(), self._handle_being_dragged)
            event.accept()
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        """Gestisce l'evento di rilascio del mouse"""
        if self._handle_being_dragged:
            self._handle_being_dragged = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            
    def itemChange(self, change, value):
        """Risponde ai cambiamenti di stato dell'elemento"""
        if change == QtWidgets.QGraphicsItem.ItemSelectedChange:
            self._is_selected = bool(value)
            self.update()
        return super().itemChange(change, value)
        
    def _resize_by_handle(self, mouse_pos, handle):
        """
        Ridimensiona la forma in base all'handle selezionato.
        Da implementare nelle sottoclassi.
        """
        raise NotImplementedError("Metodo da implementare nelle sottoclassi")
        
    def to_dict(self):
        """
        Converte l'elemento in un dizionario per la serializzazione.
        Da estendere nelle sottoclassi.
        """
        return {
            'type': self._type,
            'border_color': self._border_color.name(QtGui.QColor.HexArgb),
            'fill_color': self._fill_color.name(QtGui.QColor.HexArgb),
            'border_width': self._border_width,
            'border_style': int(self._border_style),
            'pos_x': self.pos().x(),
            'pos_y': self.pos().y(),
            'z_value': self.zValue(),
            'rotation': self.rotation()
        }
        
    @classmethod
    def from_dict(cls, data):
        """
        Crea un'istanza dell'elemento a partire da un dizionario.
        Da implementare nelle sottoclassi.
        """
        raise NotImplementedError("Metodo da implementare nelle sottoclassi")
