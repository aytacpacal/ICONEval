"""Module that manages file templates."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from iconeval._config import ESMValToolConfig
from iconeval._recipe import Recipe

if TYPE_CHECKING:
    from iconeval._simulation_info import SimulationInfo
    from iconeval._typing import FacetType, OptionValueType


class Template:
    """Base class for templates."""

    REQUIRED_PLACEHOLDERS: tuple[str, ...] = ()
    TEMPLATE_TYPE: str = "template"

    def __init__(self, path: Path, *, check_placeholders: bool = True) -> None:
        """Initialize class."""
        self._path = path
        self._content = self._get_content(check_placeholders=check_placeholders)

    def __repr__(self) -> str:
        """Return string representation of class instance."""
        return f"{self.__class__.__name__}(path={self.path!r})"

    @property
    def content(self) -> str:
        """Content of template file."""
        return self._content

    @property
    def name(self) -> str:
        """Name of template file."""
        return self._path.stem

    @property
    def path(self) -> Path:
        """Path to template file."""
        return self._path

    def _check_placeholders(self, content: str) -> None:
        """Check that required placeholders are present."""
        for placeholder in self.REQUIRED_PLACEHOLDERS:
            if placeholder not in content:
                msg = (
                    f"{self.path} is not a valid {self.TEMPLATE_TYPE}, it "
                    f"needs to include '{placeholder}'"
                )
                raise ValueError(msg)

    def _deep_replace(
        self,
        obj: Any,
        old_value: str,
        new_value: FacetType,
    ) -> Any:
        """Replace value with other value in nested object (in-place)."""
        new_obj: Any

        # For dicts and lists, call _deep_replace recursively
        if isinstance(obj, dict):
            new_obj = {}
            for key, val in obj.items():
                key = self._deep_replace(key, old_value, new_value)
                new_obj[key] = self._deep_replace(val, old_value, new_value)
        elif isinstance(obj, list):
            new_obj = []
            for elem in obj:
                new_obj.append(self._deep_replace(elem, old_value, new_value))

        # For strings, actually replace values
        elif isinstance(obj, str):
            if obj == old_value:
                new_obj = new_value
            else:
                new_obj = obj.replace(old_value, str(new_value))

        # Otherwise, just return original object
        else:
            new_obj = obj

        return new_obj

    def _fill_placeholders(
        self,
        yaml_obj: Any,
        placeholders: dict[str, FacetType],
    ) -> Any:
        """Fill placeholders in a YAML object."""
        yaml_obj = deepcopy(yaml_obj)
        for placeholder, value in placeholders.items():
            new_value: Any

            # Replace Paths with str since yaml.safe_dump() cannot handle them
            if isinstance(value, dict):
                new_value = {}
                for key, val in value.items():
                    if isinstance(key, Path):
                        key = str(key)
                    if isinstance(val, Path):
                        val = str(val)
                    new_value[key] = val
                value = new_value
            elif isinstance(value, list):
                new_value = []
                for elem in value:
                    if isinstance(elem, Path):
                        elem = str(elem)
                    new_value.append(elem)
                value = new_value
            elif isinstance(value, Path):
                value = str(value)

            yaml_obj = self._deep_replace(yaml_obj, placeholder, value)
        return yaml_obj

    def _get_content(self, *, check_placeholders: bool) -> str:
        """Read content of file and check validity."""
        content = self.path.read_text()
        if check_placeholders:
            self._check_placeholders(content)
        return content


class RecipeTemplate(Template):
    """Represents a recipe template."""

    REQUIRED_PLACEHOLDERS: tuple[str, ...] = ("{{dataset_list}}",)
    TEMPLATE_TYPE = "recipe template"

    DASK_OPTIONS_MARKER = "#DASK"
    ESMVALTOOL_OPTIONS_MARKER = "#ESMVALTOOL"
    SRUN_OPTIONS_MARKER = "#SRUN"
    TAGS_MARKER = "#TAGS"

    def __init__(self, path: Path, *, check_placeholders: bool = True) -> None:
        """Initialize class."""
        self._dask_options: dict[str, OptionValueType] | None = None
        self._esmvaltool_options: dict[str, OptionValueType] | None = None
        self._srun_options: dict[str, OptionValueType] | None = None
        self._tags: list[str] | None = None
        super().__init__(path, check_placeholders=check_placeholders)

    @property
    def dask_options(self) -> dict[str, OptionValueType]:
        """Additional dask options used to run this recipe."""
        if self._dask_options is None:
            self._dask_options = self._parse_additional_options(
                self.DASK_OPTIONS_MARKER,
                lstrip=True,
            )
        return self._dask_options

    @property
    def esmvaltool_options(self) -> dict[str, OptionValueType]:
        """Additional ESMValTool options used to run this recipe."""
        if self._esmvaltool_options is None:
            self._esmvaltool_options = self._parse_additional_options(
                self.ESMVALTOOL_OPTIONS_MARKER,
            )
        return self._esmvaltool_options

    @property
    def srun_options(self) -> dict[str, OptionValueType]:
        """Additional srun options used to run this recipe."""
        if self._srun_options is None:
            self._srun_options = self._parse_additional_options(
                self.SRUN_OPTIONS_MARKER,
            )
        return self._srun_options

    @property
    def tags(self) -> list[str]:
        """Recipe tags."""
        if self._tags is None:
            self._tags = self._parse_tags()
        return self._tags

    def get_recipe(
        self,
        path: Path,
        simulations_info: list[SimulationInfo],
        **extra_facets: FacetType,
    ) -> Recipe:
        """Get recipe from template."""
        default_facets: dict[str, FacetType] = {
            "supplementary_variables": [
                {"short_name": "areacella", "skip": True},
                {"short_name": "areacello", "skip": True},
                {"short_name": "sftlf", "skip": True},
                {"short_name": "sftof", "skip": True},
            ],
        }

        # Determine facets for all simulations
        dataset_list: list[dict[str, FacetType]] = [
            {**default_facets, **s.guessed_facets} for s in simulations_info
        ]

        # Facets given via command line always take priority
        for dataset in dataset_list:
            dataset.update(extra_facets)

        # Fill placeholders
        timerange = extra_facets.get("timerange", "*")
        placeholders: dict[str, FacetType] = {
            "{{dataset}}": extra_facets.get("dataset", "ICON"),
            "{{dataset_list}}": dataset_list,
            "{{project}}": extra_facets.get("project", "ICON"),
            "{{timerange}}": timerange,
        }
        recipe_yaml = yaml.safe_load(self.content)
        recipe_yaml = self._fill_placeholders(recipe_yaml, placeholders)
        recipe_yaml = self._fill_alias_plot_kwargs(
            recipe_yaml,
            simulations_info,
            extra_facets,
        )

        # Write recipe (incl. magic comments like #ESMVALTOOL)
        recipe_content: str = "# ESMValTool\n"
        for dask_key, dask_value in self.dask_options.items():
            recipe_content += f"{self.DASK_OPTIONS_MARKER} --{dask_key}={dask_value}\n"
        for (
            esmvaltool_key,
            esmvaltool_value,
        ) in self.esmvaltool_options.items():
            recipe_content += (
                f"{self.ESMVALTOOL_OPTIONS_MARKER} "
                f"{esmvaltool_key}={esmvaltool_value}\n"
            )
        for srun_key, srun_value in self.srun_options.items():
            recipe_content += f"{self.SRUN_OPTIONS_MARKER} {srun_key}={srun_value}\n"
        for tag in self.tags:
            recipe_content += f"{self.TAGS_MARKER} {tag}\n"
        recipe_content += "---\n"
        recipe_content += yaml.safe_dump(recipe_yaml, sort_keys=False)
        path.write_text(recipe_content, encoding="utf-8")

        return Recipe(path, self, simulations_info, timerange)

    def _fill_alias_plot_kwargs(
        self,
        obj: Any,
        simulations_info: list[SimulationInfo],
        extra_facets: dict[str, FacetType],
    ) -> Any:
        """Fill `{{alias_plot_kwargs}}` appropriately in recipe (in-place)."""
        # Possible aliases are:
        # -> {project}
        # -> {project}_{exp}
        # -> {project}_{dataset}
        # -> {project}_{dataset}_{exp}
        # These are determined by ESMValTool. For simplicity, we consider all
        # cases here (including dataset-specific facets and common facets).
        aliases: dict[FacetType, str] = {}  # map alias to color
        for idx, simulation_info in enumerate(simulations_info):
            exp = simulation_info.guessed_facets["exp"]
            if "project" in extra_facets:
                project = extra_facets["project"]
            else:
                project = simulation_info.guessed_facets["project"]
            if "dataset" in extra_facets:
                dataset = extra_facets["dataset"]
            else:
                dataset = simulation_info.guessed_facets["dataset"]
            color = f"C{idx}"

            # Avoid duplicates (always use first appearance)
            aliases.setdefault(project, color)
            aliases.setdefault(f"{project}_{exp}", color)
            aliases.setdefault(f"{project}_{dataset}", color)
            aliases.setdefault(f"{project}_{dataset}_{exp}", color)

        # Only replace {{alias_plot_kwargs}} if used as dictionary key
        new_obj: Any
        if isinstance(obj, dict):
            new_obj = {}
            for key, val in obj.items():
                val = self._fill_alias_plot_kwargs(
                    val,
                    simulations_info,
                    extra_facets,
                )
                if key == "{{alias_plot_kwargs}}":
                    for alias, color in aliases.items():
                        if isinstance(val, dict) and "color" not in val:
                            new_val = {**val, "color": color}
                        else:
                            new_val = val
                        new_obj[alias] = new_val
                else:
                    new_obj[key] = val

        elif isinstance(obj, list):
            new_obj = []
            for elem in obj:
                new_obj.append(
                    self._fill_alias_plot_kwargs(
                        elem,
                        simulations_info,
                        extra_facets,
                    ),
                )

        else:
            new_obj = obj

        return new_obj

    def _parse_additional_options(
        self,
        keyword: str,
        *,
        lstrip: bool = False,
    ) -> dict[str, OptionValueType]:
        """Parse additional options."""
        option_name = keyword.replace("#", "").lower()

        # Iterate over all recipe lines and find options
        options: dict[str, OptionValueType] = {}
        for line in self.content.split("\n"):
            original_line = line
            line = line.replace(" ", "")  # remove whitespace
            if not line.startswith(keyword):
                continue

            # Read option and check for errors
            line = line.replace(keyword, "")
            option = line.split("=")
            error_msg = (
                f"Invalid {option_name} option given in recipe template {self.path}: "
                f"'{original_line}', expected form '{keyword} --key=value' "
                f"(additional whitespace is fine)"
            )
            desired_option_length = 2
            if len(option) != desired_option_length:
                raise ValueError(error_msg)
            if not option[0].startswith("--"):
                raise ValueError(error_msg)

            # Try to cast option value to int/float and fill paths
            val: OptionValueType
            try:
                val = int(option[1])
            except ValueError:
                try:
                    val = float(option[1])
                except ValueError:
                    val = str(Path(os.path.expandvars(option[1])).expanduser())

            # Remove leading '--' if desired
            key = option[0].removeprefix("--") if lstrip else option[0]

            options[key] = val

        return options

    def _parse_tags(self) -> list[str]:
        """Parse tags."""
        tags: list[str] = []
        for line in self.content.split("\n"):
            if not line.startswith(self.TAGS_MARKER):
                continue
            tags.extend(line.replace(self.TAGS_MARKER, "").strip().split())
        return tags


class ESMValToolConfigTemplate(Template):
    """Represents an ESMValTool configuration template."""

    REQUIRED_PLACEHOLDERS: tuple[str, ...] = ()
    TEMPLATE_TYPE = "ESMValTool configuration template"

    def write_config(
        self,
        path: Path,
        simulations_info: list[SimulationInfo],
        output_dir: Path,
        dask_config: dict[str, Any],
    ) -> ESMValToolConfig:
        """Write ESMValTool configuration from template."""
        config_yaml = yaml.safe_load(self.content)

        # Add information from current ICONEval run
        config_yaml["dask"] = dask_config
        config_yaml["output_dir"] = str(output_dir)
        config_yaml = self._fill_projects(config_yaml, simulations_info)

        path.write_text(
            yaml.safe_dump(config_yaml, sort_keys=False),
            encoding="utf-8",
        )
        return ESMValToolConfig(
            path,
            self,
            simulations_info,
            output_dir,
            dask_config,
        )

    def _fill_projects(
        self,
        config_yaml: Any,
        simulations_info: list[SimulationInfo],
    ) -> Any:
        """Fill `projects` in ESMValTool configuration."""
        config_yaml = deepcopy(config_yaml)
        projects: dict[str, dict[str, Any]] = config_yaml.get("projects", {})

        # ICON
        icon_config: dict[str, Any] = {}
        for simulation_info in simulations_info:
            dirname_templates: dict[str, str] = {
                f"{simulation_info.exp}": "",
                f"{simulation_info.exp}-outdata": "outdata",
                f"{simulation_info.exp}-output": "output",
            }
            for data_name, dirname_template in dirname_templates.items():
                icon_config[data_name] = {
                    "dirname_template": dirname_template,
                    "filename_template": "{exp}_{var_type}*.nc",
                    "rootpath": str(simulation_info.path),
                    "type": "esmvalcore.io.local.LocalDataSource",
                }
        projects["ICON"] = {"data": icon_config}

        # EMAC
        emac_config: dict[str, Any] = {}
        for simulation_info in simulations_info:
            emac_config[simulation_info.exp] = {
                "dirname_template": "{channel}",
                "filename_template": "{exp}*{channel}{postproc_flag}.nc",
                "ignore_warnings": [
                    {
                        "message": r"Ignored formula of unrecognised type: .*",
                        "module": "iris",
                    },
                    {
                        "message": r"Ignoring formula terms variable .* referenced by "
                        "data variable .* via variable .*",
                        "module": "iris",
                    },
                    {
                        "message": r"Missing CF-netCDF formula term variable .*, "
                        "referenced by netCDF variable .*",
                        "module": "iris",
                    },
                    {
                        "message": r"NetCDF variable .* contains unknown cell method "
                        r".*",
                        "module": "iris",
                    },
                ],
                "rootpath": str(simulation_info.path),
                "type": "esmvalcore.io.local.LocalDataSource",
            }
        projects["EMAC"] = {"data": emac_config}

        config_yaml["projects"] = projects
        return config_yaml
