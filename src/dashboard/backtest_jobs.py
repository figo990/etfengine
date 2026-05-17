"""Background jobs for strategy backtests."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from src.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from src.data.storage import StorageEngine
from src.strategies.dca.ma_deviation_dca import MADeviationDCAStrategy
from src.strategies.dca.simple_dca import SimpleDCAStrategy
from src.strategies.grid.equal_grid import EqualGridStrategy
from src.strategies.grid.geometric_grid import GeometricGridStrategy


def run_strategy_backtest_job(
    etf_code: str,
    strategy_name: str,
    params: dict[str, Any],
    start_date: date | str,
    end_date: date | str,
) -> dict[str, Any]:
    """Run a strategy backtest and return a JSON-serializable payload."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    price_data = _load_price_data(etf_code)
    strategy = _build_strategy(strategy_name, params)
    result = BacktestEngine(BacktestConfig(start_date=start, end_date=end)).run(
        strategy,
        price_data,
        etf_code,
    )
    return serialize_backtest_result(result, strategy_name, params)


def serialize_backtest_result(
    result: BacktestResult,
    display_strategy_name: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Convert BacktestResult into a compact task result payload."""
    daily_records = [
        {
            "trade_date": record.trade_date.isoformat(),
            "total_value": round(float(record.total_value), 4),
            "total_invested": round(float(record.total_invested), 4),
            "net_return": round(float(record.net_return), 6),
        }
        for record in result.daily_records
    ]
    orders = [
        {
            "trade_date": order.trade_date.isoformat(),
            "direction": order.direction,
            "amount": round(float(order.amount), 4),
            "price": round(float(order.price), 6),
            "shares": round(float(order.shares or 0), 4),
            "reason": order.reason,
        }
        for order in result.orders
    ]
    summary = {
        "strategy_name": display_strategy_name,
        "engine_strategy_name": result.strategy_name,
        "etf_code": result.etf_code,
        "start_date": result.start_date.isoformat(),
        "end_date": result.end_date.isoformat(),
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "sortino_ratio": result.sortino_ratio,
        "calmar_ratio": result.calmar_ratio,
        "total_trades": result.total_trades,
        "total_invested": result.total_invested,
        "final_value": result.final_value,
        "params": params,
    }
    return {
        "type": "backtest",
        "summary": summary,
        "daily_records": daily_records,
        "orders": orders,
    }


def _load_price_data(etf_code: str) -> pd.DataFrame:
    storage = StorageEngine()
    try:
        storage.init_schema()
        df = storage.get_etf_daily(etf_code)
    finally:
        storage.close()
    if df.empty:
        raise ValueError(f"{etf_code} 暂无行情数据，请先补采 ETF 行情")
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    return df


def _build_strategy(strategy_name: str, params: dict[str, Any]):
    if strategy_name == "普通定投":
        return SimpleDCAStrategy(params)
    if strategy_name == "均线偏离定投":
        return MADeviationDCAStrategy(params)
    if strategy_name == "等差网格":
        return EqualGridStrategy(params)
    if strategy_name == "等比网格":
        return GeometricGridStrategy(params)
    raise ValueError(f"不支持的策略: {strategy_name}")


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
