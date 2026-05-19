"""报告自动生成脚本（周报/月报）"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

from src.analysis.fed_model import FEDModelAnalyzer
from src.analysis.fundamental import FundamentalAnalyzer
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.valuation import ValuationAnalyzer
from src.core.config import get_etf_universe, get_portfolio_config
from src.core.logging import setup_logging
from src.data.storage import StorageEngine


class ReportGenerator:
    """周报/月报生成器"""

    def __init__(self) -> None:
        self.storage = StorageEngine()
        self.valuation = ValuationAnalyzer()
        self.fed = FEDModelAnalyzer()
        self.sentiment = SentimentAnalyzer()
        self.fundamental = FundamentalAnalyzer()

    def generate_weekly_report(self, report_date: date | None = None) -> str:
        """生成周报"""
        today = report_date or date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = today

        lines = [
            "# ETFEngine 周报",
            f"**报告日期**: {today}",
            f"**报告周期**: {week_start} ~ {week_end}",
            "",
            "---",
            "",
            "## 一、市场概览",
            "",
        ]

        lines.extend(self._section_valuation_summary())
        lines.append("")
        lines.extend(self._section_etf_performance(week_start, week_end))
        lines.append("")
        lines.extend(self._section_industry_dynamics())
        lines.append("")
        lines.extend(self._section_fundamental_snapshot())
        lines.append("")
        lines.extend(self._section_signal_summary())
        lines.append("")
        lines.extend(self._section_portfolio_status())
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("> 本报告由 ETFEngine 自动生成，仅供研究参考，不构成投资建议。")

        report_content = "\n".join(lines)

        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        filepath = report_dir / f"weekly_{today.isoformat()}.md"
        filepath.write_text(report_content, encoding="utf-8")
        logger.info(f"周报已生成: {filepath}")

        return report_content

    def generate_monthly_report(self, report_date: date | None = None) -> str:
        """生成月报"""
        today = report_date or date.today()
        month_start = today.replace(day=1)

        lines = [
            "# ETFEngine 月报",
            f"**报告日期**: {today}",
            f"**报告月份**: {today.strftime('%Y年%m月')}",
            "",
            "---",
            "",
        ]

        lines.extend(self._section_valuation_summary())
        lines.append("")
        lines.extend(self._section_etf_performance(month_start, today))
        lines.append("")
        lines.extend(self._section_industry_dynamics())
        lines.append("")
        lines.extend(self._section_fundamental_snapshot())
        lines.append("")
        lines.extend(self._section_portfolio_status())
        lines.append("")
        lines.append("---")
        lines.append("> 本报告由 ETFEngine 自动生成，仅供研究参考，不构成投资建议。")

        report_content = "\n".join(lines)

        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        filepath = report_dir / f"monthly_{today.strftime('%Y%m')}.md"
        filepath.write_text(report_content, encoding="utf-8")
        logger.info(f"月报已生成: {filepath}")

        return report_content

    def _section_valuation_summary(self) -> list[str]:
        lines = ["## 估值快照", ""]
        indices = ["沪深300", "中证500", "中证1000", "中证红利"]

        lines.append("| 指数 | PE | PE百分位 | PB | 估值区间 |")
        lines.append("| --- | --- | --- | --- | --- |")

        for idx_name in indices:
            try:
                df = self.storage.get_index_valuation(idx_name)
                if df.empty:
                    continue
                snapshot = self.valuation.get_valuation_snapshot(df)
                lines.append(
                    f"| {idx_name} | {snapshot.get('pe', '-')} | "
                    f"{snapshot.get('pe_percentile', '-')}% | "
                    f"{snapshot.get('pb', '-')} | {snapshot.get('zone', '-')} |"
                )
            except Exception as e:
                logger.debug(f"指数 {idx_name} 估值数据跳过: {e}")

        return lines

    def _section_etf_performance(self, start: date, end: date) -> list[str]:
        lines = ["## ETF 表现", ""]
        universe = get_etf_universe()
        broad_etfs = universe.get("etf_universe", {}).get("broad_market", [])[:6]

        lines.append("| ETF | 区间涨跌幅 |")
        lines.append("| --- | --- |")

        for etf in broad_etfs:
            try:
                df = self.storage.get_etf_daily(etf["code"], str(start), str(end))
                if len(df) >= 2:
                    ret = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
                    lines.append(f"| {etf['name']} | {ret:.2f}% |")
            except Exception as e:
                logger.debug(f"ETF {etf.get('code')} 数据跳过: {e}")

        return lines

    def _section_industry_dynamics(self) -> list[str]:
        """行业动态板块"""
        lines = ["## 行业动态", ""]

        try:
            import json
            news_df = self.storage.get_news_articles(limit=50)
            if news_df.empty:
                lines.append("*(暂无新闻数据)*")
                return lines

            lines.append("### 近期重要新闻")
            lines.append("")
            lines.append("| 时间 | 标题 | 情绪 | 影响 | 行业 |")
            lines.append("| --- | --- | --- | --- | --- |")

            high_impact = news_df[news_df["impact_level"].isin(["high", "medium"])].head(10)
            for _, row in high_impact.iterrows():
                sectors_raw = row.get("related_sectors", "[]")
                if isinstance(sectors_raw, str):
                    try:
                        sectors = json.loads(sectors_raw)
                    except (json.JSONDecodeError, TypeError):
                        sectors = []
                else:
                    sectors = []
                sector_str = ", ".join(sectors) if sectors else "-"
                sent = float(row.get("sentiment", 0))
                sent_icon = "📈" if sent > 0.3 else ("📉" if sent < -0.3 else "➡️")
                lines.append(
                    f"| {row.get('publish_time', '-')} | {row.get('title', '')} | "
                    f"{sent_icon} {sent:+.2f} | {row.get('impact_level', '-')} | {sector_str} |"
                )
        except Exception as e:
            lines.append(f"*(行业动态加载失败: {e})*")

        return lines

    def _section_fundamental_snapshot(self) -> list[str]:
        """基本面快照"""
        lines = ["## 基本面概览", ""]

        try:
            indices = ["沪深300", "中证500", "创业板指", "中证红利"]
            compare_df = self.fundamental.compare_fundamentals(indices)
            if compare_df.empty:
                lines.append("*(基本面数据暂未采集)*")
                return lines

            lines.append("| 指数 | PE | PB | 股息率 | ROE趋势 | PE年变化 |")
            lines.append("| --- | --- | --- | --- | --- | --- |")

            for _, row in compare_df.iterrows():
                pe_change = row.get("pe_change_1y", "-")
                if isinstance(pe_change, (int, float)):
                    pe_change = f"{pe_change:+.1f}%"
                lines.append(
                    f"| {row.get('index_name', '-')} | "
                    f"{row.get('pe', '-')} | {row.get('pb', '-')} | "
                    f"{row.get('dividend_yield', '-')} | "
                    f"{row.get('roe_trend', '-')} | {pe_change} |"
                )
        except Exception as e:
            lines.append(f"*(基本面数据加载失败: {e})*")

        return lines

    def _section_signal_summary(self) -> list[str]:
        return [
            "## 本周信号汇总",
            "",
            "*(信号将在数据初始化后自动填充)*",
        ]

    def _section_portfolio_status(self) -> list[str]:
        portfolio_config = get_portfolio_config()
        holdings = portfolio_config.get("portfolio", {}).get("holdings", [])

        lines = ["## 组合状态", ""]
        lines.append("| ETF | 目标权重 |")
        lines.append("| --- | --- |")
        for h in holdings:
            lines.append(f"| {h.get('name', h['etf'])} | {h['target_weight']*100:.0f}% |")

        return lines


def main() -> None:
    setup_logging()

    import argparse
    parser = argparse.ArgumentParser(description="生成ETF投资报告")
    parser.add_argument("--type", choices=["weekly", "monthly"], default="weekly")
    parser.add_argument("--date", type=str, default=None, help="报告日期 YYYY-MM-DD")
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else date.today()
    generator = ReportGenerator()

    if args.type == "weekly":
        content = generator.generate_weekly_report(report_date)
    else:
        content = generator.generate_monthly_report(report_date)

    print(content)


if __name__ == "__main__":
    main()
