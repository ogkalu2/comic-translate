# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets
import six

# Import local modules
from . import dayu_theme
from . import utils
from .header_view import MHeaderView
from .item_model import MTableModel
from .menu import MMenu
from .qt import MPixmap
from .qt import get_scale_factor


HEADER_SORT_MAP = {"asc": QtCore.Qt.AscendingOrder, "desc": QtCore.Qt.DescendingOrder}


def draw_empty_content(view, text=None, pix_map=None):
    # Import local modules
    from . import dayu_theme

    pix_map = pix_map or MPixmap("empty.svg")
    text = text or view.tr("No Data")
    painter = QtGui.QPainter(view)
    font_metrics = painter.fontMetrics()
    painter.setPen(QtGui.QPen(QtGui.QColor(dayu_theme.secondary_text_color)))
    content_height = pix_map.height() + font_metrics.height()
    padding = 10
    proper_min_size = min(view.height() - padding * 2, view.width() - padding * 2, content_height)
    if proper_min_size < content_height:
        pix_map = pix_map.scaledToHeight(proper_min_size - font_metrics.height(), QtCore.Qt.SmoothTransformation)
        content_height = proper_min_size
    painter.drawText(
        view.width() / 2 - font_metrics.horizontalAdvance(text) / 2,
        view.height() / 2 + content_height / 2 - font_metrics.height() / 2,
        text,
    )
    painter.drawPixmap(
        view.width() / 2 - pix_map.width() / 2,
        view.height() / 2 - content_height / 2,
        pix_map,
    )
    painter.end()


class MOptionDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(MOptionDelegate, self).__init__(parent)
        self.editor = None
        self.showed = False
        self.exclusive = True
        self.parent_widget = None
        self.arrow_space = 20
        self.arrow_height = 6

    def set_exclusive(self, flag):
        self.exclusive = flag

    def createEditor(self, parent, option, index):
        self.parent_widget = parent
        self.editor = MMenu(exclusive=self.exclusive, parent=parent)
        self.editor.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        model = utils.real_model(index)
        real_index = utils.real_index(index)
        data_obj = real_index.internalPointer()
        attr = "{}_list".format(model.header_list[real_index.column()].get("key"))

        self.editor.set_data(utils.get_obj_value(data_obj, attr, []))
        self.editor.sig_value_changed.connect(self._slot_finish_edit)
        return self.editor

    def setEditorData(self, editor, index):
        editor.set_value(index.data(QtCore.Qt.EditRole))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.property("value"))

    def updateEditorGeometry(self, editor, option, index):
        editor.move(
            self.parent_widget.mapToGlobal(QtCore.QPoint(option.rect.x(), option.rect.y() + option.rect.height()))
        )

    def paint(self, painter, option, index):
        painter.save()
        icon_color = dayu_theme.icon_color
        if option.state & QtWidgets.QStyle.State_MouseOver:
            painter.fillRect(option.rect, QtGui.QColor(dayu_theme.primary_5))
            icon_color = "#fff"
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, QtGui.QColor(dayu_theme.primary_6))
            icon_color = "#fff"
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.white))
        pix = MPixmap("down_fill.svg", icon_color)
        h = option.rect.height()
        pix = pix.scaledToWidth(h * 0.5, QtCore.Qt.SmoothTransformation)
        painter.drawPixmap(option.rect.x() + option.rect.width() - h, option.rect.y() + h / 4, pix)
        painter.restore()
        super(MOptionDelegate, self).paint(painter, option, index)

    @QtCore.Slot(object)
    def _slot_finish_edit(self, obj):
        self.commitData.emit(self.editor)

    def sizeHint(self, option, index):
        orig = super(MOptionDelegate, self).sizeHint(option, index)
        return QtCore.QSize(orig.width() + self.arrow_space, orig.height())

    # def eventFilter(self, obj, event):
    #     if obj is self.editor:
    #         print event.type(), obj.size()
    #     return super(MOptionDelegate, self).eventFilter(obj, event)


def set_header_list(self, header_list):
    scale_x, _ = get_scale_factor()
    self.header_list = header_list
    if self.header_view:
        for index, i in enumerate(header_list):
            self.header_view.setSectionHidden(index, i.get("hide", False))
            self.header_view.resizeSection(index, i.get("width", 100) * scale_x)
            if "order" in i:
                order = i.get("order")
                if order in HEADER_SORT_MAP.values():
                    self.header_view.setSortIndicator(index, order)
                elif order in HEADER_SORT_MAP:
                    self.header_view.setSortIndicator(index, HEADER_SORT_MAP[order])
            if i.get("selectable", False):
                delegate = MOptionDelegate(parent=self)
                delegate.set_exclusive(i.get("exclusive", True))
                self.setItemDelegateForColumn(index, delegate)
            elif self.itemDelegateForColumn(index):
                self.setItemDelegateForColumn(index, None)


def enable_context_menu(self, enable):
    if enable:
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.slot_context_menu)
    else:
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)


