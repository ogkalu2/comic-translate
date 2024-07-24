#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import string

# Import local modules
from . import DEFAULT_STATIC_FOLDER
from . import utils
from .qt import get_scale_factor


def get_theme_size():
    scale_factor_x, scale_factor_y = get_scale_factor()
    return {
        "border_radius_large": int(6 * scale_factor_x),
        "border_radius_base": int(4 * scale_factor_x),
        "border_radius_small": int(2 * scale_factor_x),
        "huge": int(48 * scale_factor_x),
        "large": int(40 * scale_factor_x),
        "medium": int(32 * scale_factor_x),
        "small": int(24 * scale_factor_x),
        "tiny": int(18 * scale_factor_x),
        "huge_icon": int((48 - 20) * scale_factor_x),
        "large_icon": int((40 - 16) * scale_factor_x),
        "medium_icon": int((32 - 12) * scale_factor_x),
        "small_icon": int((24 - 10) * scale_factor_x),
        "tiny_icon": int((18 - 8) * scale_factor_x),
        "default_size": int(32 * scale_factor_x),
        "badge_width_radius": int(8 * scale_factor_x),
        "badge_width": int(16 * scale_factor_x),
        "badge_dot": int(8 * scale_factor_x),
        "badge_dot_radius": int(4 * scale_factor_x),
        "drop_down_huge": int(20 * scale_factor_x),
        "drop_down_large": int(16 * scale_factor_x),
        "drop_down_medium": int(14 * scale_factor_x),
        "drop_down_small": int(10 * scale_factor_x),
        "drop_down_tiny": int(8 * scale_factor_x),
        "spin_box_huge": int(28 * scale_factor_x),
        "spin_box_large": int(26 * scale_factor_x),
        "spin_box_medium": int(24 * scale_factor_x),
        "spin_box_small": int(20 * scale_factor_x),
        "spin_box_tiny": int(18 * scale_factor_x),
        "spin_box_icon_huge": int(14 * scale_factor_x),
        "spin_box_icon_large": int(12 * scale_factor_x),
        "spin_box_icon_medium": int(10 * scale_factor_x),
        "spin_box_icon_small": int(8 * scale_factor_x),
        "spin_box_icon_tiny": int(6 * scale_factor_x),
        "drag_border": int(2 * scale_factor_x),
        "drag_border_radius": int(10 * scale_factor_x),
        "drag_padding_x": int(20 * scale_factor_x),
        "drag_padding_y": int(40 * scale_factor_x),
        "drag_size": int(60 * scale_factor_x),
        "switch_width_huge": int(58 * scale_factor_x),
        "switch_height_huge": int(30 * scale_factor_x),
        "switch_radius_huge": int(15 * scale_factor_x),
        "switch_width_large": int(48 * scale_factor_x),
        "switch_height_large": int(24 * scale_factor_x),
        "switch_radius_large": int(12 * scale_factor_x),
        "switch_width_medium": int(38 * scale_factor_x),
        "switch_height_medium": int(19 * scale_factor_x),
        "switch_radius_medium": int(9 * scale_factor_x),
        "switch_width_small": int(28 * scale_factor_x),
        "switch_height_small": int(14 * scale_factor_x),
        "switch_radius_small": int(7 * scale_factor_x),
        "switch_width_tiny": int(18 * scale_factor_x),
        "switch_height_tiny": int(10 * scale_factor_x),
        "switch_radius_tiny": int(5 * scale_factor_x),
        "check_box_size": int(13 * scale_factor_x),
        "check_box_spacing": int(4 * scale_factor_x),
        "radio_size": int(14 * scale_factor_x),
        "radio_radius": int(14 * scale_factor_x / 2.0),
        "radio_spacing": int(4 * scale_factor_x),
        "slider_height": int(4 * scale_factor_x),
        "slider_radius": int(3 * scale_factor_x),
        "slider_handle_size": int(8 * scale_factor_x),
        "slider_handle_radius": int(8 * scale_factor_x / 1.5),
        "progress_circle_default_radius": int(120 * scale_factor_x),
        "progress_bar_size": int(12 * scale_factor_x),
        "progress_bar_radius": int(12 * scale_factor_x / 2.0),
        "toast_size": int(120 * scale_factor_x),
        "toast_icon_size": int(60 * scale_factor_x),
        "big_view_default_size": int(120 * scale_factor_x),
        "big_view_max_size": int(400 * scale_factor_x),
        "big_view_min_size": int(24 * scale_factor_x),
        "indicator_padding": int(4 * scale_factor_x),
        "indicator_size": int(8 * scale_factor_x),
        "scroll_bar_size": int(12 * scale_factor_x),
        "scroll_bar_margin": int(12 * scale_factor_x * 2) + 1,
        "scroll_bar_radius": int(12 * scale_factor_x / 2.0),
    }


