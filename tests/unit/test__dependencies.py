from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from iconeval._dependencies import (
    latex_is_available,
    verify_esmvaltool_installation,
    verify_slurm_installation,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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
