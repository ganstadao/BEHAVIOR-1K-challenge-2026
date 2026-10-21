#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=28G
#SBATCH --time=06:00:00
#SBATCH --job-name=behavior_eval
#SBATCH --output=turning_on_radio_%j.out
#SBATCH --error=turning_on_radio_%j.err

module load anaconda
export OMNIGIBSON_HEADLESS=1
cd ~/project/BEHAVIOR-1K
PY=/home/msai/linj0121/.conda/envs/behavior/bin/python

$PY -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 0 \
    --max-steps 500 \
    --policy local \
    --output-dir ~/project/BEHAVIOR-1K/outputs/my_eval \
    --write-video \
    --headless

echo "=== Eval test finished ==="
date