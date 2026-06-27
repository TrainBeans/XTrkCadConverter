# XTrkCadConverter

Convert DXF (AutoCAD) files to an XTrkCad `.xtc` file so they can be used as the background layer of a new layout.

> **DWG files** are not directly supported because the format is proprietary binary.  
> Please convert them to DXF first (see [Converting DWG to DXF](#converting-dwg-to-dxf)).

## Features

- Reads DXF files (all modern versions via [ezdxf](https://ezdxf.readthedocs.io/))
- Converts the following DXF entities to XTrkCad background drawing objects:
  - **LINE** → straight line segment
  - **ARC** → arc segment (angles converted between DXF and XTrkCad conventions)
  - **CIRCLE** → full-circle arc
  - **LWPOLYLINE / POLYLINE** → polyline
  - **SPLINE** → approximated as line segments
  - **TEXT / MTEXT** → text label
  - **INSERT** (block references) → expanded in place
  - **HATCH** boundary edges → lines and arcs
- Automatic unit conversion from the DXF `$INSUNITS` header variable (inches, mm, feet, etc.) to inches used by XTrkCad
- Optional manual scale override via `--scale`

## Installation

```bash
pip install .
```

Or in development mode:

```bash
pip install -e ".[dev]"
```

## Usage

```
xtrkcad-converter INPUT [OUTPUT] [OPTIONS]
```

| Argument / Option | Description |
|---|---|
| `INPUT` | Path to the input `.dxf` file |
| `OUTPUT` | Output `.xtc` path (default: same name as input with `.xtc` extension) |
| `--scale FACTOR` | Override the coordinate scale factor (input units → inches).  E.g. `--scale 0.03937` for millimetres |
| `--height INCHES` | Scale the drawing uniformly so its total height equals this value in inches (applied after unit conversion) |
| `--layer N` | XTrkCad layer number for all output objects (default: `0`) |
| `--grouped` | Put all entities in a single `DRAW` block instead of one per entity |
| `--verbose` / `-v` | Enable debug logging |
| `--version` | Print version and exit |

### Example

```bash
# Convert a DXF floor plan (units = inches) to XTrkCad
xtrkcad-converter room_plan.dxf room_plan.xtc

# Convert a metric DXF (mm) to XTrkCad (inches)
xtrkcad-converter plan_mm.dxf plan_inches.xtc --scale 0.03937

# Open the output in XTrkCad: File → Import → select room_plan.xtc
```

## Converting DWG to DXF

Use any of the following free tools:

- **LibreCAD**: `File → Export → Export as DXF`
- **FreeCAD**: `File → Export → .dxf`
- **ODA File Converter**: <https://www.opendesign.com/guestfiles/oda_file_converter>
- **AutoCAD**: `File → Save As → DXF`

## Loading the output in XTrkCad

1. Open (or create) your layout in XTrkCad.
2. Go to **File → Import** and select the `.xtc` file produced by this converter.
3. The drawing objects will appear on the selected layer and can be used as a background reference.

## Running Tests

```bash
pytest
```

## License

GNU General Public License v2.0 – see [LICENSE](LICENSE).

