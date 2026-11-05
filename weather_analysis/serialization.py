"""Explicit JSON-compatible values for the composed domain result; no HTTP schema."""
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from .models import RouteWeatherAnalysis


def analysis_to_dict(analysis: RouteWeatherAnalysis) -> dict[str, Any]:
    """Decimals remain exact strings; datetimes use offset-aware ISO 8601."""
    def convert(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return {field.name: convert(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, (tuple, list)):
            return [convert(item) for item in value]
        return value
    return convert(analysis)
