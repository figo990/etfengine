"""Tests for dashboard native navigation wiring."""

from __future__ import annotations

from src.dashboard.nav import WORKFLOW_NAV
from src.dashboard.navigation import iter_navigation_specs


def test_iter_navigation_specs_matches_workflow_nav() -> None:
    nav_labels = [label for _, links in WORKFLOW_NAV for label, _ in links]
    spec_labels = [label for _, label, _, _ in iter_navigation_specs()]
    assert spec_labels == nav_labels


def test_overview_page_is_default_in_specs() -> None:
    overview = next(spec for spec in iter_navigation_specs() if spec[1] == "总览")
    assert overview[2] == "pages/01_总览.py"
    assert overview[3] is True
