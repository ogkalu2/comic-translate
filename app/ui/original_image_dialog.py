import cv2
import numpy as np
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtWidgets import QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene, QFrame
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPixmap, QImage, QWheelEvent, QMouseEvent

class OriginalImageViewer(QGraphicsView):
    """
    Widget per visualizzare immagini con zoom e spostamento.
    """
    
    def __init__(self, parent=None):
        super(OriginalImageViewer, self).__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.photo = None
        
        # Impostazioni di visualizzazione
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        self.setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.DontSavePainterState, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFrameShape(QFrame.NoFrame)
        
        # Trasformazione
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Impostazioni mouse
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self._panning = False
        self._pan_start_pos = None
        self._drag_mode_on = False
        
    def set_image(self, image: np.ndarray):
        """Imposta l'immagine da visualizzare."""
        self.scene.clear()
        height, width, channels = image.shape
        
        # Non è necessario convertire qui perché l'immagine è già stata convertita in OriginalImageDialog
        
        # Creiamo un QImage dal numpy array
        bytes_per_line = channels * width
        if channels == 3:
            q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGB888)
        elif channels == 4:
            q_image = QImage(image.data, width, height, bytes_per_line, QImage.Format_RGBA8888)
        else:
            return
        
        # Converte in QPixmap
        pixmap = QPixmap.fromImage(q_image)
        self.photo = pixmap
        
        # Aggiunge la pixmap alla scena
        self.photo_item = self.scene.addPixmap(pixmap)
        self.photo_item.setPos(0, 0)
        
        # Imposta la scena alle dimensioni dell'immagine
        self.scene.setSceneRect(QRectF(0, 0, width, height))
        
        # Attendi che la vista sia completamente inizializzata
        QtCore.QTimer.singleShot(0, self._fit_to_view)
        
    def _fit_to_view(self):
        """Adatta l'immagine alla vista, riempiendo la finestra."""
        self.resetTransform()
        
        # Ottenere le dimensioni dell'immagine e della vista
        scene_rect = self.scene.sceneRect()
        viewport_rect = self.viewport().rect()
        
        # Calcola i fattori di scala per larghezza e altezza
        scale_w = viewport_rect.width() / scene_rect.width()
        scale_h = viewport_rect.height() / scene_rect.height()
        
        # Usa il fattore di scala minore per riempire la vista mantenendo le proporzioni
        scale = min(scale_w, scale_h)
        
        # Applica lo zoom
        self.scale(scale, scale)
        self.zoom_factor = scale
        
        # Centra la vista
        self.centerOn(scene_rect.center())
        
    def wheelEvent(self, event: QWheelEvent):
        """Gestisce lo zoom con la rotella del mouse."""
        if self.photo:
            # Calcola il fattore di zoom
            factor = 1.1
            if event.angleDelta().y() < 0:
                factor = 1.0 / factor
            
            # Aggiorna il fattore di zoom
            new_zoom = self.zoom_factor * factor
            
            # Limita il fattore di zoom
            if new_zoom < self.min_zoom:
                factor = self.min_zoom / self.zoom_factor
            elif new_zoom > self.max_zoom:
                factor = self.max_zoom / self.zoom_factor
            
            # Applica lo zoom
            self.scale(factor, factor)
            self.zoom_factor *= factor
    
    def mousePressEvent(self, event: QMouseEvent):
        """Gestisce la pressione del mouse per lo spostamento."""
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self._drag_mode_on = True
            
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Gestisce il rilascio del mouse."""
        if event.button() == Qt.LeftButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            if self._drag_mode_on:
                self.setDragMode(QGraphicsView.NoDrag)
                self._drag_mode_on = False
                
        super().mouseReleaseEvent(event)

class OriginalImageDialog(QDialog):
    """
    Finestra di dialogo che mostra l'immagine originale con possibilità
    di zoom, spostamento e ridimensionamento.
    """
    
    def __init__(self, image: np.ndarray, target_size=None, parent=None):
        super(OriginalImageDialog, self).__init__(parent)
        self.setWindowTitle("Immagine Originale")
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        
        # Layout principale
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Viewer per l'immagine
        self.image_viewer = OriginalImageViewer(self)
        
        # Converti l'immagine da BGR a RGB prima di passarla al viewer
        # OpenCV usa BGR, Qt usa RGB - dobbiamo convertire
        # Questo è il modo più affidabile per assicurarsi che i colori siano corretti
        if image.shape[2] == 3:  # Se è un'immagine a 3 canali (BGR)
            # Invertiamo i canali B e R usando lo slicing di numpy
            # Assicuriamoci che l'array sia contiguo in memoria
            rgb_image = np.ascontiguousarray(image[:, :, [2, 1, 0]])
        elif image.shape[2] == 4:  # Se è un'immagine a 4 canali (BGRA)
            # Scambia i canali B e R mantenendo il canale alpha (BGRA -> RGBA)
            rgb_image = np.ascontiguousarray(image[:, :, [2, 1, 0, 3]])
        else:
            rgb_image = image.copy()
            
        # Imposta l'immagine
        self.image_viewer.set_image(rgb_image)
        
        # Aggiungi il viewer al layout
        layout.addWidget(self.image_viewer)
        
        # Ridimensiona la finestra in base all'immagine
        height, width, _ = image.shape
        
        # Se è stato specificato un target_size, usalo
        if target_size:
            self.resize(target_size[0], target_size[1])
        else:
            # Dimensioni massime (80% dello schermo)
            screen = QtWidgets.QApplication.primaryScreen()
            screen_size = screen.size()
            max_width = int(screen_size.width() * 0.8)
            max_height = int(screen_size.height() * 0.8)
            
            # Calcola le dimensioni finali (rispettando il rapporto d'aspetto)
            if width > max_width or height > max_height:
                scale = min(max_width / width, max_height / height)
                width = int(width * scale)
                height = int(height * scale)
            
            # Aggiungi un piccolo margine per la barra del titolo
            self.resize(width, height + 30)
