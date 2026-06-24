"""Intermediate geometric entity representation for DXF → XTrkCad conversion."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Union


@dataclass
class Color:
    """An RGB colour used on a drawing segment."""

    r: int = 0
    g: int = 0
    b: int = 0

    def to_rgb_long(self) -> int:
        """Return the colour packed as a single integer (R<<16 | G<<8 | B)."""
        return (self.r << 16) | (self.g << 8) | self.b

    @classmethod
    def from_rgb_long(cls, value: int) -> "Color":
        """Construct from a packed integer."""
        return cls(
            r=(value >> 16) & 0xFF,
            g=(value >> 8) & 0xFF,
            b=value & 0xFF,
        )

    @classmethod
    def black(cls) -> "Color":
        return cls(0, 0, 0)


@dataclass
class Line:
    """A straight line segment."""

    x1: float
    y1: float
    x2: float
    y2: float
    color: Color = field(default_factory=Color.black)
    width: float = 0.0


@dataclass
class Arc:
    """A circular arc.

    ``a0`` is the start angle in XTrkCad convention (degrees, measured
    clockwise from East when Y is downward on screen).
    ``a1`` is the arc sweep (total degrees).
    """

    cx: float
    cy: float
    radius: float
    a0: float
    a1: float
    color: Color = field(default_factory=Color.black)
    width: float = 0.0


@dataclass
class Circle:
    """A full circle (unfilled outline)."""

    cx: float
    cy: float
    radius: float
    color: Color = field(default_factory=Color.black)
    width: float = 0.0


@dataclass
class FilledCircle:
    """A filled circle."""

    cx: float
    cy: float
    radius: float
    color: Color = field(default_factory=Color.black)
    width: float = 0.0


@dataclass
class PolyPoint:
    """A vertex in a polygon or polyline."""

    x: float
    y: float
    pt_type: int = 0  # 0 = straight corner


@dataclass
class Polyline:
    """A polyline or (filled) polygon."""

    points: List[PolyPoint]
    closed: bool = False
    filled: bool = False
    color: Color = field(default_factory=Color.black)
    width: float = 0.0


@dataclass
class Text:
    """A text label."""

    x: float
    y: float
    text: str
    angle: float = 0.0
    font_size: float = 0.1  # in inches
    color: Color = field(default_factory=Color.black)
    boxed: bool = False


#: Union of all supported drawing entity types.
DrawingEntity = Union[Line, Arc, Circle, FilledCircle, Polyline, Text]


def dxf_arc_to_xtc(
    cx: float,
    cy: float,
    radius: float,
    dxf_start_angle: float,
    dxf_end_angle: float,
    color: Color = None,
    width: float = 0.0,
) -> Arc:
    """Convert a DXF arc to an XTrkCad :class:`Arc`.

    DXF arcs have angles measured counter-clockwise from the positive X-axis
    (standard mathematical convention with Y pointing up).  XTrkCad stores
    angles clockwise from East because the screen Y-axis is downward.

    The inverse of XTrkCad's own DXF export::

        dxf_start = 90 - (xtc_a0 + xtc_a1)   (mod 360)
        dxf_end   = 90 - xtc_a0               (mod 360)

    Solved for xtc:

        xtc_a0 = (90 - dxf_end)  mod 360
        xtc_a1 = (dxf_end - dxf_start) mod 360

    """
    if color is None:
        color = Color.black()

    xtc_a0 = math.fmod(90.0 - dxf_end_angle, 360.0)
    if xtc_a0 < 0.0:
        xtc_a0 += 360.0

    xtc_a1 = math.fmod(dxf_end_angle - dxf_start_angle, 360.0)
    if xtc_a1 <= 0.0:
        xtc_a1 += 360.0

    return Arc(
        cx=cx,
        cy=cy,
        radius=radius,
        a0=xtc_a0,
        a1=xtc_a1,
        color=color,
        width=width,
    )
