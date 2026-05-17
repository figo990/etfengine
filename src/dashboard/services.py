"""Dashboard-facing service helpers for persistence workflows."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from src.core.config import PROJECT_ROOT
from src.data.storage import StorageEngine

DEFAULT_PORTFOLIO = {
    "portfolio": {
        "name": "默认ETF组合",
        "total_capital": 100000,
        "holdings": [],
    }
}
PORTFOLIO_PATH = PROJECT_ROOT / "config" / "portfolio.yaml"


def load_portfolio_config(path: Path | None = None) -> dict[str, Any]:
    """Load portfolio configuration with a stable default shape."""
    target = path or PORTFOLIO_PATH
    if not target.exists():
        return deepcopy(DEFAULT_PORTFOLIO)
    with open(target, encoding="utf-8") as file:
        return yaml.safe_load(file) or deepcopy(DEFAULT_PORTFOLIO)


def save_portfolio_config(config: dict[str, Any], path: Path | None = None) -> Path:
    """Persist portfolio configuration and return the target path."""
    target = path or PORTFOLIO_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as file:
        yaml.dump(
            config,
            file,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
    return target


def save_backtest_scenario(
    row: dict[str, Any],
    storage: StorageEngine | None = None,
) -> str:
    """Persist a backtest scenario through a short-lived storage session."""
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        storage.init_schema()
        return storage.save_backtest_scenario(row)
    finally:
        if owns_storage:
            storage.close()


def update_news_event_followup(
    article_id: str,
    status: str,
    note: str = "",
    storage: StorageEngine | None = None,
) -> int:
    """Persist follow-up state for a tracked news event."""
    owns_storage = storage is None
    storage = storage or StorageEngine()
    try:
        storage.init_schema()
        return storage.upsert_news_event_followup(article_id, status, note)
    finally:
        if owns_storage:
            storage.close()
