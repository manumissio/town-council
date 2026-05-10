from __future__ import annotations

import json
import logging

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import Text, TypeDecorator


logger = logging.getLogger(__name__)

VECTOR_COLUMN_TYPE: type[TypeDecorator[object | None]]

try:
    from pgvector.sqlalchemy import Vector as PgVector
except Exception:  # pragma: no cover

    class FallbackVector(TypeDecorator[object | None]):
        """
        Lightweight fallback so local imports/tests do not crash when pgvector is absent.
        """

        impl = Text
        cache_ok = True

        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__()

        def process_bind_param(self, value: object | None, dialect: Dialect) -> str | None:
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return json.dumps(list(value))
            return str(value)

        def process_result_value(self, value: object | None, dialect: Dialect) -> object | None:
            if value is None:
                return None
            if not isinstance(value, (str, bytes, bytearray)):
                return value
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except Exception as json_error:
                # Legacy rows may store plain text instead of JSON arrays; returning the raw
                # value preserves read compatibility while the warning surfaces cleanup debt.
                logger.warning("sqlalchemy.json_list_decode_failed error=%s", json_error)
            return value

    VECTOR_COLUMN_TYPE = FallbackVector
else:
    VECTOR_COLUMN_TYPE = PgVector


class Base(DeclarativeBase):
    pass
