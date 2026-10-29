# -*- coding: utf-8 -*-
"""
export_helper.py

导出功能：SVG 矢量图形、GPKG/KML/SHP 本地文件。
"""

import os
from qgis.PyQt.QtCore import QRectF, QSize
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtSvg import QSvgGenerator
from qgis.core import (
    QgsMapSettings, QgsMapRendererCustomPainterJob,
    QgsVectorFileWriter, QgsProject, QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
)

from . import i18n
from .windrose_utils import get_export_name


class ExportHelper:

    @staticmethod
    def export_layers_as_svg(layers, file_path, target_width=800, dpi=96):
        """
        将图层列表导出为 SVG 文件。

        参数:
            layers:       QgsMapLayer 列表
            file_path:    输出文件路径
            target_width: 输出宽度（像素）
            dpi:          输出分辨率
        """
        if not layers:
            raise Exception(i18n.tr("msg_no_layers_export"))

        extent = layers[0].extent()
        for layer in layers[1:]:
            extent.combineExtentWith(layer.extent())

        if extent.isEmpty() or extent.isNull():
            raise Exception(i18n.tr("msg_extent_empty"))

        target_height = int(target_width * (extent.height() / max(extent.width(), 1e-10)))

        settings = QgsMapSettings()
        settings.setLayers(layers)
        settings.setExtent(extent)
        settings.setOutputSize(QSize(target_width, max(target_height, 1)))
        settings.setOutputDpi(dpi)
        settings.setBackgroundColor(QColor(0, 0, 0, 0))

        svg_gen = QSvgGenerator()
        svg_gen.setFileName(file_path)
        svg_gen.setSize(QSize(target_width, max(target_height, 1)))
        svg_gen.setViewBox(QRectF(0, 0, target_width, max(target_height, 1)))
        svg_gen.setResolution(dpi)
        svg_gen.setTitle("WindRose")
        svg_gen.setDescription("Exported from QGIS")

        painter = QPainter()
        try:
            painter.begin(svg_gen)
            job = QgsMapRendererCustomPainterJob(settings, painter)
            job.start()
            job.waitForFinished()
        finally:
            painter.end()

        return True

    @staticmethod
    def export_layers_to_local(layers, output_path, export_format="GPKG"):
        """
        将图层导出为本地文件（GPKG / KML / SHP / GDB）。

        GPKG/KML: 所有图层写入同一个文件。
        SHP:      每个图层单独一个 .shp 文件。
        GDB:      所有图层写入同一个 File Geodatabase。
        """
        if not layers:
            raise Exception(i18n.tr("msg_no_layers_export"))

        vector_layers = [lyr for lyr in layers
                         if hasattr(lyr, 'dataProvider') and lyr.type() == 0]
        if not vector_layers:
            raise Exception(i18n.tr("msg_no_layers_export"))

        project = QgsProject.instance()
        dest_crs = project.crs()

        if export_format == "GPKG":
            _export_multi_layer(vector_layers, output_path, "GPKG", dest_crs, project)
        elif export_format == "KML":
            _export_multi_layer(vector_layers, output_path, "KML",
                                QgsCoordinateReferenceSystem("EPSG:4326"), project)
        elif export_format == "SHP":
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            for layer in vector_layers:
                file_path = os.path.join(output_path, f"{get_export_name(layer)}.shp")
                _export_single_layer(layer, file_path, "ESRI Shapefile",
                                     dest_crs, project)
        elif export_format == "GDB":
            _export_to_gdb(vector_layers, output_path, dest_crs, project)
        else:
            raise Exception(f"Unsupported export format: {export_format}")

        return True


def _export_multi_layer(layers, output_path, driver, dest_crs, project):
    """将多个图层导出到同一个文件（GPKG/KML）。"""
    transform_context = project.transformContext()
    for i, layer in enumerate(layers):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver
        if i == 0:
            options.actionOnExistingFile = (
                QgsVectorFileWriter.CreateOrOverwriteFile)
        else:
            options.actionOnExistingFile = (
                QgsVectorFileWriter.CreateOrOverwriteLayer)
        options.layerName = get_export_name(layer)
        options.ct = QgsCoordinateTransform(layer.crs(), dest_crs, project)
        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, output_path, transform_context, options)
        if error[0] != QgsVectorFileWriter.NoError:
            raise Exception(f"Export error: {error[1]}")


def _export_single_layer(layer, file_path, driver, dest_crs, project):
    """将单个图层导出到文件（SHP）。"""
    transform_context = project.transformContext()
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = driver
    options.ct = QgsCoordinateTransform(layer.crs(), dest_crs, project)
    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer, file_path, transform_context, options)
    if error[0] != QgsVectorFileWriter.NoError:
        raise Exception(f"Export error: {error[1]}")


def _export_to_gdb(layers, output_path, dest_crs, project):
    """将多个图层导出到 File Geodatabase。"""
    # 确保输出路径以 .gdb 结尾
    if not output_path.endswith('.gdb'):
        output_path = output_path + '.gdb'

    # 如果 GDB 已存在，删除它
    if os.path.exists(output_path):
        import shutil
        shutil.rmtree(output_path)

    transform_context = project.transformContext()

    for i, layer in enumerate(layers):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "OpenFileGDB"
        options.ct = QgsCoordinateTransform(layer.crs(), dest_crs, project)

        if i == 0:
            options.actionOnExistingFile = (
                QgsVectorFileWriter.CreateOrOverwriteFile)
        else:
            options.actionOnExistingFile = (
                QgsVectorFileWriter.CreateOrOverwriteLayer)

        options.layerName = get_export_name(layer)

        error = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, output_path, transform_context, options)
        if error[0] != QgsVectorFileWriter.NoError:
            raise Exception(f"Export error: {error[1]}")
