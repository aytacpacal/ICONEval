> [!NOTE]
> This is a modified version of ICONEval that supports evaluation of **any
> Earth System Model** (not just ICON) by defining your model with a YAML
> configuration file. ICON simulations are still auto-detected for backward
> compatibility. The tool was originally designed to run on [DKRZ's
> Levante](https://docs.dkrz.de/doc/levante/) and the built-in observational
> data paths in the ESMValTool configuration template are Levante-specific —
> adapt them for other systems.

---

[![LICENSE](https://img.shields.io/badge/License-Apache%202.0-blue)](https://www.apache.org/licenses/LICENSE-2.0.html)

---

# ModelEval (formerly ICONEval)

ESM output evaluation with ESMValTool.

## Table of Contents

- [ModelEval (formerly ICONEval)](#modeleval-formerly-iconeval)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
  - [Model Configuration](#model-configuration)
  - [Example Results](#example-results)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
    - [Levante](#levante)
    - [Installation from Source (Development Installation)](#installation-from-source-development-installation)
  - [Customization](#customization)
  - [ICON Output Format](#icon-output-format)
  - [FAQs](#faqs)

## Quick Start

ModelEval evaluates Earth System Model output with [ESMValTool](doc/esmvaltool.md)
by automatically running a set of predefined ESMValTool recipes.

### ICON (auto-detection)

For ICON simulations, no model configuration file is needed. Pass the path to
the simulation output directory (whose name must match the experiment name):

```bash
modeleval path/to/ICON_output
```

The `iconeval` command is kept as a backward-compatible alias.

### Other models

For any other ESM, provide a [model configuration YAML](#model-configuration):

```bash
modeleval path/to/my_simulation --model_config=my_model.yml
```

### Multiple simulations

Multiple simulations can be evaluated simultaneously:

```bash
modeleval path/to/sim1 path/to/sim2 --model_config=my_model.yml
```

---

ModelEval reads a set of file templates (ESMValTool recipes and ESMValTool
configuration) and fills these with information from the simulation that will
be evaluated. If no further options are specified, a set of default recipes
with default settings are run. If ModelEval is run as a standalone script, one
[Slurm](https://slurm.schedmd.com/) job per recipe is launched. If ModelEval
is run within an `sbatch` script or `salloc` session, one job step per recipe
is created. The following `sbatch` script can be used to submit a job on a
compute node of [DKRZ's Levante](https://docs.dkrz.de/doc/levante/) in which
8 recipes are run in parallel (see
[here](doc/customization.md#slurm-options-for-jobjob-step-submission) for
details on this):

```bash
#!/bin/bash -e
#SBATCH --mem=0
#SBATCH --nodes=1
#SBATCH --partition=compute
#SBATCH --time=03:00:00

modeleval path/to/my_simulation --model_config=my_model.yml \
    --srun_options='{"--cpus-per-task": 16, "--mem-per-cpu": "1940M"}'
```

ModelEval is highly customizable. For example, the desired time range and
frequency of the input data, as well as a flag to publish a summary HTML on a
**public** website can be passed with

```bash
modeleval path/to/my_simulation --model_config=my_model.yml \
    --timerange='20070101/20080101' --frequency=mon --publish_html=True
```

Publishing results via the command line option `--publish_html=True` uses the
[Swift object storage of
DKRZ](https://docs.dkrz.de/doc/datastorage/swift/python-swiftclient.html) and
requires a DKRZ account. User authentication works via a *Swift token* that
needs to be renewed monthly. If the token needs to be renewed, the user is
prompted for their DKRZ account and password information when running ModelEval.
The token can also be regenerated manually, see [FAQs](doc/faqs.md) for
details. The raw files (figures and data) from published results can be
accessed via DKRZ's [Swiftbrowser](https://swiftbrowser.dkrz.de/).

To only run a subset of available recipes, you can specify `--tags` when
running ModelEval:

```bash
modeleval path/to/my_simulation --model_config=my_model.yml --tags=timeseries,maps
```

An overview of all tags available in the default recipe templates is given
[here](doc/tags.md).

For more information on this and a list of all options, run

```bash
modeleval -- --help
```

or have a look at the section on [Customization](#customization).

Installing ModelEval also provides the command line tools `plots2pdf` (create
summary PDF for arbitrary ESMValTool output) and `publish_html` (publish
summary HTML on public website for arbitrary ESMValTool output). For more
information on them, run

```bash
plots2pdf -- --help
publish_html -- --help
```

## Model Configuration

To evaluate output from any ESM, create a YAML file describing your model's
output conventions. Example configuration files for several models are provided
in [`modeleval/model_configs/`](modeleval/model_configs/):

| File | Model |
|------|-------|
| `icon.yml` | ICON (standard) |
| `icon_xpp.yml` | ICON-XPP (Sapphire/Ruby) |
| `emac.yml` | EMAC |
| `cesm.yml` | CESM |
| `mpas.yml` | MPAS |
| `generic_template.yml` | Template for new models |

A minimal configuration file looks like this:

```yaml
# Required: ESMValTool project name
project: "MyModel"

# Optional: dataset identifier shown in plots (defaults to project name)
dataset: "MyModel-v1"

# Optional: free-text grid info shown in HTML summary
# grid_info: "1deg"

# Optional: extra facets passed to ESMValTool
# extra_facets:
#   frequency: "mon"

# Define where output files are and how they are named.
# {simulation_path} and {exp} are replaced at runtime.
data_sources:
  default:
    rootpath: "{simulation_path}"
    dirname_template: ""
    filename_template: "*.nc"
```

Copy `generic_template.yml` as a starting point and adapt it to your model.
The `project` field must match a project that ESMValTool can load (e.g., a
project with a registered CMORizer, or one that uses the same naming
conventions as a supported project). ICON is natively supported by ESMValTool
without any extra setup.

Run with your model config:

```bash
modeleval path/to/my_simulation --model_config=/path/to/my_model.yml
```

## Example Results

- [Fully coupled historical ICON-XPP simulation (3
  members)](https://swift.dkrz.de/v1/dkrz_4eefb34f-8803-415a-bd70-9c455db9a403/iconeval/iconeval_example/index.html)

## Prerequisites

ModelEval needs to run on a machine where the [Slurm Workload
Manager](https://slurm.schedmd.com/) is available for the submission of jobs.

## Installation

On DKRZ's Levante, a pre-installed version of ICONEval is available via a
module. Thus, there is no need to install it yourself as a user on this
machine.

However, on other machines, or if you would like to develop new features for
ModelEval on Levante, an installation from source (*development installation*)
is necessary.

### Levante

To load the ICONEval module on Levante, use

```bash
module use -a /work/bd1179/modulefiles
module load iconeval
```

Add these lines to your shell configuration file if you use ModelEval regularly.
[This file](doc/setup_module.md) describes how the ICONEval module is set up.

### Installation from Source (Development Installation)

Installation from source is described [here](doc/install_from_source.md).

## Customization

ModelEval is highly customizable. Detailed information on this can be found
[here](doc/customization.md).

## ICON Output Format

For ICON auto-detection to work smoothly, the ICON simulation output should
follow [these criteria](doc/icon_output_format.md) as closely as possible.
For other models, use `--model_config` instead (see [Model
Configuration](#model-configuration)).

## FAQs

A set of frequently asked questions can be found [here](doc/faqs.md).
