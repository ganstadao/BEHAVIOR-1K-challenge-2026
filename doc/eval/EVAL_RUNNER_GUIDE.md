# 统一评估接口使用指南

## 概述

统一评估接口 (`tools/eval_runner.py`) 提供了一个配置驱动的评估系统，支持：

- ✅ **统一接口**：通过配置文件管理所有参数，无需修改脚本
- ✅ **详细日志**：Policy server 和 OmniGibson 的完整日志记录
- ✅ **清晰的输出结构**：自动组织输出目录，每次运行独立
- ✅ **参数覆盖**：支持通过命令行覆盖配置项
- ✅ **多 Policy 支持**：支持 pi0.5 和 GR00T
- ✅ **Policy 记录**：支持 pi0.5 的 --record 功能
- ✅ **不修改源码**：所有功能通过配置和参数实现

## 快速开始

### 1. 基本使用

```bash
# 使用预定义配置运行评估
python tools/eval_runner.py --preset pi05_turning_on_radio --run-name exp1

# 或使用配置文件
python tools/eval_runner.py --config configs/pi05_turning_on_radio.yaml
```

### 2. 输出目录结构

运行后会生成如下目录结构：

```
eval_logs/
└── pi0.5/                           # Policy 类型
    └── turning_on_radio/            # 任务名称
        └── 20241005_143022_exp1/    # 时间戳_运行名称
            ├── config.yaml          # 本次运行的完整配置
            ├── summary.yaml         # 运行总结
            ├── logs/
            │   ├── policy_server.log     # Policy server 完整日志
            │   └── omnigibson_eval.log   # OmniGibson 评估日志
            ├── json/
            │   └── turning_on_radio_301_0.json  # 评估结果
            └── videos/
                └── turning_on_radio_301_0.mp4   # 评估视频
```

### 3. 查看结果

```bash
# 查看运行总结
cat eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/summary.yaml

# 查看评估结果
cat eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/json/*.json | jq '.'

# 查看日志
tail -f eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/logs/policy_server.log
```

## 配置文件

### 创建新配置

```bash
# 复制模板
cp configs/template.yaml configs/my_experiment.yaml

# 编辑配置
vim configs/my_experiment.yaml
```

### 配置文件结构

```yaml
policy:
  type: pi0.5              # pi0.5 或 gr00t
  checkpoint: ~/path/...   # 模型路径
  port: 8000              # 端口

behavior:
  path: ~/project/BEHAVIOR-1K
  python_path: ~/.conda/envs/behavior/bin/python

task:
  name: turning_on_radio  # 任务名称
  max_steps: 500
  write_video: true

logging:
  detailed_logging: true  # 详细日志
  record_policy: true     # pi0.5 的 --record

output:
  base_dir: ./eval_logs
  run_name: default       # 运行名称
```

## 高级用法

### 1. 参数覆盖

```bash
# 覆盖单个参数
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.name=turning_on_lamp \
    --run-name lamp_exp1

# 覆盖多个参数
python tools/eval_runner.py \
    --config configs/pi05_turning_on_radio.yaml \
    --set task.name=cleaning_bathtub \
    --set task.max_steps=1000 \
    --set policy.port=8001 \
    --run-name bathtub_exp2
```

### 2. 不同任务的快速测试

```bash
# 测试多个任务
for task in turning_on_radio turning_on_lamp opening_door; do
    python tools/eval_runner.py \
        --preset pi05_turning_on_radio \
        --set task.name=$task \
        --run-name baseline_test
done
```

### 3. 使用不同的 checkpoint

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.checkpoint=~/checkpoints/new_model \
    --run-name new_model_test
```

### 4. 调整日志级别

```bash
# 更详细的日志
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG \
    --run-name debug_run

# 更少的日志
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.policy_log_level=WARNING \
    --set logging.eval_log_level=WARNING \
    --run-name quiet_run
```

### 5. 禁用 policy 记录

```bash
# 不使用 --record (加快速度)
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.record_policy=false \
    --run-name no_record
