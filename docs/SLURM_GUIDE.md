# SLURM 环境使用指南

本指南专门针对只能使用 `sbatch` 提交作业的集群环境。

## 🚀 快速开始

### 1. 基本提交

```bash
# 使用预设配置
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio my_exp

# 使用配置文件
sbatch tools/submit_eval_advanced.sh configs/pi05_unlimited_steps.yaml unlimited_run
```

### 2. 不限制步数

**方法 1: 使用专门的配置文件**

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps full_eval
```

**方法 2: 通过命令行参数覆盖**

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio unlimited \
    --set task.max_steps=0
```

**方法 3: 使用 null 值（推荐）**

编辑配置文件：
```yaml
task:
  max_steps: null  # 不限制步数
```

## 📝 配置 max_steps

### 理解 max_steps 参数

- `max_steps: 500` - 限制最多 500 步
- `max_steps: 0` - 不限制步数
- `max_steps: null` - 不限制步数（推荐写法）
- 不设置 `max_steps` - 使用默认值（通常不限制）

### 示例配置

**限制步数（快速测试）**
```yaml
# configs/pi05_quick_test.yaml
task:
  name: turning_on_radio
  max_steps: 100  # 限制 100 步
  write_video: false  # 节省时间
```

**不限制步数（完整评估）**
```yaml
# configs/pi05_unlimited_steps.yaml
task:
  name: turning_on_radio
  max_steps: null  # 不限制
  write_video: true
```

## 🎯 常用场景

### 场景 1: 单个任务评估（不限步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps exp1
```

### 场景 2: 快速测试（限制步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio quick_test \
    --set task.max_steps=100 \
    --set task.write_video=false
```

### 场景 3: 评估不同任务

```bash
# 任务 1
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps radio_eval \
    --set task.name=turning_on_radio

# 任务 2
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps lamp_eval \
    --set task.name=turning_on_lamp

# 任务 3
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps door_eval \
    --set task.name=opening_door
```

### 场景 4: 批量提交多个任务

```bash
bash tools/submit_batch.sh pi05_unlimited_steps baseline \
    turning_on_radio \
    turning_on_lamp \
    opening_door
```

### 场景 5: 使用不同 checkpoint

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps ckpt1_test \
    --set policy.checkpoint=~/LINJ0121/checkpoint/model_step_1000

sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps ckpt2_test \
    --set policy.checkpoint=~/LINJ0121/checkpoint/model_step_2000
```

### 场景 6: 调试模式（不限步数但详细日志）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps debug \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG
```

## 📊 监控和管理作业

### 查看作业状态

```bash
# 查看所有作业
squeue -u $USER

# 查看特定作业
squeue -j <job_id>

# 持续监控
watch -n 5 'squeue -u $USER'
```

### 查看日志

```bash
# 实时查看输出
tail -f logs/eval_<job_id>.out

# 查看错误
tail -f logs/eval_<job_id>.err

# 查看评估日志（作业运行中）
tail -f eval_logs/pi0.5/turning_on_radio/*/logs/policy_server.log
```

### 取消作业

```bash
# 取消单个作业
scancel <job_id>

# 取消所有作业
scancel -u $USER

# 取消特定名称的作业
scancel -n eval
```

## 🔧 高级参数覆盖

### 覆盖单个参数

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test \
    --set task.max_steps=0
```

### 覆盖多个参数

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test \
    --set task.name=turning_on_lamp \
    --set task.max_steps=0 \
    --set policy.port=8001 \
    --set logging.record_policy=false
```

### 使用不同 GPU

```bash
# SLURM 会自动分配 GPU，但你可以在配置中指定
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test \
    --set policy.gpu_id=0
```

## 📁 输出目录管理

### 目录结构

```
eval_logs/
└── pi0.5/
    └── turning_on_radio/
        ├── 20241005_143022_exp1/      # 第一次运行
        ├── 20241005_150133_exp2/      # 第二次运行
        └── 20241005_163045_exp3/      # 第三次运行
```

### 查找最新结果

```bash
# 列出所有运行
ls -lt eval_logs/pi0.5/turning_on_radio/

# 查看最新结果
ls -t eval_logs/pi0.5/turning_on_radio/ | head -1

# 分析最新结果（作业完成后）
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

### 清理旧结果

```bash
# 只保留最近 5 次运行
cd eval_logs/pi0.5/turning_on_radio/
ls -t | tail -n +6 | xargs rm -rf
```

## 🎨 创建自定义配置

### 方法 1: 复制并修改

```bash
cp configs/pi05_turning_on_radio.yaml configs/my_unlimited.yaml
vim configs/my_unlimited.yaml
```

修改 `max_steps`:
```yaml
task:
  max_steps: null  # 改为 null
