"""Read DXF (and DWG) files and convert their geometry to :mod:`entities`."""

from __future__ import annotations

import logging
import os
from typing import Iterable, List, Optional

from .entities import (
    Arc,
    Circle,
    Color,
    DrawingEntity,
    FilledCircle,
    Line,
    PolyPoint,
    Polyline,
    Text,
    dxf_arc_to_xtc,
)

logger = logging.getLogger(__name__)

# ── DXF unit-to-inches conversion table (INSUNITS codes) ──────────────────────
_INSUNITS_TO_INCHES: dict = {
    0: 1.0,      # Unitless – assume inches
    1: 1.0,      # Inches
    2: 12.0,     # Feet
    3: 1609.344 * 39.3701,  # Miles (convert to inches)
    4: 1.0 / 25.4,  # Millimeters
    5: 1.0 / 2.54,  # Centimeters
    6: 39.3701,     # Meters
    7: 39370.1,     # Kilometers
    8: 1.0 / 25400000.0,  # Microinches – very rare
    9: 1.0 / 25400.0,     # Mils (thou)
    10: 36.0,              # Yards (1 yard = 36 inches)
    11: 1.0,               # Angstroms – treat as unitless
    12: 1.0,               # Nanometers – treat as unitless
    13: 1.0,               # Microns – treat as unitless
    14: 3.93701,           # Decimeters (1 dm = 100 mm = 3.93701 inches)
    15: 393.701,           # Decameters (10 m)
    16: 3937.01,           # Hectometers (100 m)
    17: 3.93701e10,        # Gigameters (1 Gm = 1e9 m)
    18: 1.0,               # Astronomical units – treat as unitless
    19: 1.0,               # Light years – treat as unitless
    20: 1.0,               # Parsecs – treat as unitless
}

# AutoCAD Color Index (ACI) → approximate RGB
_ACI_TO_RGB: dict = {
    1: (255, 0, 0),       # Red
    2: (255, 255, 0),     # Yellow
    3: (0, 255, 0),       # Green
    4: (0, 255, 255),     # Cyan
    5: (0, 0, 255),       # Blue
    6: (255, 0, 255),     # Magenta
    7: (0, 0, 0),         # Black/White – rendered as black on light backgrounds
    # Extended palette – coarse approximation
    8: (128, 128, 128),
    9: (192, 192, 192),
}


def _aci_to_color(aci: Optional[int], true_color: Optional[int] = None) -> Color:
    """Convert an AutoCAD Color Index or true-colour value to a :class:`Color`."""
    if true_color is not None and true_color >= 0:
        b = true_color & 0xFF
        g = (true_color >> 8) & 0xFF
        r = (true_color >> 16) & 0xFF
        return Color(r, g, b)
    if aci is not None and aci in _ACI_TO_RGB:
        r, g, b = _ACI_TO_RGB[aci]
        return Color(r, g, b)
    return Color.black()


def _scale(value: float, factor: float) -> float:
    return value * factor


def _entity_color(entity, layer_map: dict) -> Color:
    """Resolve an entity's colour, falling back to layer colour."""
    try:
        true_color = entity.dxf.get("true_color", None)
        if true_color is not None:
            return _aci_to_color(None, true_color)
        aci = entity.dxf.color
        if aci == 256:  # BYLAYER
            layer_name = entity.dxf.get("layer", "0")
            return layer_map.get(layer_name, Color.black())
        return _aci_to_color(aci)
    except Exception:
        return Color.black()


def _entity_width(entity, scale: float) -> float:
    """Return line width in XTrkCad inches."""
    try:
        w = entity.dxf.lineweight  # stored in hundredths of mm
        if w > 0:
            return (w / 100.0) / 25.4 * scale
    except Exception:
        pass
    return 0.0


def _build_layer_color_map(doc) -> dict:
    """Build a mapping from layer name to :class:`Color`."""
    layer_map: dict = {}
    try:
        for layer in doc.layers:
            try:
                aci = layer.dxf.color
                layer_map[layer.dxf.name] = _aci_to_color(abs(aci))
            except Exception:
                layer_map[layer.dxf.name] = Color.black()
    except Exception:
        pass
    return layer_map


