#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --job-name=gr00t_eval
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --output=logs/gr00t_eval_%j.out
#SBATCH --error=logs/gr00t_eval_%j.err

set -e

# ---------- 配置区：按本地环境修改 ----------
export GROOT_DIR=~/LINJ0121/Isaac-GR00T
export PATH_TO_BEHAVIOR_1K=~/project/BEHAVIOR-1K
export TASK_NAME=turning_on_radio
export PATH_TO_CKPT=~/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000
export PORT=8000
export HF_TOKEN="your_hf_token"   # 过了 Cosmos-Reason2-2B gate 的账号 token
export LOG_PATH=./eval_logs/$TASK_NAME

# behavior conda 环境的 Python 绝对路径（不用 conda activate，避免和 uv venv 冲突）
BEHAVIOR_PYTHON=/home/msai/linj0121/.conda/envs/behavior/bin/python

# GR00T uv venv 的 Python 绝对路径（集群上 activate 可能不改 PATH，直接用绝对路径最稳）
GROOT_PYTHON=/home/msai/linj0121/LINJ0121/Isaac-GR00T/.venv/bin/python
# ------------------------------------------

mkdir -p logs

echo "=== [1/3] Starting GR00T policy server on GPU 0, port $PORT ==="

cd "$GROOT_DIR"

# 创建日志目录和服务器日志文件（使用绝对路径）
mkdir -p "$PATH_TO_BEHAVIOR_1K/$LOG_PATH"
SERVER_LOG="$PATH_TO_BEHAVIOR_1K/$LOG_PATH/policy_server.log"
echo "Server log: $SERVER_LOG"

# 直接用绝对路径，后台启动并重定向日志
CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/b1k/serve_b1k.py \
    --model-path "$PATH_TO_CKPT" \
    --modality-config-path examples/b1k/r1pro.py \
    --embodiment-tag NEW_EMBODIMENT \
    --host 127.0.0.1 \
    --port "$PORT" \
    > "$SERVER_LOG" 2>&1 &
SERVE_PID=$!
echo "Policy server PID: $SERVE_PID"

# 等待服务器就绪（增加到 5 分钟，模型加载时间长）
echo "Waiting for policy server to be ready (max 5 minutes)..."
for i in $(seq 1 100); do
    # 检查进程是否还在运行
    if ! ps -p "$SERVE_PID" > /dev/null 2>&1; then
        echo "ERROR: Policy server process died!"
        echo "Last 30 lines of server log:"
        tail -30 "$SERVER_LOG"
        exit 1
    fi

    # 检查健康端点
    if curl -s "http://127.0.0.1:$PORT/healthz" > /dev/null 2>&1; then
        echo "✓ Policy server is ready (after ~$((i*3))s)."
        break
    fi

    # 每30秒显示一次进度
    if [ $((i % 10)) -eq 0 ]; then
        echo "  Still waiting... ($((i*3))s elapsed)"
        tail -1 "$SERVER_LOG" | sed 's/^/    /'
    fi

    sleep 3

    if [ "$i" -eq 100 ]; then
        echo "ERROR: Policy server did not become ready within 300s."
        echo "Last 30 lines of server log:"
        tail -30 "$SERVER_LOG"
        kill "$SERVE_PID" 2>/dev/null || true
        exit 1
    fi
done

echo ""
echo "=== [2/3] Starting OmniGibson evaluator on GPU 0 (shared) ==="

cd "$PATH_TO_BEHAVIOR_1K"

# 使用包装器脚本，添加专门的 Python 日志文件
EVAL_LOG="$LOG_PATH/omnigibson_eval.log"
echo "OmniGibson eval log: $EVAL_LOG"

CUDA_VISIBLE_DEVICES=0 $BEHAVIOR_PYTHON test/run_eval_with_logging.py \
    --log-file "$EVAL_LOG" \
    --log-level INFO \
    --task-name "$TASK_NAME" \
    --max-steps 500 \
    --host 127.0.0.1 \
    --port "$PORT" \
    --output-dir "$LOG_PATH" \
    --write-video

EVAL_EXIT=$?
echo "Evaluator exited with code: $EVAL_EXIT"

echo ""
echo "=== [3/3] Cleaning up policy server ==="
kill "$SERVE_PID" 2>/dev/null || true
wait "$SERVE_PID" 2>/dev/null || true

echo ""
echo "Done. Results saved to: $LOG_PATH"
echo "Logs:"
echo "  - Policy server: $SERVER_LOG"
echo "  - OmniGibson eval: $EVAL_LOG"
echo "  - SLURM stdout: logs/gr00t_eval_\${SLURM_JOB_ID}.out"
echo "  - SLURM stderr: logs/gr00t_eval_\${SLURM_JOB_ID}.err"
exit $EVAL_EXIT
