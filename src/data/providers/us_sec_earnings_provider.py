"""美股季报结构化数据：SEC EDGAR companyfacts（XBRL 汇总，非全文爬取）"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import requests
from loguru import logger

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "TotalRevenuesNetOfInterestExpense",
]
NET_INCOME_TAGS = [
    "NetIncomeLoss",
    "ProfitLoss",
    "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
    "IncomeLossFromContinuingOperations",
]
EPS_DILUTED_TAGS = [
    "EarningsPerShareDiluted",
    "EarningsPerShareBasic",
]


@dataclass
class QuarterlyFactPoint:
    """单条季报披露点（来自 SEC companyfacts）"""

    period_end: date
    fiscal_year: int
    fiscal_period: str
    form: str
    filed: date | None
    revenue: float | None
    net_income: float | None
    eps_diluted: float | None
    revenue_tag: str = ""
    net_income_tag: str = ""
    eps_tag: str = ""


class UsSecEarningsProvider:
    """从 SEC 拉取公司季报核心指标（需合规 User-Agent）"""

    _ticker_cik_cache: dict[str, int] | None = None

    def __init__(self, user_agent: str | None = None) -> None:
        self.user_agent = (
            user_agent
            or os.environ.get("SEC_EDGAR_USER_AGENT")
            or "ETFEngine/1.0 (research; contact: please-set-SEC_EDGAR_USER_AGENT)"
        )

    def _http_get_json(self, url: str) -> dict[str, Any]:
        host = "www.sec.gov" if "www.sec.gov" in url else "data.sec.gov"
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": host,
        }
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        return r.json()

    def load_ticker_cik_map(self, force: bool = False) -> dict[str, int]:
        if UsSecEarningsProvider._ticker_cik_cache is not None and not force:
            return UsSecEarningsProvider._ticker_cik_cache

        logger.info("[SEC] 加载 company_tickers.json …")
        data = self._http_get_json(SEC_TICKERS_URL)
        # 结构: {"0": {"cik_str": ..., "ticker": "AAPL", "title": "..."}, ...}
        m: dict[str, int] = {}
        for _k, v in data.items():
            if not isinstance(v, dict):
                continue
            t = str(v.get("ticker", "")).strip().upper()
            cik = v.get("cik_str")
            if t and cik is not None:
                m[t] = int(cik)
        UsSecEarningsProvider._ticker_cik_cache = m
        logger.info(f"[SEC] 已索引 {len(m)} 个 ticker")
        return m

    def resolve_cik(self, ticker: str, explicit_cik: int | None = None) -> int:
        if explicit_cik is not None:
            return int(explicit_cik)
        m = self.load_ticker_cik_map()
        t = ticker.strip().upper()
        if t not in m:
            raise ValueError(f"未知 ticker（SEC 列表中无）: {ticker}")
        return m[t]

    def fetch_company_facts(self, cik: int) -> dict[str, Any]:
        cik10 = str(cik).zfill(10)
        url = SEC_FACTS_URL.format(cik=cik10)
        time.sleep(0.15)  # 礼貌限速，避免触发 SEC 封禁
        return self._http_get_json(url)

    @staticmethod
    def _pick_usd_series(
        usgaap: dict[str, Any], tag: str, *, kind: str = "money"
    ) -> list[dict[str, Any]]:
        if tag not in usgaap:
            return []
        units = usgaap[tag].get("units") or {}
        if kind == "money":
            order = ("USD", "usd")
        else:
            # EPS 等每股指标
            order = ("USD/shares", "USD/shares/shares", "pure", "USD", "shares", "usd")
        for key in order:
            arr = units.get(key)
            if arr:
                return arr
        return []

    @staticmethod
    def _parse_filed(p: dict[str, Any]) -> date | None:
        raw = p.get("filed")
        if not raw:
            return None
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_end(p: dict[str, Any]) -> date | None:
        raw = p.get("end")
        if not raw:
            return None
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    def _extract_quarterly_points(
        self,
        facts: dict[str, Any],
        tags: list[str],
        metric: str,
    ) -> list[dict[str, Any]]:
        usgaap = facts.get("facts", {}).get("us-gaap", {})
        out: list[dict[str, Any]] = []
        kind = "money" if metric != "eps" else "per_share"
        for tag in tags:
            series = self._pick_usd_series(usgaap, tag, kind=kind)
            if not series:
                continue
            for p in series:
                fp = p.get("fp")
                if fp not in ("Q1", "Q2", "Q3", "Q4"):
                    continue
                form = str(p.get("form", ""))
                if form not in ("10-Q", "10-K"):
                    continue
                end = self._parse_end(p)
                if end is None:
                    continue
                val = p.get("val")
                if val is None:
                    continue
                try:
                    fv = float(val)
                except (TypeError, ValueError):
                    continue
                fy = int(p.get("fy", 0) or 0)
                if fy <= 0:
                    continue
                out.append(
                    {
                        "period_end": end,
                        "fiscal_year": fy,
                        "fiscal_period": fp,
                        "form": form,
                        "filed": self._parse_filed(p),
                        "val": fv,
                        "tag": tag,
                        "metric": metric,
                    }
                )
            if out:
                break
        return out

    def _dedupe_latest_filed(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """同一 (fy, fp) 或同一 period_end 保留 filed 最新的一条"""

        def key_fn(row: dict[str, Any]) -> tuple[int, str, date]:
            return row["fiscal_year"], row["fiscal_period"], row["period_end"]

        best: dict[tuple[int, str, date], dict[str, Any]] = {}
        for r in rows:
            k = key_fn(r)
            prev = best.get(k)
            if prev is None:
                best[k] = r
                continue
            fd = r.get("filed")
            pfd = prev.get("filed")
            if fd and (not pfd or fd >= pfd):
                best[k] = r
            elif not fd and not pfd and r.get("tag", "") > prev.get("tag", ""):
                best[k] = r
        return sorted(
            best.values(), key=lambda x: (x["period_end"], x["fiscal_year"], x["fiscal_period"])
        )

    @staticmethod
    def _index_by_fiscal_period(
        rows: list[dict[str, Any]],
    ) -> dict[tuple[int, str], dict[str, Any]]:
        """按 (fy, fp) 合并，同一财季保留 filed 最新"""
        best: dict[tuple[int, str], dict[str, Any]] = {}
        for r in rows:
            k = (r["fiscal_year"], r["fiscal_period"])
            prev = best.get(k)
            if prev is None:
                best[k] = r
                continue
            fd, pfd = r.get("filed"), prev.get("filed")
            if fd and (not pfd or fd >= pfd):
                best[k] = r
        return best

    def build_quarterly_table(self, facts: dict[str, Any]) -> list[QuarterlyFactPoint]:
        rev = self._extract_quarterly_points(facts, REVENUE_TAGS, "revenue")
        ni = self._extract_quarterly_points(facts, NET_INCOME_TAGS, "net_income")
        eps = self._extract_quarterly_points(facts, EPS_DILUTED_TAGS, "eps")

        rev_d = self._dedupe_latest_filed(rev)
        ni_d = self._dedupe_latest_filed(ni)
        eps_d = self._dedupe_latest_filed(eps)

        i_rev = self._index_by_fiscal_period(rev_d)
        i_ni = self._index_by_fiscal_period(ni_d)
        i_eps = self._index_by_fiscal_period(eps_d)
        keys = set(i_rev) | set(i_ni) | set(i_eps)

        merged: list[QuarterlyFactPoint] = []
        for fy, fp in sorted(
            keys, key=lambda x: (x[0], {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}.get(x[1], 0))
        ):
            r0 = i_rev.get((fy, fp))
            n0 = i_ni.get((fy, fp))
            e0 = i_eps.get((fy, fp))
            base = r0 or n0 or e0
            if not base:
                continue
            pend = base["period_end"]
            filed_dates = [x.get("filed") for x in (r0, n0, e0) if x and x.get("filed")]
            filed_max = max(filed_dates) if filed_dates else None
            merged.append(
                QuarterlyFactPoint(
                    period_end=pend,
                    fiscal_year=fy,
                    fiscal_period=fp,
                    form=str(base.get("form", "")),
                    filed=filed_max,
                    revenue=r0["val"] if r0 else None,
                    net_income=n0["val"] if n0 else None,
                    eps_diluted=e0["val"] if e0 else None,
                    revenue_tag=r0["tag"] if r0 else "",
                    net_income_tag=n0["tag"] if n0 else "",
                    eps_tag=e0["tag"] if e0 else "",
                )
            )
        merged.sort(key=lambda x: (x.period_end, x.fiscal_year, x.fiscal_period))
        return merged

    def fetch_quarterly_metrics(
        self, ticker: str, cik: int | None = None
    ) -> list[QuarterlyFactPoint]:
        cik_i = self.resolve_cik(ticker, cik)
        facts = self.fetch_company_facts(cik_i)
        return self.build_quarterly_table(facts)
