# ModelEval / ICONEval — Claude context

## Project overview

This is a fork of **ICONEval** (renamed **ClimateEval**) that evaluates any Earth System Model (ESM) output using ESMValTool. Originally ICON-only; generalized via YAML model config files.

The main goal is to support non-ICON ESMs (e.g., EMAC, CESM, MPAS) as part of the diffESM project.

## Package structure

- `ClimateEval/` — generalized ESM evaluation package (active development)
- `iconeval/` — legacy ICON-specific package (kept for backward compatibility)
- `doc/` — documentation
- `test_jcm/` — local test scripts (untracked)
- `output_ClimateEval/` — local output (untracked)

## Key conventions

- Backward compatibility with ICON auto-detection must be preserved
- Runs on DKRZ's Levante HPC with Slurm job submission
- ESMValTool recipes and config are filled from templates at runtime
- Model configs are YAML files in `ClimateEval/model_configs/`
- Main CLI: `ClimateEval` (aliases: `modeleval`, `iconeval`)
- Tags system for selecting recipe subsets: `--tags=timeseries,maps`
- Results can be published to DKRZ Swift object storage via `--publish_html=True`
- `--portable_html=True` creates a single `index_portable.html` with all realm navigation, recipe thumbnails, recipe content, and figures embedded as base64 data URIs for single-file sharing