@QtCore.Slot(QtCore.QPoint)
def slot_context_menu(self, point):
    proxy_index = self.indexAt(point)
    if proxy_index.isValid():
        need_map = isinstance(self.model(), QtCore.QSortFilterProxyModel)
        selection = []
        for index in self.selectionModel().selectedRows() or self.selectionModel().selectedIndexes():
            data_obj = self.model().mapToSource(index).internalPointer() if need_map else index.internalPointer()
            selection.append(data_obj)
        event = utils.ItemViewMenuEvent(view=self, selection=selection, extra={})
        self.sig_context_menu.emit(event)
    else:
        event = utils.ItemViewMenuEvent(view=self, selection=[], extra={})
        self.sig_context_menu.emit(event)


def mouse_move_event(self, event):
    index = self.indexAt(event.pos())
    real_index = utils.real_index(index)
    if self.header_list[real_index.column()].get("is_link", False):
        key_name = self.header_list[real_index.column()]["attr"]
        data_obj = utils.real_model(self.model()).data_list[real_index.row()]
        value = utils.get_obj_value(data_obj, key_name)
        if value:
            self.setCursor(QtCore.Qt.PointingHandCursor)
            return
    self.setCursor(QtCore.Qt.ArrowCursor)


def mouse_release_event(self, event):
    if event.button() != QtCore.Qt.LeftButton:
        QtWidgets.QTableView.mouseReleaseEvent(self, event)
        return
    index = self.indexAt(event.pos())
    real_index = utils.real_index(index)
    if self.headerList[real_index.column()].get("is_link", False):
        key_name = self.header_list[real_index.column()]["attr"]
        data_obj = utils.real_model(self.model()).data_list[real_index.row()]
        value = utils.get_obj_value(data_obj, key_name)
        if value:
            if isinstance(value, dict):
                self.sig_link_clicked.emit(value)
            elif isinstance(value, six.string_types):
                self.sig_link_clicked.emit(data_obj)
            elif isinstance(value, list):
                for i in value:
                    self.sig_link_clicked.emit(i)


class MTableView(QtWidgets.QTableView):
    set_header_list = set_header_list
    enable_context_menu = enable_context_menu
    slot_context_menu = slot_context_menu
    sig_context_menu = QtCore.Signal(object)

    def __init__(self, size=None, show_row_count=False, parent=None):
        super(MTableView, self).__init__(parent)
        self._no_data_image = None
        self._no_data_text = self.tr("No Data")
        size = size or dayu_theme.default_size
        ver_header_view = MHeaderView(QtCore.Qt.Vertical, parent=self)
        ver_header_view.setDefaultSectionSize(size)
        ver_header_view.setSortIndicatorShown(False)
        self.setVerticalHeader(ver_header_view)
        self.header_list = []
        self.header_view = MHeaderView(QtCore.Qt.Horizontal, parent=self)
        self.header_view.setFixedHeight(size)
        if not show_row_count:
            ver_header_view.hide()
        self.setHorizontalHeader(self.header_view)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)

    def set_no_data_text(self, text):
        self._no_data_text = text

    def set_no_data_image(self, image):
        self._no_data_image = image

    def setShowGrid(self, flag):
        self.header_view.setProperty("grid", flag)
        self.verticalHeader().setProperty("grid", flag)
        self.header_view.style().polish(self.header_view)

        return super(MTableView, self).setShowGrid(flag)

        # setting = {
        #     'key': attr,  # 必填，用来读取 model后台数据结构的属性
        #     'label': attr.title(),  # 选填，显示在界面的该列的名字
        #     'width': 100,  # 选填，单元格默认的宽度
        #     'default_filter': False,  # 选填，如果有组合的filter组件，该属性默认是否显示，默认False
        #     'searchable': False,  # 选填，如果有搜索组件，该属性是否可以被搜索，默认False
        #     'editable': False,  # 选填，该列是否可以双击编辑，默认False
        #     'selectable': False,  # 选填，该列是否可以双击编辑，且使用下拉列表选择。该下拉框的选项们，是通过 data 拿数据的
        #     'checkable': False,  # 选填，该单元格是否要加checkbox，默认False
        #     'exclusive': True,  # 配合selectable，如果是可以多选的则为 False，如果是单选，则为True
        #     'order': None,  # 选填，初始化时，该列的排序方式, 0 升序，1 降序
        #     # 下面的是每个单元格的设置，主要用来根据本单元格数据，动态设置样式
        #     'color': None,  # QColor选填，该单元格文字的颜色，例如根据百分比数据大小，大于100%显示红色，小于100%显示绿色
        #     'bg_color': None,  # 选填，该单元格的背景色，例如根据bool数据，True显示绿色，False显示红色
        #     'display': None,  # 选填，该单元显示的内容，例如数据是以分钟为单位，可以在这里给转换成按小时为单位
        #     'align': None,  # 选填，该单元格文字的对齐方式
        #     'font': None,  # 选填，该单元格文字的格式，例如加下划线、加粗等等
        #     'icon': None,  # 选填，该单格元的图标，注意，当 QListView 使用图标模式时，每个item的图片也是在这里设置
        #     'tooltip': None,  # 选填，鼠标指向该单元格时，显示的提示信息
        #     'size': None,  # 选填，该列的 hint size，设置
        #     'data': None,
        #     'edit': None
        # }

    def paintEvent(self, event):
        """Override paintEvent when there is no data to show, draw the preset picture and text."""
        model = utils.real_model(self.model())
        if model is None:
            draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        elif isinstance(model, MTableModel):
            if not model.get_data_list():
                draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        return super(MTableView, self).paintEvent(event)

    def save_state(self, name):
        settings = QtCore.QSettings(
            QtCore.QSettings.IniFormat,
            QtCore.QSettings.UserScope,
            "DAYU",
            ".",
        )
        settings.setValue("{}/headerState".format(name, self.header_view.saveState()))

    def load_state(self, name):
        settings = QtCore.QSettings(
            QtCore.QSettings.IniFormat,
            QtCore.QSettings.UserScope,
            "DAYU",
            ".",
        )
        if settings.value("{}/headerState".format(name)):
            self.header_view.restoreState(settings.value("{}/headerState".format(name)))