```

提交：
```bash
sbatch tools/submit_eval_advanced.sh configs/my_unlimited.yaml my_run
```

### 方法 2: 使用配置生成器

```bash
python tools/config_gen.py \
    --type pi0.5 \
    --task turning_on_radio \
    --checkpoint ~/LINJ0121/checkpoint/my_model \
    --no-max-steps \
    --output configs/my_unlimited.yaml

sbatch tools/submit_eval_advanced.sh configs/my_unlimited.yaml my_run
```

## 📋 批量评估工作流

### 1. 创建任务列表

```bash
cat > tasks.txt << EOF
turning_on_radio
turning_on_lamp
opening_door
closing_door
EOF
```

### 2. 批量提交

```bash
bash tools/submit_batch.sh pi05_unlimited_steps baseline \
    $(cat tasks.txt)
```

### 3. 监控所有作业

```bash
squeue -u $USER
```

### 4. 等待完成后分析

```bash
# 对每个任务分析结果
for task in $(cat tasks.txt); do
    echo "=== $task ==="
    bash tools/analyze_results.sh latest pi0.5 $task
done
```

## ⚡ 性能优化

### 快速测试配置

```yaml
task:
  max_steps: 50
  write_video: false

logging:
  record_policy: false
  policy_log_level: WARNING
```

提交：
```bash
sbatch tools/submit_eval_advanced.sh configs/quick_test.yaml fast
```

### 完整评估配置

```yaml
task:
  max_steps: null
  write_video: true

logging:
  record_policy: true
  policy_log_level: DEBUG
```

提交：
```bash
sbatch tools/submit_eval_advanced.sh configs/full_eval.yaml complete
```

## 🔍 故障排查

### 问题 1: 作业卡住不动

```bash
# 查看作业状态
squeue -j <job_id>

# 查看日志
tail -100 logs/eval_<job_id>.out
tail -100 logs/eval_<job_id>.err

# 如果需要，取消并重新提交
scancel <job_id>
sbatch tools/submit_eval_advanced.sh ...
```

### 问题 2: Policy server 启动失败

查看日志：
```bash
tail -100 eval_logs/pi0.5/task/latest/logs/policy_server.log
```

常见问题：
- Checkpoint 路径错误
- 端口被占用
- GPU 内存不足

### 问题 3: 评估时间过长

检查是否设置了步数限制：
```bash
cat eval_logs/pi0.5/task/latest/config.yaml | grep max_steps
```

如果需要限制：
```bash
# 取消当前作业
scancel <job_id>

# 重新提交并限制步数
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test \
    --set task.max_steps=500
```

## 📚 预定义配置

系统提供了以下预设配置：

| 配置 | max_steps | 用途 |
|------|-----------|------|
| `pi05_turning_on_radio` | 500 | 标准评估 |
| `pi05_unlimited_steps` | null | 不限制步数 |
| `gr00t_turning_on_radio` | 500 | GR00T 评估 |

查看所有配置：
```bash
ls configs/*.yaml
```

## 💡 最佳实践

1. **使用描述性的 run_name**
   ```bash
   sbatch tools/submit_eval_advanced.sh config exp_v1_unlimited
   ```

2. **测试时限制步数**
   ```bash
   sbatch tools/submit_eval_advanced.sh config test --set task.max_steps=100
   ```

3. **完整评估时不限制步数**
   ```bash
   sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps final_eval
   ```

4. **批量评估使用统一前缀**
   ```bash
   bash tools/submit_batch.sh config baseline task1 task2 task3
   ```

5. **保存成功的配置**
   ```bash
   cp eval_logs/pi0.5/task/20241005_143022_success/config.yaml \
      configs/successful_unlimited.yaml
   ```

## 🎯 快速参考

```bash
# 不限步数评估
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps my_run

# 限制步数评估
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test \
    --set task.max_steps=100

# 批量评估
bash tools/submit_batch.sh pi05_unlimited_steps baseline task1 task2 task3

# 查看作业
squeue -u $USER

# 查看日志
tail -f logs/eval_<job_id>.out

# 取消作业
scancel <job_id>

# 分析结果
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

---

**开始使用**: `sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test`
