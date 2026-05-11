from __future__ import annotations

import logging


def configure_cli_logging(log_format: str) -> None:
    logging.basicConfig(level=logging.INFO, format=log_format)
