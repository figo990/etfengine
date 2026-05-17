"""风险平价策略"""

from __future__ import annotations

import numpy as np
import pandas as pd
from loguru import logger
from scipy.optimize import minimize


class RiskParityAllocator:
    """风险平价配置器

    使各资产对组合总风险的贡献相等。
    波动率高的资产分配较低权重，波动率低的资产分配较高权重。
    """

    def __init__(self, lookback_days: int = 252) -> None:
        self.lookback_days = lookback_days

    def calc_weights(
        self,
        returns_df: pd.DataFrame,
    ) -> dict[str, float]:
        """计算风险平价权重

        Args:
            returns_df: DataFrame, columns=ETF代码, values=日收益率

        Returns:
            {etf_code: weight}
        """
        returns_df = returns_df.tail(self.lookback_days).dropna(axis=1, how="all")
        returns_df = returns_df.dropna()

        if returns_df.empty or len(returns_df.columns) < 2:
            # 不足以计算，等权分配
            n = len(returns_df.columns) or 1
            return {col: 1.0 / n for col in returns_df.columns}

        cov_matrix = returns_df.cov().values
        n = len(returns_df.columns)

        # 风险平价优化目标：最小化风险贡献差异
        def risk_budget_objective(weights: np.ndarray) -> float:
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            if portfolio_vol == 0:
                return 0.0
            marginal_risk = cov_matrix @ weights
            risk_contribution = weights * marginal_risk / portfolio_vol
            target_risk = portfolio_vol / n
            return np.sum((risk_contribution - target_risk) ** 2)

        x0 = np.ones(n) / n
        bounds = tuple((0.01, 0.5) for _ in range(n))
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        try:
            result = minimize(
                risk_budget_objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 1000, "ftol": 1e-12},
            )
            weights = result.x if result.success else x0
        except Exception as e:
            logger.warning(f"风险平价优化失败，使用等权: {e}")
            weights = x0

        weights = weights / weights.sum()
        return {col: round(float(w), 4) for col, w in zip(returns_df.columns, weights)}

    def calc_risk_metrics(
        self,
        returns_df: pd.DataFrame,
        weights: dict[str, float] | None = None,
    ) -> dict:
        """计算组合风险指标

        Returns:
            {portfolio_vol, individual_vols, correlations, risk_contributions}
        """
        returns_df = returns_df.tail(self.lookback_days).dropna()

        if returns_df.empty:
            return {}

        if weights is None:
            weights = self.calc_weights(returns_df)

        cols = [c for c in weights if c in returns_df.columns]
        w = np.array([weights[c] for c in cols])
        returns_subset = returns_df[cols]

        cov_matrix = returns_subset.cov().values
        corr_matrix = returns_subset.corr()

        portfolio_vol = np.sqrt(w @ cov_matrix @ w) * np.sqrt(252)
        individual_vols = returns_subset.std() * np.sqrt(252)

        # 风险贡献
        marginal = cov_matrix @ w
        risk_contrib_raw = w * marginal
        total_risk = np.sqrt(w @ cov_matrix @ w)
        risk_contribution = risk_contrib_raw / total_risk if total_risk > 0 else risk_contrib_raw

        return {
            "portfolio_vol": round(float(portfolio_vol), 4),
            "individual_vols": {col: round(float(v), 4) for col, v in zip(cols, individual_vols)},
            "correlation_matrix": corr_matrix.round(3).to_dict(),
            "risk_contributions": {
                col: round(float(rc), 4) for col, rc in zip(cols, risk_contribution * np.sqrt(252))
            },
            "weights": {col: weights[col] for col in cols},
        }

    def calc_max_sharpe_weights(
        self,
        returns_df: pd.DataFrame,
        risk_free_rate: float = 0.025,
    ) -> dict[str, float]:
        """最大夏普比率配置（对比用）"""
        returns_df = returns_df.tail(self.lookback_days).dropna()

        if returns_df.empty or len(returns_df.columns) < 2:
            n = len(returns_df.columns) or 1
            return {col: 1.0 / n for col in returns_df.columns}

        mean_returns = returns_df.mean().values * 252
        cov_matrix = returns_df.cov().values * 252
        n = len(returns_df.columns)
        rf = risk_free_rate

        def neg_sharpe(weights: np.ndarray) -> float:
            port_return = weights @ mean_returns
            port_vol = np.sqrt(weights @ cov_matrix @ weights)
            if port_vol == 0:
                return 0.0
            return -(port_return - rf) / port_vol

        x0 = np.ones(n) / n
        bounds = tuple((0.0, 0.5) for _ in range(n))
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        try:
            result = minimize(
                neg_sharpe,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
            )
            weights = result.x if result.success else x0
        except Exception:
            weights = x0

        weights = weights / weights.sum()
        return {col: round(float(w), 4) for col, w in zip(returns_df.columns, weights)}
