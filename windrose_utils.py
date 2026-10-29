# -*- coding: utf-8 -*-
"""
windrose_utils.py

核心算法模块：风向频率计算、矢量图层创建、样式匹配。

设计原则：
- 所有图层创建函数统一返回 QgsVectorLayer
- 每个图层携带 "layer_type" 字段，供样式管理器按类型匹配（不依赖图层名）
- 同心圆模式使用梯形（4顶点）替代圆弧扇形（8+顶点），减少内存和渲染开销
- 预览和生成共享同一套图层创建函数，消除代码重复
"""

import numpy as np
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsPointXY,
    QgsProject, QgsLayerTreeLayer, QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol,
    QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsProperty,
    QgsTextFormat, QgsTextBufferSettings,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from . import i18n

# ─── 全局常量 ───────────────────────────────────────────────────────

# 16方向标签与角度
DIR_LABELS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]
DIR_ANGLES = np.arange(0, 360, 22.5)   # 0, 22.5, 45, ... 337.5

# 缩放因子：频率 → 经纬度偏移（度）
SCALE = 1.0 / 1000.0

# 默认风速区间 (m/s)：0-3 / 3-6 / 6-9 / 9-12 / 12-15 / >=15
DEFAULT_SPEED_BINS = [0, 3, 6, 9, 12, 15]

# 风速区间颜色方案
SPEED_COLORS = [
    QColor(173, 216, 230),   # 浅蓝  - 0-3   m/s 微风
    QColor(76, 175, 80),     # 绿色  - 3-6  m/s 轻风
    QColor(255, 235, 59),    # 黄色  - 6-9 m/s 中风
    QColor(255, 152, 0),     # 橙色  - 9-12 m/s 大风
    QColor(244, 67, 54),     # 红色  - 12-15 m/s 强风
    QColor(128, 0, 128),     # 紫色  - >=15  m/s 烈风
]

# 风速区间标签
SPEED_LABELS = [
    "0-3 m/s", "3-6 m/s", "6-9 m/s",
    "9-12 m/s", "12-15 m/s", ">=15 m/s",
]

# 图层类型标识（写入图层属性，供样式管理器匹配）
LAYER_TYPE_POINT = "point"
LAYER_TYPE_OUTLINE = "outline"
LAYER_TYPE_POLYGON = "closed_polygon"
LAYER_TYPE_SECTOR = "sector"
LAYER_TYPE_RING = "ring"
LAYER_TYPE_COORD = "coord_lines"
LAYER_TYPE_ARROW = "north_arrow"
LAYER_TYPE_CIRCLES = "circles"
LAYER_TYPE_DIRECTION = "direction_labels"
LAYER_TYPE_FREQ_TABLE = "freq_table"

# ASCII 安全导出名（避免 GDAL 在中文表名/文件名下静默失败）
LAYER_TYPE_EXPORT_NAMES = {
    LAYER_TYPE_POINT: "point",
    LAYER_TYPE_OUTLINE: "outline",
    LAYER_TYPE_POLYGON: "closed_polygon",
    LAYER_TYPE_SECTOR: "sectors",
    LAYER_TYPE_RING: "rings",
    LAYER_TYPE_COORD: "coord_lines",
    LAYER_TYPE_ARROW: "north_arrow",
    LAYER_TYPE_CIRCLES: "circles",
    LAYER_TYPE_DIRECTION: "direction_labels",
}


def get_export_name(layer):
    """从 layer_type 取 ASCII 导出名，兜底用 layer_。"""
    lt = layer.customProperty("layer_type", "")
    return LAYER_TYPE_EXPORT_NAMES.get(lt, "layer")


# ─── 频率计算 ───────────────────────────────────────────────────────

def compute_frequencies(wind_dir_list):
    """
    计算16方向风向频率（简单模式，不含风速）。

    返回: (freq, labels, angles)
        freq:   shape=(16,) 的整数数组
        labels: 16方向标签列表
        angles: shape=(16,) 的角度数组
    """
    wd = np.array(wind_dir_list, dtype=float)
    wd_shift = (wd + 11.25) % 360
    bins = np.arange(0, 360 + 22.5, 22.5)
    freq, _ = np.histogram(wd_shift, bins)
    return freq.astype(int), list(DIR_LABELS), DIR_ANGLES.copy()


