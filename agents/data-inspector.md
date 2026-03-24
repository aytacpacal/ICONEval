# Agent: data-inspector

## Role
Scan simulation directories and inspect NetCDF files to understand the
structure of arbitrary ESM output without any prior user configuration.

## Capabilities
- Recursively scan directories for NetCDF files (`*.nc`)
- Open NetCDF files with xarray/netCDF4 to extract:
  - Variable names and their attributes (`long_name`, `standard_name`, `units`)
  - Dimension names (`time`, `lat`, `lon`, `lev`, etc.)
  - Global attributes (`source`, `model_id`, `institution`, `frequency`, etc.)
  - Temporal coverage and frequency
  - Grid type (regular lat/lon, curvilinear, unstructured)
- Identify file naming patterns for template generation
- Detect experiment name and directory organization

## Inputs
- `simulation_path`: Path to a simulation output directory

## Outputs (written to `agents/shared_memory/`)
- `discovered_structure.json`: Directory layout and file patterns found
- Updates `variable_mappings.json` with discovered variables (for validator)

## Key Logic
```
scan_directory(path)
  → find all *.nc files
  → for each file, inspect_netcdf(file)
      → extract: variables, dims, attrs, time_coverage
  → group files by naming pattern
  → detect: frequency, grid_type, experiment_name
  → produce DataSource entries (rootpath, dirname_template, filename_template)
```

## Integration
Implemented in `ClimateEval/_data_discovery.py`:
- `DataInspector` class
- Called from `SimulationInfo.from_path()` when no model_config is provided
