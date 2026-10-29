# -*- coding: utf-8 -*-
"""
windrose_dialog.py

主对话框：用户交互、数据协调、预览渲染、生成控制。

设计原则：
- 预览和生成共享同一套图层创建函数（windrose_utils.build_preview_layers）
- 异步渲染预览，不阻塞 UI
- 通过 layer_type 自定义属性匹配样式（不依赖图层名）
- 所有资源在 closeEvent / 回调中统一清理
"""

import os
import logging
import tempfile
from datetime import datetime

logger = logging.getLogger("WindRose")

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QThread, QSize, QTimer
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog, QMessageBox, QFileDialog, QApplication,
)
from qgis.core import (
    QgsProject, QgsMapSettings, QgsMapRendererSequentialJob,
    QgsVectorLayer,
)

from .windrose_worker import WindRoseWorker
from .windrose_utils import (
    build_preview_layers, add_layers_to_project,
)
from .style_manager import StyleManager
from .export_helper import ExportHelper
from . import i18n

# PyQt5/6 强类型枚举兼容（符合 QGIS 4 / Qt6 Scoped Enum 规范）
_TRANSPARENT = Qt.GlobalColor.transparent
_KEEP_ASPECT = Qt.AspectRatioMode.KeepAspectRatio
_SMOOTH = Qt.TransformationMode.SmoothTransformation
_ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
_WAIT_CURSOR = Qt.CursorShape.WaitCursor
_MSG_INFO = QMessageBox.Icon.Information
_MSG_NO_BTN = QMessageBox.StandardButton.NoButton

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), 'windrose_dialog.ui'))


