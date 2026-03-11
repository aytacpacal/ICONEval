from __future__ import annotations

from typing import TYPE_CHECKING

from iconeval.main import icon_evaluation
from tests import assert_output

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_icon_evaluation_single_input(
    expected_output_dir: Path,
    tmp_path: Path,
    patched_subprocess_return_0: Callable,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_dir = icon_evaluation(input_dir, output_dir=output_dir)

    expected_output = expected_output_dir / "test_icon_evaluation_single_input"
    assert_output([input_dir], output_dir, expected_output)
