"""回测引擎单元测试"""

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategies.dca.simple_dca import SimpleDCAStrategy


@pytest.fixture
def price_data() -> pd.DataFrame:
    """生成1年价格数据"""
    dates = pd.bdate_range(start="2023-01-01", end="2023-12-31")
    np.random.seed(42)
    prices = 4.0 + np.cumsum(np.random.randn(len(dates)) * 0.02)
    prices = np.maximum(prices, 2.0)
    return pd.DataFrame(
        {
            "trade_date": dates.date,
            "open": prices * 0.995,
            "high": prices * 1.01,
            "low": prices * 0.985,
            "close": prices,
            "volume": np.random.randint(500000, 2000000, len(dates)),
            "amount": np.random.randint(2000000, 8000000, len(dates)),
        }
    )


class TestBacktestEngine:
    def test_basic_run(self, price_data: pd.DataFrame):
        config = BacktestConfig(
            commission_rate=0.0003,
            min_commission=5.0,
            stamp_tax_rate=0.001,
            slippage_rate=0.0001,
        )
        engine = BacktestEngine(config)
        strategy = SimpleDCAStrategy({"amount": 1000, "frequency": "monthly"})

        result = engine.run(strategy, price_data, etf_code="510300")

        assert result.strategy_name == "普通定投(DCA)"
        assert result.etf_code == "510300"
        assert result.total_trades == 12
        assert result.total_invested > 0
        assert result.final_value > 0
        assert len(result.daily_records) == len(price_data)

    def test_trading_cost(self):
        config = BacktestConfig(
            commission_rate=0.0003,
            min_commission=5.0,
            stamp_tax_rate=0.001,
            slippage_rate=0.0001,
        )
        engine = BacktestEngine(config)

        buy_cost = engine._calc_trading_cost(10000, "buy")
        assert buy_cost >= 5.0  # 最低佣金

        sell_cost = engine._calc_trading_cost(10000, "sell")
        assert sell_cost > buy_cost  # 卖出有印花税

    def test_empty_data_raises(self):
        engine = BacktestEngine(BacktestConfig())
        strategy = SimpleDCAStrategy()

        with pytest.raises(ValueError, match="价格数据为空"):
            engine.run(strategy, pd.DataFrame(), etf_code="test")

    def test_metrics_calculation(self, price_data: pd.DataFrame):
        engine = BacktestEngine(BacktestConfig())
        strategy = SimpleDCAStrategy({"amount": 1000, "frequency": "monthly"})
        result = engine.run(strategy, price_data, etf_code="510300")

        assert -1 <= result.total_return <= 10
        assert -1 <= result.annual_return <= 10
        assert 0 <= result.max_drawdown <= 1
