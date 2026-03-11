from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import iconeval._dependencies


@dataclass
class Process:
    returncode: int


class PatchedSubprocess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    def run(self, *_: Any, **__: Any) -> Process:
        return Process(returncode=self.returncode)


@pytest.fixture
def patch_subprocess_run_return_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iconeval._dependencies, "subprocess", PatchedSubprocess(0))


@pytest.fixture
def patch_subprocess_run_return_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(iconeval._dependencies, "subprocess", PatchedSubprocess(1))


@pytest.fixture
def sample_data_path() -> Path:
    """Return path to sample data."""
    return Path(__file__).absolute().parent / "sample_data"
