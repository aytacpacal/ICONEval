# Agent: esmvaltool-fixer

## Role
Analyze ESMValTool error logs from ClimateEval runs and determine the root causes.
Communicate findings to code-implementer so that ANY model output can be preprocessed
into a form ESMValTool can ingest successfully.

## Errors Diagnosed (2026-03-24 — jcm_outputs run)

### Input file
`/work/bd1179/b309309/jcm_outputs/realistic_t31_simulation.nc`
- Single file, all variables together
- 6 time steps (5-day interval), 96×48 Gaussian grid
- Dimensions: `(time, lon, lat)` and `(time, level, lon, lat)` — **wrong order**
- Variable naming: dot-notation (`surface_flux.rlds`, `shortwave_rad.rsds`, etc.)
- `level` coordinate: integer indices 1-8, no CF attributes

### Error 1: regrid failure — wrong dimension order
```
ValueError: Cube 'u_wind' must contain a single 1D x coordinate.
iris.exceptions.CoordinateNotFoundError: "Expected to find exactly 1 '' coordinate, but found none."
```
**Root cause:** Dimension order `(time, lon, lat)` and `(time, level, lon, lat)`.
Iris expects lat before lon: `(time, lat, lon)`. Without `axis='X'/'Y'` attributes,
iris cannot determine which dimension is the spatial x/y axis.

**Fix:** Transpose to `(time, lat, lon)` / `(time, level, lat, lon)` AND add CF axis
attributes: `lat.attrs['axis'] = 'Y'`, `lon.attrs['axis'] = 'X'`.

### Error 2: extract_levels failure — missing pressure coordinate
```
iris.exceptions.CoordinateNotFoundError: "Expected to find exactly 1 'air_pressure' coordinate, but found none."
```
**Root cause:** `level` coordinate is integer model-level indices (1-8) with no
`standard_name`, `units`, or `axis` attribute. ESMValTool's `extract_levels`
preprocessor requires `air_pressure` as the vertical coordinate.

**Fix:** Rename `level` dimension to `plev` and assign:
- `standard_name = "air_pressure"`
- `units = "Pa"`
- `axis = "Z"`
- `positive = "down"`
- Approximate pressure values (Pa) for 8 sigma levels of a T31 model:
  `[92500, 80000, 65000, 50000, 35000, 20000, 10000, 3000]`
  (These are SPEEDY-like sigma levels converted to approximate pressure values.)
  **Note:** The exact values should come from the model documentation or be computed
  from `normalized_surface_pressure * sigma_levels`. For now, use standard T31 levels.

### Error 3: variable naming — dots and non-CMIP6 names
ESMValTool found the file but variable names don't match CMIP6 short_names.
Variable names with dots (e.g., `surface_flux.rlds`) cause iris loading issues
and don't map to CMIP6 names automatically.

**Fix:** Create per-variable NetCDF files named after CMIP6 short_names with the
variable renamed to the CMIP6 name inside. Use the mapping:
- `temperature`              → `ta`    (3D, pressure levels)
- `specific_humidity`        → `hus`
- `u_wind`                   → `ua`
- `v_wind`                   → `va`
- `humidity.rh`              → `hur`   (units: 1 → fraction)
- `surface_flux.rlds`        → `rlds`
- `shortwave_rad.rsds`       → `rsds`
- `longwave_rad.ftop`        → `rlut`  (sign convention: positive upward, outgoing)
- `shortwave_rad.ftop`       → `rsut`  (reflected SW at TOA)
- `surface_flux.tskin`       → `ts`
- `condensation.precls`      → use as part of `pr` (add convection.precnv/1000)
- `normalized_surface_pressure` → `ps` (needs ×surface_pressure_reference)
- `geopotential`             → `zg`    (m²/s² → m: divide by g=9.81)
- `surface_flux.hfluxn.0`   → `hfls`? (latent heat flux, W/m²)
- `surface_flux.shf.0`      → `hfss`  (sensible heat flux, W/m²)
- `shortwave_rad.rsns`       → `rsds-rsus` (net SW at surface → derive rsds-rsus?)

## Required Code Changes (tell code-implementer)

### 1. New `ClimateEval/_preprocessor.py`
Create a `NCPreprocessor` class that:

1. Opens input NetCDF files with xarray
2. Applies these fixes automatically:
   - **Transpose dimensions** to `(time, lat, lon)` or `(time, plev, lat, lon)`
   - **Add CF axis attributes** to lat, lon, level coordinates
   - **Rename level → plev**, assign pressure values and standard_name/units
   - **Map variable names** using `VariableMapper`, rename to CMIP6 names
   - **Unit conversions** (g/kg → kg/kg for humidity, etc.)
3. Writes per-variable files: `{output_dir}/{cmip6_name}.nc`
4. Returns a dict mapping CMIP6 name → Path to fixed file

**Output directory:** `{simulation_path}/.climateeval_preprocessed/`
**Skip if already exists** (caching).

### 2. Modify `ClimateEval/_data_discovery.py`
- After scanning, run `NCPreprocessor.preprocess_if_needed(sim_path)`
- Update `DiscoveredDataInfo.nc_files` and `file_groups` to point to preprocessed files
- Update `to_model_config()` to use preprocessed directory as rootpath
- Add per-variable filename template: `{short_name}.nc`

### 3. Modify `ClimateEval/_variable_mapping.py`
Add these aliases (they were missing or returning None):
- `temperature` → `ta` (was returning None — needs to be added)
- `u_wind` → `ua`
- `v_wind` → `va`
- `temperature` → `ta`
- `surface_flux.rlds` → `rlds` (dot-suffix extraction logic needed)
- `shortwave_rad.rsds` → `rsds`
- `longwave_rad.ftop` → `rlut`
- `shortwave_rad.ftop` → `rsut`
- `surface_flux.tskin` → `ts`
- `normalized_surface_pressure` → `ps`
- `condensation.precls` → `pr`

Also add **dot-suffix strategy**: if variable name contains a dot, extract the last
component and check if it's a known CMIP6 name or alias.

### 4. Modify `ClimateEval/_simulation_info.py`
- In `_from_path_auto_discover()`, after auto-discovery, call preprocessing
- Store preprocessed path on SimulationInfo

## Files Created/Modified
- [x] `ClimateEval/_preprocessor.py` (new)
- [x] `ClimateEval/_data_discovery.py` (modified)
- [x] `ClimateEval/_variable_mapping.py` (modified — add missing aliases + dot-suffix)
- [x] `ClimateEval/_simulation_info.py` (modified)
