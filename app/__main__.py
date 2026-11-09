"""Command-line entry point: `python -m app <command>` (see app.adapters.cli)."""

import sys

from app.adapters.cli import main
from app.bootstrap import bootstrap
from app.log_config import configure_logging

if __name__ == "__main__":
    configure_logging()
    sys.exit(main(sys.argv[1:], bootstrap()))
