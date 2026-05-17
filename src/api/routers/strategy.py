"""策略 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.api.schemas import BacktestRequest, BacktestResponse
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.data.storage import StorageEngine
from src.strategies.dca.ma_deviation_dca import MADeviationDCAStrategy
from src.strategies.dca.simple_dca import SimpleDCAStrategy
from src.strategies.dca.valuation_dca import ValuationDCAStrategy
from src.strategies.grid.equal_grid import EqualGridStrategy
from src.strategies.grid.geometric_grid import GeometricGridStrategy

router = APIRouter(prefix="/api/strategy", tags=["策略"])

STRATEGY_MAP = {
    "simple_dca": SimpleDCAStrategy,
    "valuation_dca": ValuationDCAStrategy,
    "ma_deviation_dca": MADeviationDCAStrategy,
    "equal_grid": EqualGridStrategy,
    "geometric_grid": GeometricGridStrategy,
}


@router.get("/list")
def list_strategies():
    """列出可用策略"""
    strategies = []
    for key, cls in STRATEGY_MAP.items():
        instance = cls()
        strategies.append(
            {
                "key": key,
                "name": instance.name,
                "description": instance.description,
            }
        )
    return {"strategies": strategies}


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest):
    """运行策略回测"""
    if req.strategy_type not in STRATEGY_MAP:
        raise HTTPException(400, f"不支持的策略类型: {req.strategy_type}")

    storage = StorageEngine()
    try:
        df = storage.get_etf_daily(
            req.etf_code,
            str(req.start_date) if req.start_date else None,
            str(req.end_date) if req.end_date else None,
        )
        if df.empty:
            raise HTTPException(404, f"ETF {req.etf_code} 无数据")

        strategy_cls = STRATEGY_MAP[req.strategy_type]
        strategy = strategy_cls(req.params)

        config = BacktestConfig(
            start_date=req.start_date,
            end_date=req.end_date,
        )
        engine = BacktestEngine(config)
        result = engine.run(strategy, df, req.etf_code)

        return BacktestResponse(
            strategy_name=result.strategy_name,
            etf_code=result.etf_code,
            start_date=str(result.start_date),
            end_date=str(result.end_date),
            total_return=round(result.total_return, 4),
            annual_return=round(result.annual_return, 4),
            max_drawdown=round(result.max_drawdown, 4),
            sharpe_ratio=round(result.sharpe_ratio, 4),
            sortino_ratio=round(result.sortino_ratio, 4),
            calmar_ratio=round(result.calmar_ratio, 4),
            total_trades=result.total_trades,
            total_invested=round(result.total_invested, 2),
            final_value=round(result.final_value, 2),
        )
    finally:
        storage.close()
