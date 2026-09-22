"""Standard logging configuration for the reconciliation engine.

Purpose
-------
Provide one shared way to obtain a configured ``logging.Logger`` without any
module reaching for global mutable state or reconfiguring the root logger
behind the caller's back. Safe to import from Dataiku, tests, or a plain
script.

Public functions
-----------------
``get_logger(name)`` -- return a namespaced logger under ``iraq_recon.*``.
``configure_logging(level)`` -- attach a single stream handler with a
structured formatter to the ``iraq_recon`` package logger; idempotent.

Dependencies: standard library only (``logging``).
"""

from __future__ import annotations

import logging

_PACKAGE_LOGGER_NAME = "iraq_recon"
_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a single formatted stream handler to the package logger.

    Safe to call multiple times; only the first call attaches a handler.

    Args:
        level: Logging level for the ``iraq_recon`` package logger.
    """
    global _configured
    package_logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    if _configured:
        package_logger.setLevel(level)
        return

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    package_logger.addHandler(handler)
    package_logger.setLevel(level)
    package_logger.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the ``iraq_recon`` package.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A ``logging.Logger`` instance. Ensures :func:`configure_logging`
        has run at least once so log output is visible by default.
    """
    if not _configured:
        configure_logging()
    if name.startswith(_PACKAGE_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_PACKAGE_LOGGER_NAME}.{name}")
