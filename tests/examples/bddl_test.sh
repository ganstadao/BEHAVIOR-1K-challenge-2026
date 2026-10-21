#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --job-name=behavior_eval
#SBATCH --output=outputs/bddl_test_out.log
#SBATCH --error=outputs/bddl_test_err.log

export OMNIGIBSON_HEADLESS=1
cd ~/project/BEHAVIOR-1K
PY=/home/msai/linj0121/.conda/envs/behavior/bin/python

$PY tests/test_bddl.py