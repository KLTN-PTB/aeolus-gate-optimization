"""Minimal structured logging helpers for project operations."""

from __future__ import annotations

import logging
from typing import Final


LOGGER_NAME: Final = "aeolus.data"
_LOG_FORMAT: Final = (
    "%(asctime)s %(levelname)s operation=%(operation)s "
    "config_version=%(config_version)s year=%(year)s "
    "purpose=%(purpose)s access=%(access)s message=%(message)s"
)


def configure_project_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure one console handler for metadata-only project operation logs."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
    return logger


def log_data_access(
    *,
    operation: str,
    config_version: str,
    year: int,
    purpose: str,
    allowed: bool,
    reason: str,
) -> None:
    """Log a data-access decision without logging rows or raw-data content."""
    logger = configure_project_logging()
    logger.info(
        reason,
        extra={
            "operation": operation,
            "config_version": config_version,
            "year": year,
            "purpose": purpose,
            "access": "allowed" if allowed else "blocked",
        },
    )
