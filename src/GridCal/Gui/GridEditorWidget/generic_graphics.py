# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *

# Declare colors
ACTIVE = {'style': Qt.SolidLine, 'color': Qt.black}
DEACTIVATED = {'style': Qt.DashLine, 'color': Qt.gray}
EMERGENCY = {'style': Qt.SolidLine, 'color': Qt.yellow}
OTHER = ACTIVE
FONT_SCALE = 1.9


class LineUpdateMixin(object):

    def __init__(self, parent):
        super(LineUpdateMixin, self).__init__(parent)
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.parentItem().update_line(value)
        return super(LineUpdateMixin, self).itemChange(change, value)


class Polygon(LineUpdateMixin, QGraphicsPolygonItem):
    pass


class Square(LineUpdateMixin, QGraphicsRectItem):
    pass


class Circle(LineUpdateMixin, QGraphicsEllipseItem):
    pass


class Line(LineUpdateMixin, QGraphicsLineItem):
    pass


class ParameterDialog(QDialog):

    def __init__(self, parent=None):
        super(ParameterDialog, self).__init__(parent)
        self.button = QPushButton('Ok', self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.button)
        self.button.clicked.connect(self.OK)

    def OK(self):
        self.close()
