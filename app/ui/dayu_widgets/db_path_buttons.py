#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2018.5
# Email : muyanru345@163.com
###################################################################

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
from functools import partial
from itertools import izip_longest

# Import third-party modules
from qt import *
import utils


def parse_db_orm(orm):
    orm_map = {"view": "items", "search": "items", "folder": "children"}
    return {
        "name": "ROOT" if hasattr(orm, "parent") and orm.parent is None else orm.name,
        "icon": utils.icon_formatter(orm),
        "get_children": lambda x: [
            parse_db_orm(orm) for orm in getattr(x, orm_map.get(x.__tablename__, None)) if orm.active
        ],
        "has_children": lambda x: hasattr(x, orm_map.get(x.__tablename__, None)),
        "data": orm,
    }


def parse_path(path):
    # Import built-in modules
    import os

    # Import third-party modules
    from static import request_file

    return {
        "name": os.path.basename(path) or path,
        "icon": utils.icon_formatter(request_file("icon-browser.png")),
        "get_children": lambda x: [
            parse_path(os.path.join(path, i)) for i in os.listdir(path) if os.path.isdir(os.path.join(path, i))
        ],
        "has_children": lambda x: next(
            (True for i in os.listdir(path) if os.path.isdir(os.path.join(path, i))),
            False,
        ),
        "data": path,
    }


class MBaseButton(QWidget):
    sig_name_button_clicked = Signal(int)
    sig_menu_action_clicked = Signal(int, dict)

    def __init__(self, data_dict, parent=None):
        super(MBaseButton, self).__init__(parent)
        self.data_dict = data_dict
        name_button = QToolButton(parent=self)
        name_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        name_button.setIcon(data_dict.get("icon"))
        name_button.clicked.connect(self.slot_button_clicked)
        name_button.setText(data_dict.get("name"))

        self.menu_button = QToolButton(parent=self)
        self.menu_button.setAutoRaise(False)
        self.menu_button.setArrowType(Qt.RightArrow)
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setIconSize(QSize(10, 10))
        self.menu_button.clicked.connect(self.slot_show_menu)
        self.menu_button.setVisible(data_dict.get("has_children")(data_dict.get("data")))
        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(name_button)
        main_lay.addWidget(self.menu_button)
        self.setLayout(main_lay)

    @Slot()
    def slot_button_clicked(self):
        self.sig_name_button_clicked.emit(self.data_dict.get("index"))

    @Slot()
    def slot_action_clicked(self, sub_obj):
        self.sig_menu_action_clicked.emit(self.data_dict.get("index"), sub_obj)

    @Slot()
    def slot_show_menu(self):
        menu = QMenu(self)
        data_list = self.data_dict.get("get_children")(self.data_dict.get("data"))
        for sub_obj in data_list:
            action = menu.addAction(sub_obj.get("icon"), sub_obj.get("name"))
            action.triggered.connect(partial(self.slot_action_clicked, sub_obj))
        self.menu_button.setMenu(menu)
        self.menu_button.showMenu()

    def enterEvent(self, *args, **kwargs):
        self.menu_button.setArrowType(Qt.DownArrow)
        return super(MBaseButton, self).enterEvent(*args, **kwargs)

    def leaveEvent(self, *args, **kwargs):
        self.menu_button.setArrowType(Qt.RightArrow)
        return super(MBaseButton, self).leaveEvent(*args, **kwargs)


class MDBPathButtons(QFrame):
    sig_current_changed = Signal()

    @utils.dayu_css()
    def __init__(self, parent=None):
        super(MDBPathButtons, self).__init__(parent)
        self.parse_function = None
        self.data_list = []

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addLayout(self.layout)
        main_lay.addStretch()
        self.setLayout(main_lay)

    def set_parse_function(self, func):
        self.parse_function = func

    def setup_data(self, obj):
        self.clear_downstream(0)
        if obj:
            self.add_level(self.parse_function(obj))
            self.sig_current_changed.emit()

    def add_level(self, data_dict):
        index = len(self.data_list)
        data_dict.update({"index": index})
        button = MBaseButton(data_dict, parent=self)
        button.sig_name_button_clicked.connect(self.slot_button_clicked)
        button.sig_menu_action_clicked.connect(self.slot_menu_button_clicked)
        self.layout.addWidget(button)
        data_dict.update({"widget": button})
        self.data_list.append(data_dict)

    def clear_downstream(self, index):
        for i, data_dict in enumerate(self.data_list):
            if i >= index:
                button = data_dict.get("widget")
                self.layout.removeWidget(button)
                button.setVisible(False)
        self.data_list = self.data_list[:index]

    @Slot(QToolButton, dict)
    def slot_show_menu(self, menu_button, data_dict):
        menu = QMenu(self)
        data_list = data_dict.get("get_children")(data_dict.get("data"))
        index = data_dict.get("index")
        for sub_obj in data_list:
            action = menu.addAction(sub_obj.get("icon"), sub_obj.get("name"))
            action.triggered.connect(partial(self.slot_menu_button_clicked, index, sub_obj))
        menu_button.setMenu(menu)
        menu_button.showMenu()

    @Slot(object)
    def slot_button_clicked(self, index):
        self.clear_downstream(index + 1)
        self.sig_current_changed.emit()

    @Slot(object)
    def slot_menu_button_clicked(self, index, data_dict):
        self.clear_downstream(index + 1)
        self.add_level(data_dict)
        self.sig_current_changed.emit()

    @Slot(object)
    def slot_go_to(self, obj_list):
        for index, (his_obj, our_obj) in enumerate(izip_longest(obj_list, self.get_obj_list())):
            if his_obj is None:
                # 如果传来的 obj_list 最后一个是 None，则我方的 obj 多，直接清理掉多余的
                self.clear_downstream(index)
                return
            elif our_obj is None:
                # 我方的 obj 不够，则追加
                self.add_level(self.parse_function(his_obj))
            elif his_obj != our_obj:
                # 我方 跟 传来的 obj 不一样，清理掉后面的，并追加传来的orm
                self.clear_downstream(index)
                self.add_level(self.parse_function(his_obj))
            else:
                # 我方和传来的 obj 完全一样，不做处理
                continue

    def get_obj_list(self):
        return [i.get("data") for i in self.data_list]


if __name__ == "__main__":
    # Import built-in modules
    import sys

    app = QApplication(sys.argv)
    test = MDBPathButtons()
    test.set_parse_function(parse_path)
    test.setup_data("d:/")
    test.show()
    sys.exit(app.exec_())
