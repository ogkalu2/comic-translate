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

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
import six

# Import local modules
from .utils import apply_formatter
from .utils import display_formatter
from .utils import font_formatter
from .utils import get_obj_value
from .utils import icon_formatter
from .utils import set_obj_value


SETTING_MAP = {
    QtCore.Qt.BackgroundRole: {"config": "bg_color", "formatter": QtGui.QColor},
    QtCore.Qt.DisplayRole: {"config": "display", "formatter": display_formatter},
    QtCore.Qt.EditRole: {"config": "edit", "formatter": None},
    QtCore.Qt.TextAlignmentRole: {
        "config": "alignment",
        "formatter": {
            "right": QtCore.Qt.AlignRight,
            "left": QtCore.Qt.AlignLeft,
            "center": QtCore.Qt.AlignCenter,
        },
    },
    QtCore.Qt.ForegroundRole: {"config": "color", "formatter": QtGui.QColor},
    QtCore.Qt.FontRole: {"config": "font", "formatter": font_formatter},
    QtCore.Qt.DecorationRole: {"config": "icon", "formatter": icon_formatter},
    QtCore.Qt.ToolTipRole: {"config": "tooltip", "formatter": display_formatter},
    QtCore.Qt.InitialSortOrderRole: {
        "config": "order",
        "formatter": {
            "asc": QtCore.Qt.AscendingOrder,
            "des": QtCore.Qt.DescendingOrder,
        },
    },
    QtCore.Qt.SizeHintRole: {
        "config": "size",
        "formatter": lambda args: QtCore.QSize(*args),
    },
    QtCore.Qt.UserRole: {"config": "data"},  # anything
}


class MTableModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super(MTableModel, self).__init__(parent)
        self.origin_count = 0
        self.root_item = {"name": "root", "children": []}
        self.data_generator = None
        self.header_list = []
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.fetchMore)

    def set_header_list(self, header_list):
        self.header_list = header_list

    def set_data_list(self, data_list):
        if hasattr(data_list, "next"):
            self.beginResetModel()
            self.root_item["children"] = []
            self.endResetModel()
            self.data_generator = data_list
            self.origin_count = 0
            self.timer.start()
        else:
            self.beginResetModel()
            self.root_item["children"] = data_list if data_list is not None else []
            self.endResetModel()
            self.data_generator = None

    def clear(self):
        self.beginResetModel()
        self.root_item["children"] = []
        self.endResetModel()

    def get_data_list(self):
        return self.root_item["children"]

    def append(self, data_dict):
        self.root_item["children"].append(data_dict)
        self.fetchMore()

    def remove(self, data_dict):
        row = self.root_item["children"].index(data_dict)
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.root_item["children"].remove(data_dict)
        self.endRemoveRows()

    def flags(self, index):
        result = QtCore.QAbstractItemModel.flags(self, index)
        if not index.isValid():
            return QtCore.Qt.ItemIsEnabled
        if self.header_list[index.column()].get("checkable", False):
            result |= QtCore.Qt.ItemIsUserCheckable
        if self.header_list[index.column()].get("selectable", False):
            result |= QtCore.Qt.ItemIsEditable
        if self.header_list[index.column()].get("editable", False):
            result |= QtCore.Qt.ItemIsEditable
        if self.header_list[index.column()].get("draggable", False):
            result |= QtCore.Qt.ItemIsDragEnabled
        if self.header_list[index.column()].get("droppable", False):
            result |= QtCore.Qt.ItemIsDropEnabled
        return QtCore.Qt.ItemFlags(result)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Vertical:
            return super(MTableModel, self).headerData(section, orientation, role)
        if not self.header_list or section >= len(self.header_list):
            return None
        if role == QtCore.Qt.DisplayRole:
            return self.header_list[section]["label"]
        return None

    def index(self, row, column, parent_index=None):
        if parent_index and parent_index.isValid():
            parent_item = parent_index.internalPointer()
        else:
            parent_item = self.root_item

        children_list = get_obj_value(parent_item, "children")
        if children_list and len(children_list) > row:
            child_item = children_list[row]
            if child_item:
                set_obj_value(child_item, "_parent", parent_item)
                return self.createIndex(row, column, child_item)
        return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        child_item = index.internalPointer()
        parent_item = get_obj_value(child_item, "_parent")

        if parent_item is None:
            return QtCore.QModelIndex()

        grand_item = get_obj_value(parent_item, "_parent")
        if grand_item is None:
            return QtCore.QModelIndex()
        parent_list = get_obj_value(grand_item, "children")
        return self.createIndex(parent_list.index(parent_item), 0, parent_item)

    def rowCount(self, parent_index=None):
        if parent_index and parent_index.isValid():
            parent_item = parent_index.internalPointer()
        else:
            parent_item = self.root_item
        children_obj = get_obj_value(parent_item, "children")
        if hasattr(children_obj, "next") or (children_obj is None):
            return 0
        else:
            return len(children_obj)

    def hasChildren(self, parent_index=None):
        if parent_index and parent_index.isValid():
            parent_data = parent_index.internalPointer()
        else:
            parent_data = self.root_item
        children_obj = get_obj_value(parent_data, "children")
        if children_obj is None:
            return False
        if hasattr(children_obj, "next"):
            return True
        else:
            return len(children_obj)

    def columnCount(self, parent_index=None):
        return len(self.header_list)

    def canFetchMore(self, index):
        try:
            if self.data_generator:
                data = self.data_generator.next()
                self.root_item["children"].append(data)
                return True
            return False
        except StopIteration:
            if self.timer.isActive():
                self.timer.stop()
            return False

    def fetchMore(self, index=None):
        self.beginResetModel()
        self.endResetModel()

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        attr_dict = self.header_list[index.column()]  # 获取该列字段的配置
        data_obj = index.internalPointer()
        attr = attr_dict.get("key")
        if role in SETTING_MAP.keys():
            role_key = SETTING_MAP[role].get("config")  # role 配置的关键字
            formatter_from_config = attr_dict.get(role_key)  # header中该role的配置
            if not formatter_from_config and role not in [
                QtCore.Qt.DisplayRole,
                QtCore.Qt.EditRole,
                QtCore.Qt.ToolTipRole,
            ]:
                # 如果header中没有配置该role，而且也不是 DisplayRole/EditRole，直接返回None
                return None
            else:
                value = apply_formatter(formatter_from_config, get_obj_value(data_obj, attr), data_obj)
            formatter_from_model = SETTING_MAP[role].get("formatter", None)  # role 配置的转换函数
            result = apply_formatter(formatter_from_model, value)
            return result

        if role == QtCore.Qt.CheckStateRole and attr_dict.get("checkable", False):
            state = get_obj_value(data_obj, attr + "_checked")
            return QtCore.Qt.Unchecked if state is None else state
        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if index.isValid() and role in [QtCore.Qt.CheckStateRole, QtCore.Qt.EditRole]:
            attr_dict = self.header_list[index.column()]
            key = attr_dict.get("key")
            data_obj = index.internalPointer()
            if role == QtCore.Qt.CheckStateRole and attr_dict.get("checkable", False):
                key += "_checked"
                # Update self
                set_obj_value(data_obj, key, value)
                self.dataChanged.emit(index, index, [role])

                # Update its children
                for row, sub_obj in enumerate(get_obj_value(data_obj, "children", [])):
                    set_obj_value(sub_obj, key, value)
                    sub_index = self.index(row, index.column(), index)
                    self.dataChanged.emit(sub_index, sub_index, [role])

                # Update its parent
                parent_index = index.parent()
                if parent_index.isValid():
                    parent_obj = parent_index.internalPointer()
                    new_parent_value = value
                    old_parent_value = get_obj_value(parent_obj, key)
                    for sibling_obj in get_obj_value(get_obj_value(data_obj, "_parent"), "children", []):
                        if value != get_obj_value(sibling_obj, key):
                            new_parent_value = QtCore.Qt.PartiallyChecked
                            break
                    if new_parent_value != old_parent_value:
                        set_obj_value(parent_obj, key, new_parent_value)
                        self.dataChanged.emit(parent_index, parent_index, [role])
            else:
                set_obj_value(data_obj, key, value)
                self.dataChanged.emit(index, index, [role])
            return True
        else:
            return False


class MSortFilterModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super(MSortFilterModel, self).__init__(parent)
        if hasattr(self, "setRecursiveFilteringEnabled"):
            self.setRecursiveFilteringEnabled(True)
        self.header_list = []
        self.search_reg = QtCore.QRegularExpression()
        self.search_reg.setPatternOptions(QtCore.QRegularExpression.CaseInsensitiveOption)
        self.search_reg.setPattern(".*")  # This sets a wildcard-like pattern in regex

    def set_header_list(self, header_list):
        self.header_list = header_list
        for head in self.header_list:
            reg_exp = QtCore.QRegularExpression()
            reg_exp.setPatternOptions(QtCore.QRegularExpression.CaseInsensitiveOption)
            head.update({"reg": reg_exp})

    def filterAcceptsRow(self, source_row, source_parent):
        # If search bar has content, first match the content of the search bar
        if self.search_reg.pattern():
            for index, data_dict in enumerate(self.header_list):
                if data_dict.get("searchable", False):
                    model_index = self.sourceModel().index(source_row, index, source_parent)
                    value = self.sourceModel().data(model_index)
                    match = self.search_reg.match(str(value))
                    if match.hasMatch():
                        # Search matched
                        break
            else:
                # All searches completed, none matched, return False directly
                return False

        # Then match the filter combination
        for index, data_dict in enumerate(self.header_list):
            model_index = self.sourceModel().index(source_row, index, source_parent)
            value = self.sourceModel().data(model_index)
            reg_exp = data_dict.get("reg", None)
            if reg_exp and reg_exp.pattern():
                match = reg_exp.match(str(value))
                if not match.hasMatch():
                    # Does not meet the filter, return False directly
                    return False

        return True

    def set_search_pattern(self, pattern):
        self.search_reg.setPattern(pattern)
        self.invalidateFilter()

    def set_filter_attr_pattern(self, attr, pattern):
        for data_dict in self.header_list:
            if data_dict.get("key") == attr:
                data_dict.get("reg").setPattern(pattern)
                break
        self.invalidateFilter()

