#!/bin/bash
# 诊断当前卡住的评估任务

echo "========================================"
echo "  评估任务诊断脚本"
echo "  时间: $(date)"
echo "========================================"
echo ""

JOB_ID=35353  # 从日志文件名提取

echo "=== 1. 检查进程状态 ==="
echo ""
echo "Policy Server 进程:"
ps aux | grep "serve_b1k.py" | grep -v grep || echo "  未找到 policy server 进程"

echo ""
echo "OmniGibson 评估器进程:"
ps aux | grep "omnigibson.eval.eval" | grep -v grep || echo "  未找到 evaluator 进程"

echo ""
echo "=== 2. 检查端口监听 ==="
netstat -tlnp 2>/dev/null | grep ":8000" || echo "  端口 8000 未被监听"

echo ""
echo "=== 3. 检查 GPU 使用 ==="
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv

echo ""
echo "=== 4. 尝试连接 Policy Server ==="
if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
    echo "  ✓ Policy server 健康检查通过"
    curl -s http://127.0.0.1:8000/healthz
else
    echo "  ✗ 无法连接到 policy server"
fi

echo ""
echo "=== 5. 检查日志文件 ==="
LOG_FILE="logs/gr00t_eval_${JOB_ID}.out"
ERR_FILE="logs/gr00t_eval_${JOB_ID}.err"

if [ -f "$LOG_FILE" ]; then
    echo "标准输出日志 (最后 20 行):"
    echo "----------------------------------------"
    tail -n 20 "$LOG_FILE"
    echo "----------------------------------------"
else
    echo "  未找到 $LOG_FILE"
fi

echo ""
if [ -f "$ERR_FILE" ]; then
    if [ -s "$ERR_FILE" ]; then
        echo "错误日志 (最后 20 行):"
        echo "----------------------------------------"
        tail -n 20 "$ERR_FILE"
        echo "----------------------------------------"
    else
        echo "  错误日志为空"
    fi
else
    echo "  未找到 $ERR_FILE"
fi

echo ""
echo "=== 6. 建议的操作 ==="
echo ""

# 检查是否有进程在运行
if ps aux | grep -q "[s]erve_b1k.py"; then
    SERVE_PID=$(ps aux | grep "[s]erve_b1k.py" | awk '{print $2}')
    echo "✓ Policy server 正在运行 (PID: $SERVE_PID)"

    if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
        echo "✓ Policy server 响应正常"
    else
        echo "⚠ Policy server 进程存在但不响应健康检查"
        echo "   可能原因：启动中、端口被占用、配置错误"
    fi
fi

if ps aux | grep -q "[o]mnigibson.eval.eval"; then
    EVAL_PID=$(ps aux | grep "[o]mnigibson.eval.eval" | awk '{print $2}')
    echo "✓ OmniGibson 评估器正在运行 (PID: $EVAL_PID)"
    echo ""
    echo "⚠ 评估器可能在执行以下操作（耗时较长）："
    echo "   - 首次下载场景资源（可能需要 10-30 分钟）"
    echo "   - 加载大型场景模型"
    echo "   - 初始化物理引擎"
    echo "   - 等待 WebSocket 连接"
    echo ""
    echo "建议："
    echo "   1. 继续等待（如果已经等待 < 30 分钟）"
    echo "   2. 检查网络连接（如果正在下载资源）"
    echo "   3. 查看完整日志： tail -f $LOG_FILE"
else
    echo "⚠ 未找到 OmniGibson 评估器进程"

    if [ -f "$LOG_FILE" ] && grep -q "app ready" "$LOG_FILE"; then
        echo "   日志显示 'app ready'，但进程不存在"
        echo "   可能原因：进程已崩溃或正常退出"
        echo ""
        echo "建议："
        echo "   1. 检查错误日志： cat $ERR_FILE"
        echo "   2. 重新运行脚本"
    fi
fi

echo ""
echo "========================================"
echo "  诊断完成"
echo "========================================"

echo ""
echo "如果需要终止卡住的任务："
echo "  killall -9 python"
echo "  # 或更精确地："
if ps aux | grep -q "[s]erve_b1k.py"; then
    echo "  kill -9 $(ps aux | grep '[s]erve_b1k.py' | awk '{print $2}')"
fi
if ps aux | grep -q "[o]mnigibson.eval.eval"; then
    echo "  kill -9 $(ps aux | grep '[o]mnigibson.eval.eval' | awk '{print $2}')"
fi