def compute_frequencies_by_speed(wind_dirs, wind_speeds, speed_bins=None):
    """
    按风速区间和16方向分组统计频率矩阵。

    返回: (freq_matrix, labels, angles, speed_bins)
        freq_matrix: shape=(16, n_bins) 的整数数组
    """
    if speed_bins is None:
        speed_bins = list(DEFAULT_SPEED_BINS)

    wind_dirs = np.array(wind_dirs, dtype=float)
    wind_speeds = np.array(wind_speeds, dtype=float)

    n_dirs = 16
    n_bins = len(speed_bins)
    freq_matrix = np.zeros((n_dirs, n_bins), dtype=int)

    # 风向索引
    dir_indices = ((wind_dirs + 11.25) % 360 // 22.5).astype(int)
    dir_indices[dir_indices >= 16] = 0

    # 风速索引
    speed_indices = np.digitize(wind_speeds, speed_bins) - 1
    speed_indices = np.clip(speed_indices, 0, n_bins - 1)

    np.add.at(freq_matrix, (dir_indices, speed_indices), 1)
    return freq_matrix, list(DIR_LABELS), DIR_ANGLES.copy(), list(speed_bins)


# ─── 辅助函数 ───────────────────────────────────────────────────────

def _deg_to_xy(lon, lat, angle_deg, radius):
    """将极坐标 (角度, 半径) 转换为 WGS84 经纬度偏移。"""
    rad = np.radians((90 - angle_deg) % 360)
    return QgsPointXY(lon + radius * np.cos(rad), lat + radius * np.sin(rad))


def _add_type_field(layer, layer_type):
    """给图层添加 layer_type 属性字段（供样式管理器匹配）。"""
    layer.setCustomProperty("layer_type", layer_type)


def _freq_to_points(lon, lat, freq_array, scale):
    """将16方向频率数组转换为16个边界点坐标。"""
    points = []
    for ang, f in zip(DIR_ANGLES, freq_array):
        R = f * scale
        points.append(_deg_to_xy(lon, lat, ang, R))
    return points


# ─── 图层创建函数 ────────────────────────────────────────────────────

def create_point_layer(lon, lat, name):
    """创建采集点图层。"""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("Lon", QVariant.Double),
                      QgsField("Lat", QVariant.Double)])
    layer.updateFields()
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
    ft.setAttributes([lon, lat])
    pr.addFeature(ft)
    _add_type_field(layer, LAYER_TYPE_POINT)
    return layer


def create_outline_layer(points, max_freq, scale, name):
    """创建外环线图层。"""
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("MaxR", QVariant.Double)])
    layer.updateFields()
    polyline = points + [points[0]]
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPolylineXY(polyline))
    ft.setAttributes([float(max_freq * scale)])
    pr.addFeature(ft)
    symbol = QgsLineSymbol.createSimple({'color': 'black', 'width': '0.5'})
    layer.renderer().setSymbol(symbol)
    _add_type_field(layer, LAYER_TYPE_OUTLINE)
    return layer


def create_closed_polygon_layer(points, max_freq, scale, name):
    """创建闭合面图层（透明填充，黑色轮廓）。"""
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("MaxR", QVariant.Double)])
    layer.updateFields()
    polyline = points + [points[0]]
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPolygonXY([polyline]))
    ft.setAttributes([float(max_freq * scale)])
    pr.addFeature(ft)
    symbol = QgsFillSymbol.createSimple({
        'color': 'rgba(0,0,0,0)',
        'outline_color': 'black',
        'outline_width': '0.2',
    })
    layer.renderer().setSymbol(symbol)
    _add_type_field(layer, LAYER_TYPE_POLYGON)
    return layer


def create_sector_layer(center, points, freq, labels, angles, name):
    """创建扇区三角面图层（按 Parity 字段黑白交替着色）。"""
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([
        QgsField("Dir", QVariant.String),
        QgsField("Angle", QVariant.Double),
        QgsField("Freq", QVariant.Int),
        QgsField("Parity", QVariant.Int),
    ])
    layer.updateFields()

    features = []
    for i in range(16):
        p1 = points[i]
        p2 = points[(i + 1) % 16]
        geom = QgsGeometry.fromPolygonXY([[center, p1, p2, center]])
        ft = QgsFeature(layer.fields())
        ft.setGeometry(geom)
        ft.setAttributes([labels[i], float(angles[i]), int(freq[i]), i % 2])
        features.append(ft)
    pr.addFeatures(features)

    # 分类渲染器
    sym0 = QgsFillSymbol.createSimple({
        'color': 'white', 'outline_color': 'black', 'outline_width': '0.2'})
    sym1 = QgsFillSymbol.createSimple({
        'color': 'black', 'outline_color': 'black', 'outline_width': '0.2'})
    renderer = QgsCategorizedSymbolRenderer('Parity', [
        QgsRendererCategory(0, sym0, "Parity 0"),
        QgsRendererCategory(1, sym1, "Parity 1"),
    ])
    layer.setRenderer(renderer)
    _add_type_field(layer, LAYER_TYPE_SECTOR)
    return layer


