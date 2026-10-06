#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --job-name=behavior_eval
#SBATCH --output=%j.out
#SBATCH --error=%j.err

module load anaconda
export OMNIGIBSON_HEADLESS=1
cd ~/project/BEHAVIOR-1K

PY=/home/msai/linj0121/.conda/envs/behavior/bin/python

$PY -m omnigibson.examples.environments.vector_env_demo

echo "=== Eval test finished ==="
date