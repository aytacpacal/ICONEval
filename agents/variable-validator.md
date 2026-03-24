# Agent: variable-validator

## Role
Map model-specific variable names to CF/CMIP6 standard names, and validate
that the variables required by each recipe are available in the input data.

## Capabilities
- Maintain lookup tables: model variable names → CMIP6 short_name
- Check which variables are required for each recipe tag (maps, timeseries, etc.)
- Suggest `raw_name` / `raw_units` ESMValTool facets for non-CF variables
- Report missing variables and suggest fallback recipes to skip
- Handle common naming variations across models (ICON, EMAC, CESM, WRF, etc.)

## Inputs
- `discovered_variables`: list of variable names found by data-inspector
- `recipe_tag`: the tag (e.g., `maps`, `timeseries`) to check

## Outputs (written to `agents/shared_memory/`)
- `variable_mappings.json`: model_var → {cmip6_name, raw_name, raw_units}
- `cf_required_vars.json`: recipe_tag → [required_cmip6_vars]
- `validation_report.json`: for each recipe, which vars are available/missing

## Key Logic
```
validate_for_recipes(discovered_vars, recipe_templates)
  → for each recipe template:
      → extract required variables from recipe YAML
      → check if each var can be mapped from discovered_vars
      → if not: mark recipe as skippable, log warning
  → generate extra_facets (raw_name, raw_units) for mapped vars
  → return: {usable_recipes, extra_facets_per_var, warnings}
```

## Variable Mapping Table Structure
```json
{
  "temperature": {"cmip6_name": "tas", "raw_units": "K"},
  "T": {"cmip6_name": "ta", "level_dim": "lev"},
  "TEMP": {"cmip6_name": "thetao", "ocean": true},
  "pr": {"cmip6_name": "pr", "raw_units": "kg m-2 s-1"},
  "PREC": {"cmip6_name": "pr", "raw_units": "mm/day", "scale_factor": 1.157e-5}
}
```

## Integration
Implemented in `ClimateEval/_variable_mapping.py`:
- `VariableMapper` class with lookup tables and fuzzy matching
- `RecipeValidator` class to check recipe compatibility
- Called from `_templates.py` before recipe filling to filter recipes