```

## 预定义配置

系统提供以下预定义配置：

- `pi05_turning_on_radio` - Pi0.5 评估 turning_on_radio
- `gr00t_turning_on_radio` - GR00T 评估 turning_on_radio

查看所有配置：

```bash
ls configs/*.yaml
```

## 在 SLURM 上使用

### 1. 创建 SLURM 脚本

```bash
#!/bin/bash
#SBATCH --job-name=eval_unified
#SBATCH --partition=MGPU-TC2
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=30G
#SBATCH --time=06:00:00
#SBATCH --output=logs/eval_%j.out
#SBATCH --error=logs/eval_%j.err

cd ~/project/BEHAVIOR-1K

python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --run-name slurm_${SLURM_JOB_ID}
```

### 2. 提交任务

```bash
sbatch tools/submit_eval.sh
```

## 常见问题

### Q: 如何查看正在运行的评估？

```bash
# 查看最新的输出目录
ls -lt eval_logs/pi0.5/turning_on_radio/ | head -5

# 实时查看日志
tail -f eval_logs/pi0.5/turning_on_radio/latest/logs/policy_server.log
```

### Q: 如何比较多次运行的结果？

所有运行都保存在独立的目录中，可以轻松比较：

```bash
# 列出所有运行
ls eval_logs/pi0.5/turning_on_radio/

# 比较两次运行的结果
diff \
    eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/json/*.json \
    eval_logs/pi0.5/turning_on_radio/20241005_150133_exp2/json/*.json
```

### Q: 如何清理旧的运行结果？

```bash
# 删除特定运行
rm -rf eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/

# 只保留最近 5 次运行
cd eval_logs/pi0.5/turning_on_radio/
ls -t | tail -n +6 | xargs rm -rf
```

### Q: Policy server 启动失败怎么办？

查看 policy server 日志：

```bash
cat eval_logs/pi0.5/turning_on_radio/latest/logs/policy_server.log
```

常见问题：
- Checkpoint 路径错误：检查 `policy.checkpoint`
- 端口被占用：修改 `policy.port`
- GPU 内存不足：调整 `policy.mem_fraction`

### Q: 如何在不同 GPU 上运行？

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.gpu_id=1 \
    --run-name gpu1_test
```

## 示例场景

### 场景 1: 快速测试新 checkpoint

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.checkpoint=~/new_checkpoint \
    --set task.max_steps=100 \
    --set task.write_video=false \
    --run-name quick_test
```

### 场景 2: 完整评估实验

```bash
python tools/eval_runner.py \
    --config configs/pi05_turning_on_radio.yaml \
    --run-name full_eval_v1
```

### 场景 3: 调试模式

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG \
    --set logging.record_policy=true \
    --set task.max_steps=50 \
    --run-name debug
```

### 场景 4: 批量评估多个任务

```bash
# 创建批量脚本
cat > batch_eval.sh << 'EOF'
#!/bin/bash
TASKS="turning_on_radio turning_on_lamp opening_door"
for task in $TASKS; do
    echo "Evaluating $task..."
    python tools/eval_runner.py \
        --preset pi05_turning_on_radio \
        --set task.name=$task \
        --run-name batch_eval
done
EOF

chmod +x batch_eval.sh
./batch_eval.sh
```

## 与原脚本的对比

| 特性 | 原脚本 | 统一接口 |
|------|--------|----------|
| 参数配置 | 修改脚本 | 配置文件 |
| 输出目录 | 手动指定 | 自动生成 |
| 日志记录 | 部分支持 | 完整支持 |
| 参数覆盖 | 不支持 | 支持 |
| 多次运行区分 | 手动管理 | 自动管理 |
| Policy 记录 | 需手动添加 | 配置开关 |
| 运行总结 | 无 | 自动生成 |

## 贡献

如需添加新功能或修复问题，请修改：

- `tools/eval_runner.py` - 主程序
- `configs/*.yaml` - 配置模板
- 本文档

## 参考

- OpenPI 文档: `~/LINJ0121/openpi/README.md`
- BEHAVIOR-1K 文档: `README.md`
- 原评估脚本: `test/run_pi0_5_eval.sh`
