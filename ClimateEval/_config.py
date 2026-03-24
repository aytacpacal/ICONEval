"""Module that manages ESMValTool configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from pathlib import Path

    from ClimateEval._simulation_info import SimulationInfo
    from ClimateEval._templates import ESMValToolConfigTemplate


class ESMValToolConfig(NamedTuple):
    """Represents an ESMValTool configuration file."""

    path: Path
    template: ESMValToolConfigTemplate
    simulations_info: list[SimulationInfo]
    output_dir: Path
    dask_config: dict[str, Any]

    @property
    def dir(self) -> Path:
        """Configuration directory."""
        return self.path.parent
