"""Tests for entity dataclasses and DXF arc conversion."""

import math
import pytest

from xtrkcad_converter.entities import (
    Arc,
    Circle,
    Color,
    FilledCircle,
    Line,
    PolyPoint,
    Polyline,
    Text,
    dxf_arc_to_xtc,
)


class TestColor:
    def test_black_default(self):
        c = Color()
        assert c.r == 0
        assert c.g == 0
        assert c.b == 0

    def test_to_rgb_long_black(self):
        assert Color(0, 0, 0).to_rgb_long() == 0

    def test_to_rgb_long_red(self):
        assert Color(255, 0, 0).to_rgb_long() == 0xFF0000

    def test_to_rgb_long_mixed(self):
        c = Color(1, 2, 3)
        assert c.to_rgb_long() == (1 << 16) | (2 << 8) | 3

    def test_from_rgb_long_roundtrip(self):
        original = Color(100, 150, 200)
        assert Color.from_rgb_long(original.to_rgb_long()) == original

    def test_black_classmethod(self):
        assert Color.black() == Color(0, 0, 0)


class TestDxfArcToXtc:
    """Tests for the DXF → XTrkCad arc angle conversion.

    The inverse relationship (from XTrkCad's own DXF export code) is:

        dxf_start = (90 - (xtc_a0 + xtc_a1)) mod 360
        dxf_end   = (90 - xtc_a0) mod 360
    """

    def _round_trip(self, dxf_start, dxf_end, expected_a0, expected_a1):
        arc = dxf_arc_to_xtc(1.0, 2.0, 3.0, dxf_start, dxf_end)
        assert arc.cx == pytest.approx(1.0)
        assert arc.cy == pytest.approx(2.0)
        assert arc.radius == pytest.approx(3.0)
        assert arc.a0 == pytest.approx(expected_a0, abs=1e-6)
        assert arc.a1 == pytest.approx(expected_a1, abs=1e-6)

    def test_quarter_circle_0_to_90(self):
        # DXF: East → North (CCW, standard math)
        # XTrkCad: a0=0 (East), a1=90 (CW sweep)
        self._round_trip(0.0, 90.0, 0.0, 90.0)

    def test_quarter_circle_90_to_180(self):
        # DXF: North → West
        # xtc_a0 = 90 - 180 = -90 → 270, xtc_a1 = 180-90 = 90
        self._round_trip(90.0, 180.0, 270.0, 90.0)

    def test_semi_circle_0_to_180(self):
        # xtc_a0 = 90 - 180 = -90 → 270, xtc_a1 = 180
        self._round_trip(0.0, 180.0, 270.0, 180.0)

    def test_arc_crossing_zero(self):
        # DXF: 350° → 10° (20° CCW sweep crossing 0)
        # xtc_a0 = 90 - 10 = 80, xtc_a1 = (10-350+360) = 20
        self._round_trip(350.0, 10.0, 80.0, 20.0)

    def test_full_arc_360(self):
        # xtc_a0 = 90 - 360 = -270 → 90, xtc_a1 = 360
        arc = dxf_arc_to_xtc(0.0, 0.0, 5.0, 0.0, 360.0)
        assert arc.a1 == pytest.approx(360.0, abs=1e-6)

    def test_default_color_is_black(self):
        arc = dxf_arc_to_xtc(0.0, 0.0, 1.0, 0.0, 90.0)
        assert arc.color == Color.black()

    def test_custom_color_passed_through(self):
        arc = dxf_arc_to_xtc(0.0, 0.0, 1.0, 0.0, 90.0, color=Color(255, 0, 0))
        assert arc.color == Color(255, 0, 0)

    def test_verify_inverse_formula(self):
        """Verify that our formula is truly the inverse of XTrkCad's export."""
        import math

        def xtc_to_dxf(a0, a1):
            start = math.fmod(90.0 - (a0 + a1), 360.0)
            if start < 0:
                start += 360.0
            end = math.fmod(90.0 - a0, 360.0)
            if end < 0:
                end += 360.0
            return start, end

        # Test several (a0, a1) pairs
        for xtc_a0, xtc_a1 in [(0, 90), (45, 135), (270, 90), (315, 180)]:
            dxf_s, dxf_e = xtc_to_dxf(xtc_a0, xtc_a1)
            arc = dxf_arc_to_xtc(0.0, 0.0, 1.0, dxf_s, dxf_e)
            assert arc.a0 == pytest.approx(xtc_a0, abs=1e-4), (
                f"a0 mismatch for input ({xtc_a0}, {xtc_a1}): "
                f"dxf({dxf_s:.1f}, {dxf_e:.1f}) → xtc({arc.a0:.4f}, {arc.a1:.4f})"
            )
            assert arc.a1 == pytest.approx(xtc_a1, abs=1e-4), (
                f"a1 mismatch for input ({xtc_a0}, {xtc_a1})"
            )


class TestEntityDefaults:
    def test_line_defaults(self):
        line = Line(0.0, 0.0, 1.0, 1.0)
        assert line.color == Color.black()
        assert line.width == pytest.approx(0.0)

    def test_polyline_requires_points(self):
        pts = [PolyPoint(0.0, 0.0), PolyPoint(1.0, 1.0)]
        poly = Polyline(points=pts)
        assert len(poly.points) == 2
        assert poly.closed is False
        assert poly.filled is False

    def test_text_defaults(self):
        t = Text(x=0.0, y=0.0, text="hello")
        assert t.angle == pytest.approx(0.0)
        assert t.boxed is False