def _process_modelspace(msp, scale: float, layer_map: dict) -> List[DrawingEntity]:
    """Iterate over model-space entities and convert to drawing entities."""
    entities: List[DrawingEntity] = []

    for entity in msp:
        try:
            etype = entity.dxftype()
            color = _entity_color(entity, layer_map)
            width = _entity_width(entity, scale)

            if etype == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                entities.append(
                    Line(
                        x1=_scale(start.x, scale),
                        y1=_scale(start.y, scale),
                        x2=_scale(end.x, scale),
                        y2=_scale(end.y, scale),
                        color=color,
                        width=width,
                    )
                )

            elif etype == "ARC":
                entities.append(
                    dxf_arc_to_xtc(
                        cx=_scale(entity.dxf.center.x, scale),
                        cy=_scale(entity.dxf.center.y, scale),
                        radius=_scale(entity.dxf.radius, scale),
                        dxf_start_angle=entity.dxf.start_angle,
                        dxf_end_angle=entity.dxf.end_angle,
                        color=color,
                        width=width,
                    )
                )

            elif etype == "CIRCLE":
                entities.append(
                    Circle(
                        cx=_scale(entity.dxf.center.x, scale),
                        cy=_scale(entity.dxf.center.y, scale),
                        radius=_scale(entity.dxf.radius, scale),
                        color=color,
                        width=width,
                    )
                )

            elif etype in ("LWPOLYLINE", "POLYLINE"):
                points = _extract_polyline_points(entity, scale)
                if len(points) >= 2:
                    closed = bool(entity.dxf.get("flags", 0) & 1) if etype == "POLYLINE" else entity.closed
                    entities.append(
                        Polyline(
                            points=points,
                            closed=closed,
                            filled=False,
                            color=color,
                            width=width,
                        )
                    )

            elif etype == "SPLINE":
                segments = _spline_to_lines(entity, scale)
                entities.extend(
                    Line(
                        x1=seg[0], y1=seg[1],
                        x2=seg[2], y2=seg[3],
                        color=color,
                        width=width,
                    )
                    for seg in segments
                )

            elif etype in ("TEXT", "MTEXT"):
                entities.append(_convert_text(entity, scale, color))

            elif etype == "INSERT":
                # Expand block references
                sub = _expand_insert(entity, scale, layer_map)
                entities.extend(sub)

            elif etype == "HATCH":
                # Extract hatch boundary as polylines
                sub = _extract_hatch(entity, scale, color)
                entities.extend(sub)

            else:
                logger.debug("Skipping unsupported entity type: %s", etype)

        except Exception as exc:
            logger.warning("Failed to convert entity %s: %s", entity.dxftype(), exc)

    return entities


def _extract_polyline_points(entity, scale: float) -> List[PolyPoint]:
    """Extract vertices from LWPOLYLINE or POLYLINE."""
    points: List[PolyPoint] = []
    try:
        if entity.dxftype() == "LWPOLYLINE":
            for x, y in entity.get_points(format="xy"):
                points.append(PolyPoint(_scale(x, scale), _scale(y, scale)))
        else:  # POLYLINE
            for v in entity.vertices:
                try:
                    loc = v.dxf.location
                    points.append(PolyPoint(_scale(loc.x, scale), _scale(loc.y, scale)))
                except Exception:
                    pass
    except Exception as exc:
        logger.debug("Error extracting polyline points: %s", exc)
    return points


def _spline_to_lines(entity, scale: float) -> List[tuple]:
    """Approximate a spline as a sequence of (x1, y1, x2, y2) line segments."""
    try:
        pts = list(entity.flattening(0.01))
    except Exception:
        try:
            pts = list(entity.control_points)
        except Exception:
            return []

    segments = []
    for i in range(len(pts) - 1):
        p0 = pts[i]
        p1 = pts[i + 1]
        segments.append(
            (_scale(p0[0], scale), _scale(p0[1], scale),
             _scale(p1[0], scale), _scale(p1[1], scale))
        )
    return segments


