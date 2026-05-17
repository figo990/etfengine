"""API Schema 定义"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class ETFDailyRequest(BaseModel):
    code: str
    start_date: date | None = None
    end_date: date | None = None


class BacktestRequest(BaseModel):
    strategy_type: str = Field(
        description=(
            "策略类型: simple_dca|valuation_dca|ma_deviation_dca|equal_grid|geometric_grid"
        )
    )
    etf_code: str
    start_date: date | None = None
    end_date: date | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class BacktestResponse(BaseModel):
    strategy_name: str
    etf_code: str
    start_date: str
    end_date: str
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    total_trades: int
    total_invested: float
    final_value: float


class ValuationSnapshotResponse(BaseModel):
    index_name: str
    pe: float | None = None
    pb: float | None = None
    pe_percentile: float | None = None
    pb_percentile: float | None = None
    dividend_yield: float | None = None
    zone: str = ""


class FEDModelResponse(BaseModel):
    earnings_yield: float
    cn_10y_yield: float
    cn_erp: float
    cn_signal: str
    us_10y_yield: float | None = None
    us_erp: float | None = None
    us_signal: str | None = None


class SignalResponse(BaseModel):
    strategy_name: str
    etf_code: str
    signal_date: str
    direction: str
    amount: float | None = None
    reason: str
    confidence: float


class PortfolioHoldingResponse(BaseModel):
    etf_code: str
    etf_name: str
    market_value: float
    target_weight: float
    actual_weight: float
    drift: float
    profit_loss: float


class RebalanceOrderResponse(BaseModel):
    etf_code: str
    etf_name: str
    direction: str
    trade_amount: float
    target_weight: float
    current_weight: float


class DataRefreshRequest(BaseModel):
    task: Literal[
        "etf_daily",
        "index_valuation",
        "bond_yield",
        "industry_chain_companies",
        "industry_chain_fundamentals",
        "industry_chain_news_links",
        "news_monitor",
        "overseas_earnings",
    ]
    codes: list[str] = Field(default_factory=list)
    chain_id: str | None = None
    history_days: int | None = Field(default=None, ge=30, le=1000)
