# 统一评估系统

一个配置驱动的评估接口，用于 BEHAVIOR-1K 项目的 policy 评估。

## ✨ 特性

- ✅ **统一接口** - 通过配置文件管理所有参数
- ✅ **详细日志** - Policy server 和 OmniGibson 的完整日志
- ✅ **清晰输出** - 自动组织的目录结构，每次运行独立
- ✅ **参数覆盖** - 灵活的命令行参数覆盖
- ✅ **多 Policy** - 支持 pi0.5 和 GR00T
- ✅ **Policy 记录** - 支持 pi0.5 的 --record 功能
- ✅ **批量评估** - 轻松评估多个任务或 checkpoint
- ✅ **不改源码** - 所有功能通过配置实现

## 🚀 快速开始

### 1. 运行评估

```bash
# 使用预定义配置
python tools/eval_runner.py --preset pi05_turning_on_radio --run-name exp1

# 或使用配置文件
python tools/eval_runner.py --config configs/pi05_turning_on_radio.yaml
```

### 2. 查看结果

```bash
# 自动分析最新结果
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

### 3. 输出结构

```
eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/
├── config.yaml              # 运行配置
├── summary.yaml             # 运行总结
├── logs/
│   ├── policy_server.log    # Policy server 日志
│   └── omnigibson_eval.log  # 评估日志
├── json/
│   └── *.json               # 评估结果
└── videos/
    └── *.mp4                # 评估视频
```

## 📚 文档

- **[快速参考](docs/QUICK_REFERENCE.md)** - 常用命令和场景
- **[完整指南](docs/EVAL_RUNNER_GUIDE.md)** - 详细使用说明
- **[配置模板](configs/template.yaml)** - 配置文件参考

## 🛠️ 工具

| 工具 | 说明 |
|------|------|
| `eval_runner.py` | 主评估工具 |
| `batch_eval.py` | 批量评估多个任务/checkpoint |
| `config_gen.py` | 快速生成配置文件 |
| `analyze_results.sh` | 结果分析脚本 |
| `submit_eval.sh` | SLURM 提交脚本 |

## 💡 使用示例

### 基本使用

```bash
# 使用预设配置
python tools/eval_runner.py --preset pi05_turning_on_radio --run-name baseline

# 覆盖参数
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.name=turning_on_lamp \
    --run-name lamp_test
```

### 批量评估

```bash
# 评估多个任务
python tools/batch_eval.py --mode tasks \
    --config configs/pi05_turning_on_radio.yaml \
    --tasks turning_on_radio turning_on_lamp opening_door \
    --run-prefix baseline

# 评估多个 checkpoint
python tools/batch_eval.py --mode checkpoints \
    --config configs/pi05_turning_on_radio.yaml \
    --task turning_on_radio \
    --checkpoints step1k=~/ckpts/1000 step2k=~/ckpts/2000 \
    --run-prefix ckpt_compare
```

### 生成配置

```bash
# 生成新配置文件
python tools/config_gen.py \
    --type pi0.5 \
    --task turning_on_lamp \
    --checkpoint ~/checkpoints/my_model \
    --output configs/my_config.yaml
```

### 结果分析

```bash
# 分析最新运行
bash tools/analyze_results.sh latest pi0.5 turning_on_radio

# 分析特定运行
bash tools/analyze_results.sh eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1
```

## 📝 配置文件

### 创建配置

```bash
# 从模板复制
cp configs/template.yaml configs/my_experiment.yaml

# 或使用生成器
python tools/config_gen.py \
    --type pi0.5 \
    --task turning_on_radio \
    --checkpoint ~/checkpoints/model \
    --output configs/my_experiment.yaml
```

### 配置结构

```yaml
policy:
  type: pi0.5              # pi0.5 或 gr00t
  checkpoint: ~/path/...   # 模型路径
  port: 8000

behavior:
  path: ~/project/BEHAVIOR-1K
  python_path: ~/.conda/envs/behavior/bin/python

task:
  name: turning_on_radio
  max_steps: 500
  write_video: true

logging:
  detailed_logging: true   # 详细日志
  record_policy: true      # pi0.5 的 --record

output:
  base_dir: ./eval_logs
  run_name: default
```

## 🎯 常用场景

### 快速测试

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.max_steps=100 \
    --set task.write_video=false \
    --run-name quick_test
```

### 调试模式

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG \
    --run-name debug
```

### SLURM 提交

```bash
sbatch tools/submit_eval.sh pi05_turning_on_radio my_experiment
```

## 🔍 故障排查

### Policy server 启动失败

```bash
# 查看日志
cat eval_logs/pi0.5/task/latest/logs/policy_server.log

# 常见问题：
# - Checkpoint 路径错误
# - 端口被占用
# - GPU 内存不足
```

### 端口冲突

```bash
# 使用不同端口
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.port=8001 \
    --run-name port8001
```

## 📊 与原脚本对比

| 特性 | 原脚本 | 统一接口 |
|------|--------|----------|
| 参数配置 | 修改脚本 | 配置文件 ✓ |
| 输出目录 | 手动指定 | 自动生成 ✓ |
| 日志记录 | 部分支持 | 完整支持 ✓ |
| 参数覆盖 | 不支持 | 支持 ✓ |
| 多次运行区分 | 手动管理 | 自动管理 ✓ |
| Policy 记录 | 需手动添加 | 配置开关 ✓ |
| 运行总结 | 无 | 自动生成 ✓ |
| 批量评估 | 不支持 | 支持 ✓ |

## 📁 文件结构

```
tools/
├── eval_runner.py         # 主评估工具
├── batch_eval.py          # 批量评估
├── config_gen.py          # 配置生成器
├── analyze_results.sh     # 结果分析
└── submit_eval.sh         # SLURM 提交

configs/
├── template.yaml          # 配置模板
├── pi05_turning_on_radio.yaml
└── gr00t_turning_on_radio.yaml

docs/
├── EVAL_RUNNER_GUIDE.md   # 完整指南
└── QUICK_REFERENCE.md     # 快速参考

eval_logs/
└── <policy_type>/
    └── <task_name>/
        └── <timestamp>_<run_name>/
            ├── config.yaml
            ├── summary.yaml
            ├── logs/
            ├── json/
            └── videos/
```

## 🤝 贡献

如需添加功能或修复问题：

1. 修改对应的工具脚本
2. 更新配置模板（如需要）
3. 更新文档

## 📖 更多资源

- OpenPI: `~/LINJ0121/openpi/`
- BEHAVIOR-1K: `README.md`
- 原评估脚本: `test/run_pi0_5_eval.sh`, `test/turning_on_radio_with_logging.sh`

## 💬 常见问题

**Q: 如何查看正在运行的评估？**

```bash
# 实时查看日志
tail -f eval_logs/pi0.5/turning_on_radio/latest/logs/policy_server.log
```

**Q: 如何比较多次运行？**

所有运行都在独立目录中，可以轻松比较：

```bash
# 列出所有运行
ls eval_logs/pi0.5/turning_on_radio/

# 比较结果
diff eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1/json/*.json \
     eval_logs/pi0.5/turning_on_radio/20241005_150133_exp2/json/*.json
```

**Q: 如何清理旧结果？**

```bash
# 只保留最近 5 次运行
cd eval_logs/pi0.5/turning_on_radio/
ls -t | tail -n +6 | xargs rm -rf
```

---

**开始使用**: `python tools/eval_runner.py --preset pi05_turning_on_radio --run-name test`

**查看文档**: [快速参考](docs/QUICK_REFERENCE.md) | [完整指南](docs/EVAL_RUNNER_GUIDE.md)
