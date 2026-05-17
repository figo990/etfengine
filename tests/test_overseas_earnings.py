"""外盘季报模块单元测试（不访问外网）"""

from __future__ import annotations

from datetime import date

from src.analysis.earnings_analyzer import attach_yoy_metrics, build_fact_brief_cn
from src.data.providers.us_sec_earnings_provider import QuarterlyFactPoint, UsSecEarningsProvider


def test_build_quarterly_table_minimal_facts() -> None:
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2022-09-30",
                                "val": 90e9,
                                "fy": 2022,
                                "fp": "Q4",
                                "form": "10-K",
                                "filed": "2022-10-28",
                            },
                            {
                                "end": "2023-09-30",
                                "val": 89e9,
                                "fy": 2023,
                                "fp": "Q4",
                                "form": "10-K",
                                "filed": "2023-10-27",
                            },
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "end": "2022-09-30",
                                "val": 20e9,
                                "fy": 2022,
                                "fp": "Q4",
                                "form": "10-K",
                                "filed": "2022-10-28",
                            },
                            {
                                "end": "2023-09-30",
                                "val": 22e9,
                                "fy": 2023,
                                "fp": "Q4",
                                "form": "10-K",
                                "filed": "2023-10-27",
                            },
                        ]
                    }
                },
            }
        }
    }
    p = UsSecEarningsProvider(user_agent="ETFEngineTest/1.0 (test@example.com)")
    rows = p.build_quarterly_table(facts)
    assert len(rows) == 2
    assert rows[-1].fiscal_year == 2023
    assert rows[-1].revenue == 89e9


def test_attach_yoy_and_brief() -> None:
    pts = [
        QuarterlyFactPoint(
            date(2022, 9, 30),
            2022,
            "Q4",
            "10-K",
            date(2022, 10, 28),
            90e9,
            20e9,
            1.0,
            "R",
            "NI",
            "EPS",
        ),
        QuarterlyFactPoint(
            date(2023, 9, 30),
            2023,
            "Q4",
            "10-K",
            date(2023, 10, 27),
            89e9,
            22e9,
            1.1,
            "R",
            "NI",
            "EPS",
        ),
    ]
    rows = attach_yoy_metrics("DEMO", "演示公司", pts)
    last = max(rows, key=lambda r: r["period_end"])
    assert last["revenue_yoy_pct"] is not None
    assert abs(last["revenue_yoy_pct"] - (89 / 90 - 1) * 100) < 0.01
    brief = build_fact_brief_cn("DEMO", "演示公司", last)
    assert "演示公司" in brief
    assert "SEC" in brief


def test_storage_overseas_roundtrip(tmp_path) -> None:
    from src.data.storage import StorageEngine

    db = tmp_path / "t.duckdb"
    eng = StorageEngine(str(db))
    eng.init_schema()
    rows = [
        {
            "ticker": "ZZZ",
            "company_name": "测试",
            "period_end": date(2024, 6, 30),
            "fiscal_year": 2024,
            "fiscal_period": "Q2",
            "form": "10-Q",
            "filed_date": date(2024, 8, 1),
            "revenue_usd": 1e9,
            "net_income_usd": 1e8,
            "eps_diluted": 0.5,
            "revenue_yoy_pct": 10.0,
            "net_income_yoy_pct": 5.0,
            "revenue_tag": "R",
            "net_income_tag": "NI",
            "eps_tag": "E",
        }
    ]
    n = eng.upsert_overseas_earnings_metrics(rows)
    assert n == 1
    df = eng.get_overseas_earnings_metrics("ZZZ")
    assert len(df) == 1
    eng.upsert_overseas_earnings_analysis(
        [
            {
                "ticker": "ZZZ",
                "period_end": date(2024, 6, 30),
                "summary_zh": "测试摘要",
                "sentiment": 0.1,
                "impact_level": "low",
                "related_etf_codes": ["513100"],
                "fact_brief": "事实",
            }
        ]
    )
    da = eng.get_overseas_earnings_analysis("ZZZ")
    assert len(da) == 1
    eng.close()
