from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor


class SplashScreen(QWidget):
    """Custom splash screen with minimize and cancel buttons."""
    
    cancelled = Signal()  # Signal emitted when cancel button is clicked
    
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create container widget for the splash content
        container = QWidget()
        container.setObjectName("splashContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Title bar with minimize and close buttons
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(8, 4, 8, 4)
        title_bar_layout.setSpacing(4)
        
        # Title (empty for now, just spacer)
        title_label = QLabel()
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        
        # Minimize button
        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setObjectName("minimizeBtn")
        self.minimize_btn.setFixedSize(24, 24)
        self.minimize_btn.clicked.connect(self.showMinimized)
        self.minimize_btn.setToolTip("Minimize")
        title_bar_layout.addWidget(self.minimize_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setToolTip("Cancel and exit")
        title_bar_layout.addWidget(self.cancel_btn)
        
        container_layout.addWidget(title_bar)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setPixmap(pixmap)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.image_label)
        
        main_layout.addWidget(container)
        
        # Apply styling
        self.setStyleSheet("""
            #splashContainer {
                background-color: white;
                border: 2px solid #cccccc;
                border-radius: 8px;
            }
            #titleBar {
                background-color: #f0f0f0;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #333333;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            #cancelBtn:hover {
                background-color: #ff5555;
                color: white;
            }
            #minimizeBtn:hover {
                background-color: #cccccc;
            }
        """)
        
        # Adjust size to fit content
        self.adjustSize()
        
        # For dragging the window
        self._drag_pos = None
        
    def _on_cancel(self):
        """Handle cancel button click."""
        self.cancelled.emit()
        self.close()
        
    def finish(self, main_window):
        """Close the splash screen and show the main window."""
        if main_window:
            main_window.show()
        self.close()
        
    def mousePressEvent(self, event):
        """Enable dragging the splash screen."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Handle dragging the splash screen."""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        """Stop dragging."""
        self._drag_pos = None
