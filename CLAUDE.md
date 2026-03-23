# ModelEval / ICONEval — Claude context

## Project overview

This is a fork of **ICONEval** (renamed **ModelEval**) that evaluates any Earth System Model (ESM) output using ESMValTool. Originally ICON-only; generalized via YAML model config files.

The main goal is to support non-ICON ESMs (e.g., EMAC, CESM, MPAS) as part of the diffESM project.

## Package structure

- `modeleval/` — generalized ESM evaluation package (active development)
- `iconeval/` — legacy ICON-specific package (kept for backward compatibility)
- `doc/` — documentation
- `test_jcm/` — local test scripts (untracked)
- `output_modeleval/` — local output (untracked)

## Key conventions

- Backward compatibility with ICON auto-detection must be preserved
- Runs on DKRZ's Levante HPC with Slurm job submission
- ESMValTool recipes and config are filled from templates at runtime
- Model configs are YAML files in `modeleval/model_configs/`
- Main CLI: `modeleval` (alias: `iconeval`)
- Tags system for selecting recipe subsets: `--tags=timeseries,maps`
- Results can be published to DKRZ Swift object storage via `--publish_html=True`
- `--portable_html=True` creates `*_portable.html` copies of all summary HTML files with all local PNG figures embedded as base64 data URIs, for single-file sharing
