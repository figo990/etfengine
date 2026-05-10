"""网格策略单元测试"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.strategies.grid.equal_grid import EqualGridStrategy
from src.strategies.grid.geometric_grid import GeometricGridStrategy
from src.strategies.grid.atr_grid import ATRGridStrategy


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    dates = pd.bdate_range(start="2024-01-01", end="2024-06-30")
    np.random.seed(42)
    prices = 3.8 + np.cumsum(np.random.randn(len(dates)) * 0.02)
    prices = np.clip(prices, 3.0, 4.5)
    return pd.DataFrame({
        "trade_date": dates.date,
        "open": prices * 0.998,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": [1000000] * len(dates),
        "amount": [4000000] * len(dates),
    })


class TestEqualGrid:
    def test_grid_setup(self):
        strategy = EqualGridStrategy({
            "price_upper": 4.5,
            "price_lower": 3.0,
            "num_grids": 10,
        })
        strategy.reset()
        assert len(strategy._grid_lines) == 11
        assert strategy._grid_lines[0] == pytest.approx(3.0)
        assert strategy._grid_lines[-1] == pytest.approx(4.5)

    def test_initial_position(self, sample_prices: pd.DataFrame):
        strategy = EqualGridStrategy({
            "price_upper": 5.0,
            "price_lower": 3.0,
            "num_grids": 10,
            "amount_per_grid": 500,
            "initial_position_ratio": 0.5,
        })
        signal = strategy.generate_signal(
            date(2024, 1, 2), sample_prices.head(1)
        )
        assert signal is not None
        assert signal.direction == "buy"
        assert signal.reason == "网格初始建仓"

    def test_generates_trades(self, sample_prices: pd.DataFrame):
        strategy = EqualGridStrategy({
            "price_upper": 5.0,
            "price_lower": 3.0,
            "num_grids": 10,
            "amount_per_grid": 500,
        })
        signals = []
        for i in range(len(sample_prices)):
            d = sample_prices["trade_date"].iloc[i]
            sig = strategy.generate_signal(d, sample_prices.iloc[:i + 1])
            if sig:
                signals.append(sig)
        assert len(signals) >= 1  # 至少有初始建仓


class TestGeometricGrid:
    def test_grid_lines_are_geometric(self):
        strategy = GeometricGridStrategy({
            "price_upper": 4.0,
            "price_lower": 1.0,
            "num_grids": 4,
        })
        strategy.reset()
        lines = strategy._grid_lines
        assert len(lines) == 5
        assert lines[0] == pytest.approx(1.0)
        assert lines[-1] == pytest.approx(4.0)
        # 等比间距: 每段比值相等
        ratios = [lines[i + 1] / lines[i] for i in range(len(lines) - 1)]
        for r in ratios:
            assert r == pytest.approx(ratios[0], rel=1e-6)


class TestATRGrid:
    def test_atr_calculation(self, sample_prices: pd.DataFrame):
        strategy = ATRGridStrategy({"atr_period": 14})
        atr = strategy._calc_atr(sample_prices.head(20))
        assert atr > 0

    def test_initial_buy(self, sample_prices: pd.DataFrame):
        strategy = ATRGridStrategy({"atr_period": 14, "amount_per_grid": 500})
        sig = strategy.generate_signal(
            date(2024, 2, 1), sample_prices.head(20)
        )
        assert sig is not None
        assert sig.direction == "buy"