class QssTemplate(string.Template):
    delimiter = "@"
    idpattern = r"[_a-z][_a-z0-9]*"


class MTheme(object):
    blue = "#1890ff"
    purple = "#722ed1"
    cyan = "#13c2c2"
    green = "#52c41a"
    magenta = "#eb2f96"
    pink = "#ef5b97"
    red = "#f5222d"
    orange = "#fa8c16"
    yellow = "#fadb14"
    volcano = "#fa541c"
    geekblue = "#2f54eb"
    lime = "#a0d911"
    gold = "#faad14"
    female_color = "#ef5b97"
    male_color = "#4ebbff"

    def __init__(self, theme="light", primary_color=None):
        super(MTheme, self).__init__()
        default_qss_file = utils.get_static_file("main.qss")
        with open(default_qss_file, "r") as f:
            self.default_qss = QssTemplate(f.read())
        self.primary_color, self.item_hover_bg = (None, None)
        (
            self.primary_1,
            self.primary_2,
            self.primary_3,
            self.primary_4,
            self.primary_5,
            self.primary_6,
            self.primary_7,
            self.primary_8,
            self.primary_9,
            self.primary_10,
        ) = (None,) * 10
        self.hyperlink_style = ""
        self._init_color()
        self.set_primary_color(primary_color or MTheme.blue)
        self.set_theme(theme)
        self._init_font()
        # self._init_size()
        self.unit = "px"
        self.font_unit = "pt"

        self.text_error_color = self.error_7
        self.text_color_inverse = "#fff"
        self.text_warning_color = self.warning_7

    def set_theme(self, theme):
        if theme == "light":
            self._light()
        else:
            self._dark()
        self._init_icon(theme)

    def set_primary_color(self, color):
        self.primary_color = color
        self.primary_1 = utils.generate_color(color, 1)
        self.primary_2 = utils.generate_color(color, 2)
        self.primary_3 = utils.generate_color(color, 3)
        self.primary_4 = utils.generate_color(color, 4)
        self.primary_5 = utils.generate_color(color, 5)
        self.primary_6 = utils.generate_color(color, 6)
        self.primary_7 = utils.generate_color(color, 7)
        self.primary_8 = utils.generate_color(color, 8)
        self.primary_9 = utils.generate_color(color, 9)
        self.primary_10 = utils.generate_color(color, 10)
        # item
        self.item_hover_bg = self.primary_1
        # rich text hyperlink style
        self.hyperlink_style = """
        <style>
         a {{
            text-decoration: none;
            color: {0};
        }}
        </style>""".format(
            self.primary_color
        )

    def _init_icon(self, theme):
        # icon
        pre_str = DEFAULT_STATIC_FOLDER.replace("\\", "/")
        suf_str = "" if theme == "light" else "_dark"
        url_prefix = "{pre}/{{}}{suf}.png".format(pre=pre_str, suf=suf_str)
        url_prefix_2 = "{pre}/{{}}.svg".format(pre=pre_str)
        self.icon_down = url_prefix.format("down_line")
        self.icon_up = url_prefix.format("up_line")
        self.icon_left = url_prefix.format("left_line")
        self.icon_right = url_prefix.format("right_line")
        self.icon_close = url_prefix.format("close_line")
        self.icon_calender = url_prefix.format("calendar_fill")
        self.icon_splitter = url_prefix.format("splitter")
        self.icon_float = url_prefix.format("float")
        self.icon_size_grip = url_prefix.format("size_grip")

        self.icon_check = url_prefix_2.format("check")
        self.icon_minus = url_prefix_2.format("minus")
        self.icon_circle = url_prefix_2.format("circle")
        self.icon_sphere = url_prefix_2.format("sphere")

    def _init_color(self):
        self.info_color = self.blue
        self.success_color = self.green
        self.processing_color = self.blue
        self.error_color = self.red
        self.warning_color = self.gold

        self.info_1 = utils.fade_color(self.info_color, "15%")
        self.info_2 = utils.generate_color(self.info_color, 2)
        self.info_3 = utils.fade_color(self.info_color, "35%")
        self.info_4 = utils.generate_color(self.info_color, 4)
        self.info_5 = utils.generate_color(self.info_color, 5)
        self.info_6 = utils.generate_color(self.info_color, 6)
        self.info_7 = utils.generate_color(self.info_color, 7)
        self.info_8 = utils.generate_color(self.info_color, 8)
        self.info_9 = utils.generate_color(self.info_color, 9)
        self.info_10 = utils.generate_color(self.info_color, 10)

        self.success_1 = utils.fade_color(self.success_color, "15%")
        self.success_2 = utils.generate_color(self.success_color, 2)
        self.success_3 = utils.fade_color(self.success_color, "35%")
        self.success_4 = utils.generate_color(self.success_color, 4)
        self.success_5 = utils.generate_color(self.success_color, 5)
        self.success_6 = utils.generate_color(self.success_color, 6)
        self.success_7 = utils.generate_color(self.success_color, 7)
        self.success_8 = utils.generate_color(self.success_color, 8)
        self.success_9 = utils.generate_color(self.success_color, 9)
        self.success_10 = utils.generate_color(self.success_color, 10)

        self.warning_1 = utils.fade_color(self.warning_color, "15%")
        self.warning_2 = utils.generate_color(self.warning_color, 2)
        self.warning_3 = utils.fade_color(self.warning_color, "35%")
        self.warning_4 = utils.generate_color(self.warning_color, 4)
        self.warning_5 = utils.generate_color(self.warning_color, 5)
        self.warning_6 = utils.generate_color(self.warning_color, 6)
        self.warning_7 = utils.generate_color(self.warning_color, 7)
        self.warning_8 = utils.generate_color(self.warning_color, 8)
        self.warning_9 = utils.generate_color(self.warning_color, 9)
        self.warning_10 = utils.generate_color(self.warning_color, 10)

        self.error_1 = utils.fade_color(self.error_color, "15%")
        self.error_2 = utils.generate_color(self.error_color, 2)
        self.error_3 = utils.fade_color(self.error_color, "35%")
        self.error_4 = utils.generate_color(self.error_color, 4)
        self.error_5 = utils.generate_color(self.error_color, 5)
        self.error_6 = utils.generate_color(self.error_color, 6)
        self.error_7 = utils.generate_color(self.error_color, 7)
        self.error_8 = utils.generate_color(self.error_color, 8)
        self.error_9 = utils.generate_color(self.error_color, 9)
        self.error_10 = utils.generate_color(self.error_color, 10)

    def _init_font(self):
        # font
        self.font_family = (
            'BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",'
            '"Helvetica Neue",Helvetica,Arial,sans-serif'
        )
        self.font_size_base = 9
        self.font_size_large = self.font_size_base + 2
        self.font_size_small = self.font_size_base - 2
        self.h1_size = int(self.font_size_base * 2.71)
        self.h2_size = int(self.font_size_base * 2.12)
        self.h3_size = int(self.font_size_base * 1.71)
        self.h4_size = int(self.font_size_base * 1.41)

    def __getattribute__(self, item):
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            return get_theme_size().get(item, 0)

    def _dark(self):
        self.title_color = "#ffffff"
        self.primary_text_color = "#d9d9d9"
        self.secondary_text_color = "#a6a6a6"
        self.disable_color = "#737373"
        self.border_color = "#1e1e1e"
        self.divider_color = "#262626"
        self.header_color = "#0a0a0a"
        self.icon_color = "#a6a6a6"

        self.background_color = "#323232"
        self.background_selected_color = "#292929"
        self.background_in_color = "#3a3a3a"
        self.background_out_color = "#494949"
        self.mask_color = utils.fade_color(self.background_color, "90%")
        self.toast_color = "#555555"

    def _light(self):
        self.title_color = "#262626"
        self.primary_text_color = "#595959"
        self.secondary_text_color = "#8c8c8c"
        self.disable_color = "#e5e5e5"
        self.border_color = "#d9d9d9"
        self.divider_color = "#e8e8e8"
        self.header_color = "#fafafa"
        self.icon_color = "#8c8c8c"

        self.background_color = "#f8f8f9"
        self.background_selected_color = "#bfbfbf"
        self.background_in_color = "#ffffff"
        self.background_out_color = "#eeeeee"
        self.mask_color = utils.fade_color(self.background_color, "90%")
        self.toast_color = "#333333"

    def apply(self, widget):
        size_dict = get_theme_size()
        size_dict.update(vars(self))
        widget.setStyleSheet(self.default_qss.substitute(size_dict))

    def deco(self, cls):
        original_init__ = cls.__init__

        def my__init__(instance, *args, **kwargs):
            original_init__(instance, *args, **kwargs)
            size_dict = get_theme_size()
            size_dict.update(vars(self))
            instance.setStyleSheet(self.default_qss.substitute(size_dict))

        def polish(instance):
            instance.style().polish(instance)

        setattr(cls, "__init__", my__init__)
        setattr(cls, "polish", polish)
        return cls
