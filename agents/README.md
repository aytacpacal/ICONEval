# ClimateEval Auto-Discovery Agent Team

This directory contains the definitions and shared memory for the ClimateEval
auto-discovery agent team. The team automates the process of understanding
arbitrary ESM NetCDF output without requiring users to preprocess data.

## Goal

Enable `ClimateEval` to run against **any** model output folder without
requiring:
- A user-provided YAML model config
- Manual CF-compliance preprocessing

The system should:
1. Scan the input directory and inspect NetCDF files automatically
2. Map model-specific variable names to CMIP6/CF-standard names
3. Detect file structure, frequency, and grid type
4. Generate a working `ModelConfig` on-the-fly

## Agent Roles

| Agent | File | Responsibility |
|-------|------|----------------|
| data-inspector | `data-inspector.md` | Scan dirs, inspect NetCDF metadata, detect structure |
| variable-validator | `variable-validator.md` | Map model vars to CF/CMIP6 standards, validate recipe requirements |
| code-implementer | `code-implementer.md` | Implement code changes in ClimateEval package |

## Shared Memory

`shared_memory/` contains JSON/YAML files passed between agents:

| File | Written by | Read by | Content |
|------|-----------|---------|---------|
| `variable_mappings.json` | variable-validator | data-inspector, code-implementer | CF ↔ model name lookup tables |
| `cf_required_vars.json` | variable-validator | code-implementer | Variables needed per recipe tag |
| `implementation_plan.md` | code-implementer | all | Current implementation status |

## Integration Points in Code

- `ClimateEval/_data_discovery.py` — New module: scans dirs, inspects files
- `ClimateEval/_variable_mapping.py` — New module: CF variable name mappings
- `ClimateEval/_simulation_info.py` — Modified: calls auto-discovery when no model_config
- `ClimateEval/_model_config.py` — Modified: adds `auto_discover()` classmethod
