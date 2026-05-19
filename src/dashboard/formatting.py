"""Display formatting helpers for dashboard metrics and tables."""

from __future__ import annotations

import re
from datetime import date, datetime

import pandas as pd

_ISO_DATETIME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?"
)
_DATE_ONLY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def format_display_datetime(value: object, *, date_only: bool = False) -> str:
    """Format dates for KPI/caption display as a single readable string."""
    try:
        if pd.isna(value):
            return "--"
    except (TypeError, ValueError):
        pass
    if value is None:
        return "--"
    if isinstance(value, str):
        text = value.strip().replace("/", "-")
        if not text:
            return "--"
        if text in {"暂无", "--"}:
            return text
        if date_only:
            match = _DATE_ONLY_RE.match(text[:10])
            if match:
                return match.group(1)
        match = _ISO_DATETIME_RE.match(text)
        if match:
            day = match.group(1)
            if date_only or (match.group(2) == "00" and match.group(3) == "00"):
                return day
            return f"{day} {match.group(2)}:{match.group(3)}"
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text[:10] if date_only else text[:16]
        return text

    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return "--"
        if date_only:
            return value.strftime("%Y-%m-%d")
        if value.hour == 0 and value.minute == 0 and value.second == 0:
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M")

    if isinstance(value, datetime):
        if isinstance(value, pd.Timestamp) and pd.isna(value):
            return "--"
        if date_only:
            return value.strftime("%Y-%m-%d")
        if value.hour == 0 and value.minute == 0 and value.second == 0:
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    try:
        if pd.isna(value):
            return "--"
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    if not text or text.lower() in {"nat", "none", "nan"}:
        return "--"
    return format_display_datetime(text, date_only=date_only)


def coerce_metric_display(value: object) -> str | int | float:
    """Ensure metric widget values are plain strings when they look like dates."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if pd.isna(value):
                return "--"
        except (TypeError, ValueError):
            pass
        return value
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return format_display_datetime(value)
    if isinstance(value, str):
        text = value.strip()
        if _ISO_DATETIME_RE.match(text.replace("/", "-")) or _DATE_ONLY_RE.match(text[:10]):
            return format_display_datetime(text)
        return text if text else "--"
    try:
        if pd.isna(value):
            return "--"
    except (TypeError, ValueError):
        pass
    if value is None:
        return "--"
    text = str(value).strip()
    if _ISO_DATETIME_RE.match(text.replace("/", "-")):
        return format_display_datetime(text)
    return text if text else "--"


def format_valuation_field(value: object, field: str) -> str:
    """Format valuation table fields; distinguish missing PB from numeric values."""
    pb_fields = {"PB", "PB百分位", "pb", "pb_percentile"}
    if value is None:
        return "暂无" if field in pb_fields else "--"
    try:
        if pd.isna(value):
            return "暂无" if field in pb_fields else "--"
    except (TypeError, ValueError):
        pass
    if field in pb_fields:
        try:
            numeric = float(value)
            return f"{numeric:.2f}"
        except (TypeError, ValueError):
            return "暂无"
    try:
        if value is None or pd.isna(value):
            return "--"
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "--"
