# 统一评估系统使用总结

## 🎉 已创建的完整系统

我为你创建了一个完整的配置驱动评估系统，解决了你提出的所有问题：

### ✅ 解决的问题

1. ✅ **统一接口** - 不用每次修改 sh 脚本中的路径和参数
2. ✅ **详细日志** - 类似 `turning_on_radio_with_logging.sh` 的功能
3. ✅ **支持 pi0.5 和 GR00T** - 两种 policy 都支持
4. ✅ **Policy 记录** - 支持 pi0.5 的 --record 参数
5. ✅ **优化输出目录** - 清晰的目录结构，区分每次提交
6. ✅ **不修改源码** - 所有功能通过配置和参数实现

## 📁 创建的文件

### 核心工具
- `tools/eval_runner.py` - 主评估工具（350+ 行）
- `tools/batch_eval.py` - 批量评估工具
- `tools/config_gen.py` - 配置生成器
- `tools/analyze_results.sh` - 结果分析脚本
- `tools/submit_eval.sh` - SLURM 提交脚本

### 配置文件
- `configs/template.yaml` - 配置模板（带详细注释）
- `configs/pi05_turning_on_radio.yaml` - Pi0.5 示例配置
- `configs/gr00t_turning_on_radio.yaml` - GR00T 示例配置

### 文档
- `tools/README.md` - 工具总览
- `docs/EVAL_RUNNER_GUIDE.md` - 完整使用指南
- `docs/QUICK_REFERENCE.md` - 快速参考

## 🚀 立即开始

### 1. 第一次运行

```bash
cd ~/project/BEHAVIOR-1K

# 使用预设配置运行 pi0.5 评估
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --run-name first_test
```

### 2. 查看结果

```bash
# 自动分析最新结果
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

### 3. 输出目录

```
eval_logs/
└── pi0.5/                           # Policy 类型
    └── turning_on_radio/            # 任务名称
        └── 20241005_143022_first_test/  # 时间戳_运行名称
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

## 💡 常用命令

### 基本使用

```bash
# 1. 使用预设配置
python tools/eval_runner.py --preset pi05_turning_on_radio --run-name exp1

# 2. 使用配置文件
python tools/eval_runner.py --config configs/pi05_turning_on_radio.yaml

# 3. 覆盖参数
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.name=turning_on_lamp \
    --set task.max_steps=1000 \
    --run-name lamp_test
```

### 测试不同任务

```bash
# 快速切换任务（不用修改脚本！）
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.name=opening_door \
    --run-name door_test
```

### 使用不同 checkpoint

```bash
# 快速切换模型（不用修改脚本！）
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.checkpoint=~/LINJ0121/checkpoint/new_model \
    --run-name new_model_test
```

### 批量评估

```bash
# 一次评估多个任务
python tools/batch_eval.py --mode tasks \
    --config configs/pi05_turning_on_radio.yaml \
    --tasks turning_on_radio turning_on_lamp opening_door \
    --run-prefix baseline_eval

# 一次评估多个 checkpoint
python tools/batch_eval.py --mode checkpoints \
    --config configs/pi05_turning_on_radio.yaml \
    --task turning_on_radio \
    --checkpoints \
        step1k=~/LINJ0121/checkpoint/step_1000 \
        step2k=~/LINJ0121/checkpoint/step_2000 \
    --run-prefix ckpt_comparison
```

### 在 SLURM 上运行

```bash
# 提交作业
sbatch tools/submit_eval.sh pi05_turning_on_radio my_experiment

# 或自定义
sbatch --wrap="cd ~/project/BEHAVIOR-1K && \
    python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --run-name slurm_\${SLURM_JOB_ID}"
```

## 🎯 实用场景

### 场景 1: 快速测试新 checkpoint

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set policy.checkpoint=~/new_checkpoint \
    --set task.max_steps=100 \
    --set task.write_video=false \
    --set logging.record_policy=false \
    --run-name quick_test
```

### 场景 2: 完整评估实验（带所有日志）

```bash
python tools/eval_runner.py \
    --config configs/pi05_turning_on_radio.yaml \
    --run-name full_eval_with_logs
```

### 场景 3: 调试模式

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.policy_log_level=DEBUG \
    --set logging.eval_log_level=DEBUG \
    --set task.max_steps=50 \
    --run-name debug_run
```

### 场景 4: 使用 GR00T

```bash
python tools/eval_runner.py \
    --preset gr00t_turning_on_radio \
    --run-name groot_test
```

## 📊 与原脚本的对比

### 原来的方式（需要修改脚本）

```bash
# test/run_pi0_5_eval.sh
export TASK_NAME=turning_on_radio      # 要改这里
export PATH_TO_CKPT=~/checkpoint/...   # 要改这里
export LOG_PATH=./eval_logs/...        # 要改这里
```

### 现在的方式（命令行参数）

