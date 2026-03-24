# Implementation Plan — Auto-Discovery System

**Status:** In Progress
**Updated:** 2026-03-24

## Overview

Add automatic NetCDF data discovery to ClimateEval so users can point it at any
model output directory without writing a model config YAML or preprocessing
their data to CF-compliance.

## Tier System (backward-compatible)

```
Input: ClimateEval /path/to/sim [--model_config=...]

Tier 1 (existing): model_config YAML provided
  → Use ModelConfig.from_yaml() as before

Tier 2 (existing): ICON output detected automatically
  → Use create_icon_config() as before

Tier 3 (NEW): Unknown model output
  → DataInspector.scan(sim_path)
  → VariableMapper.map(discovered_vars)
  → ModelConfig.auto_discover(sim_path) → auto-generated config
  → RecipeVariableChecker.filter(recipes, available_vars)
     → skip recipes that need unavailable variables
     → inject raw_name/raw_units facets for mapped variables
```

## Files Created

- [x] `ClimateEval/_data_discovery.py` — 601 lines, DataInspector + discover_model_config()
- [x] `ClimateEval/_variable_mapping.py` — 629 lines, 124 aliases, VariableMapper + RecipeVariableChecker

## Files Modified

- [x] `ClimateEval/_model_config.py` — added `discovered_vars: list[str]` field to ModelConfig
- [x] `ClimateEval/_simulation_info.py` — added _is_icon_output(), _from_path_auto_discover() (Tier 3)
- [x] `ClimateEval/_io_handler.py` — added _filter_recipes_by_available_vars() method

## Completed: 2026-03-24

## Key Design Decisions

1. **Non-breaking**: Tiers 1 and 2 unchanged; Tier 3 is new fallback
2. **xarray-first**: Use xarray to inspect NetCDF files (already in env)
3. **Fuzzy matching**: Match variable names case-insensitively + common aliases
4. **Standard_name priority**: CF `standard_name` attribute takes precedence
5. **Pattern detection**: Group files by naming pattern to build filename_template
6. **Frequency detection**: Infer from time coordinate spacing
7. **Recipe filtering**: Skip recipes silently (with warning) if vars missing
8. **raw_name injection**: Add raw_name/raw_units to recipe dataset entries

## Test Cases

- ICON output (existing — must still work)
- EMAC output (existing model config)
- Generic model with CMIP6-style variable names
- Generic model with WRF-style variable names (T2, PREC, etc.)
- Generic model with ERA5-style names (t2m, tp, etc.)
