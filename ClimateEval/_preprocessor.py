"""Preprocessor module for ClimateEval.

Fixes common issues in arbitrary ESM NetCDF files so they can be ingested by
ESMValTool / Iris without errors:

1. Wrong dimension order: (time, lon, lat) → (time, lat, lon)
2. Missing pressure coordinate attributes on vertical level dimension
3. Non-CMIP6 variable names (including dot-notation names)
4. Single multi-variable files → per-variable files named after CMIP6 short_name
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import xarray as xr
from loguru import logger

from ClimateEval._variable_mapping import CMIP6MappingInfo, VariableMapper

logger = logger.opt(colors=True)


# ---------------------------------------------------------------------------
# Pressure level lookup for common model vertical grids
# ---------------------------------------------------------------------------

STANDARD_PRESSURE_LEVELS: dict[int, list[int]] = {
    2:  [50000, 20000],
    4:  [85000, 50000, 25000, 10000],
    8:  [92500, 80000, 65000, 50000, 35000, 20000, 10000, 3000],   # SPEEDY T31
    16: [100000, 92500, 85000, 70000, 60000, 50000, 40000, 30000,
         25000, 20000, 15000, 10000, 7000, 5000, 3000, 1000],
    19: [100000, 92500, 85000, 70000, 60000, 50000, 40000, 30000,
         25000, 20000, 15000, 10000, 7000, 5000, 3000, 2000, 1000, 500, 100],
}


# ---------------------------------------------------------------------------
# CMIP6 standard attribute lookup
# ---------------------------------------------------------------------------

CMIP6_STANDARD_ATTRS: dict[str, dict[str, str]] = {
    "tas":  {"standard_name": "air_temperature",
             "long_name": "Near-Surface Air Temperature", "units": "K"},
    "ta":   {"standard_name": "air_temperature",
             "long_name": "Air Temperature", "units": "K"},
    "pr":   {"standard_name": "precipitation_flux",
             "long_name": "Precipitation", "units": "kg m-2 s-1"},
    "hus":  {"standard_name": "specific_humidity",
             "long_name": "Specific Humidity", "units": "kg kg-1"},
    "ua":   {"standard_name": "eastward_wind",
             "long_name": "Eastward Wind", "units": "m s-1"},
    "va":   {"standard_name": "northward_wind",
             "long_name": "Northward Wind", "units": "m s-1"},
    "ps":   {"standard_name": "surface_air_pressure",
             "long_name": "Surface Air Pressure", "units": "Pa"},
    "psl":  {"standard_name": "air_pressure_at_mean_sea_level",
             "long_name": "Sea Level Pressure", "units": "Pa"},
    "ts":   {"standard_name": "surface_temperature",
             "long_name": "Surface Temperature", "units": "K"},
    "tos":  {"standard_name": "sea_surface_temperature",
             "long_name": "Sea Surface Temperature", "units": "K"},
    "rlut": {"standard_name": "toa_outgoing_longwave_flux",
             "long_name": "TOA Outgoing Longwave Radiation", "units": "W m-2"},
    "rsut": {"standard_name": "toa_outgoing_shortwave_flux",
             "long_name": "TOA Outgoing Shortwave Radiation", "units": "W m-2"},
    "rsds": {"standard_name": "surface_downwelling_shortwave_flux_in_air",
             "long_name": "Surface Downwelling Shortwave Radiation", "units": "W m-2"},
    "rlds": {"standard_name": "surface_downwelling_longwave_flux_in_air",
             "long_name": "Surface Downwelling Longwave Radiation", "units": "W m-2"},
    "zg":   {"standard_name": "geopotential_height",
             "long_name": "Geopotential Height", "units": "m"},
    "hur":  {"standard_name": "relative_humidity",
             "long_name": "Relative Humidity", "units": "%"},
    "clt":  {"standard_name": "cloud_area_fraction",
             "long_name": "Total Cloud Fraction", "units": "1"},
    "hfls": {"standard_name": "surface_upward_latent_heat_flux",
             "long_name": "Surface Upward Latent Heat Flux", "units": "W m-2"},
    "hfss": {"standard_name": "surface_upward_sensible_heat_flux",
             "long_name": "Surface Upward Sensible Heat Flux", "units": "W m-2"},
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PreprocessingResult:
    """Result of a preprocessing run."""

    preprocessed_dir: Path
    """Directory containing fixed per-variable NetCDF files."""
    variable_map: dict[str, Path] = field(default_factory=dict)
    """CMIP6 short_name → Path to fixed .nc file."""
    skipped_vars: list[str] = field(default_factory=list)
    """Variables that could not be mapped or processed."""
    was_cached: bool = False
    """True if the preprocessed directory already existed and was reused."""


# ---------------------------------------------------------------------------
# NCPreprocessor
# ---------------------------------------------------------------------------

class NCPreprocessor:
    """Preprocesses arbitrary ESM NetCDF files for ESMValTool compatibility."""

    _COORD_SKIP_NAMES: frozenset[str] = frozenset({
        "time", "lat", "lon", "latitude", "longitude",
        "level", "lev", "plev", "depth",
        "lat_bnds", "lon_bnds", "time_bnds", "lev_bnds", "plev_bnds",
        "lat_bounds", "lon_bounds", "time_bounds",
        "bnds", "bounds",
    })

    def __init__(self) -> None:
        self._mapper = VariableMapper()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess(
        self,
        sim_path: Path,
        variable_names: list[str] | None = None,
    ) -> PreprocessingResult:
        """Preprocess all NetCDF files in *sim_path*.

        Parameters
        ----------
        sim_path:
            Root directory of the ESM simulation.
        variable_names:
            Optional list of CMIP6 variable names to restrict output.
            If None, all mappable variables are written.

        Returns
        -------
        PreprocessingResult
        """
        sim_path = Path(sim_path).expanduser().resolve()
        # Prefer writing inside the simulation directory; fall back to a
        # user-level cache when the directory is not writable (e.g. shared
        # read-only project data).
        _candidate = sim_path / ".climateeval_preprocessed"
        try:
            _candidate.mkdir(parents=True, exist_ok=True)
            preprocessed_dir = _candidate
        except PermissionError:
            import hashlib  # noqa: PLC0415
            _hash = hashlib.md5(str(sim_path).encode()).hexdigest()[:12]
            preprocessed_dir = (
                Path.home() / ".climateeval" / "preprocessed" / _hash
            )
            logger.debug(
                "Cannot write to {}, using cache at <cyan>{}</cyan>",
                sim_path,
                preprocessed_dir,
            )

        # Return cached result if directory exists and has .nc files
        if preprocessed_dir.is_dir():
            existing = list(preprocessed_dir.glob("*.nc"))
            if existing:
                logger.info(
                    f"Using cached preprocessed data in "
                    f"<cyan>{preprocessed_dir}</cyan> "
                    f"({len(existing)} file(s))"
                )
                variable_map = {p.stem: p for p in existing}
                return PreprocessingResult(
                    preprocessed_dir=preprocessed_dir,
                    variable_map=variable_map,
                    was_cached=True,
                )

        preprocessed_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Preprocessing simulation data from <cyan>{sim_path}</cyan>"
        )

        # Collect .nc files — flat first, recurse if none found
        nc_files = [
            p for p in sim_path.iterdir()
            if p.is_file() and p.suffix == ".nc"
        ]
        if not nc_files:
            logger.debug("No .nc files at top level; scanning subdirectories")
            nc_files = [
                p for p in sim_path.rglob("*.nc")
                if ".climateeval_preprocessed" not in p.parts
            ]

        if not nc_files:
            logger.warning(f"No NetCDF files found in <yellow>{sim_path}</yellow>")
            return PreprocessingResult(preprocessed_dir=preprocessed_dir)

        logger.debug(f"Found {len(nc_files)} NetCDF file(s) to preprocess")

        variable_map: dict[str, Path] = {}
        skipped_vars: list[str] = []
        target_set = set(variable_names) if variable_names else None

        for nc_path in nc_files:
            self._process_file(
                nc_path,
                preprocessed_dir,
                variable_map,
                skipped_vars,
                target_set,
            )

        logger.info(
            f"Preprocessing complete: {len(variable_map)} variable(s) written, "
            f"{len(skipped_vars)} skipped"
        )
        if skipped_vars:
            logger.debug(f"Skipped variables: {skipped_vars}")

        return PreprocessingResult(
            preprocessed_dir=preprocessed_dir,
            variable_map=variable_map,
            skipped_vars=skipped_vars,
            was_cached=False,
        )

    # ------------------------------------------------------------------
    # File-level processing
    # ------------------------------------------------------------------

    def _process_file(
        self,
        nc_path: Path,
        preprocessed_dir: Path,
        variable_map: dict[str, Path],
        skipped_vars: list[str],
        target_set: set[str] | None,
    ) -> None:
        """Open one NetCDF file, fix it, and write per-variable outputs."""
        logger.debug(f"Processing <blue>{nc_path.name}</blue>")

        ds = self._open_dataset(nc_path)
        if ds is None:
            return

        try:
            ds = self._fix_dimensions(ds)
            ds = self._fix_coordinates(ds)

            # Identify data variables (skip bounds, coordinate helpers, etc.)
            coord_names = set(ds.coords)
            data_vars = [
                v for v in ds.data_vars
                if v not in coord_names
                and not v.endswith(("_bnds", "_bounds"))
                and v != "time_bnds"
            ]

            for var_name in data_vars:
                self._process_variable(
                    ds,
                    var_name,
                    preprocessed_dir,
                    variable_map,
                    skipped_vars,
                    target_set,
                )
        except Exception as exc:
            logger.warning(
                f"Failed to process file <yellow>{nc_path.name}</yellow>: {exc}"
            )
        finally:
            ds.close()

    def _process_variable(
        self,
        ds: xr.Dataset,
        var_name: str,
        preprocessed_dir: Path,
        variable_map: dict[str, Path],
        skipped_vars: list[str],
        target_set: set[str] | None,
    ) -> None:
        """Map, fix, and write one variable from *ds*."""
        da = ds[var_name]
        attrs = da.attrs

        mapping = self._mapper.map_variable(
            var_name,
            standard_name=attrs.get("standard_name"),
            units=attrs.get("units"),
        )

        # Also try dot-suffix extraction (e.g. "surface_flux.rlds" → "rlds")
        if mapping is None and "." in var_name:
            suffix = var_name.rsplit(".", 1)[-1]
            mapping = self._mapper.map_variable(suffix, units=attrs.get("units"))
            if mapping is not None:
                logger.debug(
                    f"Mapped dot-suffix variable <green>{var_name}</green> "
                    f"via suffix '<green>{suffix}</green>' -> "
                    f"<cyan>{mapping.cmip6_name}</cyan>"
                )

        if mapping is None:
            logger.debug(f"No mapping for variable <yellow>{var_name}</yellow> — skipping")
            skipped_vars.append(var_name)
            return

        cmip6_name = mapping.cmip6_name

        # Filter to requested variables
        if target_set is not None and cmip6_name not in target_set:
            return

        # Skip if already written (first occurrence wins)
        if cmip6_name in variable_map:
            logger.debug(
                f"Variable <cyan>{cmip6_name}</cyan> already written; "
                f"skipping duplicate source <yellow>{var_name}</yellow>"
            )
            return

        try:
            da_fixed = self._fix_variable(da, cmip6_name, mapping)
            out_path = preprocessed_dir / f"{cmip6_name}.nc"
            out_ds = da_fixed.to_dataset(name=cmip6_name)
            out_ds = self._add_time_bounds(out_ds)
            out_ds.to_netcdf(str(out_path))
            variable_map[cmip6_name] = out_path
            logger.debug(
                f"Wrote <cyan>{cmip6_name}</cyan> → <blue>{out_path.name}</blue>"
            )
        except Exception as exc:
            logger.warning(
                f"Could not process variable <yellow>{var_name}</yellow> "
                f"(→ {cmip6_name}): {exc}"
            )
            skipped_vars.append(var_name)

    # ------------------------------------------------------------------
    # Dataset-level fixes
    # ------------------------------------------------------------------

    def _open_dataset(self, path: Path) -> xr.Dataset | None:
        """Open a NetCDF file with xarray, falling back to decode_times=False."""
        try:
            return xr.open_dataset(str(path), decode_times=True, engine="netcdf4")
        except Exception:
            pass
        try:
            return xr.open_dataset(str(path), decode_times=False, engine="netcdf4")
        except Exception as exc:
            logger.warning(
                f"Cannot open <yellow>{path.name}</yellow>: {exc} — skipping"
            )
            return None

    # Dimension names treated as vertical coordinates
    _VERTICAL_DIMS = frozenset({"level", "lev", "plev", "depth", "height", "sigma"})

    def _fix_dimensions(self, ds: xr.Dataset) -> xr.Dataset:
        """Transpose every data variable to CF canonical order.

        Target ordering (CF convention, ESMValTool expected):
          (time, <vertical>, lat, lon)   — for 4-D fields
          (time, lat, lon)               — for 3-D fields
          (lat, lon)                     — for 2-D fields
        """
        all_dims = list(ds.dims)

        lat_dim = next((d for d in all_dims if d.lower() in ("lat", "latitude")), None)
        lon_dim = next((d for d in all_dims if d.lower() in ("lon", "longitude")), None)
        time_dim = next((d for d in all_dims if d.lower() == "time"), None)
        vert_dim = next((d for d in all_dims if d.lower() in self._VERTICAL_DIMS), None)

        if lat_dim is None or lon_dim is None:
            return ds  # nothing to fix

        # Transpose each data variable individually so vertical dims stay
        # in position 1 (after time) regardless of the dataset-level dim order.
        new_ds = ds.copy(deep=False)
        for var_name in list(ds.data_vars):
            da = ds[var_name]
            var_dims = list(da.dims)
            has_time = time_dim in var_dims
            has_vert = vert_dim in var_dims if vert_dim else False
            has_lat = lat_dim in var_dims
            has_lon = lon_dim in var_dims

            if not (has_lat and has_lon):
                continue  # skip non-spatial variables

            # Build canonical target order for this variable
            target: list[str] = []
            if has_time:
                target.append(time_dim)  # type: ignore[arg-type]
            if has_vert:
                target.append(vert_dim)  # type: ignore[arg-type]
            target.append(lat_dim)
            target.append(lon_dim)
            # Append any remaining dims not covered above
            for d in var_dims:
                if d not in target:
                    target.append(d)

            if var_dims != target:
                logger.debug(f"Transposing {var_name}: {var_dims} → {target}")
                new_ds[var_name] = da.transpose(*target)

        return new_ds

    def _fix_coordinates(self, ds: xr.Dataset) -> xr.Dataset:
        """Add missing CF attributes to coordinate variables."""
        coords = dict(ds.coords)
        updated: dict[str, xr.DataArray] = {}
        # Track coordinates that need to be renamed (old_name → new_name)
        renames: dict[str, str] = {}

        for coord_name, coord_da in coords.items():
            name_lower = coord_name.lower()

            if name_lower in ("lat", "latitude"):
                updated[coord_name] = self._fix_lat_coord(coord_da)

            elif name_lower in ("lon", "longitude"):
                updated[coord_name] = self._fix_lon_coord(coord_da)

            elif name_lower in ("level", "lev"):
                fixed = self._fix_vertical_coord(coord_da, coord_name)
                # Store under the OLD name for now; we rename dims/vars after.
                if fixed.name is not None and fixed.name != coord_name:
                    renames[coord_name] = fixed.name
                # Always store under the current (old) coord name so that
                # assign_coords does not conflict with an existing dimension.
                updated[coord_name] = fixed.rename(coord_name)

            elif name_lower == "time":
                updated[coord_name] = self._fix_time_coord(coord_da)

        if updated:
            ds = ds.assign_coords(updated)

        # Rename dimensions AND coordinate variables that were relabelled
        # (e.g. level → plev).  Must be done AFTER assign_coords so the old
        # name still exists as a dimension when rename is called.
        if renames:
            ds = ds.rename(renames)

        return ds

    # ------------------------------------------------------------------
    # Coordinate-level fixes
    # ------------------------------------------------------------------

    def _fix_lat_coord(self, da: xr.DataArray) -> xr.DataArray:
        attrs = dict(da.attrs)
        changed = False
        if "standard_name" not in attrs:
            attrs["standard_name"] = "latitude"
            changed = True
        if "units" not in attrs:
            attrs["units"] = "degrees_north"
            changed = True
        if "axis" not in attrs:
            attrs["axis"] = "Y"
            changed = True
        if changed:
            da = da.copy()
            da.attrs = attrs
        return da

    def _fix_lon_coord(self, da: xr.DataArray) -> xr.DataArray:
        attrs = dict(da.attrs)
        changed = False
        if "standard_name" not in attrs:
            attrs["standard_name"] = "longitude"
            changed = True
        if "units" not in attrs:
            attrs["units"] = "degrees_east"
            changed = True
        if "axis" not in attrs:
            attrs["axis"] = "X"
            changed = True
        if changed:
            da = da.copy()
            da.attrs = attrs
        return da

    def _fix_vertical_coord(
        self, da: xr.DataArray, coord_name: str
    ) -> xr.DataArray:
        """Fix a vertical level coordinate.

        Handles three cases:

        1. **Sigma coordinates** — float values in (0, 1] with no pressure
           units and no standard_name.  Converted via
           ``plev_Pa = sigma * 100000`` (assuming p_ref = 1000 hPa).

        2. **Integer model-level indices** — replaced with approximate pressure
           values from STANDARD_PRESSURE_LEVELS when the count matches.

        3. **Already-pressure coordinates** — missing CF attributes are added.
        """
        attrs = dict(da.attrs)
        values = da.values

        units = attrs.get("units", "")
        standard_name = attrs.get("standard_name", "")

        # Determine if the coordinate already has pressure-like units
        pressure_units = {"pa", "hpa", "mbar", "pascal", "pascals"}
        has_pressure_units = units.lower().strip() in pressure_units

        n_levels = len(values)
        float_values = np.array(values, dtype=np.float64)

        # ------------------------------------------------------------------
        # Case 1: Sigma coordinates — floats in (0, 1]
        # ------------------------------------------------------------------
        is_sigma = (
            not has_pressure_units
            and not standard_name
            and np.issubdtype(np.array(values).dtype, np.floating)
            and float_values.min() > 0.0
            and float_values.max() <= 1.0
        )

        if is_sigma:
            logger.debug(
                f"Detected sigma coordinate '{coord_name}' "
                f"({n_levels} levels, range [{float_values.min():.3f}, "
                f"{float_values.max():.3f}]); converting to pressure (Pa)"
            )
            pressure_vals = float_values * 100000.0  # sigma * p_ref (Pa)
            da = xr.DataArray(
                pressure_vals,
                dims=da.dims,
                name="plev",
                attrs={
                    "standard_name": "air_pressure",
                    "long_name": "Pressure",
                    "units": "Pa",
                    "axis": "Z",
                    "positive": "down",
                },
            )
            return da

        # ------------------------------------------------------------------
        # Case 2: Integer model-level indices
        # ------------------------------------------------------------------
        is_index_levels = (
            not has_pressure_units
            and not standard_name
            and np.issubdtype(np.array(values).dtype, np.integer)
        )

        if is_index_levels and n_levels in STANDARD_PRESSURE_LEVELS:
            logger.debug(
                f"Replacing integer level indices ({n_levels} levels) "
                f"with standard pressure values"
            )
            pressure_vals = np.array(
                STANDARD_PRESSURE_LEVELS[n_levels], dtype=np.float64
            )
            da = xr.DataArray(
                pressure_vals,
                dims=da.dims,
                name="plev",
                attrs={
                    "standard_name": "air_pressure",
                    "long_name": "Pressure",
                    "units": "Pa",
                    "axis": "Z",
                    "positive": "down",
                },
            )
            return da

        # ------------------------------------------------------------------
        # Case 3: Already a pressure coordinate — add missing CF attributes
        # ------------------------------------------------------------------
        changed = False
        if has_pressure_units or standard_name == "air_pressure":
            if "standard_name" not in attrs:
                attrs["standard_name"] = "air_pressure"
                changed = True
            if "axis" not in attrs:
                attrs["axis"] = "Z"
                changed = True
            if "positive" not in attrs:
                attrs["positive"] = "down"
                changed = True
        else:
            # Generic vertical coordinate: at minimum add axis
            if "axis" not in attrs:
                attrs["axis"] = "Z"
                changed = True

        if changed:
            da = da.copy()
            da.attrs = attrs

        return da

    def _fix_time_coord(self, da: xr.DataArray) -> xr.DataArray:
        """Ensure the time coordinate has CF-compliant units if not decoded."""
        attrs = dict(da.attrs)
        # If already a datetime object, nothing to do
        if np.issubdtype(da.dtype, np.datetime64):
            return da
        # If it's a float and has no units, add a placeholder CF units string
        if "units" not in attrs and np.issubdtype(da.dtype, np.floating):
            attrs["units"] = "days since 1850-01-01 00:00:00"
            logger.debug(
                "Added placeholder CF units to time coordinate "
                "(original was float with no units)"
            )
            da = da.copy()
            da.attrs = attrs
        return da

    def _add_time_bounds(self, ds: xr.Dataset) -> xr.Dataset:
        """Add CF time bounds required by ESMValTool's climate_statistics.

        Computes centred bounds: each bound is half a time step before/after
        the cell centre. Works with both datetime64 and numeric time axes.
        Falls back gracefully on any error.
        """
        if "time" not in ds.coords:
            return ds
        time = ds["time"]
        if time.size < 2:
            return ds
        try:
            tv = time.values
            if np.issubdtype(tv.dtype, np.datetime64):
                # datetime64 arithmetic — keep as timedelta / datetime
                steps = np.diff(tv)
                half = steps / 2
                lo = np.empty(len(tv), dtype=tv.dtype)
                hi = np.empty(len(tv), dtype=tv.dtype)
                lo[0]  = tv[0]  - half[0]
                lo[1:] = tv[1:] - half
                hi[:-1] = tv[:-1] + half
                hi[-1]  = tv[-1]  + half[-1]
            else:
                # Numeric (float / int) time axis
                t = tv.astype("float64")
                half = np.diff(t) / 2.0
                lo = np.empty_like(t)
                lo[0]  = t[0]  - half[0]
                lo[1:] = t[1:] - half
                hi = np.empty_like(t)
                hi[:-1] = t[:-1] + half
                hi[-1]  = t[-1]  + half[-1]

            bnds = np.stack([lo, hi], axis=1)
            ds = ds.copy()
            ds["time_bnds"] = xr.DataArray(
                bnds,
                dims=["time", "bnds"],
                attrs={"long_name": "time bounds"},
            )
            # Tell CF which variable carries the bounds
            t_attrs = dict(time.attrs)
            t_attrs["bounds"] = "time_bnds"
            ds["time"] = time.copy(data=time.values, deep=False)
            ds["time"].attrs = t_attrs
        except Exception as exc:
            logger.debug(f"Could not add time bounds: {exc}")
        return ds

    # ------------------------------------------------------------------
    # Variable-level fixes
    # ------------------------------------------------------------------

    def _fix_variable(
        self,
        da: xr.DataArray,
        cmip6_name: str,
        mapping: CMIP6MappingInfo,
    ) -> xr.DataArray:
        """Rename variable, apply unit conversions, and set CMIP6 attributes.

        Parameters
        ----------
        da:
            Input DataArray (with original variable name).
        cmip6_name:
            Target CMIP6 short_name.
        mapping:
            Mapping metadata from VariableMapper.

        Returns
        -------
        xr.DataArray
            Fixed DataArray with CMIP6 name and correct attributes.
        """
        da = da.copy()
        raw_units = mapping.raw_units or da.attrs.get("units", "")

        # Apply unit conversions
        da = self._apply_unit_conversion(da, cmip6_name, raw_units)

        # Rename to CMIP6 name
        da.name = cmip6_name

        # Apply CMIP6 standard attributes
        std_attrs = CMIP6_STANDARD_ATTRS.get(cmip6_name, {})
        new_attrs = dict(da.attrs)
        for key, val in std_attrs.items():
            new_attrs[key] = val

        # Also use mapping's standard_name if we don't have one yet
        if "standard_name" not in new_attrs and mapping.standard_name:
            new_attrs["standard_name"] = mapping.standard_name

        da.attrs = new_attrs
        return da

    def _apply_unit_conversion(
        self,
        da: xr.DataArray,
        cmip6_name: str,
        raw_units: str,
    ) -> xr.DataArray:
        """Apply numeric unit conversions where needed."""
        raw_lower = raw_units.lower().strip()

        # g/kg → kg/kg (specific humidity, etc.)
        if raw_lower in ("g/kg", "g kg-1", "g kg**-1"):
            logger.debug(
                f"Unit conversion for <cyan>{cmip6_name}</cyan>: g/kg → kg/kg"
            )
            return da * 0.001

        # g/m²/s → kg/m²/s (precipitation)
        if raw_lower in ("g/m2/s", "g m-2 s-1", "g m**-2 s**-1"):
            logger.debug(
                f"Unit conversion for <cyan>{cmip6_name}</cyan>: g/m²/s → kg/m²/s"
            )
            return da * 0.001

        # m²/s² → m (geopotential to geopotential height)
        if raw_lower in ("m2/s2", "m**2 s**-2", "m2 s-2", "m^2/s^2"):
            logger.debug(
                f"Unit conversion for <cyan>{cmip6_name}</cyan>: m²/s² → m (÷g)"
            )
            return da / 9.80665

        # % → 1 (cloud fraction, relative humidity expressed as percentage)
        if raw_lower == "%":
            # Only divide if CMIP6 target expects a fraction (e.g. clt → 1, not hur → %)
            target_units = CMIP6_STANDARD_ATTRS.get(cmip6_name, {}).get("units", "")
            if target_units == "1":
                logger.debug(
                    f"Unit conversion for <cyan>{cmip6_name}</cyan>: % → 1 (÷100)"
                )
                return da / 100.0

        return da


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def preprocess_simulation(
    sim_path: Path,
    variable_names: list[str] | None = None,
) -> PreprocessingResult:
    """Preprocess an ESM simulation directory for ESMValTool compatibility.

    Convenience wrapper around :class:`NCPreprocessor`. Creates per-variable
    NetCDF files with CMIP6-compliant names, dimension order, and coordinate
    attributes in ``{sim_path}/.climateeval_preprocessed/``.

    Parameters
    ----------
    sim_path:
        Root directory of the ESM simulation.
    variable_names:
        Optional list of CMIP6 short_names to restrict output. If None,
        all mappable variables found in the input files are written.

    Returns
    -------
    PreprocessingResult
        Contains the preprocessed directory path, variable→file map,
        list of skipped variables, and a ``was_cached`` flag.
    """
    preprocessor = NCPreprocessor()
    return preprocessor.preprocess(sim_path, variable_names=variable_names)
