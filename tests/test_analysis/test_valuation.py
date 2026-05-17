"""估值分析模块测试"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.fed_model import FEDModelAnalyzer
from src.analysis.regression import RegressionAnalyzer
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.valuation import ValuationAnalyzer


class TestValuationAnalyzer:
    def test_percentile_calculation(self):
        analyzer = ValuationAnalyzer()
        pe = pd.Series(np.random.uniform(8, 20, 1260))
        result = analyzer.calc_percentile(pe, lookback_years=5)
        assert not result.isna().all()
        last = result.dropna().iloc[-1]
        assert 0 <= last <= 100

    def test_valuation_snapshot(self):
        analyzer = ValuationAnalyzer()
        df = pd.DataFrame(
            {
                "trade_date": pd.bdate_range("2019-01-01", periods=1260).date,
                "pe": np.random.uniform(8, 20, 1260),
                "pb": np.random.uniform(0.8, 2.0, 1260),
                "dividend_yield": np.random.uniform(1, 4, 1260),
            }
        )
        snapshot = analyzer.get_valuation_snapshot(df)
        assert "pe" in snapshot
        assert "zone" in snapshot
        assert snapshot["zone"] in ["极度低估", "低估", "适中", "高估", "极度高估"]


class TestFEDModel:
    def test_erp_calculation(self):
        analyzer = FEDModelAnalyzer()
        snapshot = analyzer.get_fed_snapshot(pe=12.0, cn_10y_yield=2.5)
        assert snapshot["earnings_yield"] == pytest.approx(8.33, abs=0.01)
        assert snapshot["cn_erp"] == pytest.approx(5.83, abs=0.01)
        assert snapshot["cn_signal"] in ["强烈看多", "偏多", "中性", "偏空", "强烈看空"]

    def test_allocation_suggestion(self):
        analyzer = FEDModelAnalyzer()
        result = analyzer.get_allocation_suggestion(cn_erp=5.0)
        assert result["equity_weight"] == 1.0


class TestSentiment:
    def test_sentiment_zones(self):
        analyzer = SentimentAnalyzer()
        assert analyzer.get_sentiment_snapshot(0.35)["zone"] == "泡沫"
        assert analyzer.get_sentiment_snapshot(-0.12)["zone"] == "底部"
        assert analyzer.get_sentiment_snapshot(0.05)["zone"] == "正常"

    def test_market_temperature(self):
        analyzer = SentimentAnalyzer()
        result = analyzer.calc_market_temperature(pe_percentile=20, erp=5.0, sentiment_value=-8)
        assert "temperature" in result
        assert 0 <= result["temperature"] <= 100


class TestRegression:
    def test_log_regression(self):
        analyzer = RegressionAnalyzer()
        np.random.seed(42)
        t = np.arange(1, 501, dtype=float)
        prices = pd.Series(np.exp(0.1 * np.log(t) + 7 + np.random.randn(500) * 0.05))
        result = analyzer.fit_log_regression(prices)
        assert "current_position" in result
        assert "r_squared" in result
        assert 0 < result["r_squared"] <= 1
