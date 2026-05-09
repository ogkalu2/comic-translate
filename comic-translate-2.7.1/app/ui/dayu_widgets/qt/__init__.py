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

# Import built-in modules
import contextlib
import signal
import sys

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets
from PySide6.QtGui import QGuiApplication
from PySide6.QtSvg import QSvgRenderer
import six


class MCacheDict(object):
    def __init__(self, cls):
        super(MCacheDict, self).__init__()
        self.cls = cls
        self._cache_pix_dict = {}
        self._renderer = None

    def _get_renderer(self):
        if self._renderer is None:
            self._renderer = QSvgRenderer()
        return self._renderer

    def _render_svg(self, svg_path, replace_color=None):
        # Import local modules
        from .. import dayu_theme

        replace_color = replace_color or dayu_theme.icon_color
        if (self.cls is QtGui.QIcon) and (replace_color is None):
            return QtGui.QIcon(svg_path)
        with open(svg_path, "r") as f:
            data_content = f.read()
            if replace_color is not None:
                data_content = data_content.replace("#555555", replace_color)
            renderer = self._get_renderer()
            renderer.load(QtCore.QByteArray(six.b(data_content)))
            pix = QtGui.QPixmap(128, 128)
            pix.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pix)
            renderer.render(painter)
            painter.end()
            if self.cls is QtGui.QPixmap:
                return pix
            else:
                return self.cls(pix)

    def __call__(self, path, color=None):
        # Import local modules
        from .. import utils

        full_path = utils.get_static_file(path)
        if full_path is None:
            return self.cls()
        key = "{}{}".format(full_path.lower(), color or "")
        pix_map = self._cache_pix_dict.get(key, None)
        if pix_map is None:
            if full_path.endswith("svg"):
                pix_map = self._render_svg(full_path, color)
            else:
                pix_map = self.cls(full_path)
            self._cache_pix_dict.update({key: pix_map})
        return pix_map


def get_scale_factor():
    if not QtWidgets.QApplication.instance():
        app = QtWidgets.QApplication([])
    standard_dpi = 96.0
    scale_factor_x = QGuiApplication.primaryScreen().logicalDotsPerInchX() / standard_dpi
    scale_factor_y = QGuiApplication.primaryScreen().logicalDotsPerInchX() / standard_dpi
    return scale_factor_x, scale_factor_y


@contextlib.contextmanager
def application(*args):
    app = QtWidgets.QApplication.instance()

    if not app:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        app = QtWidgets.QApplication(sys.argv)
        yield app
        app.exec_()
    else:
        yield app


MPixmap = MCacheDict(QtGui.QPixmap)
MIcon = MCacheDict(QtGui.QIcon)
