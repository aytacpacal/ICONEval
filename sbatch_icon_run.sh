#!/bin/bash -e
#SBATCH --mem=0
#SBATCH --nodes=1
#SBATCH --partition=compute
#SBATCH --time=04:00:00
#SBATCH --account=bd1179

iconeval /work/bd1179/b309275/icon-ml_models/icon-a-ml_for_Arthur/experiments/ag_atm_amip_r2b5_cov15_tuned_Arthur_long --srun_options='{"--cpus-per-task": 16, "--mem-per-cpu": "1940M"}' --tags='["atmosphere"]'
