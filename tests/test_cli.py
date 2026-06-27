"""Tests for the command-line interface."""

import sys
import io
import pytest
from pathlib import Path
from unittest.mock import patch

from xtrkcad_converter.cli import main


class TestCLI:
    def test_missing_input_exits_with_error(self, tmp_path):
        result = main([str(tmp_path / "nonexistent.dxf")])
        assert result != 0

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_convert_line_dxf(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (1, 0, 0))
        in_path = tmp_path / "input.dxf"
        doc.saveas(str(in_path))

        out_path = tmp_path / "output.xtc"
        result = main([str(in_path), str(out_path)])
        assert result == 0
        assert out_path.exists()
        content = out_path.read_text()
        assert content.startswith("VERSION 12\n")
        assert "ROOMSIZE " in content
        assert "\tL3 " in content

    def test_default_output_path(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (1, 0, 0))
        in_path = tmp_path / "layout.dxf"
        doc.saveas(str(in_path))

        result = main([str(in_path)])
        assert result == 0
        expected_out = tmp_path / "layout.xtc"
        assert expected_out.exists()

    def test_scale_override(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (25.4, 0, 0))
        in_path = tmp_path / "mm.dxf"
        doc.saveas(str(in_path))

        out_path = tmp_path / "out.xtc"
        result = main([str(in_path), str(out_path), "--scale", str(1.0 / 25.4)])
        assert result == 0
        content = out_path.read_text()
        assert "1.000000" in content

    def test_layer_flag(self, tmp_path):
        import ezdxf

        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (1, 0, 0))
        in_path = tmp_path / "input.dxf"
        doc.saveas(str(in_path))

        out_path = tmp_path / "out.xtc"
        result = main([str(in_path), str(out_path), "--layer", "3"])
        assert result == 0
        content = out_path.read_text()
        assert "DRAW 1 3 " in content

    def test_dwg_file_returns_error(self, tmp_path):
        fake_dwg = tmp_path / "test.dwg"
        fake_dwg.write_bytes(b"AC1015\x00" * 10)
        result = main([str(fake_dwg)])
        assert result == 1

    def test_height_flag_scales_drawing(self, tmp_path):
        import ezdxf

        # Line from (0,0) to (10,5) in inches → request height=10 → scale×2
        doc = ezdxf.new(dxfversion="R2010")
        doc.header["$INSUNITS"] = 1
        msp = doc.modelspace()
        msp.add_line((0, 0, 0), (10, 5, 0))
        in_path = tmp_path / "input.dxf"
        doc.saveas(str(in_path))

        out_path = tmp_path / "out.xtc"
        result = main([str(in_path), str(out_path), "--height", "10"])
        assert result == 0
        content = out_path.read_text()
        # ROOMSIZE should now be 20 × 10
        assert "ROOMSIZE 20.000000 x 10.000000\n" in content

