from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

import iconeval._dependencies
from iconeval._dependencies import (
    latex_is_available,
    verify_esmvaltool_installation,
    verify_slurm_installation,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_latex_is_available_true(patch_subprocess_run_return_0: Callable) -> None:
    assert latex_is_available() is True


def test_latex_is_available_false(patch_subprocess_run_return_1: Callable) -> None:
    assert latex_is_available() is False


def test_verify_esmvaltool_installation_success(
    patch_subprocess_run_return_0: Callable,
) -> None:
    verify_esmvaltool_installation("esmvaltool")


def test_verify_esmvaltool_installation_fail(
    patch_subprocess_run_return_1: Callable,
) -> None:
    msg = r"esmvaltool command not found"
    with pytest.raises(RuntimeError, match=msg):
        verify_esmvaltool_installation("esmvaltool")


def test_verify_slurm_installation_success(
    patch_subprocess_run_return_0: Callable,
) -> None:
    verify_slurm_installation("srun")


def test_verify_slurm_installation_fail(
    patch_subprocess_run_return_1: Callable,
) -> None:
    msg = r"srun command not found"
    with pytest.raises(RuntimeError, match=msg):
        verify_slurm_installation("srun")
