from pathlib import Path

import pytest


@pytest.fixture
def sample_data_path() -> Path:
    """Return path to sample data."""
    return Path(__file__).absolute().parent / "sample_data"
