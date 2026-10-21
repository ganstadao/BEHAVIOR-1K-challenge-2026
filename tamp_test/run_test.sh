#!/bin/bash
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --job-name=tamp_test
#SBATCH --output=outputs/tamp_test_out.log
#SBATCH --error=outputs/tamp_test_err.log

export OMNIGIBSON_HEADLESS=1
cd ~/project/BEHAVIOR-1K/tamp_test
PY=/home/msai/linj0121/.conda/envs/behavior/bin/python

# Configuration
INSTANCE_ID=301
CONFIG="configs/turning_on_radio.yaml"
OUTPUT_DIR="results"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}TAMP Test: Turning On Radio${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check if conda environment is activated
if [[ -z "${CONDA_DEFAULT_ENV}" ]]; then
    echo -e "${YELLOW}Warning: No conda environment detected${NC}"
    echo -e "${YELLOW}Please activate the 'behavior' environment:${NC}"
    echo -e "${YELLOW}  conda activate behavior${NC}"
    exit 1
fi

echo -e "Conda environment: ${GREEN}${CONDA_DEFAULT_ENV}${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/logs"

# Run evaluation
echo -e "${GREEN}Starting evaluation...${NC}"
echo -e "Instance ID: ${YELLOW}${INSTANCE_ID}${NC}"
echo -e "Config: ${YELLOW}${CONFIG}${NC}"
echo ""

# Set headless mode
export OMNIGIBSON_HEADLESS=1


$PY -m debugpy --listen 0.0.0.0:1234 --wait-for-client eval/run_eval.py \
    --config "$CONFIG" \
    --instance "$INSTANCE_ID" \
    --output "$OUTPUT_DIR" \
    2>&1 | tee "$OUTPUT_DIR/logs/eval_${INSTANCE_ID}.log"

# $PY eval/run_eval.py \
#     --config "$CONFIG" \
#     --instance "$INSTANCE_ID" \
#     --output "$OUTPUT_DIR" \
#     2>&1 | tee "$OUTPUT_DIR/logs/eval_${INSTANCE_ID}.log"

# Check if evaluation succeeded
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}Evaluation completed successfully!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo -e "Results saved to: ${YELLOW}$OUTPUT_DIR/instance_${INSTANCE_ID}_result.json${NC}"
    echo -e "Logs saved to: ${YELLOW}$OUTPUT_DIR/logs/eval_${INSTANCE_ID}.log${NC}"
else
    echo ""
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}Evaluation failed!${NC}"
    echo -e "${RED}======================================${NC}"
    echo ""
    echo -e "Check logs: ${YELLOW}$OUTPUT_DIR/logs/eval_${INSTANCE_ID}.log${NC}"
    exit 1
fi
