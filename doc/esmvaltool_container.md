[Back to README](../README.md)

# Containerized Installation of ESMValTool

To avoid installing a development installation of ESMValTool in a conda/mamba
environment that creates thousands of files, a containerized installation can
be used. This can be done with [Apptainer](https://apptainer.org/) (formerly
Singularity), which is an alternative to [Docker](https://www.docker.com/) more
suitable for HPC systems.

For example, on Levante, a container image is available at
`/work/bd1179/esmvaltool/bin/esmvaltool.sif`. It can be run via

```bash
singularity run -B /work:/work,/scratch:/scratch esmvaltool.sif run /path/to/recipe.yml
```

Make sure to `module load singularity` first.

To build a custom container image, you need root access. Note that you can
build the container image on another machine and then copy it to the machine of
your choice. Use the following instructions to build an ESMValTool container
image:

1. Clone the [ESMValTool](https://github.com/ESMValGroup/ESMValTool) and
   [ESMValCore](https://github.com/ESMValGroup/ESMValCore) repositories.

2. Create a [definition
   file](https://apptainer.org/docs/user/main/definition_files.html) called
   `esmvaltool.def` with the following contents:

   ```def
   Bootstrap: docker
   From: condaforge/mambaforge

   %labels
       Author manuel.schlund@dlr.de

   %files
       ../ESMValCore /ESMValCore
       ../ESMValTool /ESMValTool

   %post
       mamba env create -y -q -n esm -f ESMValTool/environment.yml
       cd /ESMValTool
       /opt/conda/envs/esm/bin/pip install -e ".[develop]"
       cd /ESMValCore
       /opt/conda/envs/esm/bin/pip install -e ".[develop]"
       mamba env list
       mamba list -n esm

   %environment
       source /opt/conda/bin/activate esm

   %runscript
       esmvaltool "$@"
   ```

3. Build the container image with

   ```bash
   sudo -E apptainer build esmvaltool.sif esmvaltool.def
   ```
