from __future__ import annotations

import argparse

from pipeline.maintenance_run_status import validate_run_id


def positive_int(value: str) -> int:
    parsed_value = int(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed_value


def nonnegative_int(value: str) -> int:
    parsed_value = int(value)
    if parsed_value < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed_value


def safe_run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except ValueError as validation_error:
        raise argparse.ArgumentTypeError(str(validation_error)) from validation_error
