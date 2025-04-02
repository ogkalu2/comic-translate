"""
Widget pulsante per la selezione del colore.
"""

from PySide6 import QtCore, QtGui, QtWidgets


class MColorToolButton(QtWidgets.QToolButton):
    """
    Pulsante per la selezione del colore con anteprima del colore selezionato.
    Emette un segnale quando il colore viene cambiato.
    """
    
    colorChanged = QtCore.Signal(QtGui.QColor)
    
    def __init__(self, tooltip="", parent=None):
        super().__init__(parent)
        self._color = QtGui.QColor(0, 0, 0, 255)  # Nero opaco di default
        self.setToolTip(tooltip)
        self.setFixedSize(32, 32)
        self.clicked.connect(self._on_clicked)
        
    def _on_clicked(self):
        """Apre il selettore di colore e aggiorna il colore se l'utente ne seleziona uno"""
        color = QtWidgets.QColorDialog.getColor(
            self._color, 
            self,
            self.toolTip(),
            QtWidgets.QColorDialog.ShowAlphaChannel
        )
        
        if color.isValid():
            self.set_color(color)
            
    def set_color(self, color):
        """Imposta il colore corrente e aggiorna l'aspetto del pulsante"""
        if isinstance(color, str):
            color = QtGui.QColor(color)
            
        self._color = color
        self.update()
        self.colorChanged.emit(color)
        
    def color(self):
        """Restituisce il colore corrente"""
        return self._color
        
    def paintEvent(self, event):
        """Dipinge l'aspetto del pulsante con il colore selezionato"""
        super().paintEvent(event)
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Disegna il rettangolo di anteprima colore
        rect = QtCore.QRect(4, 4, self.width() - 8, self.height() - 8)
        
        # Disegna uno sfondo a scacchiera per trasparenza
        if self._color.alpha() < 255:
            checkerboard = QtGui.QPixmap(16, 16)
            checkerboard.fill(QtCore.Qt.white)
            painter2 = QtGui.QPainter(checkerboard)
            painter2.fillRect(0, 0, 8, 8, QtCore.Qt.lightGray)
            painter2.fillRect(8, 8, 8, 8, QtCore.Qt.lightGray)
            painter2.end()
            
            painter.drawTiledPixmap(rect, checkerboard)
        
        # Disegna il colore selezionato
        painter.setPen(QtCore.Qt.black)
        painter.setBrush(QtGui.QBrush(self._color))
        painter.drawRoundedRect(rect, 4, 4)
        
        painter.end()
