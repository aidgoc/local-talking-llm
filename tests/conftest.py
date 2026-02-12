"""Shared test fixtures."""

import os
import sys
import tempfile

# Ensure project root is on sys.path so 'src' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.database import DatabaseManager


@pytest.fixture
def tmp_db():
    """Provide a temporary DatabaseManager instance, cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    db.init_db()
    yield db
    os.unlink(path)
