"""Module that manages simulation metadata for model evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from ClimateEval import get_user_name

if TYPE_CHECKING:
    from pathlib import Path

    from ClimateEval._model_config import ModelConfig
    from ClimateEval._typing import FacetType


@dataclass
class SimulationInfo:
    """Information about a simulation directory.

    This class extracts and stores metadata about a simulation. It supports
    both auto-detection (for ICON backward compatibility) and user-provided
    model configurations for generic ESM support.

    """

    date: str
    exp: str
    grid_info: str
    guessed_facets: dict[str, FacetType]
    namelist_files: list[Path]
    owner: str
    path: Path
    model_config: ModelConfig | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        model_config: ModelConfig | None = None,
    ) -> SimulationInfo:
        """Load simulation info from simulation path.

        Parameters
        ----------
        path
            Path to the simulation directory.
        model_config
            Optional model configuration. If provided, uses its project
            and dataset settings. If None, falls back to ICON auto-detection.

        Returns
        -------
        SimulationInfo
            Extracted simulation metadata.

        """
        dir_stat = path.stat()

        # Date and time
        date = datetime.fromtimestamp(dir_stat.st_ctime).strftime(
            "%Y-%m-%d %H:%M:%S%z",
        )

        # Experiment name
        exp = path.name

        # Owner
        owner = get_user_name(dir_stat.st_uid)

        if model_config is not None:
            # Use model configuration provided by user
            grid_info = model_config.grid_info
            guessed_facets: dict[str, FacetType] = {
                "dataset": model_config.dataset,
                "exp": exp,
                "project": model_config.project,
            }
            # Merge any extra facets from model config
            guessed_facets.update(model_config.extra_facets)

            # Look for namelist files generically
            namelist_files = list(path.glob("NAMELIST_*")) + list(
                path.glob("namelist_*")
            )

            return cls(
                date=date,
                exp=exp,
                grid_info=grid_info,
                guessed_facets=guessed_facets,
                namelist_files=namelist_files,
                owner=owner,
                path=path,
                model_config=model_config,
            )

        # Fallback: ICON auto-detection (backward compatibility)
        return cls._from_path_icon(path, date, exp, owner)

    @classmethod
    def _from_path_icon(
        cls,
        path: Path,
        date: str,
        exp: str,
        owner: str,
    ) -> SimulationInfo:
        """ICON-specific auto-detection (original ICONEval behavior)."""
        # Grid information (e.g., R02B04, R02B05)
        grid_pattern = re.compile(r"R\d{2}B\d{2}")
        grid_info = "unknown"
        for grid_file in path.glob("icon_grid_*"):
            match = grid_pattern.search(grid_file.name)
            if match:
                grid_info = match.group(0)
                break

        # Guessed facets
        guessed_facets: dict[str, FacetType] = {
            "dataset": cls._guess_dataset_icon(path),
            "exp": exp,
            "project": cls._guess_project_icon(path),
        }

        # Namelist files
        namelist_files = list(path.glob("NAMELIST_*"))

        return cls(
            date=date,
            exp=exp,
            grid_info=grid_info,
            guessed_facets=guessed_facets,
            namelist_files=namelist_files,
            owner=owner,
            path=path,
            model_config=None,
        )

    @staticmethod
    def _guess_dataset_icon(path: Path) -> str:
        """Guess dataset facet for ICON."""
        # ICON-XPP
        namelist = path / "NAMELIST_ICON_output_atm"
        if namelist.is_file():
            namelist_content = namelist.read_text()
            if "ECHAM_" not in namelist_content:
                return "ICON-XPP"

        # Default
        return "ICON"

    @staticmethod
    def _guess_project_icon(path: Path) -> str:  # noqa: ARG004
        """Guess project facet for ICON."""
        return "ICON"
