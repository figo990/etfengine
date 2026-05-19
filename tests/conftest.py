"""Shared pytest fixtures for stable local Windows runs."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path() -> Path:
    """Use a project-local temp root to avoid locked user temp/cache directories."""
    root = Path.cwd() / "tmp_check_all" / "pytest_cases"
    root.mkdir(parents=True, exist_ok=True)
    case_dir = root / uuid.uuid4().hex
    case_dir.mkdir()
    return case_dir
