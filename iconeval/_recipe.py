"""Module that manages ESMValTool recipes."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from pathlib import Path

    from iconeval._simulation_info import SimulationInfo
    from iconeval._templates import RecipeTemplate
    from iconeval._typing import FacetType


class Recipe(NamedTuple):
    """Class representing an ESMValTool recipe."""

    path: Path
    template: RecipeTemplate
    simulations_info: list[SimulationInfo]
    timerange: FacetType

    @property
    def name(self) -> str:
        """Name of recipe."""
        return self.path.stem
