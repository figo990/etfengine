"""Dashboard service helper tests."""

from __future__ import annotations

from datetime import date

from src.dashboard.services import (
    load_portfolio_config,
    save_backtest_scenario,
    save_portfolio_config,
    update_news_event_followup,
)
from src.data.storage import StorageEngine


def test_portfolio_config_roundtrip(tmp_path):
    target = tmp_path / "portfolio.yaml"
    config = {
        "portfolio": {
            "name": "测试组合",
            "total_capital": 200000,
            "holdings": [{"etf": "510300", "name": "沪深300ETF", "target_weight": 1.0}],
        }
    }

    save_portfolio_config(config, target)

    assert load_portfolio_config(target) == config


def test_load_portfolio_config_uses_default_when_missing(tmp_path):
    config = load_portfolio_config(tmp_path / "missing.yaml")

    assert config["portfolio"]["name"] == "默认ETF组合"
    assert config["portfolio"]["holdings"] == []


def test_save_backtest_scenario_with_existing_storage(tmp_path):
    storage = StorageEngine(db_path=str(tmp_path / "dashboard-services.duckdb"))
    storage.init_schema()
    try:
        scenario_id = save_backtest_scenario(
            {
                "scenario_name": "服务层方案",
                "etf_code": "510300",
                "strategy_name": "普通定投",
                "params": {"amount": 1000},
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 12, 31),
            },
            storage=storage,
        )
        result = storage.get_backtest_scenarios()
    finally:
        storage.close()

    assert result["id"].iloc[0] == scenario_id
    assert result["scenario_name"].iloc[0] == "服务层方案"


def test_update_news_event_followup_with_existing_storage(tmp_path):
    storage = StorageEngine(db_path=str(tmp_path / "dashboard-followup.duckdb"))
    storage.init_schema()
    try:
        update_news_event_followup("evt-1", "跟踪中", "等待政策落地", storage=storage)
        result = storage.get_news_event_followups(["evt-1"])
    finally:
        storage.close()

    assert result["status"].iloc[0] == "跟踪中"
    assert result["note"].iloc[0] == "等待政策落地"
