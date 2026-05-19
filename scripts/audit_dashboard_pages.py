"""Browser smoke audit for Streamlit dashboard pages."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from src.dashboard.nav import WORKFLOW_NAV

BASE_URL = os.getenv("DASHBOARD_AUDIT_BASE_URL", "http://localhost:8501")
STRICT_CONSOLE = os.getenv("DASHBOARD_AUDIT_STRICT_CONSOLE", "").lower() in {"1", "true", "yes"}
DEFAULT_SETTLE_MS = 4_000
DEFAULT_BODY_TIMEOUT_MS = 15_000
PAGE_WAIT_BUDGETS = {
    "产业链研究": (25_000, 30_000),
}
BAD_TEXT_PATTERNS = [
    re.compile(r"Traceback\s*\(most recent call last\)", re.IGNORECASE),
    re.compile(r'File\s+"[^"]+",\s+line\s+\d+', re.IGNORECASE),
    re.compile(r"(AttributeError|KeyError):\s+['\"]?[\w\u4e00-\u9fff]+", re.IGNORECASE),
    re.compile(r"更新失败[:：]\s*\S+"),
]


def _page_path(label: str) -> str:
    """URL path segment matching the dashboard sidebar label."""
    return "/" + quote(label, safe="")


def _route_for_page(label: str, rel_path: str) -> str:
    if label == "总览" or rel_path.endswith("01_总览.py"):
        return "/"
    return _page_path(label)


def _audit_pages() -> list[tuple[str, str, int, int]]:
    pages = []
    for _, links in WORKFLOW_NAV:
        for label, path in links:
            route = _route_for_page(label, path)
            settle_ms, body_timeout_ms = PAGE_WAIT_BUDGETS.get(
                label,
                (DEFAULT_SETTLE_MS, DEFAULT_BODY_TIMEOUT_MS),
            )
            pages.append((label, route, settle_ms, body_timeout_ms))
    return pages


PAGES = _audit_pages()


def _bad_text_matches(body: str) -> list[str]:
    return [pattern.pattern for pattern in BAD_TEXT_PATTERNS if pattern.search(body)]


def _is_ignorable_console_error(text: str) -> bool:
    """Return whether a browser console error is known Streamlit deep-link noise."""
    return (
        "Failed to load resource" in text
        and "404" in text
        and "Not Found" in text
    )


def main() -> None:
    out_dir = Path("tmp_page_audit")
    out_dir.mkdir(exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, path, settle_ms, body_timeout_ms in PAGES:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            console_errors: list[str] = []
            page.on(
                "console",
                lambda msg, errors=console_errors: errors.append(msg.text)
                if msg.type == "error"
                else None,
            )
            try:
                page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(settle_ms)
                body = page.locator("body").inner_text(timeout=body_timeout_ms)
                exception_count = page.locator('[data-testid="stException"]').count()
                bad = _bad_text_matches(body)
                (out_dir / f"{name}.txt").write_text(body, encoding="utf-8")
                page.screenshot(path=str(out_dir / f"{name}.png"), full_page=True)
                actionable_console_errors = [
                    error for error in console_errors if not _is_ignorable_console_error(error)
                ]
                ignored_console_errors = len(console_errors) - len(actionable_console_errors)
                print(
                    f"{name}: chars={len(body)}, stException={exception_count}, "
                    f"bad={bad or '-'}, console_errors={len(actionable_console_errors)}, "
                    f"ignored_console={ignored_console_errors}"
                )
                if actionable_console_errors:
                    (out_dir / f"{name}.console.txt").write_text(
                        "\n".join(actionable_console_errors),
                        encoding="utf-8",
                    )
                if exception_count or bad or (STRICT_CONSOLE and actionable_console_errors):
                    failures.append(name)
            except Exception as exc:
                failures.append(f"{name} ({type(exc).__name__}: {exc})")
                page.screenshot(path=str(out_dir / f"{name}.error.png"), full_page=True)
                print(f"{name}: ERROR {type(exc).__name__}: {exc}")
            finally:
                page.close()
        browser.close()

    if failures:
        raise SystemExit(f"Dashboard page audit failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
