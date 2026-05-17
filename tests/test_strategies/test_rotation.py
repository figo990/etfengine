"""轮动策略单元测试"""

from datetime import date

import numpy as np
import pandas as pd

from src.strategies.rotation.bond_equity import BondEquityRotationStrategy
from src.strategies.rotation.dividend_rotation import DividendRotationStrategy
from src.strategies.rotation.sector_rotation import SectorRotationStrategy


class TestBondEquityRotation:
    def test_high_erp_full_equity(self):
        strategy = BondEquityRotationStrategy()
        weight = strategy._calc_target_weight(5.0)
        assert weight == 1.0

    def test_low_erp_full_bond(self):
        strategy = BondEquityRotationStrategy()
        weight = strategy._calc_target_weight(-2.0)
        assert weight == 0.0

    def test_mid_range(self):
        strategy = BondEquityRotationStrategy()
        assert strategy._calc_target_weight(2.0) == 0.7
        assert strategy._calc_target_weight(0.0) == 0.3

    def test_signal_generation(self):
        strategy = BondEquityRotationStrategy({"rebalance_frequency": "monthly"})
        prices = pd.DataFrame(
            {
                "trade_date": [date(2024, 1, 2)],
                "close": [4.0],
            }
        )
        signal = strategy.generate_signal(
            date(2024, 1, 2),
            prices,
            current_pe=12.0,
            bond_yield_10y=2.5,
            position_value=10000,
        )
        assert signal is not None
        assert "股债轮动" in signal.reason


class TestSectorRotation:
    def test_momentum_score(self):
        strategy = SectorRotationStrategy()
        np.random.seed(42)
        prices = pd.Series(100 + np.cumsum(np.random.randn(300) * 0.5))
        score = strategy._calc_momentum_score(prices)
        assert isinstance(score, float)

    def test_requires_enough_sectors(self):
        strategy = SectorRotationStrategy({"top_n": 3})
        prices = pd.DataFrame({"trade_date": [date(2024, 1, 2)], "close": [100]})
        # 只传入1个行业，不足top_n
        signal = strategy.generate_signal(
            date(2024, 1, 2),
            prices,
            sector_prices={"510230": pd.Series(range(300))},
        )
        assert signal is None


class TestDividendRotation:
    def test_switch_to_hk(self):
        strategy = DividendRotationStrategy({"switch_threshold": 0.05})
        prices = pd.DataFrame({"trade_date": [date(2024, 6, 1)], "close": [1.0]})

        np.random.seed(42)
        # A股红利大幅跑赢 → 切换到港股
        a = pd.Series(np.linspace(100, 120, 50))
        hk = pd.Series(np.linspace(80, 82, 50))

        signal = strategy.generate_signal(
            date(2024, 6, 1),
            prices,
            a_prices=a,
            hk_prices=hk,
            position_value=10000,
        )
        assert signal is not None
        assert "港股红利" in signal.reason
