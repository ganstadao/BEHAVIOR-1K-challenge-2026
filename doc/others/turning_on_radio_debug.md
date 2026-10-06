# Turning On Radio 任务调试与学习路线

## 📊 当前状态

### ✅ 已完成
- 环境搭建（behavior conda + GR00T uv venv）
- 跑通 GR00T baseline checkpoint（turning_on_radio_GR00T-checkpoint-150000）
- Policy server 正常启动（Qwen3VL + DiT）
- OmniGibson evaluator 运行成功
- 生成评估视频和日志
- 对代码框架有整体理解

### ❌ 当前问题
- **任务失败**: `success: false`, `q_score: 0.0`
- **运行**: 3225 步（107.5秒）但未成功
- **目标**: 让 radio 从 `toggled_off` 变为 `toggled_on`

### 📋 任务定义（BDDL）
```
初始状态:
  - radio_receiver.n.01_1 在 table.n.02_1 上
  - radio 未开启 (not toggled_on)
  - agent 在 living_room 的 floor 上

目标状态:
  - toggled_on radio_receiver.n.01_1
```

---

## 🎯 第一阶段：失败原因诊断（1-2天）⭐ 最重要

### 1.1 视频分析（最直观的方式）

**操作步骤：**
```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K/eval_logs/turning_on_radio/videos/

# 查看视频
# 使用本地播放器或者转移到有GUI的机器上
ls -lh turning_on_radio_301_0.mp4
```

**观察清单：**
- [ ] 机器人是否朝 radio 方向移动？
- [ ] 机器人是否成功接近桌子？
- [ ] 机器人手臂是否伸向 radio？
- [ ] 是否尝试按下按钮/旋转旋钮？
- [ ] 是否有碰撞、卡住、抖动？
- [ ] 是否一直在原地打转或不动？
- [ ] 导航阶段耗时多少？操作阶段耗时多少？

**常见失败模式：**
1. **导航失败**: 机器人无法到达桌子附近
2. **感知失败**: 没有看到/识别 radio
3. **操作失败**: 到达但无法成功操作（手够不到、力度不够、角度不对）
4. **策略失败**: 动作序列不合理（比如一直后退）
5. **碰撞卡死**: 撞到桌子或其他物体后无法恢复

---

### 1.2 分析评估指标

**已有数据：**
```json
{
  "steps": 3225,
  "success": false,
  "agent_distance": {
    "base": 0.233,      // 底座移动距离（米）
    "left": 3.557,      // 左臂移动距离
    "right": 4.821      // 右臂移动距离
  },
  "normalized_agent_distance": {
    "base": 24.428,     // 相对人类的移动效率
    "left": 0.916,
    "right": 0.845
  },
  "time": {
    "simulator_time": 107.5,  // 仿真时间（秒）
    "normalized_time": 0.667   // 相对人类的时间效率
  }
}
```

**关键分析：**
- `base: 0.233m` - 底座移动很少！可能根本没有导航到桌子
- `normalized_base: 24.428` - 比人类移动效率低24倍，说明移动策略有问题
- `left/right arm` - 手臂有移动，但可能是无效的挥动
- `time: 107.5s` - 用了66.7%的人类基准时间，但没成功

**推测：** 导航阶段可能失败，机器人没有到达桌子旁边

---

### 1.3 启用详细日志重新运行

**创建带详细日志的评估脚本：**

```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K

# 创建诊断脚本
cat > test/turning_on_radio_debug.sh << 'EOF'
#!/bin/bash
export GROOT_DIR=~/LINJ0121/Isaac-GR00T
export PATH_TO_BEHAVIOR_1K=~/project/BEHAVIOR-1K
export TASK_NAME=turning_on_radio
export PATH_TO_CKPT=~/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000
export PORT=8000
export LOG_PATH=./eval_logs/${TASK_NAME}_debug

mkdir -p $LOG_PATH

# 启动 policy server
cd "$GROOT_DIR"
CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/b1k/serve_b1k.py \
    --model-path "$PATH_TO_CKPT" \
    --modality-config-path examples/b1k/r1pro.py \
    --embodiment-tag NEW_EMBODIMENT \
    --host 127.0.0.1 \
    --port "$PORT" \
    > "$PATH_TO_BEHAVIOR_1K/$LOG_PATH/policy_server.log" 2>&1 &
SERVE_PID=$!
sleep 60  # 等待服务器启动

# 运行评估，添加详细日志
cd "$PATH_TO_BEHAVIOR_1K"
OMNIGIBSON_HEADLESS=1 \
CUDA_VISIBLE_DEVICES=0 \
python -m omnigibson.eval.eval \
    --task-name "$TASK_NAME" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --output-dir "$LOG_PATH" \
    --write-video \
    --log-level DEBUG 2>&1 | tee "$LOG_PATH/omnigibson_eval_debug.log"

kill "$SERVE_PID"
EOF

chmod +x test/turning_on_radio_debug.sh
```