class WindRoseDialog(QDialog, FORM_CLASS):

    pick_point_clicked = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.resize(600, 500)
        self.setMinimumSize(500, 400)
        self.setMaximumSize(800, 600)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.project = QgsProject.instance()

        self.current_lon = None
        self.current_lat = None

        # 缓存
        self._cached_params = None
        self._cached_wind_dirs = None
        self._cached_wind_speeds = None
        self._cached_labels = None
        self._cached_angles = None

        # 数据获取线程
        self._worker = None
        self._thread = None
        # 当前任务的参数（回调从实例变量取，避免用 lambda 跨线程传参）
        self._preview_params = None
        self._gen_params = None

        # 异步预览渲染
        self._is_rendering = False
        self._preview_job = None
        self._preview_layers = []

        # 防止初始化期间信号触发
        self._initializing = True

        # 信号连接
        self.btn_map_point.clicked.connect(self._on_map_point)
        self.btn_manual.clicked.connect(self._on_manual_input)
        self.btn_generate.clicked.connect(self.generate_rose)
        self.btn_browse_svg.clicked.connect(self._browse_svg)
        self.btn_browse_local.clicked.connect(self._browse_local)
        self.btn_language.clicked.connect(self._switch_language)
        self.btn_preview.clicked.connect(self.preview_rose)
        self.btn_help.clicked.connect(self._toggle_help_panel)
        self.cmb_export_format.currentIndexChanged.connect(
            self._on_export_format_changed)

        self._refresh_ui_texts()
        self._init_help_panel()

        # 默认值
        current_year = datetime.now().year
        self.spin_year.setRange(1940, current_year - 1)
        self.spin_year.setValue(current_year - 1)
        self.cmb_height.setCurrentIndex(0)
        self.cb_show_points.setChecked(False)
        self.line_svg_path.setText(
            os.path.join(tempfile.gettempdir(), 'windrose.svg'))
        self.line_local_path.setText(
            os.path.join(tempfile.gettempdir(), 'windrose.gpkg'))

        self.status_label.hide()
        self._initializing = False

    # ─── 对话框关闭 ─────────────────────────────────────────────────

    def closeEvent(self, event):
        """关闭时安全清理所有后台资源。"""
        self._cancel_preview_render()
        self._cancel_worker()
        if event:
            event.accept()

    def _cancel_preview_render(self):
        """取消正在进行的预览渲染。"""
        if self._preview_job:
            try:
                self._preview_job.cancel()
            except Exception as e:
                logger.debug("Cancel preview job ignored: %s", e)
            try:
                self._preview_job.finished.disconnect()
            except Exception as e:
                logger.debug("Disconnect preview job ignored: %s", e)
        self._preview_job = None
        self._preview_layers = []
        self._is_rendering = False

    def _cancel_worker(self):
        """取消正在进行的数据获取线程。"""
        if self._worker:
            try:
                self._worker.cancel()
            except Exception as e:
                logger.debug("Cancel worker ignored: %s", e)
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._worker = None
        self._thread = None

    def _clear_thread_refs(self):
        """
        在 QThread 完全退出后（finished 信号）安全清理引用。
        让 Qt 通过 deleteLater 管理底层 C++ 对象的生命周期，
        避免在 worker 仍持有引用时提前释放造成段错误。
        """
        self._worker = None
        self._thread = None

    # ─── 帮助面板 ─────────────────────────────────────────────────

    def _init_help_panel(self):
        """初始化帮助面板内容。"""
        # 帮助面板初始隐藏
        self.helpPanel.setVisible(False)
        self._help_visible = False

        # 更新帮助文本
        self._update_help_texts()

    def _toggle_help_panel(self):
        """切换帮助面板显示/隐藏。"""
        self._help_visible = not self._help_visible
        self.helpPanel.setVisible(self._help_visible)

        # 调整窗口大小
        if self._help_visible:
            # 展开：增加宽度
            new_width = min(self.width() + 220, 900)
            self.resize(new_width, self.height())
        else:
            # 收起：减少宽度
            new_width = max(self.width() - 220, 500)
            self.resize(new_width, self.height())

    def _update_help_texts(self):
        """更新帮助面板文本（语言切换时调用）。"""
        # 设置工具箱项目标题
        self.helpToolBox.setItemText(0, i18n.tr("help_quick_start"))
        self.helpToolBox.setItemText(1, i18n.tr("help_features"))
        self.helpToolBox.setItemText(2, i18n.tr("help_faq"))

        # 设置帮助内容（使用 HTML 格式）
        self.textBrowserQuickStart.setHtml(i18n.tr("help_quick_start_text"))
        self.textBrowserFeatures.setHtml(i18n.tr("help_features_text"))
        self.textBrowserFAQ.setHtml(i18n.tr("help_faq_text"))

    # ─── UI 文本刷新（语言切换） ─────────────────────────────────────

    def _refresh_ui_texts(self):
        self.setWindowTitle(i18n.tr("dialog_title"))
        self.grp_location.setTitle("📍 " + i18n.tr("grp_input"))
        self.grp_params.setTitle("📊 " + i18n.tr("groupBox"))
        self.grp_style.setTitle("🎨 " + i18n.tr("groupBox_2"))
        self.grp_preview.setTitle("👁 " + i18n.tr("grp_preview"))
        self.grp_output.setTitle("📤 " + i18n.tr("grp_output"))

        self.label_lon.setText(i18n.tr("label_lon"))
        self.label_lat.setText(i18n.tr("label_lat"))
        self.label_year.setText(i18n.tr("label_year"))
        self.label_month.setText(i18n.tr("label_month"))
        self.label_height.setText(i18n.tr("label_height"))
        self.label_style.setText(i18n.tr("label_style"))
        self.label_graph_style.setText(i18n.tr("label_graph_style"))

        self.btn_map_point.setText(i18n.tr("btn_map_point"))
        self.btn_manual.setText(i18n.tr("btn_manual"))
        self.btn_browse_svg.setText(i18n.tr("btn_browse_svg"))
        self.btn_generate.setText(i18n.tr("btn_generate"))
        self.btn_cancel.setText(i18n.tr("btn_cancel"))
        self.btn_preview.setText(i18n.tr("btn_preview"))

        lang = i18n.get_language()
        self.btn_language.setText("English" if lang == 'zh' else "中文")

        self.cb_show_points.setText(i18n.tr("cb_show_points"))
        self.cb_add_to_project.setText(i18n.tr("cb_add_to_project"))
        self.cb_export_svg.setText(i18n.tr("cb_export_svg"))
        self.cb_export_local.setText(i18n.tr("cb_export_local"))

        self.btn_map_point.setToolTip(i18n.tr("tooltip_map_point"))
        self.btn_manual.setToolTip(i18n.tr("tooltip_manual"))
        self.line_svg_path.setPlaceholderText(i18n.tr("label_svg_path"))
        self.line_local_path.setPlaceholderText(i18n.tr("label_local_path"))
        self.label_project_hint.setText(i18n.tr("label_project_hint"))
        self.label_preview.setText(i18n.tr("label_preview_hint"))

        # 保存当前选中值
        cur_style = self._style_key()
        cur_graph = self._graph_style_key()
        cur_month = self.cmb_month.currentText()

        self._populate_combos()

        # 恢复选中
        self._set_style_key(cur_style)
        self._set_graph_style_key(cur_graph)
        idx = self.cmb_month.findText(cur_month)
        if idx >= 0:
            self.cmb_month.setCurrentIndex(idx)

        # 更新帮助面板
        self._update_help_texts()

    def _populate_combos(self):
        self.cmb_style.clear()
        for name in i18n.get_style_names():
            self.cmb_style.addItem(name)
        self.cmb_graph_style.clear()
        for name in i18n.get_graph_style_names():
            self.cmb_graph_style.addItem(name)
        self.cmb_month.clear()
        for name in i18n.get_month_names():
            self.cmb_month.addItem(name)

    # ─── 样式/图形选择 ──────────────────────────────────────────────

    def _style_key(self):
        return i18n.get_style_key(self.cmb_style.currentText())

    def _set_style_key(self, key):
        for i in range(self.cmb_style.count()):
            if i18n.get_style_key(self.cmb_style.itemText(i)) == key:
                self.cmb_style.setCurrentIndex(i)
                break

    def _graph_style_key(self):
        return i18n.get_graph_style_key(self.cmb_graph_style.currentText())

    def _set_graph_style_key(self, key):
        for i in range(self.cmb_graph_style.count()):
            if i18n.get_graph_style_key(self.cmb_graph_style.itemText(i)) == key:
                self.cmb_graph_style.setCurrentIndex(i)
                break

    # ─── 语言切换 ───────────────────────────────────────────────────

    def _switch_language(self):
        cur = i18n.get_language()
        i18n.set_language('en' if cur == 'zh' else 'zh')
        self._refresh_ui_texts()

    # ─── 坐标输入 ───────────────────────────────────────────────────

    def _on_map_point(self):
        self.pick_point_clicked.emit()

    def _on_manual_input(self):
        from qgis.PyQt.QtWidgets import QInputDialog
        lon, ok1 = QInputDialog.getDouble(
            self, i18n.tr("btn_manual"), i18n.tr("label_lon"), 0, -180, 180, 6)
        if not ok1:
            return
        lat, ok2 = QInputDialog.getDouble(
            self, i18n.tr("btn_manual"), i18n.tr("label_lat"), 0, -90, 90, 6)
        if not ok2:
            return
        self.set_coordinates(lon, lat)

    def set_coordinates(self, lon, lat):
        self.current_lon = lon
        self.current_lat = lat
        self._update_coord_display()
        self.raise_()
        self.activateWindow()

    def _update_coord_display(self):
        if self.current_lon is not None and self.current_lat is not None:
            self.line_lon.setText(f'{self.current_lon:.6f}')
            self.line_lat.setText(f'{self.current_lat:.6f}')
        else:
            self.line_lon.clear()
            self.line_lat.clear()

    # ─── 文件浏览 ───────────────────────────────────────────────────

    def _browse_svg(self):
        path, _ = QFileDialog.getSaveFileName(
            self, i18n.tr("btn_export_svg"),
            self.line_svg_path.text(), 'SVG files (*.svg)')
        if path:
            self.line_svg_path.setText(path)

    def _browse_local(self):
        fmt = self.cmb_export_format.currentText()
        if fmt in ("SHP", "GDB"):
            # SHP 和 GDB 是目录格式
            path = QFileDialog.getExistingDirectory(
                self, i18n.tr("btn_browse_local"),
                self.line_local_path.text())
            if path:
                self.line_local_path.setText(path)
        else:
            flt = ("GeoPackage (*.gpkg)" if fmt == "GPKG"
                   else "KML (*.kml)")
            path, _ = QFileDialog.getSaveFileName(
                self, i18n.tr("btn_browse_local"),
                self.line_local_path.text(), flt)
            if path:
                self.line_local_path.setText(path)

    def _on_export_format_changed(self):
        """切换导出格式时，自动更新路径扩展名。"""
        fmt = self.cmb_export_format.currentText()
        current_path = self.line_local_path.text()

        if not current_path:
            return

        # 替换扩展名
        base = os.path.splitext(current_path)[0]
        ext_map = {"GPKG": ".gpkg", "KML": ".kml", "SHP": "", "GDB": ".gdb"}
        new_ext = ext_map.get(fmt, ".gpkg")

        if fmt == "SHP":
            # SHP 是目录，移除扩展名
            new_path = base
        elif fmt == "GDB":
            # GDB 是目录，需要 .gdb 后缀
            if not base.endswith('.gdb'):
                new_path = base + '.gdb'
            else:
                new_path = base
        else:
            new_path = base + new_ext

        self.line_local_path.setText(new_path)

    # ─── 参数获取 ───────────────────────────────────────────────────

    def _get_selected_month(self):
        text = self.cmb_month.currentText()
        if text == i18n.tr("month_full_year"):
            return None
        names = i18n.get_month_names()
        try:
            return names.index(text)
        except ValueError:
            return None

    def _get_selected_height(self):
        text = self.cmb_height.currentText()
        if not text:
            return 10
        try:
            return int(text.replace('m', ''))
        except ValueError:
            return 10

    def _current_params(self):
        if self.current_lon is None or self.current_lat is None:
            return None
        return {
            'lon': self.current_lon,
            'lat': self.current_lat,
            'year': self.spin_year.value(),
            'month': self._get_selected_month(),
            'height': self._get_selected_height(),
        }

    # ─── 缓存 ───────────────────────────────────────────────────────

    def _is_cached(self, params):
        return (params is not None and
                self._cached_params is not None and
                self._cached_params == params and
                self._cached_wind_dirs is not None)

    def _update_cache(self, params, dirs, speeds, labels, angles):
        self._cached_params = params.copy() if params else None
        self._cached_wind_dirs = dirs
        self._cached_wind_speeds = speeds
        self._cached_labels = labels
        self._cached_angles = angles

    def _use_cached(self):
        if self._cached_wind_dirs is not None:
            return (self._cached_wind_dirs, self._cached_wind_speeds,
                    self._cached_labels, self._cached_angles)
        return None

    # ─── 预览流程 ───────────────────────────────────────────────────

    def preview_rose(self):
        if self._is_rendering:
            return

        params = self._current_params()
        if params is None:
            QMessageBox.warning(self, i18n.tr("dialog_title"),
                                i18n.tr("msg_no_point"))
            return

        if self._is_cached(params):
            data = self._use_cached()
            if data:
                self._start_preview_render(*data)
                return

        # 检查是否有正在运行的数据线程
        if self._thread and self._thread.isRunning():
            return

        self.btn_preview.setEnabled(False)
        self.btn_preview.setText(i18n.tr("btn_preview_loading"))

        # 参数存到实例变量，回调通过 _on_data_ready 取用（避免 lambda 跨线程传参）
        self._preview_params = params
        self._worker = WindRoseWorker(
            params['lon'], params['lat'],
            params['year'], params['month'], params['height'])
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        # bound method：PyQt 跨线程自动用 QueuedConnection，回调回到主线程执行
        self._worker.finished.connect(self._on_data_ready)
        self._worker.error.connect(self._on_data_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        # 生命周期托管：线程完全退出后再清理引用，避免段错误
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread_refs)

        self._thread.start()

    def _on_data_ready(self, dirs, speeds, labels, angles):
        """worker.finished 槽（主线程执行）。params 从实例变量取。"""
        params = self._preview_params
        self._update_cache(params, dirs, speeds, labels, angles)
        # 不在此处清理 worker/thread 引用——交给 _thread.finished 信号统一处理
        self._start_preview_render(dirs, speeds, labels, angles)

    def _on_data_error(self, msg):
        self.btn_preview.setEnabled(True)
        self.btn_preview.setText(i18n.tr("btn_preview"))
        QTimer.singleShot(100, lambda: self._show_warning(msg))

    def _start_preview_render(self, wind_dirs, wind_speeds, labels, angles):
        """创建图层并启动异步渲染（使用 SequentialJob，无需 QPainter）。"""
        if self._is_rendering:
            return
        self._is_rendering = True
        self.btn_preview.setEnabled(False)
        self.btn_preview.setText(i18n.tr("btn_preview_loading"))

        try:
            graph_key = self._graph_style_key()
            show_pts = self.cb_show_points.isChecked()
            style_key = self._style_key()

            layers, _, _ = build_preview_layers(
                self.current_lon, self.current_lat,
                wind_dirs, wind_speeds, graph_key, show_pts)

            StyleManager.apply_style_to_layers(layers, style_key, 1.0)

            if not layers:
                self._finish_render()
                return

            # 计算 extent
            extent = layers[0].extent()
            for lyr in layers[1:]:
                extent.combineExtentWith(lyr.extent())
            if extent.isEmpty() or extent.isNull():
                self._finish_render()
                return

            margin_x = extent.width() * 0.15
            margin_y = extent.height() * 0.15
            extent.grow(margin_x)
            extent.grow(margin_y)

            # 输出尺寸
            frame_sz = self.preview_frame.size()
            w = max(min(frame_sz.width() - 4, 400), 150)
            h = max(min(frame_sz.height() - 4, 200), 100)

            settings = QgsMapSettings()
            settings.setLayers(layers)
            settings.setExtent(extent)
            settings.setOutputSize(QSize(w, h))
            settings.setBackgroundColor(_TRANSPARENT)

            # 使用 SequentialJob：QGIS 内部管理 QImage，无需 QPainter
            job = QgsMapRendererSequentialJob(settings)
            self._preview_job = job
            self._preview_layers = layers
            job.finished.connect(self._on_render_finished)
            job.start()

        except Exception as e:
            self._finish_render()
            self.label_preview.setText(
                i18n.tr("preview_error", error=str(e)))

    def _on_render_finished(self):
        """异步渲染完成回调。"""
        try:
            if self._preview_job:
                img = self._preview_job.renderedImage()
                if img and not img.isNull():
                    pixmap = QPixmap.fromImage(img)
                    frame_sz = self.preview_frame.size()
                    tw = frame_sz.width() - 4
                    th = frame_sz.height() - 4
                    scaled = pixmap.scaled(
                        tw, th, _KEEP_ASPECT, _SMOOTH)
                    self.label_preview.setFixedSize(tw, th)
                    self.label_preview.setPixmap(scaled)
                    self.label_preview.setAlignment(_ALIGN_CENTER)
        except Exception as e:
            self.label_preview.setText(
                i18n.tr("preview_error", error=str(e)))
        finally:
            self._preview_job = None
            self._preview_layers = []
            self._finish_render()

    def _finish_render(self):
        self._is_rendering = False
        self.btn_preview.setEnabled(True)
        self.btn_preview.setText(i18n.tr("btn_preview"))

    # ─── 生成流程 ───────────────────────────────────────────────────

    def generate_rose(self):
        if self._thread and self._thread.isRunning():
            QMessageBox.warning(self, i18n.tr("dialog_title"),
                                i18n.tr("msg_wait_previous"))
            return

        params = self._current_params()
        if params is None:
            QMessageBox.warning(self, i18n.tr("dialog_title"),
                                i18n.tr("msg_no_point"))
            return

        # 保存生成参数
        self._gen_style_key = self._style_key()
        self._gen_graph_key = self._graph_style_key()
        self._gen_show_points = self.cb_show_points.isChecked()
        self._gen_add_to_project = self.cb_add_to_project.isChecked()
        self._gen_export_svg = self.cb_export_svg.isChecked()
        self._gen_svg_path = (self.line_svg_path.text()
                              if self._gen_export_svg else None)
        self._gen_export_local = self.cb_export_local.isChecked()
        self._gen_local_path = (self.line_local_path.text()
                                if self._gen_export_local else None)
        self._gen_export_format = (self.cmb_export_format.currentText()
                                   if self._gen_export_local else None)

        month_text = self.cmb_month.currentText()
        month_str = (i18n.tr("month_full_year")
                     if month_text == i18n.tr("month_full_year")
                     else month_text)
        lon_str = f"{params['lon']:.4f}".replace('.', '_')
        lat_str = f"{params['lat']:.4f}".replace('.', '_')
        self._gen_group_name = (
            f"{i18n.tr('group_prefix')}-"
            f"{params['year']}-{month_str}-{lon_str}_{lat_str}")

        if self._is_cached(params):
            data = self._use_cached()
            if data:
                # 缓存命中：参数存到实例变量，按新签名调用（无 params 参数）
                self._gen_params = params
                self._on_generate_data_ready(*data)
                return

        self.btn_generate.setEnabled(False)
        QApplication.setOverrideCursor(_WAIT_CURSOR)
        self.status_label.setText(i18n.tr("status_fetching_data"))
        self.status_label.show()

        # 参数存到实例变量，回调通过 _on_generate_data_ready 取用（避免 lambda 跨线程传参）
        self._gen_params = params
        self._worker = WindRoseWorker(
            params['lon'], params['lat'],
            params['year'], params['month'], params['height'])
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        # bound method：PyQt 跨线程自动用 QueuedConnection，回调回到主线程执行
        self._worker.finished.connect(self._on_generate_data_ready)
        self._worker.error.connect(self._on_generate_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        # 生命周期托管：线程完全退出后再清理引用，避免段错误
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread_refs)
        self._thread.start()

    def _on_generate_data_ready(self, dirs, speeds, labels, angles):
        """worker.finished 槽（主线程执行）。params 从实例变量取。"""
        params = self._gen_params
        self._update_cache(params, dirs, speeds, labels, angles)

        QApplication.restoreOverrideCursor()
        self.btn_generate.setEnabled(True)
        self.status_label.hide()

        try:
            # 始终创建内存图层（用于预览 + 作为样式克隆源）
            layers, _, _ = build_preview_layers(
                params['lon'], params['lat'],
                dirs, speeds, self._gen_graph_key, self._gen_show_points)
            StyleManager.apply_style_to_layers(layers, self._gen_style_key, 1.0)

            # 1. 导出本地文件（独立于"添加到项目"选项）
            if self._gen_export_local and self._gen_local_path:
                ExportHelper().export_layers_to_local(
                    layers, self._gen_local_path, self._gen_export_format)

            # 2. 导出 SVG（独立）
            if self._gen_export_svg and layers and self._gen_svg_path:
                ExportHelper().export_layers_as_svg(layers, self._gen_svg_path)

            # 3. 添加到项目（根据选项）
            if self._gen_add_to_project:
                if self._gen_export_local and self._gen_local_path:
                    # 从文件加载
                    file_layers = self._load_layers_from_file(
                        self._gen_local_path, self._gen_export_format, layers)
                    add_layers_to_project(file_layers, self._gen_group_name)
                else:
                    # 内存图层直接添加
                    add_layers_to_project(layers, self._gen_group_name)

            # 4. 更新预览（始终用内存图层）
            if not self._is_rendering:
                self._start_preview_render(dirs, speeds, labels, angles)

            self._show_auto_close(
                i18n.tr("dialog_title"), i18n.tr("msg_complete"), 700)

        except Exception as e:
            QMessageBox.critical(
                self, i18n.tr("dialog_title"),
                i18n.tr("msg_error_generate", error=str(e)))

    def _load_layers_from_file(self, file_path, export_format, memory_layers):
        """从导出文件加载 QgsVectorLayer，并克隆 memory 图层的样式。"""
        from .windrose_utils import get_export_name
        mem_by_name = {get_export_name(lyr): lyr for lyr in memory_layers}
        file_layers = []

        if export_format == "GPKG":
            for name in mem_by_name:
                uri = f"{file_path}|layername={name}"
                lyr = QgsVectorLayer(uri, name, "ogr")
                if lyr.isValid():
                    file_layers.append(lyr)
        elif export_format == "KML":
            tmp = QgsVectorLayer(file_path, "kml_root", "ogr")
            if tmp.isValid():
                sublayers = tmp.dataProvider().subLayers()
                if len(sublayers) > 1:
                    for sub in sublayers:
                        sub_name = sub.split("!!::!!")[1] if "!!::!!" in sub else sub
                        matched = next((n for n in mem_by_name if n in sub_name), None)
                        if matched:
                            uri = f"{file_path}|layername={sub_name}"
                            file_layers.append(QgsVectorLayer(uri, matched, "ogr"))
                else:
                    file_layers.append(tmp)
        elif export_format == "SHP":
            for name in mem_by_name:
                shp = os.path.join(file_path, f"{name}.shp")
                if os.path.exists(shp):
                    file_layers.append(QgsVectorLayer(shp, name, "ogr"))
        elif export_format == "GDB":
            # GDB 格式：使用 |layername= 语法加载特定图层
            for name in mem_by_name:
                uri = f"{file_path}|layername={name}"
                lyr = QgsVectorLayer(uri, name, "ogr")
                if lyr.isValid():
                    file_layers.append(lyr)

        # 核心：克隆 memory 图层的样式到文件图层
        for fl in file_layers:
            mem = mem_by_name.get(fl.name())
            if mem and fl.isValid():
                fl.setCustomProperty("layer_type", mem.customProperty("layer_type"))
                fl.setRenderer(mem.renderer().clone())
                try:
                    if mem.labeling():
                        fl.setLabeling(mem.labeling().clone())
                        fl.setLabelsEnabled(True)
                except Exception as e:
                    logger.debug("Copy labeling ignored: %s", e)
        return file_layers

    def _on_generate_error(self, msg):
        QApplication.restoreOverrideCursor()
        self.btn_generate.setEnabled(True)
        self.status_label.hide()
        QTimer.singleShot(100, lambda: self._show_critical(msg))

    # ─── 辅助方法 ───────────────────────────────────────────────────

    def _show_warning(self, msg):
        try:
            QMessageBox.warning(self, i18n.tr("dialog_title"), msg)
        except Exception as e:
            logger.warning("Show warning dialog failed: %s (msg: %s)", e, msg)

    def _show_critical(self, msg):
        try:
            QMessageBox.critical(self, i18n.tr("dialog_title"), msg)
        except Exception as e:
            logger.error("Show critical dialog failed: %s (msg: %s)", e, msg)

    def _show_auto_close(self, title, message, timeout_ms=700):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(_MSG_INFO)
        box.setStandardButtons(_MSG_NO_BTN)
        QTimer.singleShot(timeout_ms, box.accept)
        # PyQt5 用 exec_()，PyQt6 用 exec()
        (box.exec if hasattr(box, 'exec') else box.exec_)()
