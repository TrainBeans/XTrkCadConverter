"""Tests for the XTrkCad .xtc file writer."""

import io
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
)
from xtrkcad_converter.xtc_writer import entities_to_string, write_xtc


class TestVersionHeader:
    def test_version_line_present(self):
        output = entities_to_string([])
        assert output.startswith("VERSION 19\n")

    def test_empty_entities_only_header(self):
        output = entities_to_string([])
        assert output == "VERSION 19\n"


class TestWriteLine:
    def _make_line(self, x1=0.0, y1=0.0, x2=1.0, y2=1.0, color=None, width=0.0):
        return Line(x1=x1, y1=y1, x2=x2, y2=y2,
                    color=color or Color.black(), width=width)

    def test_draw_block_for_line(self):
        output = entities_to_string([self._make_line()])
        lines = output.splitlines()
        assert any(l.startswith("DRAW 1 0 0 ") for l in lines)

    def test_line_segment_format(self):
        line = self._make_line(x1=1.0, y1=2.0, x2=3.0, y2=4.0)
        output = entities_to_string([line])
        # Segment line starts with tab + 'L3'
        assert "\tL3 0 0.000000 1.000000 2.000000 0 3.000000 4.000000 0\n" in output

    def test_line_with_color(self):
        line = self._make_line(color=Color(255, 0, 0))
        output = entities_to_string([line])
        # Color 255,0,0 → 0xFF0000 = 16711680
        assert "\tL3 16711680 " in output

    def test_end_segs_present(self):
        output = entities_to_string([self._make_line()])
        assert "\tEND$SEGS\n" in output

    def test_multiple_entities_multiple_draw_blocks(self):
        entities = [self._make_line(), self._make_line()]
        output = entities_to_string(entities)
        assert output.count("DRAW ") == 2
        assert output.count("\tEND$SEGS\n") == 2

    def test_grouped_mode_single_draw_block(self):
        entities = [self._make_line(), self._make_line()]
        output = entities_to_string(entities, one_entity_per_draw=False)
        assert output.count("DRAW ") == 1
        assert output.count("\tEND$SEGS\n") == 1

    def test_draw_index_increments(self):
        entities = [self._make_line(), self._make_line(), self._make_line()]
        output = entities_to_string(entities)
        assert "DRAW 1 " in output
        assert "DRAW 2 " in output
        assert "DRAW 3 " in output

    def test_layer_parameter(self):
        output = entities_to_string([self._make_line()], layer=5)
        assert "DRAW 1 5 " in output


class TestWriteArc:
    def test_arc_segment_format(self):
        arc = Arc(cx=5.0, cy=3.0, radius=2.0, a0=0.0, a1=90.0)
        output = entities_to_string([arc])
        # A3 <color> <width> <radius> <cx> <cy> 0 <a0> <a1>
        assert "\tA3 0 0.000000 2.000000 5.000000 3.000000 0 0.000000 90.000000\n" in output


class TestWriteCircle:
    def test_circle_written_as_full_arc(self):
        circle = Circle(cx=0.0, cy=0.0, radius=1.0)
        output = entities_to_string([circle])
        # A full circle arc has a1=360
        assert "360.000000" in output
        assert "\tA3 " in output

    def test_filled_circle_uses_G_segment(self):
        fc = FilledCircle(cx=1.0, cy=2.0, radius=3.0)
        output = entities_to_string([fc])
        assert "\tG3 " in output
        assert "3.000000 1.000000 2.000000" in output


class TestWritePolyline:
    def test_polyline_segment_format(self):
        pts = [PolyPoint(0.0, 0.0), PolyPoint(1.0, 0.0), PolyPoint(1.0, 1.0)]
        poly = Polyline(points=pts)
        output = entities_to_string([poly])
        assert "\tY4 0 0.000000 3 " in output
        assert "\t\t0.000000 0.000000 0\n" in output
        assert "\t\t1.000000 0.000000 0\n" in output
        assert "\t\t1.000000 1.000000 0\n" in output

    def test_filled_polygon_uses_F_segment(self):
        pts = [PolyPoint(0.0, 0.0), PolyPoint(1.0, 0.0), PolyPoint(0.5, 1.0)]
        poly = Polyline(points=pts, filled=True, closed=True)
        output = entities_to_string([poly])
        assert "\tF4 " in output


class TestWriteText:
    def test_text_segment_format(self):
        text = Text(x=1.0, y=2.0, text="Hello", angle=0.0, font_size=0.1)
        output = entities_to_string([text])
        assert '\tZ 0 1.000000 2.000000 0.000000 0 0.100000 "Hello"' in output

    def test_text_with_special_chars_escaped(self):
        text = Text(x=0.0, y=0.0, text='Say "hi"')
        output = entities_to_string([text])
        assert '\\"hi\\"' in output

    def test_text_backslash_escaped(self):
        text = Text(x=0.0, y=0.0, text="a\\b")
        output = entities_to_string([text])
        assert "a\\\\b" in output

    def test_text_boxed(self):
        text = Text(x=0.0, y=0.0, text="boxed", boxed=True)
        output = entities_to_string([text])
        assert " 1 " in output  # boxed flag = 1


class TestWriteToFile:
    def test_write_to_file(self, tmp_path):
        out = tmp_path / "test.xtc"
        write_xtc([Line(0.0, 0.0, 1.0, 1.0)], out)
        content = out.read_text()
        assert content.startswith("VERSION 19\n")
        assert "\tL3 " in content

    def test_write_to_stream(self):
        buf = io.StringIO()
        write_xtc([Line(0.0, 0.0, 1.0, 1.0)], buf)
        assert buf.getvalue().startswith("VERSION 19\n")

    def test_unsupported_entity_raises(self):
        class Unknown:
            pass

        buf = io.StringIO()
        with pytest.raises(TypeError):
            write_xtc([Unknown()], buf)  # type: ignore