**运行并收集日志：**
```bash
bash test/turning_on_radio_debug.sh
```

**分析日志：**
```bash
# 查看是否有错误或警告
grep -i "error\|warn\|fail" eval_logs/turning_on_radio_debug/omnigibson_eval_debug.log

# 查看 BDDL 条件评估
grep -i "condition\|goal\|satisfy" eval_logs/turning_on_radio_debug/omnigibson_eval_debug.log

# 查看 policy 推理日志
tail -100 eval_logs/turning_on_radio_debug/policy_server.log
```

---

### 1.4 检查任务实例配置

```bash
# 查看具体的任务实例配置
cd /home/msai/linj0121/project/BEHAVIOR-1K

# 查看 instance 301 的配置
find datasets/2026-challenge-task-instances -name "*301*" -path "*turning_on_radio*" | head -3
```

**需要确认：**
- Radio 的初始位置和朝向
- 桌子的位置
- 机器人的初始位置
- 房间布局

---

### 1.5 理解 object_states 系统

**阅读关键代码：**
```bash
# 查看 ToggledOn 状态的实现
find OmniGibson/omnigibson/object_states -name "*toggle*" -type f
```

**关键问题：**
- Radio 如何被"打开"？（按按钮？旋转旋钮？）
- 需要什么交互条件？（接触？施加力？特定部位？）
- transition rules 是什么？

---

## 🎯 第二阶段：根据诊断结果调整策略（3-5天）

### 场景A：导航失败

**如果机器人没有到达桌子：**

#### A1. 检查 baseline 训练数据质量
```bash
# 查看训练用的 demo 数据
export DATA_ROOT=~/2026-challenge-demos  # 如果你有的话
ls -lh $DATA_ROOT/data/chunk-000/  # turning_on_radio 是 task_id=0
```

**分析要点：**
- Demo 数量够吗？质量如何？
- Demo 中机器人是否成功导航到桌子？
- 观察空间是否充足（视觉、本体感觉）？

#### A2. 可视化 policy 输出
创建脚本打印每步的 action：
```python
# 在评估循环中添加日志
# 查看 action 的 base 部分是否合理
# 是否有朝目标方向的移动？
```

#### A3. 尝试简化场景
- 减少障碍物
- 缩短机器人到桌子的距离
- 固定机器人初始朝向

---

### 场景B：导航成功但操作失败

**如果机器人到达但无法操作 radio：**

#### B1. 检查 radio 的可交互性
```bash
# 查看 radio 的物体定义
find OmniGibson -name "*radio*" -type f | grep -v __pycache__
find datasets/behavior-1k-assets -name "*radio*" -type d
```

#### B2. 理解 ToggledOn 的触发机制
```python
# 阅读代码
# OmniGibson/omnigibson/object_states/toggled_on.py
# 找到触发条件
```

#### B3. 手动遥操作测试
```bash
# 使用 joylo 手动控制机器人测试任务
# 验证任务本身是可完成的
```

---

### 场景C：Policy 完全不工作

**如果动作完全混乱：**

#### C1. 检查 checkpoint 是否正确加载
```bash
# 查看 policy server 日志
cat eval_logs/turning_on_radio/policy_server.log

# 确认：
# - Checkpoint 路径正确
# - 模型权重加载成功
# - 没有 shape mismatch 错误
```

#### C2. 验证观察空间匹配
- Policy 训练时的观察空间
- 评估时的观察空间
- 是否有 wrapper 不匹配？

