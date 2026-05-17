"""信号引擎：统一管理各策略的信号生成与分发"""

from __future__ import annotations

from datetime import date, datetime

from loguru import logger

from src.analysis.fed_model import FEDModelAnalyzer
from src.analysis.valuation import ValuationAnalyzer
from src.core.config import get_strategy_config
from src.data.models import TradeSignal
from src.data.storage import StorageEngine
from src.intelligence.news_monitor import NewsMonitor
from src.intelligence.sector_tracker import SectorTracker
from src.strategies.dca.ma_deviation_dca import MADeviationDCAStrategy


class SignalEngine:
    """每日信号生成引擎"""

    def __init__(self) -> None:
        self.storage = StorageEngine()
        self.valuation_analyzer = ValuationAnalyzer()
        self.fed_analyzer = FEDModelAnalyzer()
        self._news_monitor: NewsMonitor | None = None
        self._sector_tracker: SectorTracker | None = None

    def close(self) -> None:
        self.storage.close()

    def generate_daily_signals(self, target_date: date | None = None) -> list[TradeSignal]:
        """生成当日所有策略信号"""
        target = target_date or date.today()
        logger.bind(signal=True).info(f"开始生成 {target} 信号")

        signals: list[TradeSignal] = []

        try:
            dca_signals = self._generate_dca_signals(target)
            signals.extend(dca_signals)
        except Exception as e:
            logger.error(f"定投信号生成失败: {e}")

        try:
            valuation_signals = self._generate_valuation_alerts(target)
            signals.extend(valuation_signals)
        except Exception as e:
            logger.error(f"估值信号生成失败: {e}")

        try:
            news_signals = self._generate_news_sentiment_signals(target)
            signals.extend(news_signals)
        except Exception as e:
            logger.error(f"新闻情绪信号生成失败: {e}")

        for sig in signals:
            logger.bind(signal=True).info(
                f"信号: {sig.strategy_name} | {sig.etf_code} | "
                f"{sig.direction.value} | {sig.amount} | {sig.reason}"
            )

        if signals:
            self._persist_signals(signals)

        logger.bind(signal=True).info(f"共生成 {len(signals)} 条信号")
        return signals

    def _persist_signals(self, signals: list[TradeSignal]) -> None:
        """将信号写入数据库"""
        import pandas as pd

        rows = []
        for sig in signals:
            rows.append(
                {
                    "strategy_name": sig.strategy_name,
                    "etf_code": sig.etf_code,
                    "signal_date": sig.signal_date,
                    "direction": sig.direction.value,
                    "amount": sig.amount,
                    "reason": sig.reason,
                    "confidence": sig.confidence,
                    "generated_at": sig.generated_at,
                }
            )

        df = pd.DataFrame(rows)  # noqa: F841 - DuckDB replacement scan reads this variable.
        try:
            self.storage.conn.execute("""
                INSERT OR REPLACE INTO trade_signals (
                    strategy_name, etf_code, signal_date, direction,
                    amount, reason, confidence, generated_at
                ) SELECT strategy_name, etf_code, signal_date, direction,
                         amount, reason, confidence, generated_at
                FROM df
            """)
            logger.debug(f"已持久化 {len(signals)} 条信号到数据库")
        except Exception as e:
            logger.warning(f"信号持久化失败: {e}")

    def _generate_dca_signals(self, target_date: date) -> list[TradeSignal]:
        """生成定投信号"""
        signals = []
        strategy_config = get_strategy_config()
        dca_config = strategy_config.get("strategies", {}).get("dca", {})

        # 示例: 对沪深300生成均线偏离定投信号
        etf_codes = ["510300", "515080", "513100"]

        for code in etf_codes:
            try:
                price_df = self.storage.get_etf_daily(code)
                if price_df.empty:
                    continue

                ma_config = dca_config.get("ma_deviation", {})
                strategy = MADeviationDCAStrategy(
                    {
                        "base_amount": ma_config.get("base_amount", 1000),
                        "ma_period": ma_config.get("ma_period", 250),
                        "tiers": ma_config.get("tiers"),
                    }
                )

                signal = strategy.generate_signal(
                    current_date=target_date,
                    price_data=price_df,
                )

                if signal is not None:
                    signals.append(
                        TradeSignal(
                            strategy_name="均线偏离定投",
                            etf_code=code,
                            signal_date=target_date,
                            direction=TradeSignal.Direction.BUY,
                            amount=signal.amount,
                            reason=signal.reason,
                            generated_at=datetime.now(),
                        )
                    )
            except Exception as e:
                logger.warning(f"ETF {code} 定投信号生成失败: {e}")

        return signals

    def _generate_valuation_alerts(self, target_date: date) -> list[TradeSignal]:
        """生成估值预警信号"""
        signals = []

        index_etf_map = {
            "沪深300": "510300",
            "中证500": "510500",
            "中证红利": "515080",
        }

        for index_name, etf_code in index_etf_map.items():
            try:
                val_df = self.storage.get_index_valuation(index_name)
                if val_df.empty:
                    continue

                snapshot = self.valuation_analyzer.get_valuation_snapshot(val_df)
                pe_pctile = snapshot.get("pe_percentile")

                if pe_pctile is not None and pe_pctile < 20:
                    signals.append(
                        TradeSignal(
                            strategy_name="估值预警",
                            etf_code=etf_code,
                            signal_date=target_date,
                            direction=TradeSignal.Direction.BUY,
                            reason=f"{index_name} PE百分位{pe_pctile:.1f}% 极度低估",
                            confidence=0.8,
                            generated_at=datetime.now(),
                        )
                    )
                elif pe_pctile is not None and pe_pctile > 80:
                    signals.append(
                        TradeSignal(
                            strategy_name="估值预警",
                            etf_code=etf_code,
                            signal_date=target_date,
                            direction=TradeSignal.Direction.SELL,
                            reason=f"{index_name} PE百分位{pe_pctile:.1f}% 极度高估",
                            confidence=0.8,
                            generated_at=datetime.now(),
                        )
                    )
            except Exception as e:
                logger.warning(f"指数 {index_name} 估值预警生成失败: {e}")

        return signals

    def _generate_news_sentiment_signals(self, target_date: date) -> list[TradeSignal]:
        """新闻情绪极端时生成辅助信号"""
        signals = []

        if self._news_monitor is None:
            self._news_monitor = NewsMonitor()
        if self._sector_tracker is None:
            self._sector_tracker = SectorTracker()

        try:
            analyzed = self._news_monitor.run_cycle(use_llm=True)
        except Exception as e:
            logger.warning(f"LLM 新闻分析失败，降级为关键词模式: {e}")
            analyzed = self._news_monitor.run_cycle(use_llm=False)

        if not analyzed:
            return signals

        self.storage.upsert_news_articles(analyzed)

        heatmap = self._news_monitor.get_sector_heatmap(analyzed)
        alerts = self._sector_tracker.track(analyzed)

        from src.core.config import load_yaml_config

        intel_config = load_yaml_config("intelligence.yaml")
        sectors = intel_config.get("sectors", {})

        for sector_name, stats in heatmap.items():
            avg_sent = stats.get("avg_sentiment", 0)
            count = stats.get("count", 0)
            if count < 3:
                continue

            sector_info = sectors.get(sector_name, {})
            etf_codes = sector_info.get("etf_codes", [])
            if not etf_codes:
                continue

            etf_code = etf_codes[0]

            if avg_sent < -0.4:
                reason = f"{sector_name}行业连续利空({count}条, 情绪{avg_sent:+.2f}), 建议减仓"
                signals.append(
                    TradeSignal(
                        strategy_name="新闻情绪预警",
                        etf_code=etf_code,
                        signal_date=target_date,
                        direction=TradeSignal.Direction.SELL,
                        reason=reason,
                        confidence=min(abs(avg_sent), 0.9),
                        generated_at=datetime.now(),
                    )
                )
            elif avg_sent > 0.5:
                signals.append(
                    TradeSignal(
                        strategy_name="新闻情绪预警",
                        etf_code=etf_code,
                        signal_date=target_date,
                        direction=TradeSignal.Direction.BUY,
                        reason=f"{sector_name}行业情绪转多({count}条, 情绪{avg_sent:+.2f}), 可关注",
                        confidence=min(abs(avg_sent), 0.9),
                        generated_at=datetime.now(),
                    )
                )

        for sector_name, sector_alerts in alerts.items():
            high_impact = [a for a in sector_alerts if a.impact_score > 0.8]
            if not high_impact:
                continue

            sector_info = sectors.get(sector_name, {})
            etf_codes = sector_info.get("etf_codes", [])
            if not etf_codes:
                continue

            alert = high_impact[0]
            direction = (
                TradeSignal.Direction.BUY if alert.sentiment > 0 else TradeSignal.Direction.SELL
            )
            signals.append(
                TradeSignal(
                    strategy_name="政策预警",
                    etf_code=etf_codes[0],
                    signal_date=target_date,
                    direction=direction,
                    reason=f"[{sector_name}] {alert.title[:30]}",
                    confidence=min(alert.impact_score, 0.9),
                    generated_at=datetime.now(),
                )
            )

        return signals

    def get_latest_signals(self, strategy_name: str | None = None) -> list[TradeSignal]:
        """获取最近生成的信号（从数据库读取）"""
        try:
            conn = self.storage.conn
            query = "SELECT * FROM trade_signals ORDER BY signal_date DESC LIMIT 50"
            if strategy_name:
                query = (
                    "SELECT * FROM trade_signals WHERE strategy_name = ? "
                    "ORDER BY signal_date DESC LIMIT 50"
                )
                df = conn.execute(query, [strategy_name]).fetchdf()
            else:
                df = conn.execute(query).fetchdf()

            if df.empty:
                return []

            signals = []
            for _, row in df.iterrows():
                try:
                    signals.append(
                        TradeSignal(
                            strategy_name=row.get("strategy_name", ""),
                            etf_code=row.get("etf_code", ""),
                            signal_date=row.get("signal_date", date.today()),
                            direction=TradeSignal.Direction(row.get("direction", "buy")),
                            amount=row.get("amount"),
                            reason=row.get("reason", ""),
                            confidence=row.get("confidence"),
                            generated_at=row.get("generated_at", datetime.now()),
                        )
                    )
                except Exception as e:
                    logger.debug(f"解析信号记录失败: {e}")
                    continue
            return signals
        except Exception as e:
            logger.debug(f"读取历史信号失败（表可能不存在）: {e}")
            return []
