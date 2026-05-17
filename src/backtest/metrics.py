"""绩效指标计算工具函数"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def calc_total_return(final_value: float, total_invested: float) -> float:
    """总收益率"""
    if total_invested <= 0:
        return 0.0
    return (final_value - total_invested) / total_invested


def calc_annual_return(total_return: float, days: int) -> float:
    """年化收益率"""
    if days <= 0:
        return 0.0
    years = days / 365.25
    return (1 + total_return) ** (1 / years) - 1


def calc_max_drawdown(values: pd.Series) -> float:
    """最大回撤"""
    if values.empty:
        return 0.0
    peak = values.expanding().max()
    drawdown = (values - peak) / peak
    return abs(drawdown.min())


def calc_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.025,
    periods_per_year: int = 252,
) -> float:
    """夏普比率"""
    if returns.empty or returns.std() == 0:
        return 0.0
    rf_per_period = risk_free_rate / periods_per_year
    excess = returns - rf_per_period
    return excess.mean() / excess.std() * np.sqrt(periods_per_year)


def calc_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.025,
    periods_per_year: int = 252,
) -> float:
    """索提诺比率"""
    if returns.empty:
        return 0.0
    rf_per_period = risk_free_rate / periods_per_year
    excess = returns - rf_per_period
    downside = excess[excess < 0]
    if downside.empty or downside.std() == 0:
        return 0.0
    return excess.mean() / downside.std() * np.sqrt(periods_per_year)


def calc_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    """卡玛比率"""
    if max_drawdown == 0:
        return 0.0
    return annual_return / max_drawdown


def calc_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    """年化波动率"""
    if returns.empty:
        return 0.0
    return returns.std() * np.sqrt(periods_per_year)


def calc_xirr(
    cashflows: list[tuple[date, float]],
    guess: float = 0.1,
) -> float:
    """计算 XIRR（精确年化收益率，适用于不定期现金流）

    Args:
        cashflows: [(date, amount), ...] 负数=投入，正数=回收
        guess: 初始猜测值
    """
    try:
        import pyxirr

        dates = [cf[0] for cf in cashflows]
        amounts = [cf[1] for cf in cashflows]
        result = pyxirr.xirr(dates, amounts)
        return result if result is not None else 0.0
    except Exception:
        return 0.0


def calc_win_rate(orders: list, final_value: float, total_invested: float) -> float:
    """胜率（简化版：定投场景以最终盈亏判断）"""
    if not orders or total_invested <= 0:
        return 0.0
    return 1.0 if final_value > total_invested else 0.0


def calc_information_ratio(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """信息比率"""
    if portfolio_returns.empty or benchmark_returns.empty:
        return 0.0
    active_returns = portfolio_returns - benchmark_returns
    tracking_error = active_returns.std()
    if tracking_error == 0:
        return 0.0
    return active_returns.mean() / tracking_error * np.sqrt(periods_per_year)


def calc_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """VaR (Value at Risk)"""
    if returns.empty:
        return 0.0
    return abs(np.percentile(returns, (1 - confidence) * 100))


def calc_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """CVaR (Conditional VaR / Expected Shortfall)"""
    if returns.empty:
        return 0.0
    var = np.percentile(returns, (1 - confidence) * 100)
    return abs(returns[returns <= var].mean())
