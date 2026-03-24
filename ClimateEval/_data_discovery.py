"""Data discovery module for ClimateEval.

Scans ESM simulation directories, inspects NetCDF files, and auto-generates a
ModelConfig that can be used directly by ClimateEval / ESMValTool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from ClimateEval._model_config import DataSource, ModelConfig

logger = logger.opt(colors=True)

# ---------------------------------------------------------------------------
# Date-string patterns found in typical ESM output filenames
# ---------------------------------------------------------------------------
_DATE_PATTERNS = [
    re.compile(r"\d{8}"),        # YYYYMMDD
    re.compile(r"\d{6}"),        # YYYYMM
    re.compile(r"\d{4}-\d{2}-\d{2}"),  # YYYY-MM-DD
    re.compile(r"\d{4}-\d{2}"),  # YYYY-MM
    re.compile(r"\d{4}_\d{2}"),  # YYYY_MM
    re.compile(r"\d{4}"),        # YYYY (standalone year)
]

# Coordinate name sets used for grid-type detection
_LATLON_1D = {"lat", "lon", "latitude", "longitude"}
_LATLON_NAMES = {"lat", "lon", "latitude", "longitude", "nav_lat", "nav_lon"}
_UNSTRUCTURED_DIMS = {"ncells", "cell", "nCells", "ncol"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FileGroup:
    """A group of files sharing the same directory and naming pattern."""

    dirname: str          # relative subdirectory from sim_path
    pattern: str          # glob pattern that matches these files
    example_file: Path    # one representative file from this group
    variables: list[str]  # climate variables found in these files
    frequency: str        # detected temporal frequency for this group


@dataclass
class DiscoveredDataInfo:
    """All information discovered from scanning a simulation directory."""

    sim_path: Path
    exp_name: str
    nc_files: list[Path]           # all NetCDF files found
    file_groups: list[FileGroup]   # files grouped by directory + pattern
    variable_names: list[str]      # unique variable names across all files
    global_attrs: dict             # merged global attributes from sampled files
    grid_type: str                 # "regular_latlon" | "curvilinear" | "unstructured" | "unknown"
    detected_frequency: str        # "mon" | "day" | "6hr" | "3hr" | "1hr" | "fx" | "unknown"
    model_name: str | None         # from global attrs (e.g. "source", "model_id")
    institution: str | None        # from global attrs


# ---------------------------------------------------------------------------
# DataInspector
# ---------------------------------------------------------------------------

class DataInspector:
    """Inspects ESM simulation directories and produces ModelConfig objects."""

    # Maximum directory depth to recurse into
    MAX_DEPTH: int = 5
    # How many files per group to sample for metadata
    SAMPLE_PER_GROUP: int = 3
    # If total files > this threshold, only sample a subset
    LARGE_DIR_THRESHOLD: int = 100
    LARGE_DIR_SAMPLE: int = 10

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def scan(self, sim_path: Path) -> DiscoveredDataInfo:
        """Recursively scan *sim_path* and return a DiscoveredDataInfo.

        Parameters
        ----------
        sim_path:
            Root directory of the ESM simulation.

        Returns
        -------
        DiscoveredDataInfo
            Complete metadata about the simulation layout.
        """
        sim_path = Path(sim_path).expanduser().resolve()
        if not sim_path.is_dir():
            msg = f"Simulation path '{sim_path}' is not a directory"
            raise NotADirectoryError(msg)

        logger.info(f"Scanning simulation directory: <cyan>{sim_path}</cyan>")

        # ---- collect all *.nc files up to MAX_DEPTH levels deep -----------
        nc_files = self._collect_nc_files(sim_path)
        logger.debug(f"Found {len(nc_files)} NetCDF file(s)")

        # ---- group by directory + naming pattern --------------------------
        file_groups = self._group_files_by_pattern(nc_files, sim_path)
        logger.debug(f"Identified {len(file_groups)} file group(s)")

        # ---- inspect a sample of files ------------------------------------
        all_variables: list[str] = []
        merged_attrs: dict[str, Any] = {}
        grid_types: list[str] = []
        frequencies: list[str] = []

        for group in file_groups:
            # Sample a few files from each group
            candidates = list(
                sim_path.glob(
                    (group.dirname + "/" if group.dirname else "") + group.pattern
                )
            )
            sample = candidates[: self.SAMPLE_PER_GROUP]
            if not sample:
                sample = [group.example_file]

            group_vars: list[str] = []
            group_freqs: list[str] = []
            for fpath in sample:
                info = self._inspect_nc_file(fpath)
                if info is None:
                    continue
                group_vars.extend(info["variables"])
                merged_attrs.update(info["attrs"])
                grid_types.append(info.get("grid_type", "unknown"))
                group_freqs.append(info.get("frequency", "unknown"))

            # Deduplicate group variables and store
            group.variables = list(dict.fromkeys(group_vars))
            # Use most common frequency in group
            group.frequency = self._most_common(group_freqs) or "unknown"

            all_variables.extend(group_vars)
            frequencies.append(group.frequency)

        # ---- overall summary stats ----------------------------------------
        unique_vars = list(dict.fromkeys(all_variables))
        overall_freq = self._most_common(frequencies) or "unknown"
        overall_grid = self._most_common(
            [g for g in grid_types if g != "unknown"]
        ) or ("unstructured" if grid_types else "unknown")

        model_name = (
            merged_attrs.get("model_id")
            or merged_attrs.get("source_id")
            or merged_attrs.get("source")
            or merged_attrs.get("model")
        )
        institution = (
            merged_attrs.get("institution")
            or merged_attrs.get("institution_id")
        )

        return DiscoveredDataInfo(
            sim_path=sim_path,
            exp_name=sim_path.name,
            nc_files=nc_files,
            file_groups=file_groups,
            variable_names=unique_vars,
            global_attrs=merged_attrs,
            grid_type=overall_grid,
            detected_frequency=overall_freq,
            model_name=str(model_name) if model_name else None,
            institution=str(institution) if institution else None,
        )

    # -----------------------------------------------------------------------
    # NetCDF inspection
    # -----------------------------------------------------------------------

    def _inspect_nc_file(self, path: Path) -> dict | None:
        """Open a single NetCDF file and extract metadata.

        Uses xarray with ``decode_times=False`` to avoid calendar issues.
        Falls back to netCDF4 if xarray is unavailable.

        Returns
        -------
        dict with keys: variables, dims, attrs, file_path, grid_type, frequency
        None if the file cannot be read.
        """
        try:
            import xarray as xr  # noqa: PLC0415

            ds = xr.open_dataset(str(path), decode_times=False, engine="netcdf4")
            return self._extract_from_xarray(ds, path)
        except Exception as exc_xr:
            logger.warning(
                f"xarray failed on <yellow>{path.name}</yellow>: {exc_xr!s} — "
                "trying netCDF4 fallback"
            )

        try:
            import netCDF4 as nc  # noqa: PLC0415

            return self._extract_from_netcdf4(nc.Dataset(str(path), "r"), path)
        except Exception as exc_nc:
            logger.warning(
                f"Cannot read <yellow>{path.name}</yellow>: {exc_nc!s} — skipping"
            )
            return None

    def _extract_from_xarray(self, ds: Any, path: Path) -> dict:
        """Extract metadata from an open xarray Dataset."""
        # Coordinate / bound names to exclude from climate variables
        coord_names = set(ds.coords)
        bound_names = {
            v for v in ds.data_vars
            if v.endswith("_bnds") or v.endswith("_bounds") or v == "time_bnds"
        }
        variables = [
            v for v in ds.data_vars
            if v not in coord_names and v not in bound_names
        ]

        dims = list(ds.dims)
        attrs = dict(ds.attrs)

        # Frequency from time coordinate
        frequency = "fx"
        if "time" in ds.coords and ds.coords["time"].size > 1:
            time_vals = ds.coords["time"].values
            time_units = ds.coords["time"].attrs.get("units", "")
            frequency = self._detect_frequency(time_vals, str(time_units))

        grid_type = self._detect_grid_type(ds)
        ds.close()

        return {
            "variables": variables,
            "dims": dims,
            "attrs": attrs,
            "file_path": path,
            "grid_type": grid_type,
            "frequency": frequency,
        }

    def _extract_from_netcdf4(self, ds: Any, path: Path) -> dict:
        """Extract metadata from an open netCDF4.Dataset."""
        coord_names = set(ds.dimensions)
        variables = [
            v for v in ds.variables
            if v not in coord_names
            and not v.endswith("_bnds")
            and not v.endswith("_bounds")
        ]
        dims = list(ds.dimensions)
        attrs = {k: getattr(ds, k) for k in ds.ncattrs()}

        # Frequency detection via time variable
        frequency = "fx"
        if "time" in ds.variables and ds.variables["time"].size > 1:
            time_var = ds.variables["time"]
            time_vals = time_var[:]
            time_units = getattr(time_var, "units", "")
            frequency = self._detect_frequency(time_vals, str(time_units))

        # Grid detection: check variable names for lat/lon
        var_names_lower = {v.lower() for v in ds.variables}
        has_lat = "lat" in var_names_lower or "latitude" in var_names_lower
        has_lon = "lon" in var_names_lower or "longitude" in var_names_lower
        has_ncells = any(d in _UNSTRUCTURED_DIMS for d in dims)

        if has_ncells and not (has_lat and has_lon):
            grid_type = "unstructured"
        elif has_lat and has_lon:
            # Check dimensionality
            lat_var = ds.variables.get("lat") or ds.variables.get("latitude")
            grid_type = "curvilinear" if lat_var and lat_var.ndim > 1 else "regular_latlon"
        else:
            grid_type = "unknown"

        ds.close()

        return {
            "variables": variables,
            "dims": dims,
            "attrs": attrs,
            "file_path": path,
            "grid_type": grid_type,
            "frequency": frequency,
        }

    # -----------------------------------------------------------------------
    # Frequency detection
    # -----------------------------------------------------------------------

    def _detect_frequency(self, time_values: Any, time_units: str) -> str:
        """Estimate output frequency from the time coordinate.

        Parameters
        ----------
        time_values:
            Raw numeric time values (decoded_times=False).
        time_units:
            CF units string, e.g. "days since 1850-01-01".

        Returns
        -------
        str
            One of "mon", "day", "6hr", "3hr", "1hr", "fx", "unknown".
        """
        try:
            import numpy as np  # noqa: PLC0415

            arr = np.asarray(time_values, dtype=float)
            if arr.size < 2:
                return "fx"

            # Determine scale factor relative to days
            units_lower = time_units.lower()
            if "hour" in units_lower:
                scale = 1.0 / 24.0
            elif "minute" in units_lower:
                scale = 1.0 / (24.0 * 60.0)
            elif "second" in units_lower:
                scale = 1.0 / (24.0 * 3600.0)
            else:
                scale = 1.0  # assume days

            diffs = np.diff(arr) * scale
            median_step = float(np.median(diffs[diffs > 0])) if (diffs > 0).any() else 0.0

            if median_step <= 0:
                return "unknown"
            if median_step >= 28:    # monthly (28–31 day months)
                return "mon"
            if 1.9 <= median_step < 28:  # multi-day (2-day to sub-monthly)
                return "day"
            if 0.9 <= median_step <= 1.1:
                return "day"
            if 0.24 <= median_step <= 0.26:
                return "6hr"
            if 0.12 <= median_step <= 0.13:
                return "3hr"
            if 0.04 <= median_step <= 0.045:
                return "1hr"
            return "unknown"
        except Exception as exc:
            logger.debug(f"Frequency detection failed: {exc}")
            return "unknown"

    # -----------------------------------------------------------------------
    # Grid-type detection
    # -----------------------------------------------------------------------

    def _detect_grid_type(self, ds: Any) -> str:
        """Detect grid type from an xarray Dataset's coordinate structure.

        Parameters
        ----------
        ds:
            An open xarray Dataset.

        Returns
        -------
        str
            "regular_latlon", "curvilinear", "unstructured", or "unknown".
        """
        coord_names = {c.lower() for c in ds.coords}
        dim_names = set(ds.dims)

        # Unstructured: ICON-style ncells dimension, no regular lat/lon
        if _UNSTRUCTURED_DIMS & dim_names:
            lat_present = bool(_LATLON_NAMES & {c.lower() for c in ds.coords})
            if not lat_present:
                return "unstructured"

        # Check for lat/lon coordinates
        has_lat = any(c in coord_names for c in ("lat", "latitude", "nav_lat"))
        has_lon = any(c in coord_names for c in ("lon", "longitude", "nav_lon"))
        if not (has_lat and has_lon):
            return "unknown"

        # Determine dimensionality of lat coordinate
        lat_coord_name = next(
            (c for c in ds.coords if c.lower() in ("lat", "latitude", "nav_lat")),
            None,
        )
        if lat_coord_name is not None:
            lat_dims = ds.coords[lat_coord_name].dims
            if len(lat_dims) == 1:
                return "regular_latlon"
            if len(lat_dims) >= 2:
                return "curvilinear"

        return "regular_latlon"

    # -----------------------------------------------------------------------
    # File grouping
    # -----------------------------------------------------------------------

    def _collect_nc_files(self, sim_path: Path) -> list[Path]:
        """Recursively collect *.nc files up to MAX_DEPTH below sim_path."""
        nc_files: list[Path] = []
        self._walk(sim_path, sim_path, depth=0, result=nc_files)
        return sorted(nc_files)

    def _walk(self, root: Path, current: Path, depth: int, result: list[Path]) -> None:
        if depth > self.MAX_DEPTH:
            return
        try:
            for entry in current.iterdir():
                if entry.is_file() and entry.suffix == ".nc":
                    result.append(entry)
                elif entry.is_dir() and not entry.name.startswith("."):
                    self._walk(root, entry, depth + 1, result)
        except PermissionError as exc:
            logger.warning(f"Permission denied: {exc}")

    def _group_files_by_pattern(
        self, nc_files: list[Path], sim_path: Path
    ) -> list[FileGroup]:
        """Group NetCDF files by subdirectory and detect a common pattern.

        The pattern is derived by:
        1. Replacing the experiment name (sim_path.name) with ``{exp}``.
        2. Replacing known variable names with ``{short_name}``.
        3. Replacing date strings with ``*``.

        Parameters
        ----------
        nc_files:
            All NetCDF files found under sim_path.
        sim_path:
            Root simulation directory (used for relative dirname and exp name).

        Returns
        -------
        list[FileGroup]
        """
        exp_name = sim_path.name

        # Group files by their parent directory
        by_dir: dict[str, list[Path]] = {}
        for f in nc_files:
            try:
                rel_dir = str(f.parent.relative_to(sim_path))
            except ValueError:
                rel_dir = ""
            if rel_dir == ".":
                rel_dir = ""
            by_dir.setdefault(rel_dir, []).append(f)

        groups: list[FileGroup] = []

        for dirname, files in by_dir.items():
            # Large directory: only sample for pattern detection
            sample = files[: self.LARGE_DIR_SAMPLE] if len(files) > self.LARGE_DIR_THRESHOLD else files

            # Build a representative pattern from sampled file names
            patterns: list[str] = []
            for f in sample:
                stem = f.stem
                # Replace exp name occurrence
                stem = stem.replace(exp_name, "{exp}")
                # Replace date-like substrings
                for date_re in _DATE_PATTERNS:
                    stem = date_re.sub("*", stem)
                # Collapse consecutive wildcards
                while "**" in stem:
                    stem = stem.replace("**", "*")
                patterns.append(stem + f.suffix)

            # Choose the most-common pattern as the group representative
            pattern = self._most_common(patterns) or "*.nc"

            groups.append(
                FileGroup(
                    dirname=dirname,
                    pattern=pattern,
                    example_file=files[0],
                    variables=[],   # filled in during scan()
                    frequency="unknown",
                )
            )

        return groups

    # -----------------------------------------------------------------------
    # ModelConfig construction
    # -----------------------------------------------------------------------

    def to_model_config(self, info: DiscoveredDataInfo) -> ModelConfig:
        """Convert a DiscoveredDataInfo into a ModelConfig.

        Parameters
        ----------
        info:
            Output of :meth:`scan`.

        Returns
        -------
        ModelConfig
            Ready-to-use model configuration.
        """
        dataset = info.model_name or info.exp_name
        attrs = info.global_attrs

        # Heuristic: if files contain CMIP6-style global attributes → CMIP6
        is_cmip6 = bool(
            attrs.get("mip_era") == "CMIP6"
            or attrs.get("activity_id")
            or attrs.get("source_id")
        )
        project = "CMIP6" if is_cmip6 else "UNKNOWN"

        # Build one DataSource per FileGroup
        data_sources: list[DataSource] = []
        for idx, group in enumerate(info.file_groups):
            name = f"group_{idx:02d}" if not group.dirname else group.dirname.replace("/", "_")
            data_sources.append(
                DataSource(
                    name=name,
                    rootpath=str(info.sim_path),
                    dirname_template=group.dirname,
                    filename_template=group.pattern,
                )
            )

        if not data_sources:
            # Fallback: single catch-all source
            data_sources = [
                DataSource(
                    name=info.exp_name,
                    rootpath=str(info.sim_path),
                    dirname_template="",
                    filename_template="*.nc",
                )
            ]

        extra_facets: dict[str, Any] = {}
        if info.detected_frequency not in ("unknown", "fx"):
            extra_facets["frequency"] = info.detected_frequency
        if info.grid_type != "unknown":
            extra_facets["grid_type"] = info.grid_type

        # Populate discovered_vars: map model variable names to CMIP6 names
        from ClimateEval._variable_mapping import VariableMapper  # noqa: PLC0415
        mapper = VariableMapper()
        discovered_vars: list[str] = []
        for var_name in info.variable_names:
            mapping = mapper.map_variable(var_name)
            if mapping is not None and mapping.cmip6_name not in discovered_vars:
                discovered_vars.append(mapping.cmip6_name)

        return ModelConfig(
            project=project,
            dataset=dataset,
            data_sources=data_sources,
            extra_facets=extra_facets,
            grid_info=info.grid_type,
            discovered_vars=discovered_vars,
        )

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _most_common(items: list[str]) -> str | None:
        """Return the most frequently occurring item in *items*, or None."""
        if not items:
            return None
        return max(set(items), key=items.count)


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def discover_model_config(sim_path: Path, exp_name: str | None = None) -> ModelConfig:
    """Scan *sim_path*, preprocess for CF compliance, and return a ModelConfig.

    This is the main entry point for the data-discovery subsystem. It is
    intended to be called by ``SimulationInfo.from_path()`` as a fallback
    when no explicit model config is provided.

    The function:
    1. Scans the directory for NetCDF files and detects structure/variables.
    2. Runs the CF preprocessor to fix dimension order, coordinate attributes,
       variable names, and unit conversions — writing fixed files to
       ``{sim_path}/.climateeval_preprocessed/``.
    3. Returns a ModelConfig pointing at the preprocessed directory so that
       ESMValTool can load data without further manual preparation.

    Parameters
    ----------
    sim_path:
        Root directory of the ESM simulation.
    exp_name:
        Optional experiment name override. If omitted, ``sim_path.name`` is
        used (consistent with :meth:`SimulationInfo.from_path`).

    Returns
    -------
    ModelConfig
        Auto-generated model configuration based on directory scan.
    """
    sim_path = Path(sim_path).expanduser().resolve()
    inspector = DataInspector()
    info = inspector.scan(sim_path)
    if exp_name:
        info.exp_name = exp_name

    # Run CF preprocessor: fix dimensions, coordinates, rename variables
    try:
        from ClimateEval._preprocessor import preprocess_simulation  # noqa: PLC0415
        logger.info(
            "Running CF preprocessor on <magenta>{}</magenta> ...", sim_path
        )
        prep_result = preprocess_simulation(sim_path, info.variable_names)
        if prep_result.variable_map:
            logger.info(
                "Preprocessed <green>{}</green> variable(s) → <cyan>{}</cyan>",
                len(prep_result.variable_map),
                str(prep_result.preprocessed_dir),
            )
            if prep_result.skipped_vars:
                logger.debug(
                    "Skipped {} variable(s) with no CMIP6 mapping: {}",
                    len(prep_result.skipped_vars),
                    prep_result.skipped_vars[:10],
                )
            # Build model config from preprocessed directory.
            # Use a single data source with {short_name}.nc template so that
            # ESMValTool automatically looks for <variable>.nc per variable
            # instead of scanning all files for every request.
            preprocessed_sources = [
                DataSource(
                    name="preprocessed",
                    rootpath=str(prep_result.preprocessed_dir),
                    dirname_template="",
                    filename_template="{short_name}.nc",
                )
            ]
            discovered_cmip6_vars = list(prep_result.variable_map.keys())
            model_config = inspector.to_model_config(info)
            # Override data_sources and discovered_vars with preprocessed info
            from dataclasses import replace  # noqa: PLC0415
            return replace(
                model_config,
                data_sources=preprocessed_sources,
                discovered_vars=discovered_cmip6_vars,
            )
    except Exception as exc:
        logger.warning(
            "CF preprocessing failed ({}), using raw data sources. "
            "ESMValTool may report coordinate or variable errors.",
            exc,
        )

    return inspector.to_model_config(info)
