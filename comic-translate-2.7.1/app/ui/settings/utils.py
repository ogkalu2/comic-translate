from PySide6 import QtWidgets
from PySide6.QtGui import QFontMetrics

from ..dayu_widgets.label import MLabel
from ..dayu_widgets.combo_box import MComboBox


def create_title_and_combo(title: str, options: list[str], h4: bool = True) -> tuple[QtWidgets.QWidget, MComboBox]:
    """Create a small widget containing a title label and a combo box.

    Returns (widget, combo_box).
    """
    w = QtWidgets.QWidget()
    v = QtWidgets.QVBoxLayout(w)
    label = MLabel(title).h4() if h4 else MLabel(title)
    combo = MComboBox().small()
    combo.addItems(options)
    v.addWidget(label)
    v.addWidget(combo)
    return w, combo

def set_combo_box_width(combo_box: MComboBox, items: list[str], padding: int = 40) -> None:
    """Set a fixed width on a combo box based on the widest item."""
    metrics = QFontMetrics(combo_box.font())
    max_width = max((metrics.horizontalAdvance(i) for i in items), default=100)
    combo_box.setFixedWidth(max_width + padding)

def set_label_width(label: MLabel, padding: int = 20) -> None:
    """Set a fixed width on a label based on its text."""
    metrics = label.fontMetrics()
    text_width = metrics.horizontalAdvance(label.text())
    label.setFixedWidth(text_width + padding)
