"""Write drawing entities to an XTrkCad ``.xtc`` file.

XTrkCad file format reference
------------------------------
The file format (version 19+) relevant to background drawings:

Header::

    VERSION 19

A drawing object::

    DRAW <index> <layer> <lineType> 0 0 <orig.x> <orig.y> 0 <angle>

Followed by segments (tab-indented), terminated by ``END$SEGS``::

    Straight line  (SEG_STRLIN = 'L'):
        \\tL3 <color> <width> <x1> <y1> 0 <x2> <y2> 0

    Arc / curve    (SEG_CRVLIN = 'A'):
        \\tA3 <color> <width> <radius> <cx> <cy> 0 <a0> <a1>

    Filled circle  (SEG_FILCRCL = 'G'):
        \\tG3 <color> <width> <radius> <cx> <cy> 0

    Polyline       (SEG_POLY = 'Y') / filled polygon (SEG_FILPOLY = 'F'):
        \\tY4 <color> <width> <point_count> <poly_type> \\n
        \\t\\t<x> <y> <pt_type>   (one per vertex)

    Text           (SEG_TEXT = 'Z'):
        \\tZ <color> <x> <y> <angle> <boxed> <fontSize> "<text>"

    End of segment list:
        \\tEND$SEGS
"""

from __future__ import annotations

import io
import os
from typing import Iterable, List, Union

from .entities import (
    Arc,
    Circle,
    DrawingEntity,
    FilledCircle,
    Line,
    Polyline,
    Text,
)

# XTrkCad file format version written by this converter
_FORMAT_VERSION = 19

# Segment type characters (from XTrkCad track.h)
_SEG_STRLIN = "L"
_SEG_CRVLIN = "A"
_SEG_FILCRCL = "G"
_SEG_POLY = "Y"
_SEG_FILPOLY = "F"
_SEG_TEXT = "Z"

# Poly sub-types
_POLYTYPE_POLYLINE = 1
_POLYTYPE_FREEFORM = 0


def _escape_text(text: str) -> str:
    """Escape backslashes and double-quotes for XTrkCad text segments."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _write_line(f, seg: Line) -> None:
    color = seg.color.to_rgb_long()
    f.write(
        f"\t{_SEG_STRLIN}3 {color} {seg.width:.6f} "
        f"{seg.x1:.6f} {seg.y1:.6f} 0 "
        f"{seg.x2:.6f} {seg.y2:.6f} 0\n"
    )


def _write_arc(f, seg: Arc) -> None:
    color = seg.color.to_rgb_long()
    f.write(
        f"\t{_SEG_CRVLIN}3 {color} {seg.width:.6f} "
        f"{seg.radius:.6f} "
        f"{seg.cx:.6f} {seg.cy:.6f} 0 "
        f"{seg.a0:.6f} {seg.a1:.6f}\n"
    )


def _write_circle(f, seg: Circle) -> None:
    """Write a full circle as a 360-degree arc."""
    color = seg.color.to_rgb_long()
    f.write(
        f"\t{_SEG_CRVLIN}3 {color} {seg.width:.6f} "
        f"{seg.radius:.6f} "
        f"{seg.cx:.6f} {seg.cy:.6f} 0 "
        f"0.000000 360.000000\n"
    )


def _write_filled_circle(f, seg: FilledCircle) -> None:
    color = seg.color.to_rgb_long()
    f.write(
        f"\t{_SEG_FILCRCL}3 {color} {seg.width:.6f} "
        f"{seg.radius:.6f} "
        f"{seg.cx:.6f} {seg.cy:.6f} 0\n"
    )


def _write_polyline(f, seg: Polyline) -> None:
    if len(seg.points) < 2:
        return
    color = seg.color.to_rgb_long()
    poly_type = _POLYTYPE_POLYLINE if not seg.closed else _POLYTYPE_FREEFORM
    seg_char = _SEG_FILPOLY if seg.filled else _SEG_POLY
    f.write(
        f"\t{seg_char}4 {color} {seg.width:.6f} "
        f"{len(seg.points)} {poly_type} \n"
    )
    for pt in seg.points:
        f.write(f"\t\t{pt.x:.6f} {pt.y:.6f} {pt.pt_type}\n")


def _write_text(f, seg: Text) -> None:
    color = seg.color.to_rgb_long()
    escaped = _escape_text(seg.text)
    f.write(
        f"\t{_SEG_TEXT} {color} "
        f"{seg.x:.6f} {seg.y:.6f} {seg.angle:.6f} "
        f"{1 if seg.boxed else 0} "
        f"{seg.font_size:.6f} \"{escaped}\"\n"
    )


def _write_entity(f, entity: DrawingEntity) -> None:
    """Write the segment line(s) for a single entity."""
    if isinstance(entity, Line):
        _write_line(f, entity)
    elif isinstance(entity, Arc):
        _write_arc(f, entity)
    elif isinstance(entity, Circle):
        _write_circle(f, entity)
    elif isinstance(entity, FilledCircle):
        _write_filled_circle(f, entity)
    elif isinstance(entity, Polyline):
        _write_polyline(f, entity)
    elif isinstance(entity, Text):
        _write_text(f, entity)
    else:
        raise TypeError(f"Unsupported entity type: {type(entity)}")


def write_xtc(
    entities: Iterable[DrawingEntity],
    output: Union[str, os.PathLike, io.IOBase],
    layer: int = 0,
    line_type: int = 0,
    one_entity_per_draw: bool = True,
) -> None:
    """Write drawing entities to an XTrkCad ``.xtc`` file.

    Parameters
    ----------
    entities:
        Iterable of :class:`~xtrkcad_converter.entities.DrawingEntity`
        objects to write.
    output:
        Destination file path (str or :class:`os.PathLike`) or an open
        :class:`io.IOBase` text stream.
    layer:
        XTrkCad layer number (0 = default layer).
    line_type:
        XTrkCad line type (0 = solid, 1 = dashed, 2 = dotted, …).
    one_entity_per_draw:
        When ``True`` (default) each drawing entity is wrapped in its own
        ``DRAW`` block, which is the simplest approach.  When ``False`` all
        entities are grouped into a single ``DRAW`` block.
    """
    entity_list = list(entities)

    def _write_to(f) -> None:
        f.write(f"VERSION {_FORMAT_VERSION}\n")

        if one_entity_per_draw:
            for idx, entity in enumerate(entity_list, start=1):
                f.write(
                    f"DRAW {idx} {layer} {line_type} "
                    f"0 0 0.000000 0.000000 0 0.000000\n"
                )
                _write_entity(f, entity)
                f.write("\tEND$SEGS\n")
        else:
            f.write(
                f"DRAW 1 {layer} {line_type} "
                f"0 0 0.000000 0.000000 0 0.000000\n"
            )
            for entity in entity_list:
                _write_entity(f, entity)
            f.write("\tEND$SEGS\n")

    if isinstance(output, (str, os.PathLike)):
        with open(output, "w", newline="\n", encoding="utf-8") as fh:
            _write_to(fh)
    else:
        _write_to(output)


def entities_to_string(
    entities: Iterable[DrawingEntity],
    layer: int = 0,
    line_type: int = 0,
    one_entity_per_draw: bool = True,
) -> str:
    """Return the ``.xtc`` content as a string (useful for testing)."""
    buf = io.StringIO()
    write_xtc(
        entities,
        buf,
        layer=layer,
        line_type=line_type,
        one_entity_per_draw=one_entity_per_draw,
    )
    return buf.getvalue()
