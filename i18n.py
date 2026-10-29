# -*- coding: utf-8 -*-
"""
i18n.py

国际化模块：中英文翻译字典，运行时语言切换。
内部标识统一使用英文键名。
"""

from qgis.PyQt.QtCore import QSettings

_LANGUAGE_KEY = "WindRose/Language"

# ─── 中文翻译 ───────────────────────────────────────────────────────

_ZH = {
    # 对话框
    "dialog_title": "风向玫瑰图设置",
    "grp_input": "位置输入",
    "btn_map_point": "地图选点",
    "btn_manual": "手动输入",
    "label_lon": "经度:",
    "label_lat": "纬度:",
    "groupBox": "数据参数",
    "label_year": "年份:",
    "label_month": "月份:",
    "label_height": "高度:",
    "groupBox_2": "输出样式",
    "label_style": "配色方案:",
    "label_graph_style": "图形样式:",
    "cb_show_points": "显示坐标点",
    "cb_add_to_project": "添加到QGIS项目",
    "cb_export_svg": "导出SVG",
    "label_svg_path": "SVG保存路径:",
    "btn_browse_svg": "浏览...",
    "btn_generate": "生成",
    "btn_export_svg": "导出SVG",
    "btn_cancel": "取消",

    # 月份
    "month_full_year": "全年",
    "month_jan": "1月", "month_feb": "2月", "month_mar": "3月",
    "month_apr": "4月", "month_may": "5月", "month_jun": "6月",
    "month_jul": "7月", "month_aug": "8月", "month_sep": "9月",
    "month_oct": "10月", "month_nov": "11月", "month_dec": "12月",

    # 图形样式（显示文本）
    "style_sector": "扇区式",
    "style_concentric": "同心圆式",

    # 配色方案（显示文本）
    "color_default": "默认",
    "color_warm": "暖色",
    "color_cold": "冷色",

    # 图层名称
    "layer_point": "采集点",
    "layer_freq_table": "风向频率",
    "layer_outline": "外环线",
    "layer_closed_polygon": "闭合面",
    "layer_sectors": "扇区面",
    "layer_coord_lines": "坐标线",
    "layer_north_arrow": "指北箭头",
    "layer_circles": "同心圆参考线",
    "layer_ring": "同心圆环",
    "layer_direction_labels": "方向标注",

    # 组名
    "group_prefix": "风玫瑰图",

    # 输出
    "grp_output": "输出",
    "label_project_hint": "将风玫瑰图层添加到当前项目",
    "label_svg_hint": "导出为矢量图形文件",
    "cb_export_local": "导出文件",
    "label_local_path": "保存路径",
    "btn_browse_local": "选择保存路径",

    # 预览
    "grp_preview": "预览",
    "btn_preview": "🔄 生成预览",
    "btn_preview_loading": "⏳ 加载中...",
    "label_preview_hint": "点击下方\"生成预览\"按钮查看效果",
    "preview_generated": "✓ 已生成",
    "preview_error": "预览失败: {error}",

    # 消息
    "msg_no_point": "请先选择一个点（地图选点或手动输入）",
    "msg_wait_previous": "上一个生成任务尚未完成，请稍候。",
    "msg_complete": "风玫瑰图生成完成",
    "msg_error_generate": "生成过程中发生错误: {error}",
    "msg_error_api": "API请求失败: {error}",
    "msg_no_wind_data": "未找到风向数据（高度{height}m可能不支持）",
    "msg_wind_data_empty": "风向数据全部为空",
    "msg_pick_point": "请在地图上点击一个点。",
    "msg_export_hint": "请在生成时勾选「导出SVG」自动导出。",
    "msg_no_layers_export": "没有图层可导出",
    "msg_extent_empty": "图层范围为空",

    # 其他
    "tooltip_map_point": "点击地图选择点",
    "tooltip_manual": "手动输入经纬度",
    "status_generate": "生成风向玫瑰图",
    "status_fetching_data": "正在获取风向数据，请稍候...",

    # 帮助面板
    "help_quick_start": "快速入门",
    "help_quick_start_text": (
        "<b>1. 选择位置</b><br>"
        "• 点击「地图选点」后在地图上点击<br>"
        "• 或手动输入经纬度<br><br>"
        "<b>2. 设置参数</b><br>"
        "• 选择年份和月份<br>"
        "• 选择风速测量高度<br><br>"
        "<b>3. 选择样式</b><br>"
        "• 配色方案：默认/暖色/冷色<br>"
        "• 图形样式：扇区式/同心圆式<br><br>"
        "<b>4. 生成预览</b><br>"
        "• 点击「生成预览」查看效果<br><br>"
        "<b>5. 导出结果</b><br>"
        "• 添加到项目 / 导出SVG / 导出文件"
    ),
    "help_features": "功能说明",
    "help_features_text": (
        "<b>🎨 配色方案</b><br>"
        "• 默认：黑白经典配色<br>"
        "• 暖色：橙红色系<br>"
        "• 冷色：蓝紫色系<br><br>"
        "<b>📊 图形样式</b><br>"
        "• 扇区式：传统16方向扇形<br>"
        "• 同心圆式：按风速分层显示<br><br>"
        "<b>📁 导出格式</b><br>"
        "• GPKG：GeoPackage，推荐<br>"
        "• KML：Google Earth格式<br>"
        "• SHP：Shapefile格式<br><br>"
        "<b>💡 提示</b><br>"
        "• 导出后从文件加载，样式保留<br>"
        "• 保存项目后重新打开仍有效"
    ),
    "help_faq": "常见问题",
    "help_faq_text": (
        "<b>Q: 数据来源是什么？</b><br>"
        "A: Open-Meteo ERA5历史天气数据<br><br>"
        "<b>Q: 支持哪些高度？</b><br>"
        "A: 10m和100m<br><br>"
        "<b>Q: 为什么预览是空白的？</b><br>"
        "A: 请先选择一个有效的坐标点<br><br>"
        "<b>Q: 导出文件在哪里？</b><br>"
        "A: 在输出选项中设置保存路径<br><br>"
        "<b>Q: 如何切换语言？</b><br>"
        "A: 点击底部「English/中文」按钮"
    ),
}

