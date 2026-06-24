"""Allow ``python -m xtrkcad_converter`` invocation."""

from .cli import main
import sys

sys.exit(main())
