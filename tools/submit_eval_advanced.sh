#!/bin/bash
# 增强的 SLURM 评估提交脚本
# 支持更灵活的参数传递
#
# 使用方法:
#   sbatch tools/submit_eval_advanced.sh <config_or_preset> [run_name] [additional_args...]
#
# 示例:
#   sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio exp1
#   sbatch tools/submit_eval_advanced.sh configs/my_config.yaml my_run
#   sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test --set task.max_steps=0
#   sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps unlimited_run

#SBATCH --job-name=eval
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=6:00:00
#SBATCH --output=logs/eval_%j.out
#SBATCH --error=logs/eval_%j.err

set -e

# 解析参数
CONFIG_OR_PRESET="${1:-pi05_turning_on_radio}"
RUN_NAME="${2:-slurm_${SLURM_JOB_ID}}"
shift 2 || true  # 移除前两个参数，剩下的是额外参数

echo "=========================================="
echo "SLURM Evaluation Job"
echo "=========================================="
echo "Job ID: ${SLURM_JOB_ID}"
echo "Config/Preset: ${CONFIG_OR_PRESET}"
echo "Run name: ${RUN_NAME}"
echo "Node: $(hostname)"
echo "GPU: ${CUDA_VISIBLE_DEVICES:-auto}"
echo "Time: $(date)"
echo "=========================================="

cd ~/project/BEHAVIOR-1K

# 确保目录存在
mkdir -p logs

# 构建基本命令
CMD="python tools/eval_runner.py --run-name ${RUN_NAME}"

# 判断是配置文件还是预设
if [[ "${CONFIG_OR_PRESET}" == *.yaml ]]; then
    # 配置文件
    CMD="${CMD} --config ${CONFIG_OR_PRESET}"
else
    # 预设
    CMD="${CMD} --preset ${CONFIG_OR_PRESET}"
fi

# 添加额外参数
if [ $# -gt 0 ]; then
    echo "Additional arguments: $@"
    CMD="${CMD} $@"
fi

echo ""
echo "Command:"
echo "  ${CMD}"
echo ""
echo "=========================================="

# 运行评估
eval ${CMD}

EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Job completed: ${SLURM_JOB_ID}"
echo "Exit code: ${EXIT_CODE}"
echo "Time: $(date)"
echo "=========================================="

exit ${EXIT_CODE}
