"""Tests for dashboard display formatting helpers."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from src.dashboard.formatting import (
    coerce_metric_display,
    format_display_datetime,
    format_valuation_field,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "--"),
        ("", "--"),
        (pd.NaT, "--"),
        ("2026-05-17", "2026-05-17"),
        ("2026-05-17 18:44:23.048562", "2026-05-17 18:44"),
        ("2026-05-17T17:34:36", "2026-05-17 17:34"),
        ("2026/05/18", "2026-05-18"),
        (datetime(2026, 5, 15, 0, 0, 0), "2026-05-15"),
        (datetime(2026, 5, 17, 18, 44, 23), "2026-05-17 18:44"),
        (date(2026, 5, 15), "2026-05-15"),
        (pd.Timestamp("2026-05-17 18:44:23"), "2026-05-17 18:44"),
    ],
)
def test_format_display_datetime(value: object, expected: str) -> None:
    assert format_display_datetime(value) == expected


def test_format_display_datetime_date_only() -> None:
    assert format_display_datetime("2026-05-15 00:00:00", date_only=True) == "2026-05-15"
    assert format_display_datetime(datetime(2026, 5, 15, 12, 30), date_only=True) == "2026-05-15"


def test_coerce_metric_display_datetime() -> None:
    assert coerce_metric_display(pd.Timestamp("2026-05-17 18:44:23")) == "2026-05-17 18:44"
    assert coerce_metric_display(123) == 123
    assert coerce_metric_display("plain text") == "plain text"


def test_format_display_datetime_preserves_placeholder() -> None:
    assert format_display_datetime("暂无") == "暂无"
    assert format_display_datetime("--") == "--"


def test_format_valuation_field_pb_missing() -> None:
    assert format_valuation_field(None, "PB") == "暂无"
    assert format_valuation_field(pd.NA, "PB百分位") == "暂无"
    assert format_valuation_field(1.23, "PB") == "1.23"
    assert format_valuation_field(None, "PE") == "--"
