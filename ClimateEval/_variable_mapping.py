"""Variable mapping module for ClimateEval.

Maps model-specific variable names to CMIP6/CF standard names and validates
whether input data can satisfy the variable requirements of an ESMValTool recipe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

logger = logger.opt(colors=True)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CMIP6MappingInfo:
    """Mapping from a model-specific variable name to a CMIP6 short_name."""

    cmip6_name: str
    """CMIP6 short_name target (e.g. 'tas')."""
    raw_units: str | None = None
    """Units in source data if different from CMIP6 standard."""
    note: str = ""
    """Human-readable note."""
    standard_name: str | None = None
    """CF standard_name if known."""


# ---------------------------------------------------------------------------
# CF standard_name -> CMIP6 short_name lookup
# ---------------------------------------------------------------------------

CF_STANDARD_NAME_TO_CMIP6: dict[str, str] = {
    # Atmosphere — surface
    "air_temperature": "tas",
    "air_temperature_at_2m": "tas",
    "surface_temperature": "ts",
    "precipitation_flux": "pr",
    "surface_air_pressure": "ps",
    "air_pressure_at_mean_sea_level": "psl",
    "eastward_wind": "uas",
    "northward_wind": "vas",
    # Atmosphere — 3-D
    "air_temperature_on_pressure_levels": "ta",
    "specific_humidity": "hus",
    "relative_humidity": "hur",
    "eastward_wind_on_pressure_levels": "ua",
    "northward_wind_on_pressure_levels": "va",
    "lagrangian_tendency_of_air_pressure": "wap",
    "geopotential_height": "zg",
    # Radiation
    "toa_outgoing_longwave_flux": "rlut",
    "toa_outgoing_shortwave_flux": "rsut",
    "toa_incoming_shortwave_flux": "rsdt",
    "surface_downwelling_shortwave_flux_in_air": "rsds",
    "surface_downwelling_longwave_flux_in_air": "rlds",
    "surface_upwelling_shortwave_flux_in_air": "rsus",
    "surface_upwelling_longwave_flux_in_air": "rlus",
    "net_downward_radiative_flux_at_top_of_atmosphere_model": "rtmt",
    # Clouds / moisture
    "cloud_area_fraction": "clt",
    "atmosphere_cloud_ice_content": "clivi",
    "atmosphere_cloud_liquid_water_content": "clwvi",
    "atmosphere_water_vapor_content": "prw",
    # Heat fluxes
    "surface_upward_latent_heat_flux": "hfls",
    "surface_upward_sensible_heat_flux": "hfss",
    # Ocean
    "sea_water_potential_temperature": "thetao",
    "sea_water_salinity": "so",
    "sea_surface_temperature": "tos",
    "sea_surface_salinity": "sos",
    "sea_surface_height_above_geoid": "zos",
    "ocean_mixed_layer_thickness_defined_by_sigma_theta": "mlotst",
    "northward_sea_water_velocity": "vo",
    "eastward_sea_water_velocity": "uo",
    # Sea ice
    "sea_ice_area_fraction": "siconc",
    "sea_ice_thickness": "sithick",
    # Land
    "soil_temperature": "tsl",
    "soil_moisture_content": "mrlsl",
    "runoff_flux": "mrro",
    "leaf_area_index": "lai",
}


# ---------------------------------------------------------------------------
# Comprehensive alias table  (model_var_name -> CMIP6MappingInfo)
# All entries from agents/shared_memory/variable_mappings.json are embedded.
# ---------------------------------------------------------------------------

CMIP6_VARIABLE_ALIASES: dict[str, CMIP6MappingInfo] = {
    # ---- Atmosphere: near-surface temperature ----
    "temperature_2m": CMIP6MappingInfo(
        cmip6_name="tas",
        raw_units="K",
        standard_name="air_temperature",
    ),
    "T_2M": CMIP6MappingInfo(
        cmip6_name="tas",
        raw_units="K",
        standard_name="air_temperature",
    ),
    "t2m": CMIP6MappingInfo(
        cmip6_name="tas",
        raw_units="K",
        standard_name="air_temperature",
    ),
    "T2": CMIP6MappingInfo(cmip6_name="tas", raw_units="K"),
    "TEMP2": CMIP6MappingInfo(cmip6_name="tas", raw_units="K"),
    "air_temperature": CMIP6MappingInfo(
        cmip6_name="tas",
        raw_units="K",
        standard_name="air_temperature",
    ),
    # ---- Atmosphere: 3-D temperature ----
    "T": CMIP6MappingInfo(
        cmip6_name="ta",
        note="3D temperature on pressure levels",
    ),
    "ta": CMIP6MappingInfo(cmip6_name="ta"),
    "temp": CMIP6MappingInfo(cmip6_name="ta"),
    "TEMP": CMIP6MappingInfo(cmip6_name="ta"),
    # Common generic names
    "temperature": CMIP6MappingInfo(cmip6_name="ta", note="3D atmospheric temperature"),
    "u_wind": CMIP6MappingInfo(cmip6_name="ua"),
    "v_wind": CMIP6MappingInfo(cmip6_name="va"),
    "w_wind": CMIP6MappingInfo(cmip6_name="wap"),
    "normalized_surface_pressure": CMIP6MappingInfo(cmip6_name="ps", note="normalized, multiply by reference pressure"),
    "geopotential": CMIP6MappingInfo(cmip6_name="zg", raw_units="m2 s-2", note="divide by g=9.81 for height"),
    # Dot-suffix names from jcm model (SPEEDY-like)
    "surface_flux.rlds": CMIP6MappingInfo(cmip6_name="rlds"),
    "surface_flux.rlns": CMIP6MappingInfo(cmip6_name="rls", note="net LW at surface"),
    "shortwave_rad.rsds": CMIP6MappingInfo(cmip6_name="rsds"),
    "shortwave_rad.rsns": CMIP6MappingInfo(cmip6_name="rsns", note="net SW at surface"),
    "longwave_rad.ftop": CMIP6MappingInfo(cmip6_name="rlut", note="outgoing LW at TOA"),
    "shortwave_rad.ftop": CMIP6MappingInfo(cmip6_name="rsut", note="outgoing SW at TOA"),
    "surface_flux.tskin": CMIP6MappingInfo(cmip6_name="ts"),
    "surface_flux.tsfc": CMIP6MappingInfo(cmip6_name="ts"),
    "surface_flux.t0": CMIP6MappingInfo(cmip6_name="ts"),
    "condensation.precls": CMIP6MappingInfo(cmip6_name="pr", note="large-scale precipitation, combine with convective"),
    "convection.precnv": CMIP6MappingInfo(cmip6_name="prc", raw_units="g/m2/s", note="convective precip"),
    "humidity.rh": CMIP6MappingInfo(cmip6_name="hur", raw_units="1", note="relative humidity as fraction"),
    "surface_flux.hfluxn.0": CMIP6MappingInfo(cmip6_name="hfls", note="latent heat flux"),
    "surface_flux.shf.0": CMIP6MappingInfo(cmip6_name="hfss", note="sensible heat flux"),
    # ---- Atmosphere: precipitation ----
    "precipitation": CMIP6MappingInfo(
        cmip6_name="pr",
        raw_units="kg m-2 s-1",
        standard_name="precipitation_flux",
    ),
    "PREC": CMIP6MappingInfo(cmip6_name="pr", raw_units="kg m-2 s-1"),
    "pr": CMIP6MappingInfo(cmip6_name="pr"),
    "RAIN": CMIP6MappingInfo(cmip6_name="pr", raw_units="kg m-2 s-1"),
    "rain": CMIP6MappingInfo(cmip6_name="pr", raw_units="kg m-2 s-1"),
    "precip": CMIP6MappingInfo(cmip6_name="pr", raw_units="kg m-2 s-1"),
    "PRECIP": CMIP6MappingInfo(cmip6_name="pr", raw_units="kg m-2 s-1"),
    "total_precipitation": CMIP6MappingInfo(
        cmip6_name="pr",
        raw_units="m",
        note="ERA5 accumulated; unit conversion required",
    ),
    # ---- Atmosphere: winds ----
    "u10": CMIP6MappingInfo(cmip6_name="uas", raw_units="m s-1"),
    "U10": CMIP6MappingInfo(cmip6_name="uas", raw_units="m s-1"),
    "uas": CMIP6MappingInfo(cmip6_name="uas"),
    "v10": CMIP6MappingInfo(cmip6_name="vas", raw_units="m s-1"),
    "V10": CMIP6MappingInfo(cmip6_name="vas", raw_units="m s-1"),
    "vas": CMIP6MappingInfo(cmip6_name="vas"),
    "U": CMIP6MappingInfo(cmip6_name="ua", note="3D zonal wind"),
    "ua": CMIP6MappingInfo(cmip6_name="ua"),
    "V": CMIP6MappingInfo(cmip6_name="va", note="3D meridional wind"),
    "va": CMIP6MappingInfo(cmip6_name="va"),
    "W": CMIP6MappingInfo(cmip6_name="wap", note="vertical velocity"),
    "omega": CMIP6MappingInfo(cmip6_name="wap"),
    "OMEGA": CMIP6MappingInfo(cmip6_name="wap"),
    "wap": CMIP6MappingInfo(cmip6_name="wap"),
    # ---- Atmosphere: pressure ----
    "slp": CMIP6MappingInfo(cmip6_name="psl", raw_units="Pa"),
    "SLP": CMIP6MappingInfo(cmip6_name="psl", raw_units="Pa"),
    "msl": CMIP6MappingInfo(cmip6_name="psl", raw_units="Pa"),
    "MSL": CMIP6MappingInfo(cmip6_name="psl", raw_units="Pa"),
    "psl": CMIP6MappingInfo(cmip6_name="psl"),
    "sp": CMIP6MappingInfo(cmip6_name="ps", raw_units="Pa"),
    "SP": CMIP6MappingInfo(cmip6_name="ps", raw_units="Pa"),
    "PSFC": CMIP6MappingInfo(cmip6_name="ps", raw_units="Pa"),
    "p": CMIP6MappingInfo(cmip6_name="ps"),
    "ps": CMIP6MappingInfo(cmip6_name="ps"),
    # ---- Atmosphere: geopotential ----
    "z500": CMIP6MappingInfo(cmip6_name="zg", note="500 hPa geopotential"),
    "Z": CMIP6MappingInfo(cmip6_name="zg"),
    "PHI": CMIP6MappingInfo(cmip6_name="zg"),
    "zg": CMIP6MappingInfo(cmip6_name="zg"),
    # ---- Atmosphere: humidity ----
    "hus": CMIP6MappingInfo(cmip6_name="hus"),
    "Q": CMIP6MappingInfo(cmip6_name="hus"),
    "q": CMIP6MappingInfo(cmip6_name="hus"),
    "QV": CMIP6MappingInfo(cmip6_name="hus"),
    "QVAPOR": CMIP6MappingInfo(cmip6_name="hus"),
    "specific_humidity": CMIP6MappingInfo(
        cmip6_name="hus",
        standard_name="specific_humidity",
    ),
    "rh": CMIP6MappingInfo(cmip6_name="hur", raw_units="%"),
    "RH": CMIP6MappingInfo(cmip6_name="hur", raw_units="%"),
    "relative_humidity": CMIP6MappingInfo(
        cmip6_name="hur",
        standard_name="relative_humidity",
    ),
    "hur": CMIP6MappingInfo(cmip6_name="hur"),
    # ---- Atmosphere: clouds ----
    "tcc": CMIP6MappingInfo(cmip6_name="cl", note="total cloud cover (3D)"),
    "CLCT": CMIP6MappingInfo(cmip6_name="clt", raw_units="%"),
    "clt": CMIP6MappingInfo(cmip6_name="clt"),
    "cloud_fraction": CMIP6MappingInfo(cmip6_name="cl"),
    "CLDFRA": CMIP6MappingInfo(cmip6_name="cl"),
    "cl": CMIP6MappingInfo(cmip6_name="cl"),
    "clivi": CMIP6MappingInfo(
        cmip6_name="clivi",
        standard_name="atmosphere_cloud_ice_content",
    ),
    "clwvi": CMIP6MappingInfo(
        cmip6_name="clwvi",
        standard_name="atmosphere_cloud_liquid_water_content",
    ),
    "prw": CMIP6MappingInfo(
        cmip6_name="prw",
        standard_name="atmosphere_water_vapor_content",
    ),
    # ---- Atmosphere: radiation ----
    "SWDOWN": CMIP6MappingInfo(cmip6_name="rsds", raw_units="W m-2"),
    "ssrd": CMIP6MappingInfo(
        cmip6_name="rsds",
        raw_units="J m-2",
        note="ERA5 accumulated",
    ),
    "rsds": CMIP6MappingInfo(cmip6_name="rsds"),
    "LWDOWN": CMIP6MappingInfo(cmip6_name="rlds", raw_units="W m-2"),
    "strd": CMIP6MappingInfo(cmip6_name="rlds", raw_units="J m-2"),
    "rlds": CMIP6MappingInfo(cmip6_name="rlds"),
    "SWUP": CMIP6MappingInfo(cmip6_name="rsus", raw_units="W m-2"),
    "rsus": CMIP6MappingInfo(cmip6_name="rsus"),
    "OLR": CMIP6MappingInfo(cmip6_name="rlut", raw_units="W m-2"),
    "rlut": CMIP6MappingInfo(cmip6_name="rlut"),
    "rsut": CMIP6MappingInfo(cmip6_name="rsut"),
    "rsdt": CMIP6MappingInfo(cmip6_name="rsdt"),
    "rlus": CMIP6MappingInfo(cmip6_name="rlus"),
    "rtmt": CMIP6MappingInfo(
        cmip6_name="rtmt",
        note="TOA net downward total radiation",
    ),
    # Derived cloud radiative effects (ESMValTool derives these)
    "lwcre": CMIP6MappingInfo(
        cmip6_name="lwcre",
        note="Derived: TOA longwave cloud radiative effect",
    ),
    "swcre": CMIP6MappingInfo(
        cmip6_name="swcre",
        note="Derived: TOA shortwave cloud radiative effect",
    ),
    "lwp": CMIP6MappingInfo(
        cmip6_name="lwp",
        note="Derived: liquid water path",
    ),
    # ---- Atmosphere: surface temperature / heat ----
    "ts": CMIP6MappingInfo(cmip6_name="ts"),
    "SST": CMIP6MappingInfo(cmip6_name="ts"),
    "SKT": CMIP6MappingInfo(cmip6_name="ts"),
    "tsurf": CMIP6MappingInfo(cmip6_name="ts"),
    "hfls": CMIP6MappingInfo(
        cmip6_name="hfls",
        standard_name="surface_upward_latent_heat_flux",
    ),
    "hfss": CMIP6MappingInfo(
        cmip6_name="hfss",
        standard_name="surface_upward_sensible_heat_flux",
    ),
    "LHF": CMIP6MappingInfo(cmip6_name="hfls", raw_units="W m-2"),
    "SHF": CMIP6MappingInfo(cmip6_name="hfss", raw_units="W m-2"),
    # ---- Ocean ----
    "thetao": CMIP6MappingInfo(
        cmip6_name="thetao",
        standard_name="sea_water_potential_temperature",
    ),
    "TEMP_ocean": CMIP6MappingInfo(
        cmip6_name="thetao",
        note="Ocean 3D temperature",
    ),
    "SALT": CMIP6MappingInfo(
        cmip6_name="so",
        standard_name="sea_water_salinity",
    ),
    "salinity": CMIP6MappingInfo(cmip6_name="so"),
    "so": CMIP6MappingInfo(cmip6_name="so"),
    "sst": CMIP6MappingInfo(
        cmip6_name="tos",
        standard_name="sea_surface_temperature",
    ),
    "tos": CMIP6MappingInfo(cmip6_name="tos"),
    "sss": CMIP6MappingInfo(cmip6_name="sos"),
    "sos": CMIP6MappingInfo(cmip6_name="sos"),
    "SSH": CMIP6MappingInfo(cmip6_name="zos"),
    "zos": CMIP6MappingInfo(cmip6_name="zos"),
    "UVEL": CMIP6MappingInfo(cmip6_name="uo"),
    "uo": CMIP6MappingInfo(cmip6_name="uo"),
    "VVEL": CMIP6MappingInfo(cmip6_name="vo"),
    "vo": CMIP6MappingInfo(cmip6_name="vo"),
    "WVEL": CMIP6MappingInfo(cmip6_name="wo"),
    "wo": CMIP6MappingInfo(cmip6_name="wo"),
    "mld": CMIP6MappingInfo(cmip6_name="mlotst"),
    "MLD": CMIP6MappingInfo(cmip6_name="mlotst"),
    "mlotst": CMIP6MappingInfo(cmip6_name="mlotst"),
    # ---- Land ----
    "tsl": CMIP6MappingInfo(cmip6_name="tsl"),
    "mrlsl": CMIP6MappingInfo(cmip6_name="mrlsl"),
    "mrro": CMIP6MappingInfo(cmip6_name="mrro"),
    "RUNOFF": CMIP6MappingInfo(cmip6_name="mrro"),
    "LAI": CMIP6MappingInfo(cmip6_name="lai"),
    "lai": CMIP6MappingInfo(cmip6_name="lai"),
    # ---- Sea ice ----
    "siconc": CMIP6MappingInfo(
        cmip6_name="siconc",
        standard_name="sea_ice_area_fraction",
    ),
    "SIC": CMIP6MappingInfo(cmip6_name="siconc", raw_units="%"),
    "ICEFRAC": CMIP6MappingInfo(cmip6_name="siconc"),
    "sea_ice_fraction": CMIP6MappingInfo(cmip6_name="siconc"),
    "sithick": CMIP6MappingInfo(
        cmip6_name="sithick",
        standard_name="sea_ice_thickness",
    ),
    "SIT": CMIP6MappingInfo(cmip6_name="sithick"),
    "sisnthick": CMIP6MappingInfo(
        cmip6_name="sisnthick",
        note="Snow thickness on sea ice",
    ),
}

# Pre-build a case-insensitive lookup index (lower -> first matching key)
_LOWER_ALIAS_INDEX: dict[str, str] = {
    k.lower(): k for k in reversed(list(CMIP6_VARIABLE_ALIASES.keys()))
}

# Set of all CMIP6 short_names that are valid targets (identity mapping allowed)
_VALID_CMIP6_NAMES: frozenset[str] = frozenset(
    info.cmip6_name for info in CMIP6_VARIABLE_ALIASES.values()
)


# ---------------------------------------------------------------------------
# VariableMapper
# ---------------------------------------------------------------------------


class VariableMapper:
    """Maps model-specific variable names to CMIP6 short_names."""

    def map_variable(
        self,
        model_var: str,
        standard_name: str | None = None,
        units: str | None = None,
    ) -> CMIP6MappingInfo | None:
        """Map a single model variable name to its CMIP6 equivalent.

        Priority order:
        1. CF standard_name lookup (highest priority)
        2. Exact match in CMIP6_VARIABLE_ALIASES
        3. Case-insensitive exact match
        4. Identity mapping if model_var is already a valid CMIP6 name

        Parameters
        ----------
        model_var:
            The variable name as it appears in the model output file.
        standard_name:
            CF standard_name attribute from the NetCDF variable, if available.
        units:
            Units string from the NetCDF variable attribute, if available.

        Returns
        -------
        CMIP6MappingInfo or None
            Mapping info if found, None otherwise.
        """
        # 1. CF standard_name
        if standard_name and standard_name in CF_STANDARD_NAME_TO_CMIP6:
            cmip6_name = CF_STANDARD_NAME_TO_CMIP6[standard_name]
            logger.debug(
                f"Mapped <green>{model_var}</green> via CF standard_name "
                f"'{standard_name}' -> <cyan>{cmip6_name}</cyan>"
            )
            return CMIP6MappingInfo(
                cmip6_name=cmip6_name,
                raw_units=units,
                note=f"Mapped via CF standard_name '{standard_name}'",
                standard_name=standard_name,
            )

        # 2. Exact alias match
        if model_var in CMIP6_VARIABLE_ALIASES:
            info = CMIP6_VARIABLE_ALIASES[model_var]
            logger.debug(
                f"Mapped <green>{model_var}</green> (exact) -> "
                f"<cyan>{info.cmip6_name}</cyan>"
            )
            return info

        # 3. Case-insensitive match
        lower_key = _LOWER_ALIAS_INDEX.get(model_var.lower())
        if lower_key is not None:
            info = CMIP6_VARIABLE_ALIASES[lower_key]
            logger.debug(
                f"Mapped <green>{model_var}</green> (case-insensitive via "
                f"'{lower_key}') -> <cyan>{info.cmip6_name}</cyan>"
            )
            return info

        # 4. Identity: model_var is already a valid CMIP6 short_name
        if model_var in _VALID_CMIP6_NAMES:
            logger.debug(
                f"<green>{model_var}</green> is already a valid CMIP6 name "
                f"(identity mapping)"
            )
            return CMIP6MappingInfo(
                cmip6_name=model_var,
                raw_units=units,
                note="Identity mapping (already a CMIP6 short_name)",
            )

        # 5. Dot-suffix extraction — if name contains a dot, check the suffix
        if "." in model_var:
            # Extract suffix after last dot
            suffix = model_var.rsplit(".", 1)[-1]
            # Check if suffix maps to a CMIP6 name
            result = self.map_variable(suffix, standard_name=standard_name, units=units)
            if result is not None:
                logger.debug(
                    f"Mapped {model_var} via dot-suffix '{suffix}' -> {result.cmip6_name}"
                )
                return result
            # Also try prefix (before first dot)
            prefix = model_var.split(".", 1)[0]
            result_prefix = CMIP6_VARIABLE_ALIASES.get(prefix)
            if result_prefix:
                logger.debug(
                    f"Mapped {model_var} via dot-prefix '{prefix}' -> {result_prefix.cmip6_name}"
                )
                return result_prefix

        logger.debug(
            f"No CMIP6 mapping found for variable <yellow>{model_var}</yellow>"
        )
        return None

    def map_variables(
        self,
        model_vars: list[str],
        nc_attrs: dict[str, Any] | None = None,
    ) -> dict[str, CMIP6MappingInfo]:
        """Map a list of model variable names to CMIP6 equivalents.

        Parameters
        ----------
        model_vars:
            List of variable names from the model output.
        nc_attrs:
            Optional dict of per-variable NetCDF attributes, keyed by variable
            name. Each value should be a dict that may contain 'standard_name'
            and/or 'units'.

        Returns
        -------
        dict
            Mapping {model_var: CMIP6MappingInfo} for successfully mapped vars.
            Variables that could not be mapped are silently excluded.
        """
        nc_attrs = nc_attrs or {}
        result: dict[str, CMIP6MappingInfo] = {}
        for var in model_vars:
            var_attrs = nc_attrs.get(var, {})
            standard_name = var_attrs.get("standard_name") if var_attrs else None
            units = var_attrs.get("units") if var_attrs else None
            info = self.map_variable(var, standard_name=standard_name, units=units)
            if info is not None:
                result[var] = info
        return result

    def get_extra_facets_for_recipe(
        self,
        mapped_vars: dict[str, CMIP6MappingInfo],
    ) -> dict[str, dict[str, str]]:
        """Build extra_facets structure needed by ESMValTool.

        Only includes entries where the model variable name differs from the
        CMIP6 target name, or where the raw units are non-standard (not None).

        Parameters
        ----------
        mapped_vars:
            Output of :meth:`map_variables`.

        Returns
        -------
        dict
            ``{cmip6_name: {"raw_name": model_var, "raw_units": units}}``
        """
        extra_facets: dict[str, dict[str, str]] = {}
        for model_var, info in mapped_vars.items():
            needs_raw_name = model_var != info.cmip6_name
            needs_raw_units = info.raw_units is not None
            if needs_raw_name or needs_raw_units:
                entry: dict[str, str] = {}
                if needs_raw_name:
                    entry["raw_name"] = model_var
                if needs_raw_units:
                    entry["raw_units"] = info.raw_units  # type: ignore[assignment]
                extra_facets[info.cmip6_name] = entry
        return extra_facets


# ---------------------------------------------------------------------------
# RecipeVariableChecker
# ---------------------------------------------------------------------------


def _load_recipe_yaml(recipe_yaml_path: Path) -> dict[str, Any]:
    """Load a recipe YAML, skipping magic-comment lines before '---'.

    ClimateEval writes ``#TAGS ...`` comment lines before the ``---``
    document separator. PyYAML does not handle this well, so we strip
    everything up to and including the first ``---`` line before parsing.
    """
    text = recipe_yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    sep_indices = [i for i, ln in enumerate(lines) if ln.strip() == "---"]
    if sep_indices:
        # Take content after the first '---'
        yaml_text = "".join(lines[sep_indices[0] + 1 :])
    else:
        yaml_text = text
    return yaml.safe_load(yaml_text) or {}


class RecipeVariableChecker:
    """Checks ESMValTool recipe variable requirements against available data."""

    def extract_required_vars(self, recipe_yaml_path: Path) -> list[str]:
        """Parse an ESMValTool recipe and return all required variable short_names.

        Reads ``diagnostics -> * -> variables`` sections.  Each key under
        ``variables`` is treated as the CMIP6 short_name unless the dict
        value contains an explicit ``short_name`` field (as in some sea-ice
        recipes that use ``siconc_nh`` / ``siconc_sh`` as keys but
        ``short_name: siconc``).

        Parameters
        ----------
        recipe_yaml_path:
            Path to the ESMValTool recipe YAML file.

        Returns
        -------
        list[str]
            Sorted list of unique CMIP6 short_names.
        """
        recipe_yaml_path = Path(recipe_yaml_path)
        data = _load_recipe_yaml(recipe_yaml_path)

        diagnostics = data.get("diagnostics", {})
        if not isinstance(diagnostics, dict):
            return []

        found: set[str] = set()
        for _diag_name, diag_body in diagnostics.items():
            if not isinstance(diag_body, dict):
                continue
            variables = diag_body.get("variables", {})
            if not isinstance(variables, dict):
                continue
            for var_key, var_cfg in variables.items():
                # Prefer explicit short_name if provided
                if isinstance(var_cfg, dict) and "short_name" in var_cfg:
                    found.add(str(var_cfg["short_name"]))
                else:
                    found.add(str(var_key))

        return sorted(found)

    def check_recipe_compatibility(
        self,
        recipe_yaml_path: Path,
        available_cmip6_vars: list[str],
    ) -> tuple[bool, list[str], list[str]]:
        """Check whether a recipe's variable requirements can be satisfied.

        Parameters
        ----------
        recipe_yaml_path:
            Path to the ESMValTool recipe YAML file.
        available_cmip6_vars:
            CMIP6 short_names that the model data can provide (directly or
            after mapping).

        Returns
        -------
        tuple[bool, list[str], list[str]]
            ``(is_compatible, present_vars, missing_vars)`` where
            ``is_compatible`` is True only if *all* required variables are
            available.
        """
        required = self.extract_required_vars(recipe_yaml_path)
        available_set = set(available_cmip6_vars)
        present = sorted(v for v in required if v in available_set)
        missing = sorted(v for v in required if v not in available_set)
        is_compatible = len(missing) == 0
        return is_compatible, present, missing

    def filter_compatible_recipes(
        self,
        recipe_paths: list[Path],
        available_cmip6_vars: list[str],
    ) -> list[Path]:
        """Return only the recipes whose variable requirements are fully met.

        Emits a warning for each skipped recipe listing the missing variables.

        Parameters
        ----------
        recipe_paths:
            Candidate recipe file paths.
        available_cmip6_vars:
            CMIP6 short_names that the model data can provide.

        Returns
        -------
        list[Path]
            Filtered list of compatible recipe paths (order preserved).
        """
        compatible: list[Path] = []
        for recipe_path in recipe_paths:
            try:
                ok, _present, missing = self.check_recipe_compatibility(
                    recipe_path, available_cmip6_vars
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Could not parse recipe <yellow>{recipe_path.name}</yellow>: "
                    f"{exc} — skipping"
                )
                continue

            if ok:
                compatible.append(recipe_path)
            else:
                logger.warning(
                    f"Skipping recipe <yellow>{recipe_path.name}</yellow>: "
                    f"missing variables: {missing}"
                )
        return compatible
