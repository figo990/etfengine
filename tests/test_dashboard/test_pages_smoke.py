"""Dashboard page smoke tests using Streamlit's app test harness."""

from __future__ import annotations

from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

import src.data.storage as storage_module


def test_home_and_report_pages_render_on_empty_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        storage_module,
        "settings",
        lambda: SimpleNamespace(database=SimpleNamespace(path=str(tmp_path / "smoke.duckdb"))),
    )

    pages = [
        "src/dashboard/app.py",
        "src/dashboard/pages/02_估值与市场.py",
        "src/dashboard/pages/03_策略实验室.py",
        "src/dashboard/pages/04_组合中心.py",
        "src/dashboard/pages/05_产业链研究.py",
        "src/dashboard/pages/06_资讯事件.py",
        "src/dashboard/pages/07_报告中心.py",
        "src/dashboard/pages/08_数据管理.py",
    ]
    for page in pages:
        app = AppTest.from_file(page)
        app.run(timeout=20)
        assert not app.exception
