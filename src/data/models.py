"""数据模型定义：统一的数据结构规范"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MINUTE = "minute"


class ETFInfo(BaseModel):
    """ETF 基本信息"""
    code: str
    name: str
    index_tracked: str = ""
    category: str = ""
    fund_size: float | None = None
    inception_date: date | None = None
    management_fee: float | None = None


class OHLCVBar(BaseModel):
    """K线数据（OHLCV）"""
    code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    turnover_rate: float | None = None


class IndexValuation(BaseModel):
    """指数估值数据"""
    index_code: str
    index_name: str
    trade_date: date
    pe: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    ps: float | None = None
    dividend_yield: float | None = None
    pe_percentile: float | None = None
    pb_percentile: float | None = None


class BondYield(BaseModel):
    """国债收益率"""
    trade_date: date
    cn_10y: float | None = None       # 中国10年期
    cn_5y: float | None = None        # 中国5年期
    cn_1y: float | None = None        # 中国1年期
    us_10y: float | None = None       # 美国10年期


class FundIndex(BaseModel):
    """基金指数数据（偏股基金指数等）"""
    index_name: str
    trade_date: date
    close: float
    rolling_3y_annual_return: float | None = None


class TradeSignal(BaseModel):
    """交易信号"""

    class Direction(str, Enum):
        BUY = "buy"
        SELL = "sell"
        HOLD = "hold"

    strategy_name: str
    etf_code: str
    signal_date: date
    direction: Direction
    amount: float | None = None
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=datetime.now)


class BacktestResult(BaseModel):
    """回测结果"""
    strategy_name: str
    etf_code: str
    start_date: date
    end_date: date
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float | None = None
    calmar_ratio: float | None = None
    win_rate: float | None = None
    total_trades: int = 0
    profit_trades: int = 0
    loss_trades: int = 0
    total_investment: float = 0.0
    final_value: float = 0.0


class PortfolioPosition(BaseModel):
    """组合持仓"""
    etf_code: str
    etf_name: str
    shares: float = 0.0
    avg_cost: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    target_weight: float = 0.0
    actual_weight: float = 0.0
    profit_loss: float = 0.0
    profit_loss_pct: float = 0.0
