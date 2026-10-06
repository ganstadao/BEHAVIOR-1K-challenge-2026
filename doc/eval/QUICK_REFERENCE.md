# 统一评估工具快速参考

## 🚀 快速开始

```bash
# 1. 使用预定义配置运行
python tools/eval_runner.py --preset pi05_turning_on_radio --run-name exp1

# 2. 查看结果
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

## 📁 输出目录结构

```
eval_logs/
└── pi0.5/                          # Policy 类型
    └── turning_on_radio/           # 任务名称
        └── 20241005_143022_exp1/   # 时间戳_运行名称
            ├── config.yaml         # 运行配置
            ├── summary.yaml        # 运行总结
            ├── logs/
            │   ├── policy_server.log
            │   └── omnigibson_eval.log
            ├── json/
            │   └── *.json
            └── videos/
                └── *.mp4
```

## 🔧 常用命令

### 基本评估

```bash
# 使用配置文件
python tools/eval_runner.py --config configs/pi05_turning_on_radio.yaml

# 使用预设
python tools/eval_runner.py --preset pi05_turning_on_radio --run-name my_exp
```

### 参数覆盖

```bash
# 改变任务
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.name=turning_on_lamp \
    --run-name lamp_test

# 多个参数
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.max_steps=1000 \
    --set policy.port=8001 \
    --set logging.record_policy=false \
    --run-name custom
```

### 批量评估

```bash
# 多个任务
python tools/batch_eval.py --mode tasks \
    --config configs/pi05_turning_on_radio.yaml \
    --tasks turning_on_radio turning_on_lamp opening_door \
    --run-prefix baseline

# 多个 checkpoint
python tools/batch_eval.py --mode checkpoints \
    --config configs/pi05_turning_on_radio.yaml \
    --task turning_on_radio \
    --checkpoints \
        step1k=~/ckpts/step_1000 \
        step2k=~/ckpts/step_2000 \
    --run-prefix ckpt_test
```

### 结果分析

```bash
# 分析最新运行
bash tools/analyze_results.sh latest pi0.5 turning_on_radio

# 分析特定运行
bash tools/analyze_results.sh eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1
```

### 生成配置

```bash
# 生成新配置
python tools/config_gen.py \
    --type pi0.5 \
    --task turning_on_lamp \
    --checkpoint ~/checkpoints/my_model \
    --output configs/new_config.yaml

# 批量生成
for task in turning_on_radio turning_on_lamp; do
    python tools/config_gen.py \
        --type pi0.5 \
        --task $task \
        --checkpoint ~/checkpoints/base \
        --output configs/pi05_$task.yaml
done
```

## 💡 实用场景

### 场景 1: 快速测试

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.max_steps=100 \
    --set task.write_video=false \
    --set logging.record_policy=false \
    --run-name quick_test
```

### 场景 2: 调试模式

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG \
    --set task.max_steps=50 \
    --run-name debug
```

### 场景 3: SLURM 提交

```bash
# 方法 1: 使用提供的脚本
sbatch tools/submit_eval.sh pi05_turning_on_radio my_experiment

# 方法 2: 自定义脚本
sbatch --wrap="cd ~/project/BEHAVIOR-1K && \
    python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --run-name slurm_\${SLURM_JOB_ID}"
```

## 📊 查看日志

```bash
# 实时查看 policy server 日志
tail -f eval_logs/pi0.5/turning_on_radio/latest/logs/policy_server.log

# 搜索错误
grep -i error eval_logs/pi0.5/turning_on_radio/latest/logs/*.log

# 查看评估结果
cat eval_logs/pi0.5/turning_on_radio/latest/json/*.json | jq '.'
```

## 🔍 故障排查

### Policy server 启动失败

```bash
# 查看日志
cat eval_logs/pi0.5/turning_on_radio/latest/logs/policy_server.log

# 常见问题：
# - Checkpoint 路径错误 → 检查 policy.checkpoint
# - 端口被占用 → 修改 policy.port
# - GPU 内存不足 → 调整 policy.mem_fraction
```

### 评估失败

```bash
# 查看评估日志
cat eval_logs/pi0.5/turning_on_radio/latest/logs/omnigibson_eval.log

# 查看退出代码
cat eval_logs/pi0.5/turning_on_radio/latest/summary.yaml | grep exit_code
```

### 端口冲突

```bash
# 检查端口占用
lsof -i :8000

# 使用不同端口
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.port=8001 \
    --run-name port8001
```

## 📝 配置文件字段

### Policy 配置

```yaml
policy:
  type: pi0.5 或 gr00t
  checkpoint: ~/path/to/checkpoint
  port: 8000
  gpu_id: 0
  startup_timeout: 300
  
  # pi0.5 特定
  openpi_dir: ~/LINJ0121/openpi
  repo_id: task_name
  control_mode: receding_horizon
  action_horizon: 16
  mem_fraction: 0.85
  
  # gr00t 特定
  groot_dir: ~/LINJ0121/Isaac-GR00T
  modality_config: examples/b1k/r1pro.py
  embodiment_tag: NEW_EMBODIMENT
```

### 任务配置

```yaml
task:
  name: turning_on_radio
  max_steps: 500
  write_video: true
  env_wrapper: omnigibson.eval.wrappers.RGBDFullResWrapper
```

### 日志配置

```yaml
logging:
  detailed_logging: true
  record_policy: true
  policy_log_level: DEBUG  # DEBUG, INFO, WARNING, ERROR
  eval_log_level: INFO
```

### 输出配置

```yaml
output:
  base_dir: ./eval_logs
  run_name: default
```

## 🎯 最佳实践

1. **使用描述性的 run_name**
   ```bash
   --run-name baseline_v1
   --run-name ablation_no_vision
   --run-name final_model_sep30
   ```

2. **快速测试时禁用视频和记录**
   ```bash
   --set task.write_video=false
   --set logging.record_policy=false
   ```

3. **调试时使用 DEBUG 日志**
   ```bash
   --set logging.policy_log_level=DEBUG
   --set logging.eval_log_level=DEBUG
   ```

4. **批量评估使用统一前缀**
   ```bash
   --run-prefix experiment_1
   ```

5. **保存重要配置**
   ```bash
   cp eval_logs/pi0.5/task/20241005_143022_exp1/config.yaml \
      configs/successful_config.yaml
   ```

## 📚 更多文档

- 完整指南: `docs/EVAL_RUNNER_GUIDE.md`
- 配置模板: `configs/template.yaml`
- 示例配置: `configs/*.yaml`

## 🛠️ 工具列表

- `tools/eval_runner.py` - 主评估工具
- `tools/batch_eval.py` - 批量评估
- `tools/config_gen.py` - 配置生成器
- `tools/analyze_results.sh` - 结果分析
- `tools/submit_eval.sh` - SLURM 提交脚本
