"""FastAPI 应用入口"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import data, strategy

app = FastAPI(
    title="ETFEngine API",
    description="ETF 投资策略研究与管理工具 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(strategy.router)


@app.get("/")
def root():
    return {"name": "ETFEngine", "version": "0.1.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
