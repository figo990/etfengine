"""配置管理模块：加载、校验、访问全局配置"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class DatabaseConfig(BaseModel):
    engine: str = "duckdb"
    path: str = "data/db/etfengine.duckdb"
    sqlite_path: str = "data/db/etfengine.sqlite"


class RetryConfig(BaseModel):
    max_attempts: int = 3
    wait_seconds: int = 5


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 30


class CacheConfig(BaseModel):
    enabled: bool = True
    ttl_hours: int = 4


class DataSourceConfig(BaseModel):
    primary: str = "akshare"
    fallback: str = "baostock"
    retry: RetryConfig = Field(default_factory=RetryConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


class TradingCostConfig(BaseModel):
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.001
    slippage_rate: float = 0.0001


class TradingRulesConfig(BaseModel):
    t_plus_1: bool = True
    price_limit: bool = True


class BacktestConfig(BaseModel):
    default_start_date: str = "2018-01-01"
    default_end_date: str | None = None
    trading_cost: TradingCostConfig = Field(default_factory=TradingCostConfig)
    rules: TradingRulesConfig = Field(default_factory=TradingRulesConfig)


class SchedulerConfig(BaseModel):
    daily_update_time: str = "18:30"
    signal_generate_time: str = "19:00"
    industry_chain_update_time: str = "20:10"
    data_quality_check_time: str = "20:30"
    industry_chain_history_days: int = 183
    dashboard_task_cleanup_time: str = "21:10"
    dashboard_task_retention_days: int = 30
    weekly_report_enabled: bool = True
    weekly_report_time: str = "21:30"
    weekly_report_day: str = "fri"
    monthly_report_enabled: bool = True
    monthly_report_time: str = "21:45"


class DataHealthConfig(BaseModel):
    market_data_max_age_days: int = 3
    news_max_age_days: int = 2
    company_fundamentals_max_age_days: int = 150
    company_forecasts_max_age_days: int = 150
    overseas_earnings_max_age_days: int = 150
    recent_gap_lookback_days: int = 45
    recent_gap_tolerance_days: int = 0
    recent_failure_window_hours: int = 24


class AppConfig(BaseModel):
    name: str = "ETFEngine"
    version: str = "0.1.0"
    log_level: str = "INFO"
    log_dir: str = "data/logs"
    timezone: str = "Asia/Shanghai"


class NotifyChannelConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    webhook_url: str = ""

    model_config = {"extra": "allow"}


class NotifyConfig(BaseModel):
    enabled: bool = False
    channels: dict[str, NotifyChannelConfig] = Field(default_factory=dict)


class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    data_health: DataHealthConfig = Field(default_factory=DataHealthConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)


def load_yaml_config(filename: str) -> dict[str, Any]:
    """加载 YAML 配置文件"""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"配置文件不存在: {filepath}")
    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_settings() -> Settings:
    """获取全局配置（带校验）"""
    raw = load_yaml_config("settings.yaml")
    return Settings(**raw)


def get_etf_universe() -> dict[str, Any]:
    """获取 ETF 标的池配置"""
    return load_yaml_config("etf_universe.yaml")


def get_strategy_config() -> dict[str, Any]:
    """获取策略参数配置"""
    return load_yaml_config("strategies.yaml")


def get_portfolio_config() -> dict[str, Any]:
    """获取组合配置"""
    return load_yaml_config("portfolio.yaml")


def get_industry_chain_config() -> dict[str, Any]:
    """获取产业链配置"""
    return load_yaml_config("industry_chains.yaml")


_settings: Settings | None = None


def settings() -> Settings:
    """全局单例 Settings 访问"""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings
