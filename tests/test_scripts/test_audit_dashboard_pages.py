from urllib.parse import quote

from scripts.audit_dashboard_pages import PAGES, _bad_text_matches, _is_ignorable_console_error
from src.dashboard.nav import WORKFLOW_NAV


def test_audit_pages_use_sidebar_routes():
    paths = {name: path for name, path, _, _ in PAGES}

    for _, links in WORKFLOW_NAV:
        for name, source_path in links:
            expected_path = "/" if source_path == "app.py" else "/" + quote(name, safe="")
            assert paths[name] == expected_path

    assert all(not path.startswith("/0") for path in paths.values())


def test_audit_pages_are_derived_from_workflow_nav():
    nav_names = [name for _, links in WORKFLOW_NAV for name, _ in links]
    audit_names = [name for name, _, _, _ in PAGES]

    assert audit_names == nav_names


def test_industry_chain_page_has_longer_wait_budget():
    pages = {name: (settle_ms, body_timeout_ms) for name, _, settle_ms, body_timeout_ms in PAGES}

    assert pages["产业链研究"] == (25_000, 30_000)


def test_bad_text_requires_exception_context():
    assert not _bad_text_matches("这是一篇介绍 KeyError 概念的技术文章。")
    assert _bad_text_matches('Traceback (most recent call last):\n  File "app.py", line 1')
    assert _bad_text_matches("KeyError: 'history_depth'")


def test_streamlit_deep_link_health_404_is_ignorable_console_noise():
    assert _is_ignorable_console_error(
        "Failed to load resource: the server responded with a status of 404 "
        "(Not Found) http://localhost:8501/估值与市场/_stcore/health"
    )
    assert _is_ignorable_console_error(
        "Failed to load resource: the server responded with a status of 404 (Not Found)"
    )
    assert not _is_ignorable_console_error("Uncaught TypeError: Cannot read properties")
