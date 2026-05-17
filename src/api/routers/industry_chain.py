"""产业链洞察 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.data.storage import StorageEngine
from src.intelligence.industry_chain_analyzer import IndustryChainAnalyzer

router = APIRouter(prefix="/api/industry-chain", tags=["产业链"])


@router.get("/list")
def list_industry_chains():
    """列出已配置产业链"""
    storage = StorageEngine()
    try:
        analyzer = IndustryChainAnalyzer(storage)
        return {"chains": analyzer.list_chains()}
    finally:
        storage.close()


@router.get("/compare/")
def compare_industry_chains(chain_ids: list[str] = Query(...)):
    """横向对比多个产业链"""
    storage = StorageEngine()
    try:
        storage.init_schema()
        analyzer = IndustryChainAnalyzer(storage)
        df = analyzer.compare_chains(chain_ids)
        return {"count": len(df), "data": df.to_dict("records")}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    finally:
        storage.close()


@router.get("/{chain_id}")
def get_industry_chain_snapshot(chain_id: str, link_news: bool = True):
    """获取产业链快照"""
    storage = StorageEngine()
    try:
        storage.init_schema()
        analyzer = IndustryChainAnalyzer(storage)
        return analyzer.build_snapshot(chain_id, link_news=link_news)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    finally:
        storage.close()
