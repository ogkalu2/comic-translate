#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2018.9
# Email : muyanru345@163.com
###################################################################
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import functools


class MFieldMixin(object):
    computed_dict = None
    props_dict = None

    def register_field(self, name, getter=None, setter=None, required=False):
        if self.computed_dict is None:
            self.computed_dict = {}
        if self.props_dict is None:
            self.props_dict = {}
        if callable(getter):
            value = getter()
            self.computed_dict[name] = {
                "value": value,
                "getter": getter,
                "setter": setter,
                "required": required,
                "bind": [],
            }
        else:
            self.props_dict[name] = {"value": getter, "require": required, "bind": []}
        return

    def bind(self, data_name, widget, qt_property, index=None, signal=None, callback=None):
        data_dict = {
            "data_name": data_name,
            "widget": widget,
            "widget_property": qt_property,
            "index": index,
            "callback": callback,
        }
        if data_name in self.computed_dict:
            self.computed_dict[data_name]["bind"].append(data_dict)
        else:
            self.props_dict[data_name]["bind"].append(data_dict)
        if signal:  # 用户操作绑定数据
            getattr(widget, signal).connect(functools.partial(self._slot_changed_from_user, data_dict))
        self._data_update_ui(data_dict)
        return widget

    def fields(self):
        return self.props_dict.keys() + self.computed_dict.keys()

    def field(self, name):
        if name in self.props_dict:
            return self.props_dict[name]["value"]
        elif name in self.computed_dict:
            new_value = self.computed_dict[name]["getter"]()
            self.computed_dict[name]["value"] = new_value
            return new_value
        else:
            raise KeyError('There is no field named "{}"'.format(name))

    def set_field(self, name, value):
        if name in self.props_dict:
            self.props_dict[name]["value"] = value
            self._slot_prop_changed(name)

        elif name in self.computed_dict:
            self.computed_dict[name]["value"] = value

    def _data_update_ui(self, data_dict):
        data_name = data_dict.get("data_name")
        widget = data_dict["widget"]
        index = data_dict["index"]
        widget_property = data_dict["widget_property"]
        callback = data_dict["callback"]
        value = None
        if index is None:
            value = self.field(data_name)
        elif isinstance(self.field(data_name), dict):
            value = self.field(data_name).get(index)
        elif isinstance(self.field(data_name), list):
            value = self.field(data_name)[index] if index < len(self.field(data_name)) else None
        if widget.metaObject().indexOfProperty(widget_property) > -1 or widget_property in list(
            map(str, [b.data().decode() for b in widget.dynamicPropertyNames()])
        ):
            widget.setProperty(widget_property, value)
        else:
            widget.set_field(widget_property, value)
        if callable(callback):
            callback()

    def _slot_prop_changed(self, property_name):
        for key, setting_dict in self.props_dict.items():
            if key == property_name:
                for data_dict in setting_dict["bind"]:
                    self._data_update_ui(data_dict)

        for key, setting_dict in self.computed_dict.items():
            for data_dict in setting_dict["bind"]:
                self._data_update_ui(data_dict)

    def _slot_changed_from_user(self, data_dict, ui_value):
        self._ui_update_data(data_dict, ui_value)

    def _ui_update_data(self, data_dict, ui_value):
        data_name = data_dict.get("data_name")
        index = data_dict.get("index", None)
        if index is None:
            self.set_field(data_name, ui_value)
        else:
            old_value = self.field(data_name)
            old_value[index] = ui_value
            self.set_field(data_name, old_value)
        if data_name in self.props_dict.items():
            self._slot_prop_changed(data_name)

    def _is_complete(self):
        for name, data_dict in self.computed_dict.items() + self.props_dict.items():
            if data_dict["required"]:
                if not self.field(name):
                    return False
        return True
