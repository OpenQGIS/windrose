# -*- coding: utf-8 -*-
"""
style_manager.py

配色方案定义与应用。
通过图层自定义属性 "layer_type" 匹配样式，不依赖图层名称（避免国际化和哈希后缀问题）。
"""

from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol,
    QgsSimpleFillSymbolLayer, QgsCategorizedSymbolRenderer,
)

from . import windrose_utils as utils


class StyleManager:
    """
    样式配置字典。

    键名 = 图层类型标识（与 windrose_utils.LAYER_TYPE_* 常量对应）：
        sector        - 扇区面（黑白交替三角形）
        outline       - 外环线
        point         - 采集点
        coord_lines   - 坐标线
        closed_polygon - 闭合面
        circles       - 同心圆参考线
        ring          - 同心圆环（梯形）
        freq_table    - 频率表
        north_arrow   - 指北箭头
        direction_labels - 方向标注

    属性：
        fill    - 填充颜色（面图层），"transparent" 表示透明
        outline - 轮廓颜色（面图层）
        color   - 线条/点的颜色
        width   - 线宽 (mm)
        size    - 点大小 (mm)
    """

    STYLES = {
        "color_default": {
            utils.LAYER_TYPE_SECTOR: {"fill": "#FFFFFF", "outline": "#000000", "width": 0.2},
            utils.LAYER_TYPE_OUTLINE: {"color": "#000000", "width": 0.5},
            utils.LAYER_TYPE_POINT: {"color": "#FF0000", "size": 2.0},
            utils.LAYER_TYPE_COORD: {"color": "#000000", "width": 0.3},
            utils.LAYER_TYPE_POLYGON: {"fill": "transparent", "outline": "#000000", "width": 0.2},
            utils.LAYER_TYPE_CIRCLES: {"color": "#666666", "width": 0.2},
            utils.LAYER_TYPE_RING: {"outline": "#000000", "width": 0.2},
            utils.LAYER_TYPE_ARROW: {"color": "#000000", "size": 3.0},
            utils.LAYER_TYPE_DIRECTION: {"color": "#000000"},
            utils.LAYER_TYPE_FREQ_TABLE: {},
        },
        "color_warm": {
            utils.LAYER_TYPE_SECTOR: {"fill": "#FFF3E0", "outline": "#BF360C", "width": 0.2},
            utils.LAYER_TYPE_OUTLINE: {"color": "#E65100", "width": 0.5},
            utils.LAYER_TYPE_POINT: {"color": "#D32F2F", "size": 2.0},
            utils.LAYER_TYPE_COORD: {"color": "#BF360C", "width": 0.3},
            utils.LAYER_TYPE_POLYGON: {"fill": "transparent", "outline": "#E65100", "width": 0.2},
            utils.LAYER_TYPE_CIRCLES: {"color": "#FF6F00", "width": 0.2},
            utils.LAYER_TYPE_RING: {"outline": "#BF360C", "width": 0.2},
            utils.LAYER_TYPE_ARROW: {"color": "#BF360C", "size": 3.0},
            utils.LAYER_TYPE_DIRECTION: {"color": "#BF360C"},
            utils.LAYER_TYPE_FREQ_TABLE: {},
        },
        "color_cold": {
            utils.LAYER_TYPE_SECTOR: {"fill": "#E1F5FE", "outline": "#01579B", "width": 0.2},
            utils.LAYER_TYPE_OUTLINE: {"color": "#0288D1", "width": 0.5},
            utils.LAYER_TYPE_POINT: {"color": "#0D47A1", "size": 2.0},
            utils.LAYER_TYPE_COORD: {"color": "#01579B", "width": 0.3},
            utils.LAYER_TYPE_POLYGON: {"fill": "transparent", "outline": "#0288D1", "width": 0.2},
            utils.LAYER_TYPE_CIRCLES: {"color": "#4FC3F7", "width": 0.2},
            utils.LAYER_TYPE_RING: {"outline": "#01579B", "width": 0.2},
            utils.LAYER_TYPE_ARROW: {"color": "#01579B", "size": 3.0},
            utils.LAYER_TYPE_DIRECTION: {"color": "#01579B"},
            utils.LAYER_TYPE_FREQ_TABLE: {},
        },
    }

    @classmethod
    def get_style_keys(cls):
        return list(cls.STYLES.keys())

    @classmethod
    def apply_style_to_layers(cls, layers, style_key, opacity=1.0):
        """
        将指定样式应用到图层列表。

        通过图层自定义属性 "layer_type" 匹配，不依赖图层名称。
        """
        if style_key not in cls.STYLES:
            return
        style_def = cls.STYLES[style_key]

        for layer in layers:
            layer_type = layer.customProperty("layer_type", "")
            if layer_type not in style_def:
                continue

            props = style_def[layer_type]
            if not props:
                continue

            renderer = layer.renderer()
            if renderer is None:
                continue

            if isinstance(renderer, QgsCategorizedSymbolRenderer):
                # 分类渲染器（扇区面、同心圆环）
                for cat in renderer.categories():
                    symbol = cat.symbol()
                    if symbol is None:
                        continue
                    if isinstance(symbol, QgsFillSymbol):
                        if "outline" in props:
                            cls._set_fill_outline_color(
                                symbol, QColor(props["outline"]))
                        if "width" in props:
                            cls._set_fill_outline_width(
                                symbol, props["width"])
                        symbol.setOpacity(opacity)
            else:
                symbol = renderer.symbol()
                if symbol is None:
                    continue

                if isinstance(symbol, QgsFillSymbol):
                    if "fill" in props:
                        fill_color = cls._parse_color(props["fill"])
                        if fill_color:
                            cls._set_fill_color(symbol, fill_color)
                    if "outline" in props:
                        cls._set_fill_outline_color(
                            symbol, QColor(props["outline"]))
                    if "width" in props:
                        cls._set_fill_outline_width(symbol, props["width"])
                    symbol.setOpacity(opacity)
                elif isinstance(symbol, QgsLineSymbol):
                    if "color" in props:
                        symbol.setColor(QColor(props["color"]))
                    if "width" in props:
                        symbol.setWidth(props["width"])
                elif isinstance(symbol, QgsMarkerSymbol):
                    if "color" in props:
                        symbol.setColor(QColor(props["color"]))
                    if "size" in props:
                        symbol.setSize(props["size"])

            layer.triggerRepaint()

    @staticmethod
    def _parse_color(color_str):
        if color_str == "transparent":
            return QColor(0, 0, 0, 0)
        try:
            return QColor(color_str)
        except Exception:
            return None

    @staticmethod
    def _set_fill_color(symbol, color):
        if hasattr(symbol, 'setColor'):
            symbol.setColor(color)
            return
        for i in range(symbol.symbolLayerCount()):
            lyr = symbol.symbolLayer(i)
            if isinstance(lyr, QgsSimpleFillSymbolLayer):
                lyr.setColor(color)
                break

    @staticmethod
    def _set_fill_outline_color(symbol, color):
        if hasattr(symbol, 'setStrokeColor'):
            symbol.setStrokeColor(color)
            return
        for i in range(symbol.symbolLayerCount()):
            lyr = symbol.symbolLayer(i)
            if isinstance(lyr, QgsSimpleFillSymbolLayer):
                lyr.setStrokeColor(color)
                break

    @staticmethod
    def _set_fill_outline_width(symbol, width):
        if hasattr(symbol, 'setStrokeWidth'):
            symbol.setStrokeWidth(width)
            return
        for i in range(symbol.symbolLayerCount()):
            lyr = symbol.symbolLayer(i)
            if isinstance(lyr, QgsSimpleFillSymbolLayer):
                lyr.setStrokeWidth(width)
                break
