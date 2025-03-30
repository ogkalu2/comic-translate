import cv2
import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QObject
from PySide6.QtGui import QPixmap, QImage, QColor, QPen, QBrush

class WatermarkItem(QObject, QGraphicsPixmapItem):
    """
    Classe per la gestione di un watermark sull'immagine.
    Consente di regolare posizione, dimensioni e opacità.
    """
    positionChanged = Signal(QPointF)
    sizeChanged = Signal(float)
    opacityChanged = Signal(float)

    def __init__(self, parent=None):
        QObject.__init__(self)
        QGraphicsPixmapItem.__init__(self, parent)
        self.original_pixmap = None
        self.original_image = None
        self.scale_factor = 1.0
        self.opacity_value = 0.5
        
        # Impostazioni di interazione
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        
        # Imposta valori predefiniti
        self.setOpacity(self.opacity_value)
        self.resize_in_progress = False
        self.resize_handles = []  # Inizializza come lista vuota
        self.current_handle = None  # Handle attualmente selezionato
        
        # Inizializza i punti di ridimensionamento
        self.init_resize_handles()
        
    def init_resize_handles(self):
        """Inizializza i punti di ridimensionamento"""
        # Crea i punti di controllo per il ridimensionamento agli angoli
        self.resize_handles = []  # Assicurati che sia una lista vuota
        for i in range(2):  # Due punti di controllo: in alto a sinistra e in basso a destra
            handle = QtWidgets.QGraphicsRectItem(0, 0, 10, 10, self)
            handle.setBrush(QBrush(QColor(0, 120, 200, 200)))
            handle.setPen(QPen(QColor(0, 120, 200), 1))
            handle.setFlag(QGraphicsItem.ItemIsMovable, True)
            handle.setFlag(QGraphicsItem.ItemIsSelectable, False)
            handle.setCursor(Qt.SizeFDiagCursor)
            handle.hide()
            self.resize_handles.append(handle)
        
        self.update_resize_handles()
        
    def update_resize_handles(self):
        """Aggiorna la posizione dei punti di ridimensionamento"""
        if not self.pixmap():
            return
            
        rect = self.boundingRect()
        
        # Posiziona i punti di ridimensionamento agli angoli
        self.resize_handles[0].setPos(rect.topLeft())
        self.resize_handles[1].setPos(rect.bottomRight() - QPointF(10, 10))
        
    def set_watermark(self, pixmap):
        """Imposta l'immagine del watermark"""
        if pixmap is None or pixmap.isNull():
            return False
            
        self.original_pixmap = pixmap
        self.original_image = self.qpixmap_to_opencv(pixmap)
        self.setPixmap(pixmap)
        self.update_resize_handles()
        return True
        
    def set_opacity(self, opacity):
        """Imposta l'opacità del watermark"""
        self.opacity_value = opacity
        self.setOpacity(opacity)
        
    def set_scale(self, scale):
        """Imposta il fattore di scala del watermark"""
        if self.original_pixmap is None:
            return
            
        self.scale_factor = scale
        self.apply_transformations()
        
    def apply_transformations(self):
        """Applica tutte le trasformazioni (scala) al watermark"""
        if self.original_image is None:
            return
            
        # Applicazione della scala all'immagine
        img = self.original_image.copy()
        
        # Ridimensionamento dell'immagine
        if self.scale_factor != 1.0:
            h, w = img.shape[:2]
            new_h, new_w = int(h * self.scale_factor), int(w * self.scale_factor)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
        # Converti l'immagine elaborata in QPixmap
        pixmap = self.opencv_to_qpixmap(img)
        self.setPixmap(pixmap)
        self.update_resize_handles()
        
    def qpixmap_to_opencv(self, pixmap):
        """Converte un QPixmap in un'immagine OpenCV"""
        qimage = pixmap.toImage()
        width, height = qimage.width(), qimage.height()
        
        # Converti in formato compatibile con OpenCV
        if qimage.format() != QImage.Format_RGBA8888:
            qimage = qimage.convertToFormat(QImage.Format_RGBA8888)
            
        # Metodo aggiornato per PySide6 che restituisce memoryview
        # invece di sip.voidptr utilizzato in PyQt
        bytes_per_line = qimage.bytesPerLine()
        buffer = qimage.bits().tobytes()
        img = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
        
        return img.copy()  # Crea una copia per evitare problemi di riferimento
        
    def opencv_to_qpixmap(self, img):
        """Converte un'immagine OpenCV in QPixmap"""
        if img is None:
            return QPixmap()
            
        height, width = img.shape[:2]
        
        # Assicurati che l'immagine sia nel formato corretto (RGBA)
        if len(img.shape) == 2:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:  # BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        
        # Crea una QImage dall'array numpy
        qimg = QImage(img.data, width, height, img.strides[0], QImage.Format_RGBA8888)
        
        return QPixmap.fromImage(qimg)
        
    def itemChange(self, change, value):
        """Gestisce i cambiamenti di stato dell'item"""
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            # Emetti il segnale di cambio posizione
            self.positionChanged.emit(value)
        
        return super(WatermarkItem, self).itemChange(change, value)
        
    def hoverEnterEvent(self, event):
        """Gestisce l'evento di hover sul watermark"""
        if self.isSelected():
            for handle in self.resize_handles:
                handle.show()
        
        super(WatermarkItem, self).hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Gestisce l'evento di uscita dall'hover sul watermark"""
        if not self.isSelected():
            for handle in self.resize_handles:
                handle.hide()
                
        super(WatermarkItem, self).hoverLeaveEvent(event)
        
    def mousePressEvent(self, event):
        """Gestisce l'evento di pressione del mouse"""
        # Controlla se il clic è su uno dei punti di ridimensionamento
        for i, handle in enumerate(self.resize_handles):
            if handle.isUnderMouse():
                self.resize_in_progress = True
                self.current_handle = i
                return  # Non propagare l'evento
                
        super(WatermarkItem, self).mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Gestisce l'evento di rilascio del mouse"""
        if self.resize_in_progress:
            self.resize_in_progress = False
            self.current_handle = None
            
        super(WatermarkItem, self).mouseReleaseEvent(event)
        
    def mouseMoveEvent(self, event):
        """Gestisce l'evento di movimento del mouse"""
        if self.resize_in_progress and self.current_handle is not None:
            # Implementa il ridimensionamento
            new_pos = event.pos()
            
            if self.current_handle == 0:  # Handle in alto a sinistra
                # Calcola la nuova dimensione
                rect = self.boundingRect()
                br = rect.bottomRight()
                width = br.x() - new_pos.x()
                height = br.y() - new_pos.y()
                
                # Calcola il fattore di scala proporzionale
                original_width = self.original_pixmap.width() if self.original_pixmap else 1
                ratio = width / original_width
                
                # Aggiorna la scala
                self.scale_factor = max(0.1, ratio)  # Impedisce valori troppo piccoli
                self.apply_transformations()
                
                # Emetti segnale di cambio dimensione
                self.sizeChanged.emit(self.scale_factor)
                
            elif self.current_handle == 1:  # Handle in basso a destra
                # Calcola la nuova dimensione
                rect = self.boundingRect()
                tl = rect.topLeft()
                width = new_pos.x() - tl.x()
                height = new_pos.y() - tl.y()
                
                # Calcola il fattore di scala proporzionale
                original_width = self.original_pixmap.width() if self.original_pixmap else 1
                ratio = width / original_width
                
                # Aggiorna la scala
                self.scale_factor = max(0.1, ratio)  # Impedisce valori troppo piccoli
                self.apply_transformations()
                
                # Emetti segnale di cambio dimensione
                self.sizeChanged.emit(self.scale_factor)
                
            return  # Non propagare l'evento
            
        super(WatermarkItem, self).mouseMoveEvent(event)
