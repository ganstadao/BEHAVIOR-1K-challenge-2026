#!/bin/bash
#SBATCH --job-name=pi05_eval
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --output=logs/pi05_eval_%j.out
#SBATCH --error=logs/pi05_eval_%j.err

set -e

# ---------- 配置区 ----------
export OPENPI_DIR=~/LINJ0121/openpi
export PATH_TO_BEHAVIOR_1K=~/project/BEHAVIOR-1K
export TASK_NAME=turning_on_radio
export PATH_TO_CKPT=~/LINJ0121/checkpoint/pi05_turn_on_the_radio
export PORT=8000
export REPO_ID=turning_on_radio
export LOG_PATH=./eval_logs/pi05_$TASK_NAME
export OPENPI_LOG_LEVEL=DEBUG

# Python 绝对路径
export OPENPI_PYTHON=$OPENPI_DIR/.venv/bin/python
export BEHAVIOR_PYTHON=/home/msai/linj0121/.conda/envs/behavior/bin/python
# ---------------------------

mkdir -p logs "$LOG_PATH"

# 自检
if [ ! -x "$OPENPI_PYTHON" ]; then
    echo "ERROR: OPENPI_PYTHON not found: $OPENPI_PYTHON"; exit 1
fi
if [ ! -x "$BEHAVIOR_PYTHON" ]; then
    echo "ERROR: BEHAVIOR_PYTHON not found: $BEHAVIOR_PYTHON"; exit 1
fi
if [ ! -d "$PATH_TO_CKPT" ]; then
    echo "ERROR: CHECKPOINT not found: $PATH_TO_CKPT"; exit 1
fi
echo "OpenPI python: $OPENPI_PYTHON"
echo "Behavior python: $BEHAVIOR_PYTHON"
echo "Checkpoint: $PATH_TO_CKPT"

echo "=== [1/3] Starting pi0.5 policy server on GPU 0, port $PORT ==="
cd "$OPENPI_DIR"

CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.85 \
"$OPENPI_PYTHON" scripts/b1k/serve_b1k.py \
    --robot b1k/R1Pro \
    --task b1k/$TASK_NAME \
    --repo-id $REPO_ID \
    --policy.config pi05_b1k \
    --policy.dir "$PATH_TO_CKPT" \
    --control_mode receding_horizon \
    --action_horizon 16 \
    --port "$PORT" \
    &
SERVE_PID=$!
echo "Policy server PID: $SERVE_PID"

# 等待服务器就绪（最多 180 秒，JAX 加载模型较慢）
echo "Waiting for policy server to be ready..."
for i in $(seq 1 90); do
    if curl -s "http://127.0.0.1:$PORT/healthz" > /dev/null 2>&1; then
        echo "Policy server is ready (after ~$((i*2))s)."
        break
    fi
    sleep 2
    if [ "$i" -eq 90 ]; then
        echo "ERROR: Policy server did not become ready within 180s."
        kill "$SERVE_PID" 2>/dev/null || true
        exit 1
    fi
done

echo ""
echo "=== [2/3] Starting OmniGibson evaluator ==="
cd "$PATH_TO_BEHAVIOR_1K"

CUDA_VISIBLE_DEVICES=0 "$BEHAVIOR_PYTHON" -m omnigibson.eval.eval \
    --task-name "$TASK_NAME" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --output-dir "$LOG_PATH" \
    --write-video \
    --env-wrapper omnigibson.eval.wrappers.RGBDFullResWrapper

EVAL_EXIT=$?
echo "Evaluator exited with code: $EVAL_EXIT"

echo ""
echo "=== [3/3] Cleaning up ==="
kill "$SERVE_PID" 2>/dev/null || true
wait "$SERVE_PID" 2>/dev/null || true

echo "Done. Results saved to: $LOG_PATH"
exit $EVAL_EXIT
