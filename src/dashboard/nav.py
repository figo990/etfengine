"""Dashboard navigation structure (workflow grouping)."""

from __future__ import annotations

# (group label, [(label, page path relative to src/dashboard/)])
WORKFLOW_NAV: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "洞察",
        [
            ("总览", "app.py"),
            ("估值与市场", "pages/02_估值与市场.py"),
            ("产业链研究", "pages/05_产业链研究.py"),
        ],
    ),
    (
        "策略与组合",
        [
            ("策略实验室", "pages/03_策略实验室.py"),
            ("组合中心", "pages/04_组合中心.py"),
        ],
    ),
    (
        "资讯与报告",
        [
            ("资讯事件", "pages/06_资讯事件.py"),
            ("报告中心", "pages/07_报告中心.py"),
        ],
    ),
    (
        "系统",
        [
            ("数据管理", "pages/08_数据管理.py"),
        ],
    ),
]
