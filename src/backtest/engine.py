"""回测引擎：模拟策略在历史数据上的执行"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from loguru import logger

from src.core.config import settings
from src.strategies.base_strategy import BaseStrategy, TradeOrder


@dataclass
class BacktestConfig:
    """回测参数配置"""

    start_date: date | None = None
    end_date: date | None = None
    initial_cash: float = 0.0
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.001
    slippage_rate: float = 0.0001
    t_plus_1: bool = True


@dataclass
class DailyRecord:
    """每日记录"""

    trade_date: date
    price: float
    shares: float
    market_value: float
    cash: float
    total_value: float
    total_invested: float
    net_return: float = 0.0


@dataclass
class BacktestResult:
    """回测结果"""

    strategy_name: str
    etf_code: str
    start_date: date
    end_date: date
    daily_records: list[DailyRecord] = field(default_factory=list)
    orders: list[TradeOrder] = field(default_factory=list)

    # 绩效指标
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_invested: float = 0.0
    final_value: float = 0.0


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        if config is None:
            cfg = settings().backtest
            self.config = BacktestConfig(
                commission_rate=cfg.trading_cost.commission_rate,
                min_commission=cfg.trading_cost.min_commission,
                stamp_tax_rate=cfg.trading_cost.stamp_tax_rate,
                slippage_rate=cfg.trading_cost.slippage_rate,
                t_plus_1=cfg.rules.t_plus_1,
            )
        else:
            self.config = config

    def _calc_trading_cost(self, amount: float, direction: str) -> float:
        """计算交易成本（佣金 + 印花税 + 滑点）"""
        commission = max(amount * self.config.commission_rate, self.config.min_commission)
        stamp_tax = amount * self.config.stamp_tax_rate if direction == "sell" else 0.0
        slippage = amount * self.config.slippage_rate
        return commission + stamp_tax + slippage

    def _apply_slippage(self, price: float, direction: str) -> float:
        """应用滑点"""
        if direction == "buy":
            return price * (1 + self.config.slippage_rate)
        return price * (1 - self.config.slippage_rate)

    def run(
        self,
        strategy: BaseStrategy,
        price_data: pd.DataFrame,
        etf_code: str = "",
        **context,
    ) -> BacktestResult:
        """执行回测

        Args:
            strategy: 策略实例
            price_data: 包含 [trade_date, open, high, low, close, volume] 的 DataFrame
            etf_code: ETF代码
            context: 额外上下文数据（估值、收益率等）
        """
        strategy.reset()

        if price_data.empty:
            raise ValueError("价格数据为空")

        price_data = price_data.sort_values("trade_date").reset_index(drop=True)

        start = self.config.start_date or price_data["trade_date"].iloc[0]
        end = self.config.end_date or price_data["trade_date"].iloc[-1]

        mask = (price_data["trade_date"] >= start) & (price_data["trade_date"] <= end)
        data = price_data[mask].reset_index(drop=True)

        if data.empty:
            raise ValueError(f"指定日期范围 {start} ~ {end} 内无数据")

        logger.info(
            f"开始回测: {strategy.name} | {etf_code} | {start} ~ {end} | {len(data)} 交易日"
        )

        daily_records: list[DailyRecord] = []
        orders: list[TradeOrder] = []
        total_shares = 0.0
        total_invested = 0.0
        cash = self.config.initial_cash

        for i, row in data.iterrows():
            current_date = row["trade_date"]
            current_price = row["close"]
            historical = data.iloc[: int(i) + 1]

            signal = strategy.generate_signal(
                current_date=current_date,
                price_data=historical,
                **context,
            )

            signals_to_process = []
            if signal is not None:
                if isinstance(signal, list):
                    signals_to_process = signal
                else:
                    signals_to_process = [signal]

            for sig in signals_to_process:
                exec_price = self._apply_slippage(current_price, sig.direction)

                if sig.direction == "buy" and sig.amount > 0:
                    cost = self._calc_trading_cost(sig.amount, "buy")
                    actual_invest = sig.amount - cost
                    shares_bought = actual_invest / exec_price

                    total_shares += shares_bought
                    total_invested += sig.amount

                    filled_order = TradeOrder(
                        trade_date=current_date,
                        direction="buy",
                        amount=sig.amount,
                        price=exec_price,
                        shares=shares_bought,
                        reason=sig.reason,
                    )
                    orders.append(filled_order)
                    strategy.on_order_filled(filled_order)

                elif sig.direction == "sell" and sig.amount > 0:
                    shares_to_sell = min(sig.amount / exec_price, total_shares)
                    sell_amount = shares_to_sell * exec_price
                    cost = self._calc_trading_cost(sell_amount, "sell")
                    net_proceeds = sell_amount - cost

                    total_shares -= shares_to_sell
                    cash += net_proceeds

                    filled_order = TradeOrder(
                        trade_date=current_date,
                        direction="sell",
                        amount=net_proceeds,
                        price=exec_price,
                        shares=shares_to_sell,
                        reason=sig.reason,
                    )
                    orders.append(filled_order)
                    strategy.on_order_filled(filled_order)

            market_value = total_shares * current_price
            total_value = market_value + cash
            net_return = (
                (total_value - total_invested) / total_invested if total_invested > 0 else 0
            )

            daily_records.append(
                DailyRecord(
                    trade_date=current_date,
                    price=current_price,
                    shares=total_shares,
                    market_value=market_value,
                    cash=cash,
                    total_value=total_value,
                    total_invested=total_invested,
                    net_return=net_return,
                )
            )

        result = BacktestResult(
            strategy_name=strategy.name,
            etf_code=etf_code,
            start_date=start,
            end_date=end,
            daily_records=daily_records,
            orders=orders,
        )

        self._calc_metrics(result)
        return result

    def _calc_metrics(self, result: BacktestResult) -> None:
        """计算绩效指标"""
        if not result.daily_records:
            return

        records = result.daily_records
        result.total_invested = records[-1].total_invested
        result.final_value = records[-1].total_value
        result.total_trades = len(result.orders)

        if result.total_invested > 0:
            result.total_return = (
                result.final_value - result.total_invested
            ) / result.total_invested

        days = (result.end_date - result.start_date).days
        if days > 0 and result.total_invested > 0:
            years = days / 365.25
            result.annual_return = (1 + result.total_return) ** (1 / years) - 1

        # 最大回撤
        values = [r.total_value for r in records if r.total_value > 0]
        if values:
            peak = values[0]
            max_dd = 0.0
            for v in values:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak
                if dd > max_dd:
                    max_dd = dd
            result.max_drawdown = max_dd

        # 夏普比率 (假设无风险利率 2.5%)
        if len(values) > 1:
            returns = pd.Series(values).pct_change().dropna()
            if returns.std() > 0:
                risk_free_daily = 0.025 / 252
                excess_returns = returns - risk_free_daily
                result.sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

                # 索提诺比率
                downside_returns = excess_returns[excess_returns < 0]
                if len(downside_returns) > 0 and downside_returns.std() > 0:
                    result.sortino_ratio = (
                        excess_returns.mean() / downside_returns.std() * np.sqrt(252)
                    )

        # 卡玛比率
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annual_return / result.max_drawdown

        # 胜率（基于买卖配对）
        buy_orders = [o for o in result.orders if o.direction == "buy"]
        sell_orders = [o for o in result.orders if o.direction == "sell"]
        if sell_orders:
            paired = min(len(buy_orders), len(sell_orders))
            if paired > 0:
                wins = 0
                for j in range(paired):
                    if sell_orders[j].amount > buy_orders[j].amount:
                        wins += 1
                result.win_rate = wins / paired
            else:
                result.win_rate = 0.0
        elif buy_orders:
            result.win_rate = 1.0 if result.total_return > 0 else 0.0
