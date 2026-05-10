"""日志体系配置：基于 Loguru 的结构化日志"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from src.core.config import settings


def setup_logging() -> None:
    """初始化日志系统"""
    cfg = settings()
    log_dir = Path(cfg.app.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stderr,
        level=cfg.app.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
    )

    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} | {message}",
    )

    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="1 day",
        retention="90 days",
        encoding="utf-8",
    )

    logger.add(
        log_dir / "signals_{time:YYYY-MM-DD}.log",
        level="INFO",
        rotation="1 day",
        retention="365 days",
        encoding="utf-8",
        filter=lambda record: "signal" in record["extra"],
    )