# ─── 英文翻译 ───────────────────────────────────────────────────────

_EN = {
    "dialog_title": "Wind Rose Settings",
    "grp_input": "Location Input",
    "btn_map_point": "Pick from Map",
    "btn_manual": "Manual Input",
    "label_lon": "Longitude:",
    "label_lat": "Latitude:",
    "groupBox": "Data Parameters",
    "label_year": "Year:",
    "label_month": "Month:",
    "label_height": "Height:",
    "groupBox_2": "Output Style",
    "label_style": "Color Scheme:",
    "label_graph_style": "Graph Style:",
    "cb_show_points": "Show Coordinate Points",
    "cb_add_to_project": "Add to QGIS Project",
    "cb_export_svg": "Export SVG",
    "label_svg_path": "SVG Save Path:",
    "btn_browse_svg": "Browse...",
    "btn_generate": "Generate",
    "btn_export_svg": "Export SVG",
    "btn_cancel": "Cancel",

    "month_full_year": "Full Year",
    "month_jan": "January", "month_feb": "February", "month_mar": "March",
    "month_apr": "April", "month_may": "May", "month_jun": "June",
    "month_jul": "July", "month_aug": "August", "month_sep": "September",
    "month_oct": "October", "month_nov": "November", "month_dec": "December",

    "style_sector": "Sector Style",
    "style_concentric": "Concentric Style",

    "color_default": "Default",
    "color_warm": "Warm",
    "color_cold": "Cold",

    "layer_point": "Sample Point",
    "layer_freq_table": "Frequency Table",
    "layer_outline": "Outline",
    "layer_closed_polygon": "Closed Polygon",
    "layer_sectors": "Sector Faces",
    "layer_coord_lines": "Coordinate Lines",
    "layer_north_arrow": "North Arrow",
    "layer_circles": "Concentric Circles",
    "layer_ring": "Concentric Rings",
    "layer_direction_labels": "Direction Labels",

    "group_prefix": "WindRose",

    "grp_output": "Output",
    "label_project_hint": "Add wind rose layers to current project",
    "label_svg_hint": "Export as vector graphic file",
    "cb_export_local": "Export File",
    "label_local_path": "Save Path",
    "btn_browse_local": "Select Save Path",

    "grp_preview": "Preview",
    "btn_preview": "🔄 Generate Preview",
    "btn_preview_loading": "⏳ Loading...",
    "label_preview_hint": "Click \"Preview\" to generate",
    "preview_generated": "✓ Generated",
    "preview_error": "Preview failed: {error}",

    "msg_no_point": "Please select a point first (pick from map or manual input)",
    "msg_wait_previous": "Previous generation task is still running, please wait.",
    "msg_complete": "Wind rose generated successfully",
    "msg_error_generate": "Error during generation: {error}",
    "msg_error_api": "API request failed: {error}",
    "msg_no_wind_data": "Wind direction data not found (height {height}m may not be supported)",
    "msg_wind_data_empty": "All wind direction data are empty",
    "msg_pick_point": "Please click on the map to select a point.",
    "msg_export_hint": "Please check \"Export SVG\" during generation to auto-export.",
    "msg_no_layers_export": "No layers to export",
    "msg_extent_empty": "Layer extent is empty",

    "tooltip_map_point": "Click on map to select point",
    "tooltip_manual": "Enter longitude/latitude manually",
    "status_generate": "Generate wind rose diagram",
    "status_fetching_data": "Fetching wind data, please wait...",

    # Help Panel
    "help_quick_start": "Quick Start",
    "help_quick_start_text": (
        "<b>1. Select Location</b><br>"
        "• Click 'Pick from Map' then click on map<br>"
        "• Or enter longitude/latitude manually<br><br>"
        "<b>2. Set Parameters</b><br>"
        "• Select year and month<br>"
        "• Choose wind measurement height<br><br>"
        "<b>3. Choose Style</b><br>"
        "• Color scheme: Default/Warm/Cold<br>"
        "• Graph style: Sector/Concentric<br><br>"
        "<b>4. Generate Preview</b><br>"
        "• Click 'Generate Preview' to see result<br><br>"
        "<b>5. Export Result</b><br>"
        "• Add to project / Export SVG / Export file"
    ),
    "help_features": "Features",
    "help_features_text": (
        "<b>🎨 Color Schemes</b><br>"
        "• Default: Classic black & white<br>"
        "• Warm: Orange-red tones<br>"
        "• Cold: Blue-purple tones<br><br>"
        "<b>📊 Graph Styles</b><br>"
        "• Sector: Traditional 16-direction sectors<br>"
        "• Concentric: Layered by wind speed<br><br>"
        "<b>📁 Export Formats</b><br>"
        "• GPKG: GeoPackage (recommended)<br>"
        "• KML: Google Earth format<br>"
        "• SHP: Shapefile format<br><br>"
        "<b>💡 Tips</b><br>"
        "• Styles preserved when loading from file<br>"
        "• Layers persist after saving project"
    ),
    "help_faq": "FAQ",
    "help_faq_text": (
        "<b>Q: What's the data source?</b><br>"
        "A: Open-Meteo ERA5 historical weather data<br><br>"
        "<b>Q: What heights are supported?</b><br>"
        "A: 10m and 100m<br><br>"
        "<b>Q: Why is preview blank?</b><br>"
        "A: Please select a valid coordinate point first<br><br>"
        "<b>Q: Where are exported files?</b><br>"
        "A: Set save path in output options<br><br>"
        "<b>Q: How to switch language?</b><br>"
        "A: Click 'English/中文' button at bottom"
    ),
}

