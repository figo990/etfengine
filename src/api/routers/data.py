"""数据 API 路由"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException

from src.data.storage import StorageEngine

router = APIRouter(prefix="/api/data", tags=["数据"])


@router.get("/etf/daily/{code}")
def get_etf_daily(
    code: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """获取 ETF 日线数据"""
    storage = StorageEngine()
    try:
        df = storage.get_etf_daily(code, start_date, end_date)
        if df.empty:
            raise HTTPException(404, f"未找到 ETF {code} 的数据")
        df["trade_date"] = df["trade_date"].astype(str)
        return {"code": code, "count": len(df), "data": df.to_dict("records")}
    finally:
        storage.close()


@router.get("/valuation/{index_name}")
def get_index_valuation(
    index_name: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """获取指数估值数据"""
    storage = StorageEngine()
    try:
        df = storage.get_index_valuation(index_name, start_date, end_date)
        if df.empty:
            raise HTTPException(404, f"未找到指数 {index_name} 的估值数据")
        df["trade_date"] = df["trade_date"].astype(str)
        return {"index_name": index_name, "count": len(df), "data": df.to_dict("records")}
    finally:
        storage.close()


@router.get("/bond-yield")
def get_bond_yield(
    start_date: str | None = None,
    end_date: str | None = None,
):
    """获取国债收益率"""
    storage = StorageEngine()
    try:
        df = storage.get_bond_yield(start_date, end_date)
        if df.empty:
            raise HTTPException(404, "未找到国债收益率数据")
        df["trade_date"] = df["trade_date"].astype(str)
        return {"count": len(df), "data": df.to_dict("records")}
    finally:
        storage.close()