```bash
# 不用修改脚本！
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set task.name=turning_on_lamp \
    --set policy.checkpoint=~/new_ckpt \
    --run-name lamp_exp
```

## 🔧 配置管理

### 创建新配置

```bash
# 方法 1: 从模板复制
cp configs/template.yaml configs/my_config.yaml
vim configs/my_config.yaml

# 方法 2: 使用生成器
python tools/config_gen.py \
    --type pi0.5 \
    --task turning_on_lamp \
    --checkpoint ~/checkpoints/my_model \
    --output configs/my_config.yaml
```

### 配置文件的优势

1. **版本控制** - 可以 git 追踪配置变化
2. **可复现** - 每次运行自动保存配置到输出目录
3. **易分享** - 配置文件可以直接分享给他人
4. **灵活覆盖** - 可以用命令行参数临时覆盖

## 📈 输出目录的优势

### 自动组织

```
eval_logs/
├── pi0.5/                    # Policy 类型分组
│   ├── turning_on_radio/     # 任务分组
│   │   ├── 20241005_143022_exp1/   # 每次运行独立
│   │   ├── 20241005_150133_exp2/
│   │   └── 20241005_163045_exp3/
│   └── turning_on_lamp/
│       └── 20241005_170000_test/
└── gr00t/
    └── turning_on_radio/
        └── 20241005_180000_baseline/
```

### 好处

1. ✅ **清晰分类** - 按 policy 和 task 组织
2. ✅ **时间戳** - 自动记录运行时间
3. ✅ **易区分** - 通过 run_name 标识不同实验
4. ✅ **不覆盖** - 每次运行都是新目录
5. ✅ **易查找** - 结构化的目录便于查找和比较

## 🔍 结果分析

### 查看最新结果

```bash
# 自动找到并分析最新运行
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

### 输出示例

```
==========================================
Analyzing: eval_logs/pi0.5/turning_on_radio/20241005_143022_exp1
==========================================

[1] Configuration
Policy type: pi0.5
Task name: turning_on_radio
Checkpoint: ~/LINJ0121/checkpoint/pi05_turn_on_the_radio

[2] Summary
Run ID: pi0.5_turning_on_radio_20241005_143022
Timestamp: 20241005_143022
Exit code: 0

[3] Evaluation Results
File: turning_on_radio_301_0.json
  Success: true
  Steps: 234
  Satisfied predicates: 5
  Unsatisfied predicates: 0

[4] Logs
Policy server log: 1245 lines
  Errors: 0
OmniGibson eval log: 3456 lines
  Errors: 0

[5] Videos
Video files: 1
  - turning_on_radio_301_0.mp4 (45M)
```

## 📚 文档导航

- **快速开始**: 看 `tools/README.md`
- **快速命令**: 看 `docs/QUICK_REFERENCE.md`
- **完整指南**: 看 `docs/EVAL_RUNNER_GUIDE.md`
- **配置参考**: 看 `configs/template.yaml`

## 🎁 额外功能

### 1. Policy 记录

Pi0.5 支持 --record 参数来记录 policy 动作：

```yaml
# configs/pi05_turning_on_radio.yaml
logging:
  record_policy: true  # 启用 --record
```

或命令行：

```bash
python tools/eval_runner.py \
    --preset pi05_turning_on_radio \
    --set logging.record_policy=true \
    --run-name with_record
```

### 2. 详细日志

类似 `turning_on_radio_with_logging.sh` 的功能：

```yaml
# configs/pi05_turning_on_radio.yaml
logging:
  detailed_logging: true      # 使用 run_eval_with_logging.py
  policy_log_level: DEBUG     # Policy server 日志级别
  eval_log_level: INFO        # OmniGibson 日志级别
```

### 3. 运行总结

每次运行自动生成 `summary.yaml`：

```yaml
run_id: pi0.5_turning_on_radio_20241005_143022
timestamp: 20241005_143022
exit_code: 0
config:
  # 完整配置...
result_files:
  - eval_logs/.../json/result.json
```

## 💪 下一步

1. **测试系统**
   ```bash
   python tools/eval_runner.py --preset pi05_turning_on_radio --run-name test
   ```

2. **查看结果**
   ```bash
   bash tools/analyze_results.sh latest pi0.5 turning_on_radio
   ```

3. **根据需要调整配置**
   ```bash
   vim configs/pi05_turning_on_radio.yaml
   ```

4. **批量评估**
   ```bash
   python tools/batch_eval.py --mode tasks \
       --config configs/pi05_turning_on_radio.yaml \
       --tasks turning_on_radio turning_on_lamp \
       --run-prefix baseline
   ```

## 🆘 需要帮助？

- 查看 `docs/QUICK_REFERENCE.md` 获取常用命令
- 查看 `docs/EVAL_RUNNER_GUIDE.md` 获取详细说明
- 查看 `configs/template.yaml` 了解所有配置选项

---

**祝你评估顺利！** 🚀

如有问题或需要添加新功能，随时告诉我！