def create_ring_layer(center, freq_matrix, scale, speed_bins, name):
    """
    创建同心圆环图层（**梯形模式**）。

    每个区域用 4 个顶点的梯形表示，替代原来的 8+ 顶点圆弧扇形：
        P3 ──── P2   (外弧两端)
        │      │
        P0 ──── P1   (内弧两端)

    按 BinIdx 字段分类着色。
    """
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([
        QgsField("Dir", QVariant.String),
        QgsField("SpeedBin", QVariant.String),
        QgsField("Freq", QVariant.Int),
        QgsField("BinIdx", QVariant.Int),
    ])
    layer.updateFields()

    n_bins = len(speed_bins)
    cumulative = np.cumsum(freq_matrix, axis=1)

    features = []
    for d_idx in range(16):
        center_angle = DIR_ANGLES[d_idx]
        angle_start = (center_angle - 11.25) % 360
        angle_end = (center_angle + 11.25) % 360
        if angle_end < angle_start:
            angle_end += 360

        for s_idx in range(n_bins):
            inner_freq = cumulative[d_idx, s_idx - 1] if s_idx > 0 else 0
            outer_freq = cumulative[d_idx, s_idx]
            if outer_freq == 0:
                continue

            inner_r = inner_freq * scale
            outer_r = outer_freq * scale

            # 4个顶点构成梯形（扇形简化为直线边）
            p0 = _deg_to_xy(center.x(), center.y(), angle_start, inner_r)
            p1 = _deg_to_xy(center.x(), center.y(), angle_end, inner_r)
            p2 = _deg_to_xy(center.x(), center.y(), angle_end, outer_r)
            p3 = _deg_to_xy(center.x(), center.y(), angle_start, outer_r)

            ft = QgsFeature(layer.fields())
            ft.setGeometry(QgsGeometry.fromPolygonXY([[p0, p1, p2, p3, p0]]))
            speed_label = (SPEED_LABELS[s_idx] if s_idx < len(SPEED_LABELS)
                           else f">{speed_bins[-1]} m/s")
            ft.setAttributes([
                DIR_LABELS[d_idx],
                speed_label,
                int(freq_matrix[d_idx, s_idx]),
                s_idx,
            ])
            features.append(ft)

    pr.addFeatures(features)

    # 分类渲染器
    categories = []
    for s_idx in range(n_bins):
        color = (SPEED_COLORS[s_idx] if s_idx < len(SPEED_COLORS)
                 else QColor(128, 128, 128))
        symbol = QgsFillSymbol.createSimple({
            'color': color.name(),
            'outline_color': '#333333',
            'outline_width': '0.1',
        })
        symbol.setOpacity(0.8)
        label = (SPEED_LABELS[s_idx] if s_idx < len(SPEED_LABELS)
                 else f">{speed_bins[-1]} m/s")
        categories.append(QgsRendererCategory(s_idx, symbol, label))

    layer.setRenderer(QgsCategorizedSymbolRenderer('BinIdx', categories))
    _add_type_field(layer, LAYER_TYPE_RING)
    return layer