# ─── 语言管理 ───────────────────────────────────────────────────────

_current_lang = None


def set_language(lang):
    """设置当前语言: 'zh' 或 'en'"""
    global _current_lang
    _current_lang = lang
    settings = QSettings()
    settings.setValue(_LANGUAGE_KEY, lang)


def get_language():
    """获取当前语言"""
    global _current_lang
    if _current_lang is None:
        settings = QSettings()
        _current_lang = settings.value(_LANGUAGE_KEY, 'zh')
    return _current_lang


def tr(key, **kwargs):
    """翻译函数，支持格式化参数"""
    lang = get_language()
    text = (_EN if lang == 'en' else _ZH).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    return text


# ─── 组合框数据 ──────────────────────────────────────────────────────

def get_month_names():
    """月份名称列表（全年 + 1-12月）"""
    months = [tr("month_full_year")]
    for key in ["month_jan", "month_feb", "month_mar", "month_apr",
                "month_may", "month_jun", "month_jul", "month_aug",
                "month_sep", "month_oct", "month_nov", "month_dec"]:
        months.append(tr(key))
    return months


def get_style_names():
    """配色方案显示名称列表"""
    return [tr("color_default"), tr("color_warm"), tr("color_cold")]


def get_style_key(display_name):
    """配色方案显示名 → 内部键名"""
    mapping = {
        tr("color_default"): "color_default",
        tr("color_warm"): "color_warm",
        tr("color_cold"): "color_cold",
    }
    return mapping.get(display_name, "color_default")


def get_graph_style_names():
    """图形样式显示名称列表"""
    return [tr("style_sector"), tr("style_concentric")]


def get_graph_style_key(display_name):
    """
    图形样式显示名 → 内部键名（统一英文）。
    返回: "sector" 或 "concentric"
    """
    mapping = {
        tr("style_sector"): "sector",
        tr("style_concentric"): "concentric",
    }
    return mapping.get(display_name, "sector")