#### C3. 检查 action 空间匹配
- Action dimension 是否正确？
- Action normalization 是否一致？

---

## 🎯 第三阶段：改进策略（1-2周）

### 选项1：继续训练（如果有数据和资源）

```bash
# 参考 docs/challenge/baselines.md
cd $GROOT_DIR

# 更长时间训练
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
torchrun --nproc_per_node=8 scripts/b1k/train_b1k.py \
    --experiment-name b1k-turning_on_radio-v2 \
    --base-model-path nvidia/GR00T-N1.7-3B \
    --dataset-path $DATASET_PATH \
    --embodiment-tag NEW_EMBODIMENT \
    --modality-config-path examples/b1k/r1pro.py \
    --num-gpus 8 \
    --global-batch-size 2048 \
    --output-dir outputs \
    --max-steps 300000  # 增加训练步数
```

### 选项2：数据增强
- 收集更多 demo
- 添加不同初始配置的 demo
- 使用 joylo 遥操作收集数据

### 选项3：Prompt engineering（如果模型支持）
- 调整语言指令
- 添加更详细的任务描述

### 选项4：分层策略
```python
# 将任务分解为子任务：
# 1. Navigate to table
# 2. Reach for radio
# 3. Press button / turn knob
# 4. Verify toggled_on

# 每个子任务单独训练或使用 action primitives
```

### 选项5：迁移学习
- 从其他类似任务迁移（如 turning_on_lamp）
- 使用预训练的导航 policy + 微调操作部分

---

## 🎯 第四阶段：深入理解（并行进行）

### 4.1 阅读关键论文

**必读：**
1. **BEHAVIOR-1K 论文**: arXiv:2403.09227
   - 理解 benchmark 设计理念
   - 了解评估指标定义
   - 查看 baseline 结果和分析

2. **GR00T N1.7 论文/博客**:
   - https://huggingface.co/nvidia/GR00T-N1.7-3B
   - 理解模型架构（VLM + Diffusion Policy）
   - 了解训练方法和数据需求

3. **相关方法论文**:
   - Diffusion Policy
   - Visual Language Models for Robotics
   - Embodied AI Navigation

**重点关注：**
- Baseline 在这个任务上的成功率是多少？
- 常见失败模式是什么？
- 论文中提到的局限性

---

### 4.2 代码深入阅读

**核心模块：**

```bash
# 1. 评估流程
OmniGibson/omnigibson/eval/
├── eval.py           # 入口
├── evaluator.py      # 核心评估逻辑
└── utils/
    ├── eval_utils.py  # 工具函数
    ├── obs_utils.py   # 观察处理
    └── score_utils.py # 评分计算

# 2. 任务和状态
OmniGibson/omnigibson/
├── tasks/            # 任务定义
├── object_states/    # 物体状态（包括 ToggledOn）
└── transition_rules.py

# 3. BDDL
bddl3/bddl/
├── activity_definitions/turning_on_radio/
├── condition_evaluation.py
└── object_taxonomy.py
```

**阅读顺序：**
1. `evaluator.py:Evaluator.evaluate_rollout()` - 评估主循环
2. `object_states/toggled_on.py` - ToggledOn 状态实现
3. `condition_evaluation.py` - BDDL 条件如何评估
4. `tasks/behavior_task.py` - 任务接口

---

### 4.3 对比成功案例

**如果 baseline 在其他任务上成功：**
```bash
# 查看哪些任务成功率高
# 比较成功任务和失败任务的差异：
# - 任务复杂度
# - demo 数量和质量
# - 物理交互复杂度
# - 导航难度
```

---

## 📝 行动检查清单

### 本周必做（Week 1）：
- [ ] **Day 1**: 观看评估视频，记录失败模式
- [ ] **Day 1-2**: 运行 debug 脚本，分析详细日志
- [ ] **Day 2**: 阅读 ToggledOn 状态实现
- [ ] **Day 3**: 检查任务实例配置和 BDDL 定义
- [ ] **Day 3-4**: 阅读 BEHAVIOR-1K 论文相关章节
- [ ] **Day 4-5**: 理解评估流程代码
- [ ] **Day 5**: 制定具体改进方案

