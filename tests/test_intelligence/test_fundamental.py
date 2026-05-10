"""基本面分析模块测试"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.fundamental import FundamentalAnalyzer


class TestFundamentalAnalyzer:
    def setup_method(self):
        self.analyzer = FundamentalAnalyzer()

    def test_calc_roe_trend(self):
        pb = pd.Series(np.random.uniform(1.0, 2.0, 500))
        pe = pd.Series(np.random.uniform(10, 20, 500))
        roe = self.analyzer.calc_roe_trend(pb, pe)
        assert len(roe) == 500
        assert not roe.isna().all()
        valid = roe.dropna()
        assert (valid > 0).all()

    def test_calc_earnings_growth(self):
        pe = pd.Series(np.random.uniform(10, 20, 500))
        price = pd.Series(np.cumsum(np.random.randn(500) * 0.5) + 100)
        growth = self.analyzer.calc_earnings_growth(pe, price)
        assert len(growth) == 500

    def test_get_fundamental_snapshot_no_data(self):
        snapshot = self.analyzer.get_fundamental_snapshot(
            "测试指数",
            valuation_df=pd.DataFrame(),
        )
        assert snapshot["status"] == "no_data"

    def test_get_fundamental_snapshot_with_data(self):
        n = 300
        df = pd.DataFrame({
            "trade_date": pd.bdate_range("2023-01-01", periods=n).date,
            "pe": np.random.uniform(10, 18, n),
            "pb": np.random.uniform(1.0, 2.0, n),
            "dividend_yield": np.random.uniform(1.5, 3.5, n),
        })
        snapshot = self.analyzer.get_fundamental_snapshot("沪深300", df)
        assert snapshot["index_name"] == "沪深300"
        assert "pe" in snapshot
        assert "pb" in snapshot
        assert isinstance(snapshot["pe"], float)

    def test_get_fundamental_snapshot_roe_trend(self):
        n = 300
        pe_base = np.linspace(12, 14, n)
        pb_base = np.linspace(1.2, 1.5, n)
        df = pd.DataFrame({
            "trade_date": pd.bdate_range("2023-01-01", periods=n).date,
            "pe": pe_base + np.random.randn(n) * 0.1,
            "pb": pb_base + np.random.randn(n) * 0.01,
        })
        snapshot = self.analyzer.get_fundamental_snapshot("中证500", df)
        assert "roe_trend" in snapshot
        assert snapshot["roe_trend"] in ("改善", "恶化", "平稳")

    def test_compare_fundamentals_empty(self):
        result = self.analyzer.compare_fundamentals([])
        assert result.empty
