"""FastAPI 应用入口"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.routers import data, data_management, industry_chain, strategy

app = FastAPI(
    title="ETFEngine API",
    description="ETF 投资策略研究与管理工具 API",
    version="0.1.0",
)

ALLOWED_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:8501,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常 [{request.method} {request.url.path}]: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务内部错误，请稍后重试"},
    )


app.include_router(data.router)
app.include_router(data_management.router)
app.include_router(strategy.router)
app.include_router(industry_chain.router)


@app.get("/")
def root():
    return {"name": "ETFEngine", "version": "0.1.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
