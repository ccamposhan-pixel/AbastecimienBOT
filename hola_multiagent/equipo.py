from __future__ import annotations

import sys

from .interface.cli import main


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        sys.exit(main(["--consensus", "--query", " ".join(sys.argv[1:])]))
    sys.exit(main(sys.argv[1:]))
