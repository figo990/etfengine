"""手动更新：外盘科技龙头季报（SEC EDGAR → DuckDB）"""

from __future__ import annotations

from src.core.logging import setup_logging
from src.intelligence.overseas_earnings_monitor import OverseasEarningsMonitor


def main() -> None:
    setup_logging()
    result = OverseasEarningsMonitor().run_cycle()
    print(result)


if __name__ == "__main__":
    main()
