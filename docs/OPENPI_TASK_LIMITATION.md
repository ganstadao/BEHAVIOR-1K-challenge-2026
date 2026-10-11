# OpenPI 官方 Checkpoint 使用指南和任务限制

## 🔍 问题诊断

### 错误信息
```python
KeyError: 'turning_on_lamp'
```

### 根本原因

**OpenPI 官方 checkpoint 只支持有限的任务！**

查看 `~/LINJ0121/openpi/src/openpi/configs/tasks/b1k.py`:

```python
TASKS = {
    "turning_on_radio": "Turn on the radio receiver that's on the table in the living room.",
}
```

**发现**：
- ✅ 只有 `turning_on_radio` 被注册
- ❌ `turning_on_lamp` 未注册
- ❌ `opening_doors` 未注册
- ❌ 其他大部分任务也未注册

这是因为官方 checkpoint 只在特定任务上训练/测试过。

## 📊 OpenPI 支持的任务

### 当前支持
根据代码，官方 OpenPI 目前只明确支持：
- ✅ `turning_on_radio`

### 可能支持（需要验证）
其他任务可能支持，但需要手动添加到 TASK_REGISTRY 或使用不同的方式。

## 💡 解决方案

### 方案 1: 只使用 turning_on_radio（推荐）

最简单、最稳定的方式：

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps radio_test \
    --set task.name=turning_on_radio
```

### 方案 2: 手动添加其他任务到 TASK_REGISTRY

如果你想测试其他任务，需要修改 OpenPI 的任务配置。

#### 步骤 1: 编辑任务文件

```bash
vim ~/LINJ0121/openpi/src/openpi/configs/tasks/b1k.py
```

#### 步骤 2: 添加任务

```python
from . import TASK_REGISTRY

# i3l task prompts
TASKS = {
    "turning_on_radio": "Turn on the radio receiver that's on the table in the living room.",
    "turning_on_lamp": "Turn on the lamp that's on the table.",
    "opening_doors": "Open the door.",
    "closing_doors": "Close the door.",
    # 添加更多任务...
}

# Register in global registry
TASK_REGISTRY["b1k"] = TASKS
```

#### 步骤 3: 重新评估

```bash
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps lamp_test \
    --set task.name=turning_on_lamp
```

**注意**: 
- 这样做可以让代码运行，但 checkpoint 可能没有在这些任务上训练过
- 性能可能不好或完全失败
- 这是一个**实验性**的方法

### 方案 3: 使用通用 Prompt（如果 OpenPI 支持）

有些模型支持通用的自然语言 prompt 而不依赖预定义任务。

检查 OpenPI 是否支持：

```bash
grep -r "default_prompt\|prompt" ~/LINJ0121/openpi/scripts/b1k/serve_b1k.py | head -20
```

如果支持，可能可以通过配置 `default_prompt` 来处理任意任务。

### 方案 4: 不使用 OpenPI 的任务系统

这需要修改评估流程，绕过 OpenPI 的 TASK_REGISTRY 机制。

**复杂度**: 高，不推荐

## 🎯 推荐工作流

基于当前情况，我建议：

### 阶段 1: 建立 Baseline（turning_on_radio）

```bash
# 1. 快速测试
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps quick_test \
    --set task.name=turning_on_radio \
    --set task.max_steps=100

# 2. 完整评估
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps full_eval \
    --set task.name=turning_on_radio
```

### 阶段 2: 探索其他任务支持

#### 选项 A: 修改 TASK_REGISTRY（实验性）

```bash
# 1. 备份原文件
cp ~/LINJ0121/openpi/src/openpi/configs/tasks/b1k.py \
   ~/LINJ0121/openpi/src/openpi/configs/tasks/b1k.py.bak

# 2. 编辑添加任务
vim ~/LINJ0121/openpi/src/openpi/configs/tasks/b1k.py

# 3. 测试新任务
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps lamp_test \
    --set task.name=turning_on_lamp
```

#### 选项 B: 寻找其他 Checkpoint

查找支持更多任务的 checkpoint：
- 社区发布的模型
- 自己训练的模型
- 其他团队的实现

### 阶段 3: 自己训练模型

如果需要支持更多任务，考虑：
- 收集演示数据
- 微调现有模型
- 从头训练新模型

## 📝 创建任务扩展脚本

让我为你创建一个便捷的脚本来添加任务：

```bash
#!/bin/bash
# 文件: tools/add_openpi_task.sh
# 用途: 向 OpenPI 添加新任务

TASK_FILE=~/LINJ0121/openpi/src/openpi/configs/tasks/b1k.py

# 备份
cp $TASK_FILE ${TASK_FILE}.bak

# 添加任务
cat > $TASK_FILE << 'EOF'
from . import TASK_REGISTRY

# BEHAVIOR-1K task prompts
TASKS = {
    "turning_on_radio": "Turn on the radio receiver that's on the table in the living room.",
    "turning_on_lamp": "Turn on the lamp that's on the table.",
    "opening_doors": "Open the door in front of you.",
    "closing_doors": "Close the door in front of you.",
    "turning_off_radio": "Turn off the radio receiver that's on the table.",
    "cleaning_bathtub": "Clean the bathtub in the bathroom.",
}

