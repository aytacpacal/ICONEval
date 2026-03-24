# Agent: code-implementer

## Role
Implement all code changes in the ClimateEval package to enable automatic
data discovery, variable mapping, and model config generation.

## Responsibilities
- Create `ClimateEval/_data_discovery.py` (DataInspector class)
- Create `ClimateEval/_variable_mapping.py` (VariableMapper + RecipeValidator)
- Modify `ClimateEval/_simulation_info.py` to call auto-discovery
- Modify `ClimateEval/_model_config.py` to add `auto_discover()` classmethod
- Modify `ClimateEval/_templates.py` to skip recipes with missing variables
- Maintain backward compatibility with ICON auto-detection

## Implementation Status
See `agents/shared_memory/implementation_plan.md`

## Key Constraints
- Must NOT break existing ICON auto-detection (no model_config path)
- Must NOT break user-provided model_config YAML path
- New auto-discovery is a third fallback tier after both existing paths
- xarray and netCDF4 are available in the environment
- Runs on DKRZ Levante HPC (Python 3.10+)

## Code Change Summary

### New Files
1. `ClimateEval/_data_discovery.py`
   - `class DataInspector` — scan dirs, inspect NC files, detect structure
   - `class DiscoveredSimulation` — dataclass with discovered metadata

2. `ClimateEval/_variable_mapping.py`
   - `CMIP6_VARIABLE_ALIASES` — dict of common model names → CMIP6 names
   - `class VariableMapper` — map discovered vars to CF standards
   - `class RecipeVariableChecker` — check recipe var requirements

### Modified Files
3. `ClimateEval/_simulation_info.py`
   - `SimulationInfo.from_path()`: add auto-discovery tier when no model_config

4. `ClimateEval/_model_config.py`
   - `ModelConfig.auto_discover(sim_path)`: generate config from inspection

5. `ClimateEval/_templates.py`
   - `RecipeTemplate.get_recipe()`: add variable availability check; skip if vars missing

6. `ClimateEval/main.py`
   - Add `--auto_discover` flag (default True when no model_config given)
   - Log auto-discovery results for user transparency
