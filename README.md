# WindRose - Wind Rose Generator for QGIS

<p align="left">
  <img src="https://img.shields.io/badge/status-feature--complete-brightgreen?style=flat&logo=checkmarx&logoColor=white" alt="Status">
</p>

> 💡 **项目状态说明 (Project Status)**：  
> 基于气象数据的风向风速玫瑰图生成、样式映射与多格式矢量导出体系已**构建完备并稳定运行（Feature-Complete）**。当前处于长期稳定维护状态，保障数据源接口与 QGIS 核心环境的持续兼容。

**WindRose** is a QGIS plugin that generates wind rose diagrams from point locations using the [Open-Meteo](https://open-meteo.com/) historical weather API. It supports interactive point selection, manual coordinate input, monthly data filtering, multiple visual styles, and export to various formats.

## Features

- **Point Input Options**:
  - Click on the map to select a point (automatically converted to WGS84).
  - Directly enter longitude/latitude in input fields.
- **Data Parameters**:
  - Select year (2023–2026).
  - Choose month (or full year).
  - Wind height: 10m, 80m, 120m, 180m (as supported by Open-Meteo).
- **Visual Styles**:
  - Predefined color schemes: Default, Warm, Cold.
  - Graph styles:
    - **Sector Style**: Traditional sector-based wind rose with alternating colors.
    - **Concentric Ring Style**: Wind speed intervals displayed as colored rings.
  - Show/hide coordinate points option.
- **Output Options**:
  - **Add to QGIS Project**: Generate layers directly in QGIS.
  - **Export SVG**: Save as vector graphic file.
  - **Export Local Files**: Save as GPKG, KML, SHP, or GDB format.
- **Preview**:
  - Real-time preview with fixed size display.
  - Data caching for faster style adjustments.
- **Help System**:
  - Collapsible help sidebar with Quick Start, Features, and FAQ.
  - Toggle via help button in the bottom bar.
- **Internationalization**:
  - Supports Chinese and English interfaces.
  - Runtime language switching.
- **Modern UI**:
  - Card-style layout with two-column design.
  - Scrollable panel for smaller screens.
  - 600px default width.
  - Grouped button layout with color-coded buttons.

## Requirements

- **QGIS** ≥ 3.28 (LTR recommended)
- Python packages: `requests`, `numpy` (both are usually already present in QGIS; if not, install via OSGeo4W Shell).

## Installation

### From GitHub (manual)
1. Download the latest release or clone the repository.
2. Copy the `WindRose` folder into your QGIS plugin directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS and enable the plugin via `Plugins` → `Manage and Install Plugins`.

### Using QGIS Plugin Manager (future)
Once the plugin is accepted into the official repository, it will be available directly from the Plugin Manager.

## Usage

1. Click the **WindRose** toolbar button to open the dialog.
2. Choose a point:
   - Click **Map Pick** and then click on the map.
   - Or directly enter coordinates in the longitude/latitude fields.
3. Set the data parameters: year, month (or full year), and wind height.
4. Customize the output style:
   - Color scheme, graph style (Sector or Concentric Ring).
   - Option to show/hide coordinate points.
5. Click **Generate Preview** to see a preview of the wind rose.
6. Select output options:
   - **Add to QGIS Project**: Check to create layers in the current project.
   - **Export SVG**: Check and specify a file path to save a vector graphic.
   - **Export File**: Check and choose format (GPKG/KML/SHP) and save path.
   - Multiple options can be selected simultaneously.
7. Click **Generate** to create the final wind rose.

## Export Formats

| Format | Description | Path Type |
|--------|-------------|-----------|
| **GPKG** | GeoPackage - all layers in one file | File |
| **KML** | Google Earth format (auto-converts to EPSG:4326) | File |
| **SHP** | Shapefile - each layer as separate file | Folder |
| **GDB** | File Geodatabase - all layers in one database | Folder (.gdb) |

## Changelog

### Version 2.4.3
- **Bug Fix**: Fixed `exec_()` removed in PyQt6 — uses `exec()` with fallback for PyQt5.

### Version 2.4.2
- **Bug Fix**: Fixed `QMessageBox.Information` / `QMessageBox.NoButton` enum error in QGIS 4 (PyQt6).

### Version 2.4.1
- **Bug Fix**: Fixed preview failure in QGIS 4 caused by PyQt6 enum changes (`Qt.transparent` → `Qt.GlobalColor.transparent` etc.).
- **Compatibility**: PyQt5/6 compatible Qt enum access with zero runtime overhead (detected once at module load).
- **Bug Fix**: Fixed preview button staying disabled after a rendering error.

### Version 2.4.0
- **Feature**: Added collapsible help sidebar with Quick Start, Features, and FAQ sections.
- **Feature**: Added GDB (File Geodatabase) export format support.
- **Bug Fix**: Fixed export not working when only "Export File" is checked (without "Add to Project").
- **UI**: Improved button styling with grouped layout - language/help on left, preview/generate/cancel on right.
- **UI**: Updated button colors - blue for preview, green for generate, gray for others.
- **UX**: Help panel uses QTextBrowser for better long text display.

### Version 2.3.0
- **Bug Fix**: Fixed empty export files (GPKG/KML/SHP) - export now works independently of "Add to Project" option.
- **Feature**: Load layers from exported files instead of memory - layers persist after saving/reopening project.
- **Feature**: Preserve styles via renderer clone - exported file layers maintain correct colors and symbols.
- **Bug Fix**: Fixed `writeAsVectorFormatV3` API parameter error.
- **UX**: Auto-update file path extension when switching export format (GPKG/KML/SHP).
- **Technical**: ASCII-safe export names for GDAL compatibility (avoids silent failures with Chinese characters).

### Version 2.2.0
- **Feature**: Concentric Ring wind rose style with wind speed data.
- **Feature**: Background circles and direction labels (N/E/S/W) for ring mode.
- **Feature**: Local file export supporting GPKG, KML, and SHP formats.
- **Feature**: Scrollable UI panel for smaller screens.
- **UI**: Default window width increased to 600px.
- **UI**: Input fields (longitude/latitude) are now directly editable.
- **UI**: Replaced opacity slider with "Show Coordinate Points" checkbox.
- **UI**: Removed separator lines between output options.
- **Bug Fix**: Fixed preview window size growing on each preview.
- **Bug Fix**: Fixed direction label compatibility across QGIS versions.
- **Bug Fix**: Fixed string formatting errors in error messages.

### Version 2.1.0
- **Preview**: Fixed preview display to maintain 3:2 aspect ratio and adapt to window size.
- **Preview**: Removed preview button from preview area to avoid blocking content.
- **Performance**: Added data caching - no re-download when only changing styles.
- **Bug Fix**: Fixed concentric circle style to have clear visual difference from sector style.
- **Style**: Added circle line style definitions for all color schemes.

### Version 2.0.0
- **UI**: Redesigned card-style layout with two-column design.
- **UI**: Added real-time preview functionality.
- **UI**: Optimized window size (550px width, 450px minimum).
- **UI**: Output options displayed side-by-side for easier selection.

### Version 1.7.0
- Added preview functionality.

### Version 1.6.0
- Card-style layout with side-by-side output options.

### Version 1.5.0
- Compact dialog layout with real-time opacity display.

### Version 1.4.0
- Fixed English mode style application.
- Improved code structure.

### Version 1.3.9
- Added English interface support.

### Version 1.3.8
- Optimized wind rose display and SVG transparency.

### Version 1.3.7
- Updated plugin icon.

## License

This plugin is released under the **GNU General Public License v3.0** or later. See the [LICENSE](LICENSE) file for details.

## Credits

- Weather data provided by [Open-Meteo.com](https://open-meteo.com)
- Developed by hexiaosang, OpenQGIS

## Contributing

Bug reports, feature requests, and pull requests are welcome via [GitHub Issues](../../issues).
