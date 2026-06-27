"""Command-line interface for xtrkcad-converter."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .dxf_reader import read_file
from .xtc_writer import write_xtc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xtrkcad-converter",
        description=(
            "Convert a DXF (or DWG) CAD file to an XTrkCad .xtc file "
            "for use as a background drawing."
        ),
    )
    parser.add_argument(
        "input",
        metavar="INPUT",
        help="Path to the input DXF (or DWG) file.",
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        nargs="?",
        default=None,
        help=(
            "Path for the output .xtc file.  "
            "Defaults to the input filename with the extension replaced by .xtc."
        ),
    )
    parser.add_argument(
        "--scale",
        metavar="FACTOR",
        type=float,
        default=None,
        help=(
            "Override the unit scale factor (input units → inches).  "
            "E.g. --scale 0.03937 for millimetres.  "
            "By default the scale is derived from the DXF $INSUNITS header variable."
        ),
    )
    parser.add_argument(
        "--height",
        metavar="INCHES",
        type=float,
        default=None,
        help=(
            "Scale the drawing uniformly so its total height equals this value "
            "in inches.  Applied after unit conversion."
        ),
    )
    parser.add_argument(
        "--layer",
        metavar="N",
        type=int,
        default=0,
        help="XTrkCad layer number for the output objects (default: 0).",
    )
    parser.add_argument(
        "--grouped",
        action="store_true",
        default=False,
        help=(
            "Group all entities into a single DRAW block instead of one per entity."
        ),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv=None) -> int:
    """Entry point for the ``xtrkcad-converter`` command."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    input_path = Path(args.input)

    if args.output is None:
        output_path = input_path.with_suffix(".xtc")
    else:
        output_path = Path(args.output)

    try:
        entities = read_file(
            str(input_path),
            scale_override=args.scale,
            target_height=args.height,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not entities:
        print(
            "Warning: no supported drawing entities found in the input file.",
            file=sys.stderr,
        )

    write_xtc(
        entities,
        output_path,
        layer=args.layer,
        one_entity_per_draw=not args.grouped,
    )

    print(
        f"Converted {len(entities)} entit{'y' if len(entities) == 1 else 'ies'} "
        f"→ {output_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
