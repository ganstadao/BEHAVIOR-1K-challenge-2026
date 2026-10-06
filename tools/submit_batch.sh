#!/bin/bash
# 批量 SLURM 提交脚本
# 用于一次提交多个评估任务
#
# 使用方法:
#   bash tools/submit_batch.sh <config> <run_prefix> <task1> [task2] [task3] ...
#
# 示例:
#   bash tools/submit_batch.sh pi05_turning_on_radio baseline turning_on_radio turning_on_lamp
#   bash tools/submit_batch.sh configs/pi05_unlimited_steps.yaml full_eval task1 task2 task3

set -e

if [ $# -lt 3 ]; then
    echo "Usage: $0 <config_or_preset> <run_prefix> <task1> [task2] [task3] ..."
    echo ""
    echo "Examples:"
    echo "  $0 pi05_turning_on_radio baseline turning_on_radio turning_on_lamp opening_door"
    echo "  $0 configs/my_config.yaml exp1 task1 task2 task3"
    exit 1
fi

CONFIG_OR_PRESET="$1"
RUN_PREFIX="$2"
shift 2

TASKS=("$@")

echo "=========================================="
echo "Batch SLURM Submission"
echo "=========================================="
echo "Config/Preset: ${CONFIG_OR_PRESET}"
echo "Run prefix: ${RUN_PREFIX}"
echo "Tasks: ${TASKS[@]}"
echo "Total: ${#TASKS[@]} tasks"
echo "=========================================="
echo ""

JOB_IDS=()

for task in "${TASKS[@]}"; do
    run_name="${RUN_PREFIX}_${task}"

    echo "Submitting: ${task}"
    echo "  Run name: ${run_name}"

    # 提交作业
    job_output=$(sbatch tools/submit_eval_advanced.sh \
        "${CONFIG_OR_PRESET}" \
        "${run_name}" \
        --set task.name="${task}")

    # 提取 job ID
    job_id=$(echo "$job_output" | grep -oP 'Submitted batch job \K\d+')
    JOB_IDS+=($job_id)

    echo "  Job ID: ${job_id}"
    echo ""

    # 短暂延迟，避免同时启动
    sleep 2
done

echo "=========================================="
echo "All jobs submitted!"
echo "=========================================="
echo "Job IDs: ${JOB_IDS[@]}"
echo ""
echo "Monitor jobs:"
echo "  squeue -u \$USER"
echo ""
echo "Check specific job:"
echo "  tail -f logs/eval_<job_id>.out"
echo ""
echo "Cancel all jobs:"
echo "  scancel ${JOB_IDS[@]}"
echo "=========================================="