def create_coord_lines_layer(lon, lat, freq, angles, scale, name,
                             line_length=None):
    """
    创建坐标参考线图层（N/E/S/W 四条射线）。

    参数:
        line_length: 指定线长；若为 None 则从 freq 自动计算。
    返回: (layer, length)
    """
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([
        QgsField("Direction", QVariant.String),
        QgsField("Angle", QVariant.Double),
    ])
    layer.updateFields()

    if line_length is not None:
        length = line_length
    else:
        if freq is None:
            raise ValueError("freq and line_length cannot both be None")
        length = max(abs(f) for f in freq) * scale * 1.05
        length = max(length, 0.001)

    directions = [
        ("N", 0, QgsPointXY(lon, lat), QgsPointXY(lon, lat + length)),
        ("E", 90, QgsPointXY(lon, lat), QgsPointXY(lon + length, lat)),
        ("S", 180, QgsPointXY(lon, lat), QgsPointXY(lon, lat - length)),
        ("W", 270, QgsPointXY(lon, lat), QgsPointXY(lon - length, lat)),
    ]

    for dir_code, angle, start, end in directions:
        ft = QgsFeature()
        ft.setGeometry(QgsGeometry.fromPolylineXY([start, end]))
        ft.setAttributes([dir_code, float(angle)])
        pr.addFeature(ft)

    symbol = QgsLineSymbol.createSimple({'color': 'black', 'width': '0.3'})
    layer.renderer().setSymbol(symbol)

    # 沿线标注（终点显示方向文字）
    try:
        settings = QgsPalLayerSettings()
        settings.fieldName = "Direction"
        settings.enabled = True
        try:
            settings.placement = QgsPalLayerSettings.Placement.Line
        except AttributeError:
            try:
                settings.placement = QgsPalLayerSettings.Line
            except AttributeError:
                pass
        settings.lineSettings().setPlacementFlags(
            QgsPalLayerSettings.LinePlacementFlag.OnLine)
        settings.format().size = 8
        settings.format().color = QColor(0, 0, 0)
        settings.format().bold = True
        settings.setDataDefinedProperty(
            QgsPalLayerSettings.Property.LabelRotation,
            QgsProperty.fromField("Angle"))
        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)
    except Exception:
        pass

    _add_type_field(layer, LAYER_TYPE_COORD)
    return layer, length


def create_north_arrow_layer(lon, lat, sn_len, name):
    """创建指北箭头图层（三角形箭头，位于北端点）。"""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("Direction", QVariant.String)])
    layer.updateFields()
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat + sn_len)))
    ft.setAttributes(["N"])
    pr.addFeature(ft)
    arrow = QgsMarkerSymbol.createSimple({
        'name': 'triangle', 'color': 'black', 'size': '3.0',
        'angle': '0',
        'vertical_anchor_point': '1',
        'horizontal_anchor_point': '1',
    })
    layer.renderer().setSymbol(arrow)
    _add_type_field(layer, LAYER_TYPE_ARROW)
    return layer


def create_circles_layer(lon, lat, max_freq, scale, name):
    """创建同心圆参考线图层（5 条同心圆弧）。"""
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("Radius", QVariant.Double)])
    layer.updateFields()

    max_r = max_freq * scale
    angles_arr = np.arange(0, 361, 10)
    rads = np.radians(angles_arr)
    cos_vals = np.cos(rads)
    sin_vals = np.sin(rads)

    for percent in [0.2, 0.4, 0.6, 0.8, 1.0]:
        r = max_r * percent
        x_coords = lon + r * cos_vals
        y_coords = lat + r * sin_vals
        circle_pts = [QgsPointXY(x, y) for x, y in zip(x_coords, y_coords)]
        ft = QgsFeature()
        ft.setGeometry(QgsGeometry.fromPolylineXY(circle_pts))
        ft.setAttributes([float(r)])
        pr.addFeature(ft)

    symbol = QgsLineSymbol.createSimple({'color': 'black', 'width': '0.2'})
    layer.renderer().setSymbol(symbol)
    _add_type_field(layer, LAYER_TYPE_CIRCLES)
    return layer


def create_direction_labels_layer(lon, lat, length, name):
    """创建方向标注点图层（N/E/S/W 文字标注，不显示点符号）。"""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    pr = layer.dataProvider()
    pr.addAttributes([QgsField("Direction", QVariant.String)])
    layer.updateFields()

    for dir_code, x, y in [
        ("N", lon, lat + length),
        ("E", lon + length, lat),
        ("S", lon, lat - length),
        ("W", lon - length, lat),
    ]:
        ft = QgsFeature()
        ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        ft.setAttributes([dir_code])
        pr.addFeature(ft)

    # 透明符号（不显示点）
    transparent = QgsMarkerSymbol.createSimple({'name': 'circle', 'size': '0'})
    layer.renderer().setSymbol(transparent)

    # 文字标注
    try:
        settings = QgsPalLayerSettings()
        settings.fieldName = "Direction"
        settings.enabled = True
        settings.placement = QgsPalLayerSettings.AroundPoint
        settings.dist = 2
        quadrant_expr = """CASE
            WHEN "Direction" = 'N' THEN 1
            WHEN "Direction" = 'E' THEN 5
            WHEN "Direction" = 'S' THEN 7
            WHEN "Direction" = 'W' THEN 3
            ELSE 4
        END"""
        settings.setDataDefinedProperty(
            QgsPalLayerSettings.Property.QuadrantPosition,
            QgsProperty.fromExpression(quadrant_expr))
        text_fmt = QgsTextFormat()
        text_fmt.setSize(10)
        text_fmt.setColor(QColor(0, 0, 0))
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(1)
        buf.setColor(QColor(255, 255, 255))
        text_fmt.setBuffer(buf)
        settings.setFormat(text_fmt)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)
    except Exception:
        pass

    _add_type_field(layer, LAYER_TYPE_DIRECTION)
    return layer


