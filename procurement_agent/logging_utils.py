from __future__ import annotations

import logging
import os
import sys
from typing import Final


_DEFAULT_LEVEL: Final[str] = "INFO"


def configure_logging(level: str | None = None) -> None:
    """Configura logging estándar para CLI.

    Idempotente: si ya hay handlers, no duplica.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    resolved_level = (level or os.environ.get("LOG_LEVEL") or _DEFAULT_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, resolved_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)