### 下周计划（Week 2）：
- [ ] 根据诊断结果实施改进
- [ ] 尝试 2-3 种不同的调试方法
- [ ] 记录每次实验的结果
- [ ] 如果需要，准备收集新的 demo 数据

---

## 🔧 调试工具和技巧

### 1. 可视化工具
```python
# 在评估过程中保存中间状态
# - 机器人位置轨迹
# - 目标物体位置
# - action 序列可视化
```

### 2. 简化调试
```python
# 创建最小化测试环境
# - 只有机器人、桌子、radio
# - 固定初始位置
# - 移除干扰物体
```

### 3. 单元测试
```python
# 测试 ToggledOn 状态
# 手动设置机器人到理想位置
# 测试单次操作是否能触发状态变化
```

---

## 📚 学习资源

### 文档
- [OmniGibson 文档](https://behavior.stanford.edu/omnigibson/)
- [BDDL 文档](https://behavior.stanford.edu/behavior_components/bddl.html)
- [Challenge 评估规则](docs/challenge/evaluation.md)
- [Baseline 详解](docs/challenge/baselines.md)

### 代码示例
```bash
# OmniGibson examples
OmniGibson/omnigibson/examples/

# 特别关注：
# - robots/ 机器人控制示例
# - teleoperation/ 遥操作示例
# - object_states/ 状态系统示例
```

### 社区资源
- GitHub Issues: 查看类似问题
- Discord/Slack: 询问社区
- 论文作者联系方式

---

## 🎓 预期成果

### 短期目标（2周内）：
1. **明确失败原因** - 导航？感知？操作？
2. **定位问题环节** - 哪个阶段出错？
3. **制定改进计划** - 具体可执行的步骤

### 中期目标（1个月内）：
1. **任务成功** - 至少一次成功 toggle radio
2. **理解瓶颈** - 深入理解当前方法的局限
3. **建立基线** - 记录当前方法的性能边界

### 长期目标（2-3个月）：
1. **提高成功率** - 稳定在 60%+ 成功率
2. **方法创新** - 提出自己的改进方法
3. **论文产出** - 基于实验结果撰写论文

---

## 💡 建议的日常工作流

### 每天工作流程：
1. **上午**（2-3小时）：
   - 运行实验/查看结果
   - 分析日志和视频
   - 记录观察和假设

2. **下午**（2-3小时）：
   - 阅读代码/论文
   - 实现改进方案
   - 准备下一轮实验

3. **晚上**（1小时）：
   - 更新实验日志
   - 整理学到的知识
   - 规划明天任务

### 实验记录模板：
```
实验日期: 2024-XX-XX
实验目标: 测试 XXX
修改内容: 
  - 修改了 YYY
  - 参数调整为 ZZZ
结果:
  - 成功: Yes/No
  - Q-score: X.XX
  - 观察: ...
结论:
  - 学到了什么
  - 下一步做什么
```

---

## ⚠️ 常见陷阱

1. **过早优化**: 在理解问题前就开始调参
2. **忽视视频**: 不看视频只看指标
3. **孤立调试**: 不对比其他任务的表现
4. **缺乏记录**: 不记录实验过程和结果
5. **盲目训练**: 不分析就增加训练时间/数据

---

## 🚀 快速开始

**今天就可以做的第一步：**

```bash
# 1. 观看视频
cd /home/msai/linj0121/project/BEHAVIOR-1K/eval_logs/turning_on_radio/videos/
# 播放 turning_on_radio_301_0.mp4

# 2. 检查日志
cat /home/msai/linj0121/project/BEHAVIOR-1K/eval_logs/turning_on_radio/json/turning_on_radio_301_0.json

# 3. 记录你的第一个观察
echo "视频观察: [在这里记录你看到的]" > 调试日志.txt
echo "初步假设: [为什么失败]" >> 调试日志.txt
```

**然后明天：**
- 根据观察决定是看论文还是调试代码
- 选择一个具体的诊断方向深入

---

## 总结

**当前阶段的核心任务：诊断 > 理解 > 改进**

不要急于训练新模型或大规模修改，先搞清楚：
1. **What**: 到底什么失败了？
2. **Why**: 为什么会失败？
3. **How**: 如何验证你的假设？

只有在明确了上面三点后，才能有效地改进！

加油！🎯