# Register in global registry
TASK_REGISTRY["b1k"] = TASKS
EOF

echo "Tasks added! Backup saved to ${TASK_FILE}.bak"
echo "Added tasks:"
python3 -c "
import sys
sys.path.insert(0, '~/LINJ0121/openpi/src')
from openpi.configs.tasks.b1k import TASKS
for task in TASKS.keys():
    print(f'  - {task}')
"
```

使用方法：
```bash
chmod +x tools/add_openpi_task.sh
bash tools/add_openpi_task.sh
```

## 🔍 验证任务是否已注册

创建验证脚本：

```bash
#!/usr/bin/env python3
# 文件: tools/check_openpi_tasks.py
# 用途: 检查 OpenPI 支持哪些任务

import sys
sys.path.insert(0, '/home/msai/linj0121/LINJ0121/openpi/src')

try:
    from openpi.configs.tasks import TASK_REGISTRY
    
    print("OpenPI 支持的任务:")
    print("=" * 50)
    
    if 'b1k' in TASK_REGISTRY:
        for task_name, prompt in TASK_REGISTRY['b1k'].items():
            print(f"✓ {task_name}")
            print(f"  Prompt: {prompt}")
            print()
    else:
        print("❌ 'b1k' bucket not found in TASK_REGISTRY")
        
    print(f"总计: {len(TASK_REGISTRY.get('b1k', {}))} 个任务")
    
except Exception as e:
    print(f"错误: {e}")
```

使用：
```bash
python tools/check_openpi_tasks.py
```

## 🎯 实际可行的任务列表

### 目前可用
- ✅ `turning_on_radio` - 官方支持，推荐使用

### 可能添加（需要手动注册）
- ⚠️ `turning_on_lamp`
- ⚠️ `opening_doors`
- ⚠️ `closing_doors`
- ⚠️ 其他简单任务

**注意**: 添加到注册表只是让代码能运行，不保证 checkpoint 在这些任务上表现良好。

### 不推荐（模型未训练）
- ❌ 复杂的多步骤任务
- ❌ 需要特定领域知识的任务

## 📊 对比：OpenPI vs OpenPI-Comet

| 特性 | 官方 OpenPI | OpenPI-Comet |
|------|-------------|--------------|
| 兼容性 | ✅ 可用 | ❌ 不兼容 |
| 支持任务 | ⚠️ 有限（目前只有 turning_on_radio）| 🔄 可能更多（但无法运行）|
| Checkpoint | ✅ 可用 | ❌ 无法加载 |
| 性能 | 🤷 基线性能 | 🤷 未知（无法测试）|

## 💡 当前最佳策略

### 立即可做

1. **专注于 turning_on_radio**
   ```bash
   sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps radio_baseline
   ```

2. **分析性能**
   ```bash
   bash tools/analyze_results.sh latest pi0.5 turning_on_radio
   ```

3. **建立评估流程**
   - 理解评估系统
   - 调试配置
   - 优化参数

### 短期目标

1. **扩展任务支持**
   - 手动添加 2-3 个相似任务到 TASK_REGISTRY
   - 实验性测试
   - 记录性能

2. **理解 OpenPI 架构**
   - 研究代码结构
   - 理解 prompt 机制
   - 探索扩展方法

### 中长期目标

1. **收集数据**
   - 为其他任务收集演示
   - 准备训练数据

2. **训练/微调模型**
   - 在更多任务上微调
   - 或从头训练

3. **探索其他方案**
   - 其他开源模型
   - 自己的实现

## 🚀 立即开始

```bash
# 1. 评估 turning_on_radio（唯一官方支持的任务）
sbatch tools/submit_eval_advanced.sh pi05_unlimited_steps radio_test \
    --set task.name=turning_on_radio

# 2. 查看结果
squeue -u $USER

# 3. 等待完成后分析
bash tools/analyze_results.sh latest pi0.5 turning_on_radio
```

## ⚠️ 重要提醒

1. **官方 OpenPI checkpoint 设计上只支持有限任务**
   - 这不是 bug，是设计如此
   - Checkpoint 只在这些任务上训练/测试过

2. **添加任务到 TASK_REGISTRY 是实验性的**
   - 代码能运行不代表能成功
   - 可能完全失败或表现很差
   - 但值得一试来探索

3. **OpenPI-Comet 更全面但不兼容**
   - 它可能支持更多任务
   - 但需要 2025 Challenge 版本的 OmniGibson
   - 目前无法在你的环境中使用

## 📚 参考资源

- OpenPI GitHub: https://github.com/Physical-Intelligence/openpi
- BEHAVIOR-1K: https://behavior.stanford.edu/
- OpenPI-Comet 论文: https://arxiv.org/abs/2512.10071

---

**总结**: 
- 官方 OpenPI 目前**只明确支持 `turning_on_radio`**
- 可以手动添加其他任务（实验性）
- 推荐先在 `turning_on_radio` 上建立 baseline
- 然后探索扩展方法或训练自己的模型
