#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=28G
#SBATCH --time=06:00:00
#SBATCH --job-name=behavior_eval
#SBATCH --output=outputs/boil_water/boil_water_%j.out
#SBATCH --error=outputs/boil_water/boil_water_%j.err

module load anaconda
export OMNIGIBSON_HEADLESS=1
cd ~/project/BEHAVIOR-1K
PY=/home/msai/linj0121/.conda/envs/behavior/bin/python

%PY -m behavior python -m omnigibson.eval.eval \
    --task-name boil_water \
    --instance-indices 0 \
    --max-steps 100 \
    --policy local \
    --output-dir ~/outputs/boil_water \
    --write-video \
    --headles