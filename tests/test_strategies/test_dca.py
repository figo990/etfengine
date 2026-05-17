"""定投策略单元测试"""

import pandas as pd
import pytest

from src.strategies.dca.ma_deviation_dca import MADeviationDCAStrategy
from src.strategies.dca.simple_dca import SimpleDCAStrategy
from src.strategies.dca.valuation_dca import ValuationDCAStrategy


@pytest.fixture
def sample_price_data() -> pd.DataFrame:
    """生成示例价格数据"""
    dates = pd.bdate_range(start="2023-01-01", end="2023-12-31")
    import numpy as np

    np.random.seed(42)
    prices = 4.0 + np.cumsum(np.random.randn(len(dates)) * 0.02)
    return pd.DataFrame(
        {
            "trade_date": dates.date,
            "open": prices * 0.99,
            "high": prices * 1.01,
            "low": prices * 0.98,
            "close": prices,
            "volume": [1000000] * len(dates),
            "amount": [5000000] * len(dates),
        }
    )


class TestSimpleDCA:
    def test_monthly_signal(self, sample_price_data: pd.DataFrame):
        strategy = SimpleDCAStrategy({"amount": 1000, "frequency": "monthly", "day_of_month": 1})
        signals = []

        for i in range(len(sample_price_data)):
            row_date = sample_price_data["trade_date"].iloc[i]
            historical = sample_price_data.iloc[: i + 1]
            signal = strategy.generate_signal(row_date, historical)
            if signal is not None:
                signals.append(signal)

        assert len(signals) == 12  # 12个月
        assert all(s.direction == "buy" for s in signals)
        assert all(s.amount == 1000 for s in signals)

    def test_weekly_signal(self, sample_price_data: pd.DataFrame):
        strategy = SimpleDCAStrategy({"amount": 500, "frequency": "weekly"})
        signals = []

        for i in range(len(sample_price_data)):
            row_date = sample_price_data["trade_date"].iloc[i]
            historical = sample_price_data.iloc[: i + 1]
            signal = strategy.generate_signal(row_date, historical)
            if signal is not None:
                signals.append(signal)

        assert len(signals) > 40  # 大约52周
        assert all(s.amount == 500 for s in signals)


class TestValuationDCA:
    def test_low_valuation_boost(self):
        strategy = ValuationDCAStrategy({"base_amount": 1000})
        multiplier = strategy._get_multiplier(15.0)  # PE百分位15%
        assert multiplier == 2.0

    def test_high_valuation_stop(self):
        strategy = ValuationDCAStrategy({"base_amount": 1000})
        multiplier = strategy._get_multiplier(85.0)  # PE百分位85%
        assert multiplier == 0.0

    def test_normal_valuation(self):
        strategy = ValuationDCAStrategy({"base_amount": 1000})
        multiplier = strategy._get_multiplier(50.0)
        assert multiplier == 1.0


class TestMADeviationDCA:
    def test_deep_below_ma(self):
        strategy = MADeviationDCAStrategy({"base_amount": 1000})
        multiplier = strategy._get_multiplier(-15.0)  # 偏离-15%
        assert multiplier == 4.0

    def test_above_ma_reduce(self):
        strategy = MADeviationDCAStrategy({"base_amount": 1000})
        multiplier = strategy._get_multiplier(15.0)  # 偏离+15%
        assert multiplier == 0.6

    def test_far_above_ma_stop(self):
        strategy = MADeviationDCAStrategy({"base_amount": 1000})
        multiplier = strategy._get_multiplier(35.0)  # 偏离+35%
        assert multiplier == 0.0
