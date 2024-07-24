# -*- coding: utf-8 -*-
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import os
import sys


DEFAULT_STATIC_FOLDER = os.path.join(sys.modules[__name__].__path__[0], "static")
CUSTOM_STATIC_FOLDERS = []
# Import local modules
from .theme import MTheme


dayu_theme = MTheme("dark", primary_color=MTheme.orange)
# dayu_theme.default_size = dayu_theme.small
# dayu_theme = MTheme('light')

# Import local modules
from .alert import MAlert
from .avatar import MAvatar
from .badge import MBadge
from .breadcrumb import MBreadcrumb
from .browser import MClickBrowserFilePushButton
from .browser import MClickBrowserFileToolButton
from .browser import MClickBrowserFolderPushButton
from .browser import MClickBrowserFolderToolButton
from .browser import MDragFileButton
from .browser import MDragFolderButton
from .button_group import MCheckBoxGroup
from .button_group import MPushButtonGroup
from .button_group import MRadioButtonGroup
from .button_group import MToolButtonGroup
from .card import MCard
from .card import MMeta
from .carousel import MCarousel
from .check_box import MCheckBox
from .collapse import MCollapse
from .combo_box import MComboBox
from .divider import MDivider
from .field_mixin import MFieldMixin
from .flow_layout import MFlowLayout
from .item_model import MSortFilterModel
from .item_model import MTableModel
from .item_view import MBigView
from .item_view import MListView
from .item_view import MTableView
from .item_view import MTreeView
from .item_view_full_set import MItemViewFullSet
from .item_view_set import MItemViewSet
from .label import MLabel
from .line_edit import MLineEdit
from .line_tab_widget import MLineTabWidget
from .loading import MLoading
from .loading import MLoadingWrapper
from .menu import MMenu
from .menu_tab_widget import MMenuTabWidget
from .message import MMessage
from .page import MPage
from .progress_bar import MProgressBar
from .progress_circle import MProgressCircle
from .push_button import MPushButton
from .radio_button import MRadioButton
from .sequence_file import MSequenceFile
from .slider import MSlider
from .spin_box import MDateEdit
from .spin_box import MDateTimeEdit
from .spin_box import MDoubleSpinBox
from .spin_box import MSpinBox
from .spin_box import MTimeEdit
from .switch import MSwitch
from .tab_widget import MTabWidget
from .text_edit import MTextEdit
from .toast import MToast
from .tool_button import MToolButton


__all__ = [
    "MAlert",
    "MAvatar",
    "MBadge",
    "MBreadcrumb",
    "MClickBrowserFilePushButton",
    "MClickBrowserFileToolButton",
    "MClickBrowserFolderPushButton",
    "MClickBrowserFolderToolButton",
    "MDragFileButton",
    "MDragFolderButton",
    "MCheckBoxGroup",
    "MPushButtonGroup",
    "MRadioButtonGroup",
    "MToolButtonGroup",
    "MCard",
    "MMeta",
    "MCarousel",
    "MCheckBox",
    "MCollapse",
    "MComboBox",
    "MDivider",
    "MFieldMixin",
    "MFlowLayout",
    "MSortFilterModel",
    "MTableModel",
    "MBigView",
    "MListView",
    "MTableView",
    "MTreeView",
    "MItemViewFullSet",
    "MItemViewSet",
    "MLabel",
    "MLineEdit",
    "MLineTabWidget",
    "MLoading",
    "MLoadingWrapper",
    "MMenu",
    "MMenuTabWidget",
    "MMessage",
    "MPage",
    "MProgressBar",
    "MProgressCircle",
    "MPushButton",
    "MRadioButton",
    "MSequenceFile",
    "MSlider",
    "MDateEdit",
    "MDateTimeEdit",
    "MDoubleSpinBox",
    "MSpinBox",
    "MTimeEdit",
    "MSwitch",
    "MTabWidget",
    "MTextEdit",
    "MToast",
    "MToolButton",
]
