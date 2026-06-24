"""Tests for the DXF reader."""

import pytest
import os

from xtrkcad_converter.dxf_reader import read_file
from xtrkcad_converter.entities import Arc, Circle, Line, Polyline, Text


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestReadFileMissing:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            read_file("/nonexistent/file.dxf")


class TestReadFileDwg:
    def test_dwg_raises_helpful_error(self, tmp_path):
        fake_dwg = tmp_path / "test.dwg"
        fake_dwg.write_bytes(b"AC1015\x00" * 10)
        with pytest.raises(ValueError, match="DWG files are not directly supported"):
            read_file(str(fake_dwg))


class TestReadSimpleDxf:
    """Integration tests using a programmatically generated DXF file."""

    def _make_dxf(self, tmp_path):
        """Create a minimal DXF file with one line."""
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1  # inches
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (1, 0, 0))
        path = tmp_path / "simple.dxf"
        doc.saveas(str(path))
        return path

    def test_line_read_correctly(self, tmp_path):
        path = self._make_dxf(tmp_path)
        entities = read_file(str(path))
        lines = [e for e in entities if isinstance(e, Line)]
        assert len(lines) == 1
        assert lines[0].x1 == pytest.approx(0.0)
        assert lines[0].y1 == pytest.approx(0.0)
        assert lines[0].x2 == pytest.approx(1.0)
        assert lines[0].y2 == pytest.approx(0.0)

    def test_arc_read_correctly(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_arc(center=(0, 0, 0), radius=2.0, start_angle=0.0, end_angle=90.0)
        path = tmp_path / "arc.dxf"
        doc.saveas(str(path))

        entities = read_file(str(path))
        arcs = [e for e in entities if isinstance(e, Arc)]
        assert len(arcs) == 1
        assert arcs[0].cx == pytest.approx(0.0)
        assert arcs[0].cy == pytest.approx(0.0)
        assert arcs[0].radius == pytest.approx(2.0)
        # a0=0, a1=90 (verified by TestDxfArcToXtc)
        assert arcs[0].a0 == pytest.approx(0.0, abs=1e-4)
        assert arcs[0].a1 == pytest.approx(90.0, abs=1e-4)

    def test_circle_read_correctly(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_circle(center=(3, 4, 0), radius=1.5)
        path = tmp_path / "circle.dxf"
        doc.saveas(str(path))

        entities = read_file(str(path))
        circles = [e for e in entities if isinstance(e, Circle)]
        assert len(circles) == 1
        assert circles[0].cx == pytest.approx(3.0)
        assert circles[0].cy == pytest.approx(4.0)
        assert circles[0].radius == pytest.approx(1.5)

    def test_scale_mm_to_inches(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 4  # millimeters
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (25.4, 0, 0))  # 25.4 mm = 1 inch
        path = tmp_path / "mm.dxf"
        doc.saveas(str(path))

        entities = read_file(str(path))
        lines = [e for e in entities if isinstance(e, Line)]
        assert len(lines) == 1
        assert lines[0].x2 == pytest.approx(1.0, abs=1e-4)  # 25.4 mm → 1 inch

    def test_scale_override(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (2, 0, 0))
        path = tmp_path / "override.dxf"
        doc.saveas(str(path))

        entities = read_file(str(path), scale_override=0.5)
        lines = [e for e in entities if isinstance(e, Line)]
        assert lines[0].x2 == pytest.approx(1.0)

    def test_lwpolyline_read(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)])
        path = tmp_path / "poly.dxf"
        doc.saveas(str(path))

        entities = read_file(str(path))
        polys = [e for e in entities if isinstance(e, Polyline)]
        assert len(polys) == 1
        assert len(polys[0].points) == 4

    def test_text_read(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_text("Hello", dxfattribs={"insert": (1.0, 2.0), "height": 0.1})
        path = tmp_path / "text.dxf"
        doc.saveas(str(path))

        entities = read_file(str(path))
        texts = [e for e in entities if isinstance(e, Text)]
        assert len(texts) == 1
        assert texts[0].text == "Hello"
        assert texts[0].x == pytest.approx(1.0)
        assert texts[0].y == pytest.approx(2.0)
