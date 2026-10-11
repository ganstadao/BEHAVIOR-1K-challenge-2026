# OpenPI-Comet 使用指南

## 📦 已准备的资源

- ✅ Checkpoint: `~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt50-cs32` (pt50 版本，效果更好)
- ✅ Checkpoint: `~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt12-cs32` (pt12 版本)
- ✅ 项目代码: `~/LINJ0121/openpi-comet`
- ✅ 环境: 与 openpi 相同（使用 openpi-comet 的 .venv）

## 🚀 立即开始

### 方法 1: 使用预设配置（推荐）

```bash
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_test
```

### 方法 2: 命令行指定 comet checkpoint

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps comet_test \
    --set policy.openpi_dir=~/LINJ0121/openpi-comet \
    --set policy.checkpoint=~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt50-cs32
```

## 📝 关键差异

### OpenPI-Comet vs 原版 OpenPI

| 特性 | 原版 OpenPI | OpenPI-Comet |
|------|-------------|--------------|
| 项目路径 | `~/LINJ0121/openpi` | `~/LINJ0121/openpi-comet` |
| Checkpoint | 原始 pi0.5 | Team Comet pt50/pt12 |
| 参数 | `--robot`, `--task` | `--task_name`, `--dataset_root` |
| 性能 | 基准 | 改进版（pt50 效果更好） |

### 系统自动识别

评估系统会自动识别 openpi-comet：
- 通过 `policy.type: pi0.5-comet` 
- 或通过 `openpi_dir` 路径包含 "comet"
- 自动使用正确的参数格式

## 🎯 使用场景

### 场景 1: 评估 pt50 checkpoint（推荐）

```bash
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_eval
```

### 场景 2: 对比 pt50 vs pt12

```bash
# 评估 pt50
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_eval

# 评估 pt12
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt12_eval \
    --set policy.checkpoint=~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt12-cs32
```

### 场景 3: 对比 Comet vs 原版 OpenPI

```bash
# Comet pt50
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio comet_pt50

# 原版 OpenPI
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps original
```

### 场景 4: 评估不同任务（pt50）

```bash
# turning_on_lamp
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio lamp_eval \
    --set task.name=turning_on_lamp \
    --set policy.task_name=turning_on_lamp

# opening_door
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio door_eval \
    --set task.name=opening_door \
    --set policy.task_name=opening_door
```

### 场景 5: 批量评估（pt50）

```bash
# 批量评估多个任务
for task in turning_on_radio turning_on_lamp opening_door; do
    sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio "pt50_${task}" \
        --set task.name=$task \
        --set policy.task_name=$task
done
```

## ⚙️ 配置文件详解

### Comet 特有配置

```yaml
policy:
  type: pi0.5-comet  # 标识为 comet
  openpi_dir: ~/LINJ0121/openpi-comet  # comet 项目路径
  checkpoint: ~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt50-cs32  # pt50
  
  # Comet 特有参数
  dataset_root: /scr/behavior/2025-challenge-demos  # 数据集路径
  task_name: turning_on_radio  # 任务名称
  
  # 通用参数
  port: 8000
  gpu_id: 0
```

### 创建自定义 Comet 配置

```bash
# 复制模板
cp configs/comet_pt50_turning_on_radio.yaml configs/my_comet_config.yaml

# 修改任务
vim configs/my_comet_config.yaml
# 改: task.name 和 policy.task_name

# 使用
sbatch tools/submit_eval_advanced.sh configs/my_comet_config.yaml my_run
```

## 🔍 验证和调试

### 检查 checkpoint 是否正确

```bash
ls -la ~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt50-cs32/
# 应该看到: params/, assets/, _CHECKPOINT_METADATA
```

### 查看评估日志

```bash
# 实时查看
tail -f logs/eval_<job_id>.out

# 查看 policy server 日志
tail -f eval_logs/pi0.5-comet/turning_on_radio/*/logs/policy_server.log
```

### 常见问题

**Q: 如何确认使用的是 comet checkpoint？**

A: 查看输出目录和配置：
```bash
# 查看输出目录（会包含 pi0.5-comet）
ls eval_logs/

# 查看保存的配置
cat eval_logs/pi0.5-comet/turning_on_radio/*/config.yaml | grep checkpoint
```

**Q: pt50 和 pt12 哪个效果更好？**

A: 根据你的说法，pt50 (pi05-b1kpt50-cs32) 效果更好，建议优先使用。

**Q: 可以用原版 openpi 的环境吗？**

A: 建议使用 openpi-comet 自己的 .venv 环境，因为可能有依赖差异。

## 📊 性能对比

建议做以下对比实验：

```bash
# 1. Comet pt50 (推荐)
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_baseline

# 2. Comet pt12
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt12_baseline \
    --set policy.checkpoint=~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt12-cs32

# 3. 原版 OpenPI (如果有)
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps original_baseline \
    --set policy.checkpoint=~/LINJ0121/checkpoint/pi05_turn_on_the_radio
```

然后分析结果：
```bash
bash tools/analyze_results.sh eval_logs/pi0.5-comet/turning_on_radio/*/
```

## 📚 参考资源

- **Tech Report**: https://arxiv.org/abs/2512.10071
- **GitHub**: https://github.com/mli0603/openpi-comet
- **PyTorch 版本**: https://huggingface.co/sunshk/openpi_comet_pytorch

## 🎉 推荐工作流

1. **快速测试 pt50**
   ```bash
   sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio quick_test \
       --set task.max_steps=100
   ```

2. **完整评估 pt50**
   ```bash
   sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio full_eval
   ```

3. **分析结果**
   ```bash
   bash tools/analyze_results.sh latest pi0.5-comet turning_on_radio
   ```

---

**立即开始**: `sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_test`
