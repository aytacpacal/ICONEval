[Back to README](../README.md)

# ClimateEval Workflow

This document describes the detailed end-to-end workflow of ClimateEval, how CF
compliance is handled, how the tool adapts to new models, and what to do when a
model uses an unusual grid.

---

## 1. The ClimateEval Workflow

ClimateEval is a thin orchestration layer around [ESMValTool](esmvaltool.md).
The workflow proceeds in these stages:

### Stage 1 — Model configuration

ClimateEval reads a **model config YAML** (or auto-detects ICON) to learn:

- Which ESMValTool **project** name to use (e.g., `"ICON"`, `"EMAC"`, `"CESM"`)
- Where model output files live (`rootpath`, `dirname_template`,
  `filename_template`)
- Any extra ESMValTool facets (`raw_name`, `raw_units`, `horizontal_grid`, …)

This information is injected into a template that becomes the ESMValTool
**configuration file** (`config.yml`).

### Stage 2 — Recipe preparation

ClimateEval scans `ClimateEval/recipe_templates/*.yml` (and any user-supplied
templates) and creates concrete ESMValTool recipe YAMLs by substituting
placeholders:

| Placeholder          | Replaced with                                             |
|----------------------|-----------------------------------------------------------|
| `{{rootpath}}`       | Simulation directory path                                 |
| `{{project}}`        | ESMValTool project name from model config                 |
| `{{dataset}}`        | Dataset identifier from model config                      |
| `{{exp}}`            | Experiment name (= directory basename)                    |
| `{{start_year}}`     | Start year derived from available files                   |
| `{{end_year}}`       | End year derived from available files                     |
| `{{frequency}}`      | Temporal frequency (default: `mon`)                       |

Optional tags (`--tags`) filter which recipe templates are processed.

### Stage 3 — Job submission

Each recipe is submitted as a separate **Slurm job** (or job step if already
inside `sbatch`/`salloc`).  ClimateEval waits for all jobs to finish (or
returns immediately with `--no_wait`).

### Stage 4 — HTML summary

After jobs complete, ClimateEval calls `summarize()` which:

1. Reads each `recipe_*/run/main_log.txt` to determine success/failure.
2. Generates Bootstrap-based HTML overview pages (`index.html`,
   `index_atmosphere.html`, …) showing recipe cards with thumbnail figures.
3. Optionally (`--portable_html=True`) produces a **single self-contained**
   `index_portable.html` with all figures and recipe content embedded as base64
   data URIs — the file works offline and can be shared without any supporting
   files.
4. Optionally (`--publish_html=True`) uploads the result to DKRZ Swift object
   storage.

---

## 2. CF Compliance — What It Means and How It Is Handled

### What does "CF-compliant" mean here?

ESMValTool loads data using its **CMOR** (Climate Model Output Rewriter)
framework.  Every variable that passes through ESMValTool is checked against a
CMOR table, which specifies:

- Standard variable name (e.g., `tas` = near-surface air temperature)
- Units (e.g., `K`)
- Cell methods, expected axes, coordinate names

If the model output uses different names or units, ESMValTool raises an error
unless a **fixer** is in place.

### Who does the conversion?

The conversion is **not** done by ClimateEval itself.  It is handled entirely
by ESMValTool through several mechanisms — no separate "agent" or script is
needed in most cases:

| Mechanism                           | When to use                                                                           |
|-------------------------------------|---------------------------------------------------------------------------------------|
| **ESMValTool native project**       | Model is already known to ESMValTool (ICON, CMIP5/6, OBS, …).  Just set `project`.   |
| **`raw_name` / `raw_units` facets** | Variable exists but has a different name or unit in the model files.                  |
| **Custom CMOR table** (JSON)        | Variable is not in any standard table; define it once and point ESMValTool to it.     |
| **CMORizer script**                 | Heavy preprocessing needed (regridding, splitting files, reformatting).  Runs once before evaluation. |
| **`ignore_warnings` in model config** | ESMValTool warns about formula terms or cell methods that are harmless (e.g., EMAC). |

### ICON — the simplest case

ESMValTool has **built-in native support for ICON**.  It understands ICON's
unstructured triangular grid, can download the grid description file
automatically, and knows how to regrid ICON output to regular grids for
diagnostics.  No pre-conversion is needed.

For ICON-XPP (Sapphire/Ruby), some variable names differ from CMIP conventions
(e.g., `clct` instead of `clt`).  The `icon_xpp.yml` config maps these via
`raw_name` and `raw_units` extra facets defined in the recipe templates.

### EMAC, CESM, MPAS

These models each have a config file in `ClimateEval/model_configs/`.  As long
as the output contains variables named according to CMIP6 conventions (or
remapped via `raw_name`/`raw_units`), the same recipe templates work without
any pre-conversion.

---

## 3. Adding a New Model — Step-by-Step

### Step 1 — Register the model with ESMValTool

Check whether ESMValTool already knows your model:

```bash
python -c "from esmvalcore.config._config import get_extra_facets; print('ok')"
```

