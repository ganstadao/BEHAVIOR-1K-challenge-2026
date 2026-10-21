# 🔍 Action 日志记录和分析 - 快速上手指南

## ✅ 已完成的设置

### 1. 创建的文件
```
OmniGibson/omnigibson/eval/wrappers/
├── __init__.py                    # ✅ 已更新，添加了 ActionLoggingWrapper
└── action_logger.py               # ✅ 新建，Action 日志记录 Wrapper

test/
├── turning_on_radio_debug_actions.sh  # ✅ 新建，带日志的评估脚本
└── analyze_actions.py                  # ✅ 新建，Action 分析工具
```

### 2. 核心原理

**不修改源码的关键**：利用 OmniGibson 的 `--env-wrapper` 参数

```python
# 代码流程
eval.py
  └─> evaluator.step()
       ├─> self.robot_action = self.policy.forward(obs)  # 获取 action
       └─> self.env.step(self.robot_action)              # 执行 action
            └─> ActionLoggingWrapper.step(action)         # 👈 我们的 Wrapper 拦截这里
                 ├─> _log_action(action)                  # 记录到文件
                 └─> super().step(action)                 # 继续执行
```

**为什么这样设计**：
- ✅ 不修改任何源码
- ✅ 符合 OmniGibson 架构设计
- ✅ 可以随时启用/禁用
- ✅ 易于维护和复用

---

## 🚀 使用方法

### 方法 1: 使用提供的脚本（推荐）

```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K

# 运行带 action 日志的评估（只运行100步，快速调试）
bash test/turning_on_radio_debug_actions.sh

# 或者提交到 SLURM
sbatch test/turning_on_radio_debug_actions.sh
```

**日志保存位置**：
```
eval_logs/turning_on_radio_action_debug/
├── actions_readable.txt    # 人类可读格式
├── actions.jsonl           # JSON 格式（用于编程分析）
├── omnigibson_eval.log     # OmniGibson 日志
├── policy_server.log       # Policy server 日志
├── videos/                 # 评估视频
└── json/                   # 评估指标
```

### 方法 2: 手动运行（更灵活）

```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K

# 1. 启动 policy server
cd ~/LINJ0121/Isaac-GR00T
CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/b1k/serve_b1k.py \
    --model-path ~/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000 \
    --modality-config-path examples/b1k/r1pro.py \
    --embodiment-tag NEW_EMBODIMENT \
    --host 127.0.0.1 \
    --port 8000 &

# 等待服务器启动（约60秒）
sleep 60

# 2. 运行评估（使用 ActionLoggingWrapper）
cd ~/project/BEHAVIOR-1K
OMNIGIBSON_HEADLESS=1 \
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --host 127.0.0.1 \
    --port 8000 \
    --output-dir ./eval_logs/turning_on_radio_action_debug \
    --write-video \
    --env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper \
    --max-steps 100
```

**关键参数**：
- `--env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper` 👈 启用 action 日志
- `--max-steps 100` 👈 快速调试，只运行100步

---

## 📊 分析 Action 日志

### 方法 1: 使用分析脚本（推荐）

```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K

python test/analyze_actions.py eval_logs/turning_on_radio_action_debug
```

**输出示例**：
```
================================================================================
🔍 Action Log Analysis
================================================================================
📊 Total steps: 100

--------------------------------------------------------------------------------
🚶 Base Movement Analysis
--------------------------------------------------------------------------------
Moving steps:        5 / 100 (5.0%)
Stationary steps:   95 / 100 (95.0%)

Linear X (forward/backward):
  Min:  -0.00123
  Max:   0.00087
  Mean:  0.00012
  Std:   0.00034

First 10 steps:
Step   0: x= 0.0001, y=-0.0002, θ= 0.0003  🛑 STOP
Step   1: x= 0.0000, y= 0.0001, θ=-0.0001  🛑 STOP
...

🔬 Diagnosis
--------------------------------------------------------------------------------
❌ Problem: Robot is mostly STATIONARY (< 10% moving steps)

Possible causes:
  1. Policy is not outputting valid movement commands
  2. Policy thinks robot is already at target
  3. Navigation module failed in training
  4. Action normalization issue
```

### 方法 2: 手动查看日志

#### 查看可读格式
```bash
# 查看前50行
head -50 eval_logs/turning_on_radio_action_debug/actions_readable.txt

# 查看 base 移动命令
grep "Base Movement" eval_logs/turning_on_radio_action_debug/actions_readable.txt | head -20

# 统计移动 vs 静止
grep -c "MOVING" eval_logs/turning_on_radio_action_debug/actions_readable.txt
grep -c "STATIONARY" eval_logs/turning_on_radio_action_debug/actions_readable.txt
```

#### 用 Python 分析 JSON
```python
import json
import numpy as np

# 读取日志
with open('eval_logs/turning_on_radio_action_debug/actions.jsonl') as f:
    actions = [json.loads(line) for line in f]

print(f"Total steps: {len(actions)}")

# 提取 base 移动
if 'base' in actions[0]:
    base_movements = [a['base'] for a in actions]
    
    # 统计移动步数
    moving = sum(1 for b in base_movements 
                 if abs(b['linear_x']) > 0.001 or abs(b['linear_y']) > 0.001)
    
    print(f"Moving steps: {moving}/{len(base_movements)}")
    
    # 绘制轨迹
    import matplotlib.pyplot as plt
    x_vel = [b['linear_x'] for b in base_movements]
    y_vel = [b['linear_y'] for b in base_movements]
    
    plt.figure(figsize=(12, 4))
    plt.subplot(121)
    plt.plot(x_vel, label='Linear X')
    plt.plot(y_vel, label='Linear Y')
    plt.legend()
    plt.title('Base Velocity Over Time')
    
    plt.subplot(122)
    plt.scatter(x_vel, y_vel, alpha=0.5)
    plt.xlabel('Linear X')
    plt.ylabel('Linear Y')
    plt.title('Velocity Distribution')
    plt.savefig('action_analysis.png')
```