def _convert_text(entity, scale: float, color: Color) -> Text:
    """Convert TEXT or MTEXT entity."""
    etype = entity.dxftype()
    try:
        if etype == "TEXT":
            pos = entity.dxf.insert
            text_str = entity.dxf.text
            angle = entity.dxf.get("rotation", 0.0)
            height = _scale(entity.dxf.get("height", 0.1), scale)
        else:  # MTEXT
            pos = entity.dxf.insert
            text_str = entity.text
            angle = entity.dxf.get("rotation", 0.0)
            height = _scale(entity.dxf.get("char_height", 0.1), scale)
    except Exception:
        pos = type("P", (), {"x": 0.0, "y": 0.0})()
        text_str = ""
        angle = 0.0
        height = 0.1 * scale

    return Text(
        x=_scale(pos.x, scale),
        y=_scale(pos.y, scale),
        text=text_str,
        angle=angle,
        font_size=max(height, 0.01),
        color=color,
    )


def _expand_insert(entity, scale: float, layer_map: dict) -> List[DrawingEntity]:
    """Expand a block INSERT by processing its virtual entities."""
    try:
        # ezdxf provides virtual entities that account for the insert transform
        return _process_modelspace(entity.virtual_entities(), scale, layer_map)
    except Exception as exc:
        logger.debug("Could not expand INSERT block: %s", exc)
        return []


def _extract_hatch(entity, scale: float, color: Color) -> List[DrawingEntity]:
    """Extract boundary edges from a HATCH entity as polylines/arcs."""
    result: List[DrawingEntity] = []
    try:
        for path in entity.paths:
            if hasattr(path, "edges"):
                for edge in path.edges:
                    etype = edge.EDGE_TYPE if hasattr(edge, "EDGE_TYPE") else ""
                    if etype == "LineEdge":
                        result.append(
                            Line(
                                x1=_scale(edge.start.x, scale),
                                y1=_scale(edge.start.y, scale),
                                x2=_scale(edge.end.x, scale),
                                y2=_scale(edge.end.y, scale),
                                color=color,
                            )
                        )
                    elif etype == "ArcEdge":
                        result.append(
                            dxf_arc_to_xtc(
                                cx=_scale(edge.center.x, scale),
                                cy=_scale(edge.center.y, scale),
                                radius=_scale(edge.radius, scale),
                                dxf_start_angle=edge.start_angle,
                                dxf_end_angle=edge.end_angle,
                                color=color,
                            )
                        )
    except Exception as exc:
        logger.debug("Error extracting hatch: %s", exc)
    return result


def read_file(path: str, scale_override: Optional[float] = None) -> List[DrawingEntity]:
    """Read a DXF or DWG file and return a list of drawing entities.

    Parameters
    ----------
    path:
        Path to the input DXF or DWG file.
    scale_override:
        If given, multiply all coordinates by this factor to convert to
        inches.  When ``None`` (default) the scale is derived from the
        ``$INSUNITS`` DXF header variable.

    Returns
    -------
    List of :class:`~xtrkcad_converter.entities.DrawingEntity` objects.

    Raises
    ------
    FileNotFoundError:
        If *path* does not exist.
    ValueError:
        If the file cannot be read (e.g. unsupported DWG version).
    """
    import ezdxf
    from ezdxf import recover

    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    if ext == ".dwg":
        raise ValueError(
            "DWG files are not directly supported.  Please convert to DXF first.\n"
            "Free tools that can do this conversion:\n"
            "  • LibreCAD (File → Export → Export as DXF)\n"
            "  • FreeCAD (File → Export → .dxf)\n"
            "  • ODA File Converter (https://www.opendesign.com/guestfiles/oda_file_converter)\n"
            "  • AutoCAD: File → Save As → DXF\n"
        )

    try:
        doc, auditor = recover.readfile(path)
        if auditor.has_errors:
            logger.warning(
                "DXF file had %d recoverable issue(s); conversion may be incomplete.",
                len(auditor.errors),
            )
    except Exception as exc:
        raise ValueError(f"Could not read DXF file '{path}': {exc}") from exc

    # Determine unit scale factor (convert to inches)
    if scale_override is not None:
        scale = scale_override
    else:
        try:
            insunits = doc.header.get("$INSUNITS", 0)
            scale = _INSUNITS_TO_INCHES.get(int(insunits), 1.0)
        except Exception:
            scale = 1.0
        logger.debug("DXF INSUNITS=%s → scale=%.6f in/unit", insunits, scale)

    layer_map = _build_layer_color_map(doc)
    msp = doc.modelspace()
    return _process_modelspace(msp, scale, layer_map)
