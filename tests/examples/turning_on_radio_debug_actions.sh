#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --job-name=gr00t_debug
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --output=logs/gr00t_debug_%j.out
#SBATCH --error=logs/gr00t_debug_%j.err

set -e

# ---------- 配置区 ----------
export GROOT_DIR=~/LINJ0121/Isaac-GR00T
export PATH_TO_BEHAVIOR_1K=~/project/BEHAVIOR-1K
export TASK_NAME=turning_on_radio
export PATH_TO_CKPT=~/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000
export PORT=8000
export LOG_PATH=./eval_logs/${TASK_NAME}_action_debug

mkdir -p logs
mkdir -p $LOG_PATH

echo "=========================================="
echo "🔍 Action Debug Mode - With Logging"
echo "=========================================="
echo "Task: $TASK_NAME"
echo "Log path: $LOG_PATH"
echo "Max steps: 100 (for quick debugging)"
echo "=========================================="

# ---------- 启动 Policy Server ----------
echo ""
echo "=== [1/3] Starting GR00T policy server ==="

cd "$GROOT_DIR"
SERVER_LOG="$PATH_TO_BEHAVIOR_1K/$LOG_PATH/policy_server.log"

CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/b1k/serve_b1k.py \
    --model-path "$PATH_TO_CKPT" \
    --modality-config-path examples/b1k/r1pro.py \
    --embodiment-tag NEW_EMBODIMENT \
    --host 127.0.0.1 \
    --port "$PORT" \
    > "$SERVER_LOG" 2>&1 &
SERVE_PID=$!
echo "Policy server PID: $SERVE_PID"

# 等待服务器就绪
echo "Waiting for policy server..."
for i in $(seq 1 60); do
    if ! ps -p "$SERVE_PID" > /dev/null 2>&1; then
        echo "ERROR: Policy server died!"
        tail -30 "$SERVER_LOG"
        exit 1
    fi

    if curl -s "http://127.0.0.1:$PORT/healthz" > /dev/null 2>&1; then
        echo "✓ Policy server ready (after ~$((i*3))s)"
        break
    fi

    if [ $((i % 10)) -eq 0 ]; then
        echo "  Still waiting... ($((i*3))s elapsed)"
    fi

    sleep 3

    if [ "$i" -eq 60 ]; then
        echo "ERROR: Timeout waiting for server"
        tail -30 "$SERVER_LOG"
        kill "$SERVE_PID" 2>/dev/null || true
        exit 1
    fi
done

# ---------- 运行评估（带 Action Logging） ----------
echo ""
echo "=== [2/3] Running evaluation with action logging ==="
echo "Using wrapper: omnigibson.eval.wrappers.ActionLoggingWrapper"

cd "$PATH_TO_BEHAVIOR_1K"

OMNIGIBSON_HEADLESS=1 \
CUDA_VISIBLE_DEVICES=0 \
python -m omnigibson.eval.eval \
    --task-name "$TASK_NAME" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --output-dir "$LOG_PATH" \
    --write-video \
    --env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper \
    --max-steps 100 \
    2>&1 | tee "$LOG_PATH/omnigibson_eval.log"

EVAL_EXIT=$?

# ---------- 清理 ----------
echo ""
echo "=== [3/3] Cleaning up ==="
kill "$SERVE_PID" 2>/dev/null || true
wait "$SERVE_PID" 2>/dev/null || true

# ---------- 显示结果 ----------
echo ""
echo "=========================================="
echo "✅ Debugging session complete!"
echo "=========================================="
echo ""
echo "📊 Results saved to: $LOG_PATH"
echo ""
echo "📝 Check action logs:"
echo "  Readable format: $LOG_PATH/actions_readable.txt"
echo "  JSON format:     $LOG_PATH/actions.jsonl"
echo ""
echo "🎥 Video: $LOG_PATH/videos/"
echo "📈 Metrics: $LOG_PATH/json/"
echo ""
echo "=========================================="
echo "🔍 Quick analysis commands:"
echo "=========================================="
echo ""
echo "# View first 50 lines of action log:"
echo "  head -50 $LOG_PATH/actions_readable.txt"
echo ""
echo "# Check if base is moving:"
echo "  grep 'Base Movement' $LOG_PATH/actions_readable.txt | head -20"
echo ""
echo "# Count MOVING vs STATIONARY steps:"
echo "  grep -c 'MOVING' $LOG_PATH/actions_readable.txt"
echo "  grep -c 'STATIONARY' $LOG_PATH/actions_readable.txt"
echo ""
echo "# Analyze action statistics with Python:"
echo "  python -c \""
echo "import json"
echo "with open('$LOG_PATH/actions.jsonl') as f:"
echo "    actions = [json.loads(line) for line in f]"
echo "print(f'Total steps: {len(actions)}')"
echo "if len(actions) > 0 and 'base' in actions[0]:"
echo "    base_moves = [a['base'] for a in actions if 'base' in a]"
echo "    moving = sum(1 for b in base_moves if abs(b['linear_x']) > 0.001 or abs(b['linear_y']) > 0.001)"
echo "    print(f'Steps with base movement: {moving}/{len(base_moves)}')"
echo "\""
echo ""
echo "=========================================="

exit $EVAL_EXIT
