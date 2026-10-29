# -*- coding: utf-8 -*-
"""
windrose_plugin.py

QGIS 插件主类：菜单/工具栏注册、地图选点、对话框管理。
"""

from qgis.PyQt.QtCore import QCoreApplication, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.gui import QgsMapToolEmitPoint
from qgis.core import (
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject,
)
import os.path

from .windrose_dialog import WindRoseDialog
from . import i18n


class WindRosePlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&Wind Rose')
        self.toolbar = self.iface.addToolBar(u'Wind Rose')
        self.toolbar.setObjectName(u'WindRoseToolbar')

        self.dialog = None
        self.point_tool = None

        self._init_language()

    def tr(self, message):
        return QCoreApplication.translate('WindRosePlugin', message)

    def _init_language(self):
        settings = QSettings()
        lang = settings.value("WindRose/Language", "zh")
        i18n.set_language(lang)

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                   add_to_menu=True, add_to_toolbar=True,
                   status_tip=None, whats_this=None, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icons', 'windrose.svg')
        self.add_action(
            icon_path,
            text=self.tr(u'Wind Rose'),
            callback=self.run,
            status_tip=self.tr(u'Generate wind rose diagram'),
            parent=self.iface.mainWindow())

        # 语言切换菜单
        self.language_menu = QMenu(self.tr(u'Language'))
        self.action_zh = QAction(self.tr(u'中文'), self.language_menu)
        self.action_en = QAction(self.tr(u'English'), self.language_menu)
        self.action_zh.triggered.connect(lambda: self._switch_language('zh'))
        self.action_en.triggered.connect(lambda: self._switch_language('en'))
        self.language_menu.addAction(self.action_zh)
        self.language_menu.addAction(self.action_en)

        self.language_action = QAction(
            self.tr(u'Language'), self.iface.mainWindow())
        self.language_action.setMenu(self.language_menu)
        self.iface.addPluginToMenu(self.menu, self.language_action)

    def unload(self):
        if self.dialog:
            try:
                self.dialog.close()
                self.dialog.deleteLater()
            except Exception:
                pass
            self.dialog = None

        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&Wind Rose'), action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def _switch_language(self, lang):
        if i18n.get_language() == lang:
            return
        i18n.set_language(lang)
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog._refresh_ui_texts()

    def run(self):
        if self.dialog is None:
            self.dialog = WindRoseDialog(self.iface)
            self.dialog.pick_point_clicked.connect(self._activate_point_tool)
        else:
            self.dialog._refresh_ui_texts()
        self.dialog.show()

    def _activate_point_tool(self):
        canvas = self.iface.mapCanvas()
        if self.point_tool is None:
            self.point_tool = QgsMapToolEmitPoint(canvas)
            self.point_tool.canvasClicked.connect(self._on_point_clicked)
        canvas.setMapTool(self.point_tool)
        self.iface.messageBar().pushInfo(
            i18n.tr("msg_pick_point"), i18n.tr("msg_pick_point"))

    def _on_point_clicked(self, point, button):
        canvas = self.iface.mapCanvas()
        transform = QgsCoordinateTransform(
            canvas.mapSettings().destinationCrs(),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance())
        wgs84 = transform.transform(point)
        self.dialog.set_coordinates(wgs84.x(), wgs84.y())
        canvas.unsetMapTool(self.point_tool)
        self.iface.messageBar().clearWidgets()
