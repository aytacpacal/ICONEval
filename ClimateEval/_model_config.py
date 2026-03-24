"""Module that manages model configuration for generic ESM support.

Users provide a YAML file describing their model's output conventions,
or use the built-in ICON auto-detection for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from loguru import logger

if TYPE_CHECKING:
    from ClimateEval._typing import FacetType

logger = logger.opt(colors=True)


@dataclass
class DataSource:
    """Represents a single data source configuration for ESMValTool."""

    name: str
    rootpath: str
    dirname_template: str = ""
    filename_template: str = "*.nc"
    type: str = "esmvalcore.io.local.LocalDataSource"
    ignore_warnings: list[dict[str, str]] | None = None

    def to_esmvaltool_config(self) -> dict[str, Any]:
        """Convert to ESMValTool project data config entry."""
        config: dict[str, Any] = {
            "dirname_template": self.dirname_template,
            "filename_template": self.filename_template,
            "rootpath": self.rootpath,
            "type": self.type,
        }
        if self.ignore_warnings:
            config["ignore_warnings"] = self.ignore_warnings
        return config


@dataclass
class ModelConfig:
    """Configuration describing a model's output conventions.

    This is the central abstraction that allows ClimateEval to work with
    any ESM. Users provide a YAML file with this information, or use
    the built-in auto-detection for known models (ICON, EMAC).

    Parameters
    ----------
    project
        ESMValTool project name (e.g., "ICON", "EMAC", "CESM", "MPAS").
    dataset
        Dataset identifier (e.g., "ICON", "ICON-XPP", "CESM2").
    data_sources
        List of data source configurations describing where and how
        model output files are organized.
    extra_facets
        Additional facets to pass to ESMValTool (e.g., grid info).
    grid_info
        Optional grid information string.

    """

    project: str
    dataset: str
    data_sources: list[DataSource] = field(default_factory=list)
    extra_facets: dict[str, FacetType] = field(default_factory=dict)
    grid_info: str = "unknown"
    discovered_vars: list[str] = field(default_factory=list)
    """CMIP6 variable names available in this simulation (from auto-discovery)."""

    @classmethod
    def from_yaml(cls, path: Path) -> ModelConfig:
        """Load model configuration from a YAML file.

        Parameters
        ----------
        path
            Path to the model configuration YAML file.

        Returns
        -------
        ModelConfig
            Parsed model configuration.

        Raises
        ------
        FileNotFoundError
            If the YAML file does not exist.
        ValueError
            If required fields are missing.

        """
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            msg = f"Model configuration file '{path}' not found"
            raise FileNotFoundError(msg)

        logger.debug(f"Loading model configuration from {path}")
        with path.open() as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            msg = f"Model configuration file '{path}' must be a YAML mapping"
            raise ValueError(msg)

        # Required fields
        project = raw.get("project")
        if not project:
            msg = f"Model configuration file '{path}' must specify 'project'"
            raise ValueError(msg)

        dataset = raw.get("dataset", project)

        # Parse data sources
        data_sources: list[DataSource] = []
        raw_sources = raw.get("data_sources", {})
        if isinstance(raw_sources, dict):
            for name, source_config in raw_sources.items():
                if isinstance(source_config, dict):
                    data_sources.append(
                        DataSource(
                            name=name,
                            rootpath=str(source_config.get("rootpath", "")),
                            dirname_template=str(
                                source_config.get("dirname_template", "")
                            ),
                            filename_template=str(
                                source_config.get("filename_template", "*.nc")
                            ),
                            type=str(
                                source_config.get(
                                    "type",
                                    "esmvalcore.io.local.LocalDataSource",
                                )
                            ),
                            ignore_warnings=source_config.get("ignore_warnings"),
                        )
                    )

        # Parse extra facets
        extra_facets = raw.get("extra_facets", {})
        if not isinstance(extra_facets, dict):
            extra_facets = {}

        # Grid info
        grid_info = raw.get("grid_info", "unknown")

        return cls(
            project=project,
            dataset=dataset,
            data_sources=data_sources,
            extra_facets=extra_facets,
            grid_info=str(grid_info),
        )

    def build_data_source_for_exp(
        self, exp: str, simulation_path: Path
    ) -> list[DataSource]:
        """Build data sources with experiment-specific rootpath.

        If data_sources are defined in the config with explicit rootpaths,
        use those directly. Otherwise, generate default sources from the
        simulation path (similar to ICON behavior).

        Parameters
        ----------
        exp
            Experiment name.
        simulation_path
            Path to the simulation directory.

        Returns
        -------
        list[DataSource]
            Data sources ready for ESMValTool configuration.

        """
        if self.data_sources:
            # User provided explicit data sources; substitute {exp} in
            # templates and rootpath
            sources = []
            for ds in self.data_sources:
                rootpath = ds.rootpath.replace(
                    "{simulation_path}", str(simulation_path)
                )
                rootpath = rootpath.replace("{exp}", exp)
                sources.append(
                    DataSource(
                        name=ds.name.replace("{exp}", exp),
                        rootpath=rootpath,
                        dirname_template=ds.dirname_template,
                        filename_template=ds.filename_template,
                        type=ds.type,
                        ignore_warnings=ds.ignore_warnings,
                    )
                )
            return sources

        # Default: use simulation_path as rootpath with no dirname template
        # (backward compatible behavior for simple directory layouts)
        return [
            DataSource(
                name=exp,
                rootpath=str(simulation_path),
                dirname_template="",
                filename_template="*.nc",
            ),
        ]


def create_icon_config(
    exp: str,
    simulation_path: Path,
    dataset: str = "ICON",
) -> ModelConfig:
    """Create a ModelConfig for ICON simulations (backward compatibility).

    This replicates the original ICONEval auto-detection behavior.

    Parameters
    ----------
    exp
        Experiment name.
    simulation_path
        Path to the ICON simulation directory.
    dataset
        Dataset name (e.g., "ICON" or "ICON-XPP").

    Returns
    -------
    ModelConfig
        Model configuration for the ICON simulation.

    """
    data_sources = [
        DataSource(
            name=exp,
            rootpath=str(simulation_path),
            dirname_template="",
            filename_template="{exp}_{var_type}*.nc",
        ),
        DataSource(
            name=f"{exp}-outdata",
            rootpath=str(simulation_path),
            dirname_template="outdata",
            filename_template="{exp}_{var_type}*.nc",
        ),
        DataSource(
            name=f"{exp}-output",
            rootpath=str(simulation_path),
            dirname_template="output",
            filename_template="{exp}_{var_type}*.nc",
        ),
    ]
    return ModelConfig(
        project="ICON",
        dataset=dataset,
        data_sources=data_sources,
    )


def create_emac_config(
    exp: str,
    simulation_path: Path,
) -> ModelConfig:
    """Create a ModelConfig for EMAC simulations (backward compatibility).

    Parameters
    ----------
    exp
        Experiment name.
    simulation_path
        Path to the EMAC simulation directory.

    Returns
    -------
    ModelConfig
        Model configuration for the EMAC simulation.

    """
    data_sources = [
        DataSource(
            name=exp,
            rootpath=str(simulation_path),
            dirname_template="{channel}",
            filename_template="{exp}*{channel}{postproc_flag}.nc",
            ignore_warnings=[
                {
                    "message": r"Ignored formula of unrecognised type: .*",
                    "module": "iris",
                },
                {
                    "message": (
                        r"Ignoring formula terms variable .* referenced by "
                        "data variable .* via variable .*"
                    ),
                    "module": "iris",
                },
                {
                    "message": (
                        r"Missing CF-netCDF formula term variable .*, "
                        "referenced by netCDF variable .*"
                    ),
                    "module": "iris",
                },
                {
                    "message": (
                        r"NetCDF variable .* contains unknown cell method " r".*"
                    ),
                    "module": "iris",
                },
            ],
        ),
    ]
    return ModelConfig(
        project="EMAC",
        dataset="EMAC",
        data_sources=data_sources,
    )
