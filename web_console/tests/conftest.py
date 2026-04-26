"""Pytest configuration for web console tests"""
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from web_console.backend.config import BASE_DIR


@pytest.fixture
def project_root():
    """Project root directory"""
    return PROJECT_ROOT


@pytest.fixture
def web_console_root():
    """Web console backend directory"""
    return BASE_DIR / "web_console"