"""Module that manage types used in ModelEval."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

OptionValueType = str | int | float


FacetType = None | bool | str | Path | int | float | list | dict

RealmType = Literal[
    "all",
    "atmosphere",
    "ocean",
    "land",
    "sanity-consistency-checks",
]
