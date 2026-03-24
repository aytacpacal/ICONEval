"""Generic ESM output evaluation with ESMValTool."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import fire
from loguru import logger

import ClimateEval
from ClimateEval._dependencies import (
    latex_is_available,
    verify_esmvaltool_installation,
    verify_slurm_installation,
)
from ClimateEval._io_handler import ClimateEvalIOHandler
from ClimateEval._logging import configure_logging
from ClimateEval.output_handling._summarize import (
    get_html_description,
    summarize,
    summarize_portable,
)
from ClimateEval.output_handling.plots2pdf import plots2pdf
from ClimateEval.output_handling.publish_html import publish_esmvaltool_html

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from ClimateEval._job import Job
    from ClimateEval._typing import FacetType

logger = logger.opt(colors=True)

HEADER = r"""
----------------------------------------------------------
     ____ _ _                 _       _____            _
    / ___| (_)_ __ ___   __ _| |_ ___| ____|_   ____ _| |
   | |   | | | '_ ` _ \ / _` | __/ _ \  _| \ \ / / _` | |
   | |___| | | | | | | | (_| | ||  __/ |___ \ V / (_| | |
    \____|_|_|_| |_| |_|\__,_|\__\___|_____| \_/ \__,_|_|
----------------------------------------------------------
  ESM output evaluation with ESMValTool
----------------------------------------------------------
"""
TIMES: dict[str, datetime] = {}


def model_evaluation(
    *input_dirs: str | Path,
    model_config: str | Path | None = None,
    publish_html: bool = False,
    portable_html: bool = False,
    html_name: str | None = None,
    create_pdfs: bool = False,
    recipe_templates: str | Path | Iterable[str | Path] | None = None,
    always_use_default_recipe_templates: bool = False,
    log_level: str = "info",
    log_file: str | Path | None = "~/.modeleval/debug.log",
    output_dir: str | Path | None = None,
    account: str | None = None,
    background: bool = False,
    dask: bool = True,
    esmvaltool_executable: str | Path = "esmvaltool",
    srun_executable: str | Path = "srun",
    ignore_recipe_esmvaltool_options: bool = False,
    ignore_recipe_srun_options: bool = False,
    ignore_recipe_dask_options: bool = False,
    esmvaltool_options: dict | None = None,
    srun_options: dict | None = None,
    dask_options: dict | None = None,
    tags: str | list[str] | None = None,
    **extra_facets: FacetType,
) -> None:
    """Evaluate ESM output with ESMValTool.

    Specify a directory containing model simulation output and automatically
    run several (customizable) ESMValTool recipes on this output. Supports
    any Earth System Model through a model configuration file, with built-in
    auto-detection for ICON simulations.

    Parameters
    ----------
    input_dirs:
        One or multiple simulation directories that will be evaluated.
        These are the directories whose names are identical to the experiment
        name of the simulation.
    model_config:
        Path to a YAML file describing the model's output conventions
        (project name, dataset name, file naming patterns, directory
        structure). If not given, ICON auto-detection is used for backward
        compatibility. See ``model_configs/`` for examples.
    publish_html:
        Publish ESMValTool summary HTML on a **public** website using DKRZ's
        Python-swiftclient
        (https://docs.dkrz.de/doc/datastorage/swift/python-swiftclient.html).
    portable_html:
        Create self-contained ``*_portable.html`` copies of the summary HTML
        files in which all figures are embedded as base64 data URIs. The
        resulting files can be shared as a single file without needing the
        accompanying plot directories.
    html_name:
        Name that is used for the URL of the ESMValTool summary HTML and the
        output subdirectory that will be created in `output_dir`. Use this to
        get a consistent URL (this will potentially overwrite existing data!).
        If not given, use the (concatenated) experiment names of the input
        simulations including a datetime string.
    create_pdfs:
        Create PDFs that contain an overview of all plots (one PDF for each
        recipe).
    recipe_templates:
        Run the specified recipe templates. Unix-style wildcards are supported.
        To run multiple recipe (patterns), use the syntax
        `--recipe_templates='["/path/to/recipe_1.yml",
        "/path/to/recipe_2.yml"]'`. If `None`, run all default recipe templates
        available in the installation/repository directory of ClimateEval. Make
        sure that all recipe template names start with `recipe_`.
    always_use_default_recipe_templates:
        If `True`, always run all default recipe templates available in the
        installation/repository directory of ClimateEval in addition to the ones
        specified by `--recipe_templates`. If `False`, only run the recipes
        specified by `--recipe_templates`. If `--recipe_templates=None`, the
        default recipe templates will always be run.
    log_level:
        Log level. Must be one of `debug`, `info`, `warning`, `error`.
    log_file:
        File where ClimateEval debug output is logged. If `None`, do not log to a
        file. New messages are attached to existing files.
    output_dir:
        Output directory where the output of ClimateEval will be stored. If
        `None`, use the folder `output_modeleval` in the current working
        directory. If the directory does not exist yet, it will automatically
        be created. Output from individual ClimateEval runs is not stored directly
        in the `--output_dir`, but rather in a subdirectory whose name is
        determined by the option `--html_name`.
    account:
        Account that is charged for the Slurm jobs. By default, use account
        that is used for `sbatch`/`salloc` (if ClimateEval is run within `sbatch`
        script or `salloc` session), or `'bd1179'` otherwise.
    background:
        Terminate ClimateEval after submitting all jobs/job steps. Neither
        summary HTMLs nor PDFs can be published/written in this mode.
    dask:
        If `True`, use Dask distributed scheduler when running ESMValTool. If
        `False`, use default (thread-based) Dask scheduler when running
        ESMValTool.
    esmvaltool_executable:
        Path to ESMValTool executable.
    srun_executable:
        Path to `srun` executable.
    ignore_recipe_esmvaltool_options:
        If `True`, ignore additional ESMValTool configuration options specified
        in the recipe templates via the syntax `#ESMVALTOOL --option=value`. If
        `False`, do not ignore them.
    ignore_recipe_srun_options:
        If `True`, ignore additional srun options specified in the recipe
        templates via the syntax `#SRUN --option=value`. If `False`, do not
        ignore them.
    ignore_recipe_dask_options:
        If `True`, ignore additional dask options specified in the recipe
        templates via the syntax `#DASK --option=value`. If `False`, do not
        ignore them.
    esmvaltool_options:
        Additional ESMValTool configuration options used to run all recipes.
        These settings will be overwritten by recipe-specific `#ESMVALTOOL`
        options. Use the syntax `--esmvaltool_options: '{"--option":
        "value"}'`.
    srun_options:
        Additional srun options used to run all recipes. These settings will be
        overwritten by recipe-specific `#SRUN` options. Use the syntax
        `--srun_options: '{"--option": "value"}'`.
    dask_options:
        Additional Dask options used to run all recipes. These settings will be
        overwritten by recipe-specific `#DASK` options. Ignored if
        `--dask=False`. Use the syntax `--dask_options: '{"--option":
        "value"}'`.
    tags:
        Only recipes with the given tags are run. If not given, run all
        recipes.
    **extra_facets:
        Additional options are considered as extra facets for the model data.

    Raises
    ------
    FileNotFoundError
        ``recipe_templates`` not found.
    NotADirectoryError
        ``input_dir`` not found.
    ValueError
        No input directory given.
    ValueError
        Invalid ``log_level`` is given.
    ValueError
        No recipes found to evaluate.
    ValueError
        An invalid template is given.

    """
    TIMES["start"] = datetime.now(UTC)

    # Initialize tool
    configure_logging(log_level, log_file=log_file)
    logger.info("Starting ClimateEval")
    logger.info(f"ClimateEval version: {ClimateEval.__version__}")
    logger.info(f"Debug log: <cyan>{log_file}</cyan>")
    logger.info("")

    # Log all command line options
    logger.debug("Command line options:")
    logger.debug("---------------------")
    logger.debug(f"{'input_dirs':<35} = {input_dirs}")
    logger.debug(f"{'model_config':<35} = {model_config}")
    logger.debug(f"{'publish_html':<35} = {publish_html}")
    logger.debug(f"{'portable_html':<35} = {portable_html}")
    logger.debug(f"{'html_name':<35} = {html_name}")
    logger.debug(f"{'create_pdfs':<35} = {create_pdfs}")
    logger.debug(f"{'recipe_templates':<35} = {recipe_templates}")
    logger.debug(
        f"{'always_use_default_recipe_templates':<35} = "
        f"{always_use_default_recipe_templates}",
    )
    logger.debug(f"{'log_level':<35} = {log_level}")
    logger.debug(f"{'log_file':<35} = {log_file}")
    logger.debug(f"{'output_dir':<35} = {output_dir}")
    logger.debug(f"{'account':<35} = {account}")
    logger.debug(f"{'background':<35} = {background}")
    logger.debug(f"{'dask':<35} = {dask}")
    logger.debug(f"{'esmvaltool_executable':<35} = {esmvaltool_executable}")
    logger.debug(f"{'srun_executable':<35} = {srun_executable}")
    logger.debug(f"{'tags':<35} = {tags}")
    logger.debug(
        f"{'ignore_recipe_esmvaltool_options':<35} = "
        f"{ignore_recipe_esmvaltool_options}",
    )
    logger.debug(
        f"{'ignore_recipe_srun_options':<35} = {ignore_recipe_srun_options}",
    )
    logger.debug(
        f"{'ignore_recipe_dask_options':<35} = {ignore_recipe_dask_options}",
    )
    logger.debug(f"{'esmvaltool_options':<35} = {esmvaltool_options}")
    logger.debug(f"{'srun_options':<35} = {srun_options}")
    logger.debug(f"{'dask_options':<35} = {dask_options}")
    if extra_facets:
        logger.debug("Extra facets:")
        for key, val in extra_facets.items():
            logger.debug(f"  {key} = {val}")
    logger.debug("")

    # Verify that all dependencies are available
    esmvaltool_executable = str(esmvaltool_executable)
    srun_executable = str(srun_executable)
    verify_esmvaltool_installation(esmvaltool_executable)
    verify_slurm_installation(srun_executable)
    logger.debug("")

    # Get default account if necessary
    if account is None:
        if "SLURM_JOB_ACCOUNT" in os.environ:
            account = os.environ["SLURM_JOB_ACCOUNT"]
        else:
            account = "bd1179"

    # Basic setup of IO directories and files
    TIMES["start_setup"] = datetime.now(UTC)
    io_handler = ClimateEvalIOHandler(
        input_dirs, output_dir, html_name, model_config=model_config
    )
    TIMES["end_setup"] = datetime.now(UTC)

    # Setup jobs (i.e., recipes and configuration)
    jobs = io_handler.get_jobs(
        recipe_template_paths=recipe_templates,
        always_use_default_recipe_templates=always_use_default_recipe_templates,
        account=account,
        dask=dask,
        esmvaltool_executable=esmvaltool_executable,
        srun_executable=srun_executable,
        ignore_recipe_esmvaltool_options=ignore_recipe_esmvaltool_options,
        ignore_recipe_srun_options=ignore_recipe_srun_options,
        ignore_recipe_dask_options=ignore_recipe_dask_options,
        additional_esmvaltool_options=esmvaltool_options,
        additional_srun_options=srun_options,
        additional_dask_options=dask_options,
        tags=tags,
        **extra_facets,
    )
    logger.debug("Recipes:")
    logger.debug("--------")
    for job in jobs:
        logger.debug(f"  - {job.recipe.path}")
    logger.debug("")

    # Run jobs
    _run_jobs(jobs, background=background)
    if background:
        TIMES["end"] = datetime.now(UTC)
        logger.info("Ending ClimateEval")
        logger.info(
            f"Time for running ClimateEval was {TIMES['end'] - TIMES['start']}",
        )
        return

    # Create summary HTML and publish it if desired
    TIMES["start_html"] = datetime.now(UTC)
    logger.info("HTML output:")
    logger.info("------------")
    _create_summary_html(io_handler)
    if portable_html:
        summarize_portable(io_handler.output_dir_esmvaltool)
    if publish_html:
        _publish_html(io_handler, html_name)
    TIMES["end_html"] = datetime.now(UTC)
    logger.debug(
        f"Time for creating HTML output was {TIMES['end_html'] - TIMES['start_html']}",
    )
    logger.info("")

    # Create PDFs if desired
    if create_pdfs:
        _create_pdfs(io_handler, jobs)

    # Print summary
    TIMES["end"] = datetime.now(UTC)
    logger.info("Ending ClimateEval")
    logger.info(
        f"Time for running ClimateEval was {TIMES['end'] - TIMES['start']}",
    )


def _create_pdfs(io_handler: ClimateEvalIOHandler, jobs: list[Job]) -> None:
    """Create PDFs."""
    TIMES["start_pdfs"] = datetime.now(UTC)
    logger.info("PDF output:")
    logger.info("-----------")
    if latex_is_available():
        for job in jobs:
            logger.info(f"- {job}:")
            if not job.is_successful():
                logger.warning("  Skipping PDF creation since job failed")
            else:
                plots2pdf(
                    job.output_dir,  # type: ignore[arg-type]
                    output_dir=io_handler.output_dir_pdfs,
                    setup_logging=False,
                )
    else:
        logger.warning("No LaTeX distribution found, cannot create PDFs")
    TIMES["end_pdfs"] = datetime.now(UTC)
    logger.debug(
        f"Time for creating the PDFs was {TIMES['end_pdfs'] - TIMES['start_pdfs']}",
    )
    logger.info("")


def _create_summary_html(io_handler: ClimateEvalIOHandler) -> None:
    """Create summary HTML."""
    description = get_html_description(io_handler, TIMES["start"])
    summarize(io_handler.output_dir_esmvaltool, description=description)


def _publish_html(
    io_handler: ClimateEvalIOHandler,
    html_name: str | None,
) -> None:
    """Publish HTML."""
    if html_name is None:
        html_name = io_handler.output_dir.name
    container_name = "modeleval"
    logger.info(
        f"Publishing results in swift container '{container_name}' under "
        f"directory '{html_name}'",
    )
    publish_esmvaltool_html(
        io_handler.output_dir_esmvaltool,
        container_name=container_name,
        dir_name=html_name,
        setup_logging=False,
    )


def _run_jobs(jobs: Sequence[Job], *, background: bool) -> None:
    """Run all jobs."""
    TIMES["start_jobs"] = datetime.now(UTC)
    logger.info("Jobs:")
    logger.info("-----")

    # Start jobs
    for job in jobs:
        logger.info(f"- <magenta>{job}</magenta> (Log: <cyan>{job.slurm_log}</cyan>)")
        job.start()
    logger.info("")
    n_jobs = len(jobs)
    run_jobs_msg = f"Running {n_jobs} job(s):"
    logger.info(run_jobs_msg)
    logger.info("-" * len(run_jobs_msg))

    # Run jobs in background
    if background:
        TIMES["end_jobs"] = datetime.now(UTC)
        logger.info(f"All {n_jobs} job(s) are running in background now")
        logger.debug(
            f"Time for starting the job(s) was "
            f"{TIMES['end_jobs'] - TIMES['start_jobs']}",
        )
        logger.info("")
        return

    # Run jobs in foreground
    successful_jobs = []
    finished_jobs = []
    try:
        while True:
            for job in jobs:
                if job.is_running():
                    continue
                if job in finished_jobs:
                    continue
                logger.info(f"{job.log_status()}")
                logger.info(f"    Log: <cyan>{job.slurm_log}</cyan>")
                (stdout, stderr) = job.communicate()
                logger.debug("    Output to stdout:")
                logger.debug(stdout)
                logger.debug("    Output to stderr:")
                logger.debug(stderr)
                if job.is_successful():
                    successful_jobs.append(job)
                finished_jobs.append(job)
                n_running_jobs = n_jobs - len(finished_jobs)
                if n_running_jobs:
                    logger.info(
                        f"    {n_running_jobs}/{n_jobs} job(s) are still running",
                    )
            time.sleep(1.0)
            if len(finished_jobs) == n_jobs:
                break

    # Always terminate jobs when exiting the loop
    finally:
        logger.debug("Terminating all running jobs")
        for job in jobs:
            if job.is_running():
                job.terminate()
                logger.debug(f"  - Terminated {job}")

    TIMES["end_jobs"] = datetime.now(UTC)
    logger.info(
        f"{len(successful_jobs)}/{n_jobs} job(s) finished successfully",
    )
    logger.debug(
        f"Time for running the job(s) was {TIMES['end_jobs'] - TIMES['start_jobs']}",
    )
    logger.info("")

    return


def main() -> None:
    """Invoke ``fire`` to process command line arguments."""
    print(HEADER)
    fire.Fire(model_evaluation)


# Backward compatibility alias
icon_evaluation = model_evaluation


if __name__ == "__main__":
    main()