class MTreeView(QtWidgets.QTreeView):
    set_header_list = set_header_list
    enable_context_menu = enable_context_menu
    slot_context_menu = slot_context_menu
    sig_context_menu = QtCore.Signal(object)

    def __init__(self, parent=None):
        super(MTreeView, self).__init__(parent)
        self._no_data_image = None
        self._no_data_text = self.tr("No Data")
        self.header_list = []
        self.header_view = MHeaderView(QtCore.Qt.Horizontal)
        self.setHeader(self.header_view)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)

    def paintEvent(self, event):
        """Override paintEvent when there is no data to show, draw the preset picture and text."""
        model = utils.real_model(self.model())
        if model is None:
            draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        elif isinstance(model, MTableModel):
            if not model.get_data_list():
                draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        return super(MTreeView, self).paintEvent(event)

    def set_no_data_text(self, text):
        self._no_data_text = text


class MBigView(QtWidgets.QListView):
    set_header_list = set_header_list
    enable_context_menu = enable_context_menu
    slot_context_menu = slot_context_menu
    sig_context_menu = QtCore.Signal(object)

    def __init__(self, parent=None):
        super(MBigView, self).__init__(parent)
        self._no_data_image = None
        self._no_data_text = self.tr("No Data")
        self.header_list = []
        self.header_view = None
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setMovement(QtWidgets.QListView.Static)
        self.setSpacing(10)
        default_size = dayu_theme.big_view_default_size
        self.setIconSize(QtCore.QSize(default_size, default_size))

    def scale_size(self, factor):
        """Scale the icon size."""
        new_size = self.iconSize() * factor
        max_size = dayu_theme.big_view_max_size
        min_size = dayu_theme.big_view_min_size
        if new_size.width() > max_size:
            new_size = QtCore.QSize(max_size, max_size)
        elif new_size.width() < min_size:
            new_size = QtCore.QSize(min_size, min_size)
        self.setIconSize(new_size)

    def wheelEvent(self, event):
        """Override wheelEvent while user press ctrl, zoom the list view icon size."""
        if event.modifiers() == QtCore.Qt.ControlModifier:
            num_degrees = event.delta() / 8.0
            num_steps = num_degrees / 15.0
            factor = pow(1.125, num_steps)
            self.scale_size(factor)
        else:
            super(MBigView, self).wheelEvent(event)

    def paintEvent(self, event):
        """Override paintEvent when there is no data to show, draw the preset picture and text."""
        model = utils.real_model(self.model())
        if model is None:
            draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        elif isinstance(model, MTableModel):
            if not model.get_data_list():
                draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        return super(MBigView, self).paintEvent(event)

    def set_no_data_text(self, text):
        self._no_data_text = text


class MListView(QtWidgets.QListView):
    set_header_list = set_header_list
    enable_context_menu = enable_context_menu
    slot_context_menu = slot_context_menu
    sig_context_menu = QtCore.Signal(object)

    def __init__(self, size=None, parent=None):
        super(MListView, self).__init__(parent)
        self._no_data_image = None
        self._no_data_text = self.tr("No Data")
        self.setProperty("dayu_size", size or dayu_theme.default_size)
        self.header_list = []
        self.header_view = None
        self.setModelColumn(0)
        self.setAlternatingRowColors(True)

    def set_show_column(self, attr):
        for index, attr_dict in enumerate(self.header_list):
            if attr_dict.get("key") == attr:
                self.setModelColumn(index)
                break
        else:
            self.setModelColumn(0)

    def paintEvent(self, event):
        """Override paintEvent when there is no data to show, draw the preset picture and text."""
        model = utils.real_model(self.model())
        if model is None:
            draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        elif isinstance(model, MTableModel):
            if not model.get_data_list():
                draw_empty_content(self.viewport(), self._no_data_text, self._no_data_image)
        return super(MListView, self).paintEvent(event)

    def set_no_data_text(self, text):
        self._no_data_text = text
