#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --job-name=behavior_eval
#SBATCH --output=outputs/robot_test_out.log
#SBATCH --error=outputs/robot_test_err.log

module load anaconda
export OMNIGIBSON_HEADLESS=1
cd ~/project/BEHAVIOR-1K
PY=/home/msai/linj0121/.conda/envs/behavior/bin/python

$PY -m debugpy --listen 0.0.0.0:1234 --wait-for-client tests/robot_test.py
#$PY tests/robot_test.py