If not, define a minimal project entry in a custom ESMValTool config file and
point to it with `--esmvaltool_options='{"--config_dir": "/path/to/dir"}'`.

### Step 2 — Create a model config YAML

Copy `ClimateEval/model_configs/generic_template.yml` and adapt:

```yaml
project: "MyModel"
dataset: "MyModel-v1"
grid_info: "T63"  # free text, shown in HTML

data_sources:
  default:
    rootpath: "{simulation_path}"
    dirname_template: "output"
    filename_template: "{exp}_*.nc"
```

### Step 3 — Map variable names and units (if needed)

If variables use non-CMIP names, add `raw_name` / `raw_units` mappings either
in the recipe templates directly or as `extra_facets` in the model config:

```yaml
extra_facets:
  ta:
    raw_name: "temperature"
    raw_units: "degC"
```

### Step 4 — Run ClimateEval

```bash
ClimateEval /path/to/my_simulation --model_config=my_model.yml
```

### Step 5 — Iterate

Examine the debug page (`debug.html`) and `main_log_debug.txt` of failing
recipes.  Common issues and fixes are in [faqs.md](faqs.md).

---

## 4. Portability to New Models — How Much Works Out of the Box?

**Best case (CMIP-compliant output):** If your model produces output with CMIP6
variable names, units, and a regular lat-lon grid, almost all recipe templates
work without any changes.  Only the `data_sources` section in the model config
needs to be adapted to match your directory structure.

**Typical case (ICON-like unstructured grid):** ESMValTool handles unstructured
grids natively for ICON.  For other unstructured grids, a regridding pre-step
or custom fixer may be needed (see §5 below).

**Hard case (non-standard variable names, exotic formats):** Requires writing
`raw_name`/`raw_units` mappings or a CMORizer script.  This is a one-time
effort per model; once the config is written, all future runs reuse it.

**Effort estimate by model type:**

| Model type                              | Effort          |
|-----------------------------------------|-----------------|
| ICON (auto-detected)                    | Zero            |
| CMIP6-compliant (CESM, EC-Earth, …)     | Low (config YAML only) |
| Non-CMIP names, regular grid (EMAC)     | Medium (YAML + name/unit mappings) |
| Unstructured non-ICON grid (MPAS, FESOM)| Medium–High (grid fixer or regrid step) |
| Completely non-standard format          | High (CMORizer script needed)   |

---

## 5. Models with Different Grids

### Regular lat-lon grids

No special handling needed.  ESMValTool reads these directly.

### ICON unstructured triangular grid

ESMValTool handles this natively.  It needs the horizontal grid file to
perform regridding.  Either:

- Let ESMValTool download it automatically if the `grid_file_uri` attribute is
  set in the NetCDF files.
- Provide it explicitly:
  ```bash
  ClimateEval /path/to/sim --model_config=icon.yml \
      --horizontal_grid=/path/to/icon_grid.nc
  ```

### Curvilinear grids (e.g., ocean models on rotated grids)

ESMValTool supports curvilinear grids via iris / cf-python.  If the grid
coordinates (`latitude`, `longitude`) are 2D arrays in the file, ESMValTool
will use them.  No extra config is needed as long as the coordinate variable
names follow CF conventions.

### Other unstructured grids (MPAS hexagonal, FESOM triangular, …)

These require either:

1. **Pre-regridding to a regular grid** before ClimateEval is run (e.g., using
   CDO or a model-specific post-processing tool).  Then set `data_sources` to
   point to the regridded output.

2. **A custom ESMValTool fixer/regridder**: write a Python class that extends
   `esmvalcore.preprocessor` and register it for your project.  This is
   advanced but reusable.

For MPAS, a dedicated `mpas.yml` config is included.  See
`ClimateEval/model_configs/mpas.yml` for details.

### Vertical grids

- **Pressure-level data**: works directly.
- **Model-level data (sigma, hybrid-sigma-pressure)**: ESMValTool can
  interpolate to pressure levels using the `extract_levels` preprocessor if the
  correct formula terms are present in the file.  If `zg` (geopotential height)
  is in a separate file, pass it with `--zg_file`.
- **Altitude (z) coordinates**: ESMValTool can convert to pressure using the
  `extract_levels` preprocessor with `coordinate: air_pressure`.

---

## Summary Table

| Question                                    | Answer                                                                              |
|---------------------------------------------|-------------------------------------------------------------------------------------|
| Does ClimateEval convert data to CF format? | No — ESMValTool does this via CMOR fixers, `raw_name`/`raw_units`, or CMORizers     |
| Is a separate "agent" needed for conversion?| No — it is configuration-driven (YAML + optional CMORizer script)                   |
| How much works for a new CMIP-like model?   | Almost everything, with just a model config YAML                                    |
| How much works for a non-CMIP model?        | Depends on variable naming; name/unit mapping in YAML covers most cases             |
| What about unstructured grids?              | ICON: native support; others: pre-regrid or custom fixer                            |
| What about unusual vertical coordinates?    | `extract_levels` preprocessor handles most cases; `--zg_file` for ICON             |
