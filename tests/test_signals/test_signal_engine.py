"""Signal engine persistence tests."""

from __future__ import annotations

from datetime import date, datetime

from src.data.models import TradeSignal
from src.data.storage import StorageEngine
from src.signals.signal_engine import SignalEngine


def test_persist_signals_is_idempotent_by_strategy_etf_and_date(tmp_path):
    engine = SignalEngine()
    engine.storage.close()
    engine.storage = StorageEngine(db_path=str(tmp_path / "signals.duckdb"))
    engine.storage.init_schema()
    signal = TradeSignal(
        strategy_name="测试策略",
        etf_code="510300",
        signal_date=date(2026, 5, 17),
        direction=TradeSignal.Direction.BUY,
        amount=1000,
        reason="首次生成",
        generated_at=datetime(2026, 5, 17, 9, 0),
    )

    try:
        engine._persist_signals([signal])
        signal.reason = "重复生成更新"
        engine._persist_signals([signal])

        rows = engine.storage.conn.execute("SELECT * FROM trade_signals").fetchdf()
        assert len(rows) == 1
        assert rows["reason"].iloc[0] == "重复生成更新"
    finally:
        engine.close()