# ─── 组装函数（预览 & 生成共享） ─────────────────────────────────────

def build_preview_layers(lon, lat, wind_dirs, wind_speeds,
                         graph_style_key, show_points):
    """
    根据数据和样式参数，创建预览/生成所需的全部图层。

    参数:
        graph_style_key: "sector" 或 "concentric"
        show_points:     是否显示采集点

    返回: (layers, labels, angles)
        layers: [QgsVectorLayer, ...]
        labels: 16方向标签
        angles: 16方向角度
    """
    is_concentric = (graph_style_key == "concentric")

    if is_concentric:
        freq_matrix, labels, angles, speed_bins = compute_frequencies_by_speed(
            wind_dirs, wind_speeds)
        cumulative = np.cumsum(freq_matrix, axis=1)
        max_freq = cumulative.max() if cumulative.max() > 0 else 1
    else:
        freq, labels, angles = compute_frequencies(wind_dirs)
        max_freq = max(freq) if max(freq) > 0 else 1

    center = QgsPointXY(lon, lat)
    layers = []

    if show_points:
        layers.append(create_point_layer(lon, lat, i18n.tr("layer_point")))

    if is_concentric:
        max_ring_radius = max_freq * SCALE

        # 同心圆环（梯形模式）
        layers.append(
            create_ring_layer(center, freq_matrix, SCALE, speed_bins,
                              i18n.tr("layer_ring")))

        # 坐标线
        coord_layer, _ = create_coord_lines_layer(
            lon, lat, None, angles, SCALE,
            i18n.tr("layer_coord_lines"), line_length=max_ring_radius)
        layers.append(coord_layer)

        # 背景同心圆参考线
        layers.append(
            create_circles_layer(lon, lat, max_freq, SCALE,
                                 i18n.tr("layer_circles")))

        # 方向标注
        layers.append(
            create_direction_labels_layer(
                lon, lat, max_ring_radius * 1.1,
                i18n.tr("layer_direction_labels")))

        # 指北箭头
        layers.append(
            create_north_arrow_layer(
                lon, lat, max_ring_radius * 1.05,
                i18n.tr("layer_north_arrow")))
    else:
        # 简单模式
        points = _freq_to_points(lon, lat, freq, SCALE)

        # 坐标线
        coord_layer, sn_len = create_coord_lines_layer(
            lon, lat, freq, angles, SCALE, i18n.tr("layer_coord_lines"))

        # 指北箭头
        layers.append(
            create_north_arrow_layer(lon, lat, sn_len,
                                     i18n.tr("layer_north_arrow")))

        # 外环线
        layers.append(
            create_outline_layer(points, max_freq, SCALE,
                                 i18n.tr("layer_outline")))

        # 闭合面
        layers.append(
            create_closed_polygon_layer(points, max_freq, SCALE,
                                        i18n.tr("layer_closed_polygon")))

        # 扇区三角面
        layers.append(
            create_sector_layer(center, points, freq, labels, angles,
                                i18n.tr("layer_sectors")))

        # 坐标线（底层）
        layers.append(coord_layer)

    return layers, labels, angles


def add_layers_to_project(layers, group_name):
    """
    将图层列表添加到 QGIS 项目的指定图层组中。
    同名旧组会被先删除。
    """
    project = QgsProject.instance()
    root = project.layerTreeRoot()

    # 删除同名旧图层组
    old_group = root.findGroup(group_name)
    if old_group:
        ids_to_remove = []
        for child in old_group.children():
            if isinstance(child, QgsLayerTreeLayer):
                ids_to_remove.append(child.layerId())
        if ids_to_remove:
            project.removeMapLayers(ids_to_remove)
        root.removeChildNode(old_group)

    group = root.insertGroup(0, group_name)
    for lyr in layers:
        project.addMapLayer(lyr, False)
        group.addLayer(lyr)