---

## 🔍 诊断清单

根据你的观察"机器人压根就没动，就在原地转了一些角度"，检查以下内容：

### ✅ 检查点 1: Base Action 是否为零？

```bash
head -100 eval_logs/turning_on_radio_action_debug/actions_readable.txt | grep "Linear"
```

**预期**：如果要导航，`Linear X` 或 `Linear Y` 应该有明显的非零值（>0.01）

**如果全是接近 0**：
- Policy 没有输出有效的导航指令
- 可能原因：
  1. Checkpoint 加载错误
  2. 观察空间不匹配
  3. Policy 训练不足（没学会导航）
  4. Action normalization 问题

### ✅ 检查点 2: Action 的量级

```bash
grep "Stats:" eval_logs/turning_on_radio_action_debug/actions_readable.txt | head -5
```

**异常情况**：
- 全是 0 或接近 0 → Policy 完全不工作
- 全是 NaN → Policy 推理失败
- 值太大（>1.0）→ Action scaling 问题
- 值太小（<0.001）→ Action normalization 问题

### ✅ 检查点 3: Policy Server 是否正常？

```bash
tail -50 eval_logs/turning_on_radio_action_debug/policy_server.log
```

**查找**：
- 是否有错误信息？
- 模型是否正确加载？
- 推理是否正常？

### ✅ 检查点 4: 对比训练数据

如果你有训练数据：
```python
# 检查训练数据中的 action 分布
# 对比 policy 输出和 demo 中的 action
# 看看量级和分布是否一致
```

---

## 🎯 根据诊断结果的下一步

### 场景 A: Base Action 全是接近 0

**问题**：Policy 没有输出移动指令

**下一步**：
1. 检查 checkpoint 路径是否正确
2. 验证 policy server 是否正确加载模型
3. 检查观察空间是否匹配（图像分辨率、传感器配置等）
4. 查看训练数据是否包含导航阶段

**如何验证**：
```bash
# 查看 policy server 日志
grep -i "load\|checkpoint\|error" eval_logs/turning_on_radio_action_debug/policy_server.log
```

### 场景 B: Action 有值但很小（< 0.01）

**问题**：Action normalization 或 scaling 问题

**下一步**：
1. 检查训练和评估时的 action space 定义
2. 查看 action normalization 参数
3. 对比训练数据中的 action 量级

### 场景 C: 只有 Angular Z（旋转），没有 Linear X/Y

**问题**：Policy 学到了"原地旋转"而不是"导航"

**下一步**：
1. 检查训练数据质量
2. 查看 demo 中机器人是否真的移动了
3. 可能需要重新训练或增加导航相关的 demo

---

## 📝 记录实验结果

创建实验日志：
```bash
cat > experiment_log.txt << EOF
实验日期: $(date)
实验目标: 诊断为什么机器人不移动

观察:
- 机器人原地不动，只有轻微转动和手臂挥动
- 运行了 100 步

Action 日志分析:
- Base Linear X 范围: [填写]
- Base Linear Y 范围: [填写]
- 移动步数比例: [填写]%

初步结论:
[根据分析结果填写]

下一步计划:
[填写你的下一步行动]
EOF
```

---

## 💡 小贴士

### 快速重试
如果你想快速测试修改后的效果：
```bash
# 只运行 50 步，更快
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --host 127.0.0.1 \
    --port 8000 \
    --output-dir ./eval_logs/quick_test \
    --env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper \
    --max-steps 50 \
    --no-write-video  # 不生成视频，更快
```

### 对比实验
```bash
# 实验1: 使用你的 checkpoint
bash test/turning_on_radio_debug_actions.sh

# 实验2: 使用官方 baseline checkpoint（如果有）
# 修改脚本中的 PATH_TO_CKPT 然后运行

# 对比两个实验的 action 日志
diff eval_logs/exp1/actions_readable.txt eval_logs/exp2/actions_readable.txt
```

### 实时监控
```bash
# 在评估运行时，实时查看 action
tail -f eval_logs/turning_on_radio_action_debug/actions_readable.txt
```

---

## 🆘 常见问题

**Q: 运行后没有生成 action 日志？**

A: 检查：
1. 是否使用了 `--env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper` 参数？
2. 查看控制台输出，是否有 "✅ Action Logging Wrapper Enabled!" 提示？

**Q: 日志显示 "No 'base' field found"？**

A: Action 的结构可能不同，查看 `actions.jsonl` 中的完整 action 内容

**Q: 想修改日志保存位置？**

A: 修改 Wrapper 的 `__init__` 方法中的 `log_dir` 参数，或者在实例化时传入

---

## 🎓 总结

你现在有了一个**完全不修改源码**的 action 日志系统：

1. ✅ **Wrapper 方案** - 利用 OmniGibson 的设计接口
2. ✅ **易于使用** - 只需添加一个命令行参数
3. ✅ **详细日志** - JSON + 人类可读两种格式
4. ✅ **分析工具** - 自动诊断问题

**下一步**：
1. 运行评估获取 action 日志
2. 用分析脚本快速诊断
3. 根据诊断结果制定改进方案
4. 回到我之前给你的 `学习路线_turning_on_radio调试.md` 继续后续步骤

加油！🚀
