"""参数优化器：网格搜索 + Walk-Forward 验证"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd
from loguru import logger

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategies.base_strategy import BaseStrategy


@dataclass
class OptimizationResult:
    """优化结果"""

    best_params: dict[str, Any]
    best_metric: float
    metric_name: str
    all_results: list[dict]


class GridSearchOptimizer:
    """网格搜索参数优化器

    对策略参数空间进行遍历，找到最优参数组合。
    """

    def __init__(
        self,
        engine: BacktestEngine | None = None,
        optimize_metric: str = "sharpe_ratio",
    ) -> None:
        self.engine = engine or BacktestEngine()
        self.optimize_metric = optimize_metric

    def optimize(
        self,
        strategy_factory: Callable[[dict], BaseStrategy],
        param_grid: dict[str, list],
        price_data: pd.DataFrame,
        etf_code: str = "",
        **context,
    ) -> OptimizationResult:
        """网格搜索优化

        Args:
            strategy_factory: 接收参数字典，返回策略实例的工厂函数
            param_grid: {参数名: [候选值列表]}
            price_data: 价格数据
            etf_code: ETF代码
            context: 额外上下文

        Returns:
            OptimizationResult
        """
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        logger.info(f"网格搜索: {len(combinations)} 组参数组合")

        all_results: list[dict] = []
        best_metric = float("-inf")
        best_params: dict[str, Any] = {}

        for combo in combinations:
            params = dict(zip(keys, combo))
            try:
                strategy = strategy_factory(params)
                result = self.engine.run(strategy, price_data, etf_code, **context)
                metric_value = getattr(result, self.optimize_metric, 0.0)

                all_results.append(
                    {
                        "params": params,
                        "metric": metric_value,
                        "total_return": result.total_return,
                        "annual_return": result.annual_return,
                        "max_drawdown": result.max_drawdown,
                        "sharpe_ratio": result.sharpe_ratio,
                        "total_trades": result.total_trades,
                    }
                )

                if metric_value > best_metric:
                    best_metric = metric_value
                    best_params = params

            except Exception as e:
                logger.warning(f"参数组合 {params} 回测失败: {e}")

        all_results.sort(key=lambda x: x["metric"], reverse=True)

        logger.info(f"优化完成: 最优{self.optimize_metric}={best_metric:.4f}, 参数={best_params}")

        return OptimizationResult(
            best_params=best_params,
            best_metric=best_metric,
            metric_name=self.optimize_metric,
            all_results=all_results,
        )


class WalkForwardValidator:
    """Walk-Forward 前进验证

    将历史数据分为多个训练/测试窗口：
    [===训练===][=测试=]
         [===训练===][=测试=]
              [===训练===][=测试=]

    在训练窗口优化参数，在测试窗口验证，
    避免过拟合。
    """

    def __init__(
        self,
        train_days: int = 504,  # 2年训练
        test_days: int = 126,  # 半年测试
        step_days: int = 63,  # 1季度步进
        optimize_metric: str = "sharpe_ratio",
    ) -> None:
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.optimize_metric = optimize_metric

    def validate(
        self,
        strategy_factory: Callable[[dict], BaseStrategy],
        param_grid: dict[str, list],
        price_data: pd.DataFrame,
        etf_code: str = "",
        **context,
    ) -> dict:
        """执行 Walk-Forward 验证

        Returns:
            {
                windows: [{train_start, train_end, test_start, test_end, best_params, test_result}],
                overall_oos_return: 样本外综合收益率,
                stability_ratio: 参数稳定性指标
            }
        """
        price_data = price_data.sort_values("trade_date").reset_index(drop=True)
        all_dates = price_data["trade_date"].tolist()
        total_days = len(all_dates)

        if total_days < self.train_days + self.test_days:
            raise ValueError(
                f"数据不足: 需要{self.train_days + self.test_days}天, 实际{total_days}天"
            )

        windows = []
        start_idx = 0

        while start_idx + self.train_days + self.test_days <= total_days:
            train_end_idx = start_idx + self.train_days
            test_end_idx = min(train_end_idx + self.test_days, total_days)

            train_data = price_data.iloc[start_idx:train_end_idx].reset_index(drop=True)
            test_data = price_data.iloc[train_end_idx:test_end_idx].reset_index(drop=True)

            # 训练阶段：优化参数
            optimizer = GridSearchOptimizer(
                engine=BacktestEngine(BacktestConfig()),
                optimize_metric=self.optimize_metric,
            )
            opt_result = optimizer.optimize(
                strategy_factory, param_grid, train_data, etf_code, **context
            )

            # 测试阶段：用最优参数验证
            test_engine = BacktestEngine(BacktestConfig())
            strategy = strategy_factory(opt_result.best_params)

            try:
                test_result = test_engine.run(strategy, test_data, etf_code, **context)
                test_metrics = {
                    "total_return": test_result.total_return,
                    "annual_return": test_result.annual_return,
                    "max_drawdown": test_result.max_drawdown,
                    "sharpe_ratio": test_result.sharpe_ratio,
                }
            except Exception:
                test_metrics = {"total_return": 0, "sharpe_ratio": 0}

            windows.append(
                {
                    "train_start": str(all_dates[start_idx]),
                    "train_end": str(all_dates[train_end_idx - 1]),
                    "test_start": str(all_dates[train_end_idx]),
                    "test_end": str(all_dates[test_end_idx - 1]),
                    "best_params": opt_result.best_params,
                    "train_metric": opt_result.best_metric,
                    "test_metrics": test_metrics,
                }
            )

            start_idx += self.step_days

        # 汇总
        oos_returns = [w["test_metrics"]["total_return"] for w in windows]
        overall_oos = sum(oos_returns) / len(oos_returns) if oos_returns else 0

        # 参数稳定性：各窗口最优参数的一致性
        if len(windows) >= 2:
            param_sets = [str(sorted(w["best_params"].items())) for w in windows]
            unique_ratio = len(set(param_sets)) / len(param_sets)
            stability = 1.0 - unique_ratio  # 越高越稳定
        else:
            stability = 0.0

        return {
            "windows": windows,
            "num_windows": len(windows),
            "overall_oos_return": round(overall_oos, 4),
            "stability_ratio": round(stability, 3),
        }
