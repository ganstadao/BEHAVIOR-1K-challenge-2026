#!/bin/bash
# 结果分析工具 - 快速查看评估结果

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

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 使用方法
usage() {
    echo "Usage: $0 <output_directory>"
    echo ""
    echo "Example:"
    echo "  $0 eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1"
    echo ""
    echo "Or use 'latest' to analyze the most recent run:"
    echo "  $0 latest pi0.5 turning_on_radio"
    exit 1
}

# 查找最新的运行
find_latest() {
    local policy_type=$1
    local task_name=$2
    local base_dir="eval_logs/${policy_type}/${task_name}"

    if [ ! -d "$base_dir" ]; then
        echo "Error: Directory not found: $base_dir"
        exit 1
    fi

    latest=$(ls -t "$base_dir" | head -1)
    echo "${base_dir}/${latest}"
}

# 参数处理
if [ "$1" == "latest" ]; then
    POLICY_TYPE=${2:-pi0.5}
    TASK_NAME=${3:-turning_on_radio}
    OUTPUT_DIR=$(find_latest "$POLICY_TYPE" "$TASK_NAME")
elif [ -z "$1" ]; then
    usage
else
    OUTPUT_DIR=$1
fi

# 检查目录
if [ ! -d "$OUTPUT_DIR" ]; then
    echo -e "${RED}Error: Directory not found: $OUTPUT_DIR${NC}"
    exit 1
fi

echo "=========================================="
echo "Analyzing: $OUTPUT_DIR"
echo "=========================================="
echo ""

# 1. 显示配置信息
echo -e "${YELLOW}[1] Configuration${NC}"
if [ -f "$OUTPUT_DIR/config.yaml" ]; then
    echo "Policy type: $(grep 'type:' "$OUTPUT_DIR/config.yaml" | head -1 | awk '{print $2}')"
    echo "Task name: $(grep 'name:' "$OUTPUT_DIR/config.yaml" | grep -A5 'task:' | grep 'name:' | awk '{print $2}')"
    echo "Checkpoint: $(grep 'checkpoint:' "$OUTPUT_DIR/config.yaml" | head -1 | awk '{print $2}')"
else
    echo "Config file not found"
fi
echo ""

# 2. 显示运行总结
echo -e "${YELLOW}[2] Summary${NC}"
if [ -f "$OUTPUT_DIR/summary.yaml" ]; then
    echo "Run ID: $(grep 'run_id:' "$OUTPUT_DIR/summary.yaml" | awk '{print $2}')"
    echo "Timestamp: $(grep 'timestamp:' "$OUTPUT_DIR/summary.yaml" | awk '{print $2}')"
    exit_code=$(grep 'exit_code:' "$OUTPUT_DIR/summary.yaml" | awk '{print $2}')
    if [ "$exit_code" == "0" ]; then
        echo -e "Exit code: ${GREEN}$exit_code${NC}"
    else
        echo -e "Exit code: ${RED}$exit_code${NC}"
    fi
else
    echo "Summary file not found"
fi
echo ""

# 3. 分析评估结果 JSON
echo -e "${YELLOW}[3] Evaluation Results${NC}"
json_files=$(find "$OUTPUT_DIR/json" -name "*.json" 2>/dev/null)
if [ -n "$json_files" ]; then
    for json_file in $json_files; do
        echo "File: $(basename $json_file)"

        # 检查是否有 jq
        if command -v jq &> /dev/null; then
            success=$(jq -r '.success' "$json_file" 2>/dev/null || echo "N/A")
            num_steps=$(jq -r '.num_steps' "$json_file" 2>/dev/null || echo "N/A")

            if [ "$success" == "true" ]; then
                echo -e "  Success: ${GREEN}$success${NC}"
            else
                echo -e "  Success: ${RED}$success${NC}"
            fi
            echo "  Steps: $num_steps"

            # 显示满足的条件数量
            satisfied=$(jq -r '.satisfied_predicates | length' "$json_file" 2>/dev/null || echo "0")
            unsatisfied=$(jq -r '.unsatisfied_predicates | length' "$json_file" 2>/dev/null || echo "0")
            echo "  Satisfied predicates: $satisfied"
            echo "  Unsatisfied predicates: $unsatisfied"

            # 如果失败，显示未满足的条件
            if [ "$success" != "true" ] && [ "$unsatisfied" != "0" ]; then
                echo "  Unsatisfied:"
                jq -r '.unsatisfied_predicates[]' "$json_file" 2>/dev/null | sed 's/^/    - /'
            fi
        else
            # 没有 jq，使用 grep
            echo "  (Install jq for detailed analysis)"
            grep -o '"success":[^,]*' "$json_file" | head -1
            grep -o '"num_steps":[^,]*' "$json_file" | head -1
        fi
    done
else
    echo "No JSON results found"
fi
echo ""

# 4. 检查日志文件
echo -e "${YELLOW}[4] Logs${NC}"
if [ -f "$OUTPUT_DIR/logs/policy_server.log" ]; then
    server_lines=$(wc -l < "$OUTPUT_DIR/logs/policy_server.log")
    echo "Policy server log: $server_lines lines"

    # 检查错误
    server_errors=$(grep -i "error" "$OUTPUT_DIR/logs/policy_server.log" | wc -l)
    if [ "$server_errors" -gt 0 ]; then
        echo -e "  Errors: ${RED}$server_errors${NC}"
        echo "  Last error:"
        grep -i "error" "$OUTPUT_DIR/logs/policy_server.log" | tail -1 | sed 's/^/    /'
    else
        echo -e "  Errors: ${GREEN}0${NC}"
    fi
fi

if [ -f "$OUTPUT_DIR/logs/omnigibson_eval.log" ]; then
    eval_lines=$(wc -l < "$OUTPUT_DIR/logs/omnigibson_eval.log")
    echo "OmniGibson eval log: $eval_lines lines"

    # 检查错误
    eval_errors=$(grep -i "error" "$OUTPUT_DIR/logs/omnigibson_eval.log" | wc -l)
    if [ "$eval_errors" -gt 0 ]; then
        echo -e "  Errors: ${RED}$eval_errors${NC}"
    else
        echo -e "  Errors: ${GREEN}0${NC}"
    fi
fi
echo ""

# 5. 视频文件
echo -e "${YELLOW}[5] Videos${NC}"
video_count=$(find "$OUTPUT_DIR/videos" -name "*.mp4" 2>/dev/null | wc -l)
if [ "$video_count" -gt 0 ]; then
    echo "Video files: $video_count"
    find "$OUTPUT_DIR/videos" -name "*.mp4" -exec ls -lh {} \; | awk '{print "  -", $9, "("$5")"}'
else
    echo "No video files found"
fi
echo ""

# 6. 磁盘使用
echo -e "${YELLOW}[6] Disk Usage${NC}"
du -sh "$OUTPUT_DIR"
echo ""

echo "=========================================="
echo "Quick commands:"
echo "  View config: cat $OUTPUT_DIR/config.yaml"
echo "  View summary: cat $OUTPUT_DIR/summary.yaml"
echo "  View server log: less $OUTPUT_DIR/logs/policy_server.log"
echo "  View eval log: less $OUTPUT_DIR/logs/omnigibson_eval.log"
if [ "$video_count" -gt 0 ]; then
    first_video=$(find "$OUTPUT_DIR/videos" -name "*.mp4" | head -1)
    echo "  Play video: mpv $first_video"
fi
echo "=========================================="
