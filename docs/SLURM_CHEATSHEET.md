# SLURM 快速参考卡

## 🚀 最常用命令

### 1. 不限制步数的评估（推荐）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps my_experiment
```

### 2. 限制步数的快速测试

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio quick_test \
    --set task.max_steps=100
```

### 3. 评估不同任务（不限步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps lamp_eval \
    --set task.name=turning_on_lamp
```

### 4. 批量评估多个任务

```bash
bash tools/submit_batch.sh pi05_unlimited_steps baseline \
    turning_on_radio turning_on_lamp opening_door
```

## 📝 max_steps 设置方法

| 设置 | 含义 | 用法 |
|------|------|------|
| `max_steps: null` | 不限制 | 配置文件中设置 |
| `max_steps: 0` | 不限制 | 配置文件或命令行 |
| `max_steps: 500` | 限制 500 步 | 配置文件或命令行 |
| `--set task.max_steps=0` | 不限制 | 命令行覆盖 |
| `--set task.max_steps=100` | 限制 100 步 | 命令行覆盖 |

## 🎯 三种设置不限步数的方法

### 方法 1: 使用预设配置（最简单）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps my_run
```

### 方法 2: 命令行覆盖

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio my_run \
    --set task.max_steps=0
```

### 方法 3: 创建自定义配置

```bash
# 复制并修改
cp configs/pi05_turning_on_radio.yaml configs/my_unlimited.yaml
# 编辑: 设置 max_steps: null
sbatch tools/submit_eval_advanced.sh configs/my_unlimited.yaml my_run
```

## 📊 作业管理

```bash
# 查看作业
squeue -u $USER

# 查看日志
tail -f logs/eval_<job_id>.out

# 取消作业
scancel <job_id>

# 取消所有作业
scancel -u $USER
```

## 🔍 查看结果

```bash
# 分析最新结果
bash tools/analyze_results.sh latest pi0.5 turning_on_radio

# 列出所有运行
ls -lt eval_logs/pi0.5/turning_on_radio/

# 查看特定运行的配置
cat eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/config.yaml
```

## 💡 实用场景

### 快速测试新 checkpoint（限制步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_turning_on_radio test \
    --set policy.checkpoint=~/new_checkpoint \
    --set task.max_steps=100 \
    --set task.write_video=false
```

### 完整评估（不限步数）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps full_eval \
    --set policy.checkpoint=~/final_checkpoint
```

### 调试模式（不限步数，详细日志）

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps debug \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG
```

## 📁 配置文件

| 文件 | max_steps | 说明 |
|------|-----------|------|
| `pi05_turning_on_radio.yaml` | 500 | 标准配置 |
| `pi05_unlimited_steps.yaml` | null | 不限步数 |
| `gr00t_turning_on_radio.yaml` | 500 | GR00T 配置 |

## 🆘 常见问题

**Q: 如何设置不限制步数？**

A: 三种方法任选其一：
1. `sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps my_run`
2. 添加 `--set task.max_steps=0`
3. 配置文件中设置 `max_steps: null`

**Q: 如何查看作业是否还在运行？**

A: `squeue -u $USER`

**Q: 如何实时查看日志？**

A: `tail -f logs/eval_<job_id>.out`

**Q: 如何取消正在运行的作业？**

A: `scancel <job_id>`

**Q: 如何批量评估多个任务？**

A: `bash tools/submit_batch.sh pi05_unlimited_steps prefix task1 task2 task3`

## 📚 文档

- **完整 SLURM 指南**: `docs/SLURM_GUIDE.md`
- **快速参考**: `docs/QUICK_REFERENCE.md`
- **工具文档**: `tools/README.md`

---

**立即开始**: `sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps test`
