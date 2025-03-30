import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor

from ..dayu_widgets.tool_button import MToolButton
from ..dayu_widgets.push_button import MPushButton
from ..dayu_widgets.browser import MClickBrowserFileToolButton
from ..dayu_widgets.slider import MSlider
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.line_edit import MLineEdit
from ..widgets.color_button import MColorToolButton


class WatermarkWidget(QtWidgets.QWidget):
    """
    Widget per la gestione del watermark.
    Contiene controlli per caricare, regolare e applicare il watermark.
    """
    watermarkLoaded = Signal(QPixmap)
    opacityChanged = Signal(float)
    scaleChanged = Signal(float)
    positionChanged = Signal(str)
    
    def __init__(self, parent=None):
        super(WatermarkWidget, self).__init__(parent)
        self.watermark_pixmap = None
        self.position = "libera"
        
        # Inizializza l'interfaccia
        self.init_ui()
        
    def init_ui(self):
        # Creiamo un layout verticale principale con spazio tra gli elementi
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Pulsante CARICA in alto
        self.main_button = MPushButton("CARICA")
        self.main_button.setToolTip("Carica un'immagine come watermark")
        self.main_button.clicked.connect(self._on_load_watermark_clicked)
        self.main_button.setMinimumHeight(35)
        main_layout.addWidget(self.main_button)
        
        # Spazio tra pulsante e controlli
        main_layout.addSpacing(10)
        
        # Widget per contenere i controlli
        controls_widget = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)  # Aumentiamo lo spazio tra i controlli
        
        # Controllo opacità
        opacity_layout = QtWidgets.QHBoxLayout()
        
        opacity_label = MLabel("Opacità:")
        opacity_label.setFixedWidth(60)
        opacity_label.setStyleSheet("font-weight: bold;")
        
        self.opacity_slider = MSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setToolTip("Regola l'opacità del watermark")
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.opacity_slider.setStyleSheet("QSlider::handle:horizontal {width: 14px; height: 14px;}")
        
        self.opacity_value = MLineEdit()
        self.opacity_value.setFixedWidth(40)
        self.opacity_value.setText("50")
        self.opacity_value.setAlignment(Qt.AlignCenter)
        self.opacity_value.editingFinished.connect(self._on_opacity_value_changed)
        
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_value)
        
        # Controllo scala
        scale_layout = QtWidgets.QHBoxLayout()
        
        scale_label = MLabel("Scala:")
        scale_label.setFixedWidth(60)
        scale_label.setStyleSheet("font-weight: bold;")
        
        self.scale_slider = MSlider(Qt.Horizontal)
        self.scale_slider.setRange(10, 200)
        self.scale_slider.setValue(100)
        self.scale_slider.setToolTip("Regola la dimensione del watermark")
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        self.scale_slider.setStyleSheet("QSlider::handle:horizontal {width: 14px; height: 14px;}")
        
        self.scale_value = MLineEdit()
        self.scale_value.setFixedWidth(40)
        self.scale_value.setText("100")
        self.scale_value.setAlignment(Qt.AlignCenter)
        self.scale_value.editingFinished.connect(self._on_scale_value_changed)
        
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_value)
        
        # Posizione
        position_layout = QtWidgets.QHBoxLayout()
        
        position_label = MLabel("Posizione:")
        position_label.setFixedWidth(60)
        position_label.setStyleSheet("font-weight: bold;")
        
        self.position_combo = QtWidgets.QComboBox()
        self.position_combo.addItems(["Libera", "Centro", "Alto Sx", "Alto Dx", "Basso Sx", "Basso Dx"])
        self.position_combo.setCurrentText("Libera")
        self.position_combo.setFixedWidth(120)
        self.position_combo.setStyleSheet("QComboBox { padding: 3px; }")
        self.position_combo.currentTextChanged.connect(self._on_position_changed)
        
        position_layout.addWidget(position_label)
        position_layout.addWidget(self.position_combo)
        position_layout.addStretch()
        
        # Aggiungi i controlli al layout dei controlli
        controls_layout.addLayout(opacity_layout)
        controls_layout.addLayout(scale_layout)
        controls_layout.addLayout(position_layout)
        
        # Aggiungi i widget al layout principale
        main_layout.addWidget(controls_widget)
        
    def _on_load_watermark_clicked(self):
        """Gestisce il click sul pulsante di caricamento watermark"""
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setWindowTitle("Seleziona immagine watermark")
        file_dialog.setNameFilter("Immagini (*.png *.jpg *.jpeg *.bmp *.gif)")
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self._on_watermark_file_selected(selected_files[0])
                
    def _on_watermark_file_selected(self, file_path):
        """Gestisce la selezione del file watermark"""
        if not file_path:
            return
            
        # Carica l'immagine selezionata
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QtWidgets.QMessageBox.warning(self, "Errore", "Impossibile caricare l'immagine selezionata.")
            return
            
        # Imposta l'immagine watermark
        self.watermark_pixmap = pixmap
        
        # Emette il segnale che il watermark è stato caricato
        self.watermarkLoaded.emit(pixmap)
        
    def _on_opacity_changed(self, value):
        """Gestisce il cambio di opacità dal slider"""
        self.opacity_value.setText(str(value))
        opacity = value / 100.0  # Converti da percentuale a valore float 0-1
        self.opacityChanged.emit(opacity)
        
    def _on_opacity_value_changed(self):
        """Gestisce il cambio di opacità dal campo di testo"""
        try:
            value = int(self.opacity_value.text())
            value = max(0, min(100, value))  # Limita tra 0 e 100
            self.opacity_value.setText(str(value))
            self.opacity_slider.setValue(value)
            # Il segnale opacityChanged verrà emesso dal cambio di valore dello slider
        except ValueError:
            # Ripristina il valore precedente in caso di input non valido
            self.opacity_value.setText(str(self.opacity_slider.value()))
            
    def _on_scale_changed(self, value):
        """Gestisce il cambio di scala dal slider"""
        self.scale_value.setText(str(value))
        scale = value / 100.0  # Converti da percentuale a valore float
        self.scaleChanged.emit(scale)
        
    def _on_scale_value_changed(self):
        """Gestisce il cambio di scala dal campo di testo"""
        try:
            value = int(self.scale_value.text())
            value = max(10, min(200, value))  # Limita tra 10 e 200
            self.scale_value.setText(str(value))
            self.scale_slider.setValue(value)
            # Il segnale scaleChanged verrà emesso dal cambio di valore dello slider
        except ValueError:
            # Ripristina il valore precedente in caso di input non valido
            self.scale_value.setText(str(self.scale_slider.value()))
            
    def _on_color_changed(self, color):
        """Gestisce il cambio di colore - funzione rimossa ma mantenuta per compatibilità"""
        pass
        
    def _on_position_changed(self, position):
        """Gestisce il cambio di posizione"""
        self.position = position.lower()
        self.positionChanged.emit(self.position)
        
    def get_watermark_pixmap(self):
        """Restituisce il pixmap corrente del watermark"""
        return self.watermark_pixmap
