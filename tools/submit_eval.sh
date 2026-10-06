#!/bin/bash
# 便捷的评估脚本 - 用于 SLURM 提交
# 使用方法: sbatch tools/submit_eval.sh <preset> <run_name>

#SBATCH --job-name=eval
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --output=logs/eval_%j.out
#SBATCH --error=logs/eval_%j.err

set -e

# 参数
PRESET=${1:-pi05_turning_on_radio}
RUN_NAME=${2:-slurm_${SLURM_JOB_ID}}

echo "=========================================="
echo "Evaluation Job: ${SLURM_JOB_ID}"
echo "Preset: ${PRESET}"
echo "Run name: ${RUN_NAME}"
echo "=========================================="

cd ~/project/BEHAVIOR-1K

# 确保 logs 目录存在
mkdir -p logs

# 运行评估
python tools/eval_runner.py \
    --preset "${PRESET}" \
    --run-name "${RUN_NAME}"

echo "=========================================="
echo "Job completed: ${SLURM_JOB_ID}"
echo "=========================================="
