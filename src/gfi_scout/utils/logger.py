"""Structured logging for GFI Scout."""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def get_logger(name: str = "gfi_scout") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        level_name = os.getenv("LOG_LEVEL", "info").upper()
        level = getattr(logging, level_name, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        _CONFIGURED = True
    return logging.getLogger(name)
