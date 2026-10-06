# Action 日志记录方案 - 不修改源码

## 🔍 代码流程分析

### 整体调用链

```
eval.py (main)
  └─> Evaluator.__init__()
       ├─> load_env() - 创建环境
       ├─> load_robot() - 加载机器人
       └─> load_policy() - 加载 WebsocketPolicy
  
  └─> 评估循环 (eval.py:167-169)
       └─> evaluator.step()  [evaluator.py:247-263]
            ├─> self.robot_action = self.policy.forward(obs=self.obs)  [第248行] ⭐ 关键！
            │    └─> WebsocketPolicy.forward() [policies.py:67-71]
            │         └─> self.policy.act(obs) - 通过 websocket 获取 action
            │              └─> WebsocketClientPolicy (network_utils.py)
            │
            └─> obs, _, terminated, truncated, info = self.env.step(self.robot_action)  [第249行]
                 └─> 执行 action 到仿真环境
```

### 关键发现

1. **Action 获取位置**: `evaluator.py:248` 行
   ```python
   self.robot_action = self.policy.forward(obs=self.obs)
   ```

2. **Action 存储**: action 被存储在 `evaluator.robot_action` 中

3. **Action 格式**: 是一个 `torch.Tensor`，维度是 `robot.action_dim`

---

## 🎯 方案：使用自定义 Wrapper（推荐）⭐

**核心思路**: OmniGibson 的评估系统支持 `env_wrapper`，我们可以创建一个自定义 wrapper 来拦截和记录 action。

### 方案 A: 创建 Action Logging Wrapper（最优雅）

#### Step 1: 创建自定义 Wrapper

```python
# 文件: OmniGibson/omnigibson/eval/wrappers/action_logger.py

import json
import os
from typing import Any, Dict, Tuple
import torch as th
import numpy as np

from omnigibson.envs.env_wrapper import EnvironmentWrapper


class ActionLoggingWrapper(EnvironmentWrapper):
    """
    Wrapper that logs actions to a file for debugging.
    Inherits from the default wrapper and adds action logging.
    """
    
    def __init__(self, env, log_dir: str = None):
        super().__init__(env)
        
        # 设置日志目录
        if log_dir is None:
            log_dir = os.path.expanduser("~/project/BEHAVIOR-1K/eval_logs/action_debug")
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建日志文件
        self.action_log_path = os.path.join(log_dir, "actions.jsonl")
        self.action_txt_path = os.path.join(log_dir, "actions_readable.txt")
        self.step_count = 0
        
        # 打开日志文件
        self.action_log_file = open(self.action_log_path, 'w')
        self.action_txt_file = open(self.action_txt_path, 'w')
        
        print(f"✅ Action logging enabled!")
        print(f"   JSONL log: {self.action_log_path}")
        print(f"   Readable log: {self.action_txt_path}")
    
    def step(self, action: th.Tensor, n_render_iterations: int = 1) -> Tuple[Dict, float, bool, bool, Dict[str, Any]]:
        """
        Override step to log actions before executing them.
        """
        # 记录 action
        self._log_action(action)
        
        # 调用父类的 step（执行 action）
        obs, reward, terminated, truncated, info = super().step(action, n_render_iterations)
        
        self.step_count += 1
        return obs, reward, terminated, truncated, info
    
    def _log_action(self, action: th.Tensor):
        """Log action in both JSON and human-readable format."""
        action_np = action.detach().cpu().numpy()
        
        # JSON 格式 (用于后续分析)
        log_entry = {
            "step": self.step_count,
            "action": action_np.tolist(),
            "action_stats": {
                "min": float(action_np.min()),
                "max": float(action_np.max()),
                "mean": float(action_np.mean()),
                "std": float(action_np.std()),
            }
        }
        self.action_log_file.write(json.dumps(log_entry) + '\n')
        self.action_log_file.flush()
        
        # 可读格式
        self.action_txt_file.write(f"\n{'='*80}\n")
        self.action_txt_file.write(f"Step {self.step_count}\n")
        self.action_txt_file.write(f"{'-'*80}\n")
        
        # 假设 action 的结构 (R1Pro 机器人)
        # 通常格式: [base_x, base_y, base_yaw, left_arm_joints..., right_arm_joints..., ...]
        if len(action_np) >= 3:
            self.action_txt_file.write(f"Base command:\n")
            self.action_txt_file.write(f"  Linear X:  {action_np[0]:8.4f}\n")
            self.action_txt_file.write(f"  Linear Y:  {action_np[1]:8.4f}\n")
            self.action_txt_file.write(f"  Angular Z: {action_np[2]:8.4f}\n")
            
            if len(action_np) > 3:
                self.action_txt_file.write(f"Arm commands: {action_np[3:]}\n")
        
        self.action_txt_file.write(f"\nFull action vector ({len(action_np)} dims):\n")
        self.action_txt_file.write(f"{action_np}\n")
        self.action_txt_file.write(f"\nStats: min={action_np.min():.4f}, max={action_np.max():.4f}, "
                                  f"mean={action_np.mean():.4f}, std={action_np.std():.4f}\n")
        self.action_txt_file.flush()
    
    def reset(self, *args, **kwargs):
        """Reset the environment and step counter."""
        self.step_count = 0
        if hasattr(self, 'action_txt_file'):
            self.action_txt_file.write(f"\n{'#'*80}\n")
            self.action_txt_file.write(f"# ENVIRONMENT RESET\n")
            self.action_txt_file.write(f"{'#'*80}\n\n")
            self.action_txt_file.flush()
        return super().reset(*args, **kwargs)
    
    def __del__(self):
        """Clean up log files."""
        if hasattr(self, 'action_log_file'):
            self.action_log_file.close()
        if hasattr(self, 'action_txt_file'):
            self.action_txt_file.close()
```

#### Step 2: 修改评估脚本使用自定义 Wrapper

```bash
# 文件: test/turning_on_radio_with_action_logging.sh

#!/bin/bash
export GROOT_DIR=~/LINJ0121/Isaac-GR00T
export PATH_TO_BEHAVIOR_1K=~/project/BEHAVIOR-1K
export TASK_NAME=turning_on_radio
export PATH_TO_CKPT=~/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000
export PORT=8000
export LOG_PATH=./eval_logs/${TASK_NAME}_action_debug

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
echo "Policy server PID: $SERVE_PID"
sleep 60

# 运行评估，使用自定义 wrapper
cd "$PATH_TO_BEHAVIOR_1K"
OMNIGIBSON_HEADLESS=1 \
CUDA_VISIBLE_DEVICES=0 \
python -m omnigibson.eval.eval \
    --task-name "$TASK_NAME" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --output-dir "$LOG_PATH" \
    --write-video \
    --env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper \
    --max-steps 100 2>&1 | tee "$LOG_PATH/omnigibson_eval.log"

kill "$SERVE_PID"

echo ""
echo "✅ Done! Check action logs at:"
echo "   $LOG_PATH/actions_readable.txt"
echo "   $LOG_PATH/actions.jsonl"
```

---

## 🎯 方案 B: Monkey Patch（快速但不优雅）

如果你不想创建新文件，可以在运行前动态修改类：

```python
# 文件: debug_action_patch.py

import sys
import json
import torch as th
from omnigibson.eval.evaluator import Evaluator

# 保存原始的 step 方法
_original_step = Evaluator.step

# 全局变量存储日志文件
_action_log_file = None
_step_count = 0

def patched_step(self):
    """Patched step method that logs actions."""
    global _step_count
    
    # 获取 action
    self.robot_action = self.policy.forward(obs=self.obs)
    
    # 记录 action
    if _action_log_file is not None:
        action_np = self.robot_action.detach().cpu().numpy()
        log_entry = {
            "step": _step_count,
            "action": action_np.tolist(),
            "base_movement": {
                "x": float(action_np[0]) if len(action_np) > 0 else 0,
                "y": float(action_np[1]) if len(action_np) > 1 else 0,
                "theta": float(action_np[2]) if len(action_np) > 2 else 0,
            }
        }
        _action_log_file.write(json.dumps(log_entry) + '\n')
        _action_log_file.flush()
        
        # 打印到控制台
        if _step_count % 10 == 0:
            print(f"[Step {_step_count}] Base: x={action_np[0]:.3f}, y={action_np[1]:.3f}, θ={action_np[2]:.3f}")
    
    _step_count += 1
    
    # 执行原始 step 的其余部分
    obs, _, terminated, truncated, info = self.env.step(self.robot_action, n_render_iterations=1)
    obs = self._sync_lights_and_get_obs(obs)
    self.obs = self._preprocess_obs(obs)

    if self._video_path is not None:
        self._write_video()

    if terminated or truncated:
        self.n_trials += 1
        if info["done"]["success"]:
            self.n_success_trials += 1

    for metric in self.metrics:
        metric.step(self.env, self.robot_action, obs, 0.0, terminated, truncated, info)
    
    return terminated, truncated

# 应用 patch
Evaluator.step = patched_step

# 设置日志文件
import os
log_dir = os.path.expanduser("~/project/BEHAVIOR-1K/eval_logs/action_debug")
os.makedirs(log_dir, exist_ok=True)
_action_log_file = open(os.path.join(log_dir, "actions.jsonl"), 'w')

print(f"✅ Action logging patch applied! Logs will be saved to {log_dir}/actions.jsonl")
```

**使用方法**:
```bash
# 在评估前导入 patch
cd $PATH_TO_BEHAVIOR_1K
python -c "import debug_action_patch" && \
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --host 127.0.0.1 \
    --port 8000 \
    --output-dir ./eval_logs/turning_on_radio_debug \
    --write-video
```

---

## 🎯 方案 C: 继承 Evaluator（最灵活）

创建自己的 Evaluator 子类：

```python
# 文件: custom_eval_with_logging.py

import json
import os
import sys
import torch as th
from pathlib import Path

# 添加 BEHAVIOR-1K 到 path
sys.path.insert(0, str(Path(__file__).parent / "OmniGibson"))

from omnigibson.eval.evaluator import Evaluator


class LoggingEvaluator(Evaluator):
    """Evaluator with action logging."""
    
    def __init__(self, cfg):
        super().__init__(cfg)
        
        # 设置日志
        log_dir = os.path.expanduser("~/project/BEHAVIOR-1K/eval_logs/action_debug")
        os.makedirs(log_dir, exist_ok=True)
        self.action_log_path = os.path.join(log_dir, "actions.jsonl")
        self.action_txt_path = os.path.join(log_dir, "actions_readable.txt")
        self.action_log_file = open(self.action_log_path, 'w')
        self.action_txt_file = open(self.action_txt_path, 'w')
        self.step_count = 0
        
        print(f"✅ Action logging enabled!")
        print(f"   JSONL: {self.action_log_path}")
        print(f"   TXT: {self.action_txt_path}")
    
    def step(self):
        """Override step to add logging."""
        # 获取 action
        self.robot_action = self.policy.forward(obs=self.obs)
        
        # 记录 action
        self._log_action(self.robot_action)
        
        # 执行原始 step
        obs, _, terminated, truncated, info = self.env.step(self.robot_action, n_render_iterations=1)
        obs = self._sync_lights_and_get_obs(obs)
        self.obs = self._preprocess_obs(obs)

        if self._video_path is not None:
            self._write_video()

        if terminated or truncated:
            self.n_trials += 1
            if info["done"]["success"]:
                self.n_success_trials += 1

        for metric in self.metrics:
            metric.step(self.env, self.robot_action, obs, 0.0, terminated, truncated, info)
        
        self.step_count += 1
        return terminated, truncated
    
    def _log_action(self, action: th.Tensor):
        """Log action."""
        action_np = action.detach().cpu().numpy()
        
        # JSON log
        log_entry = {
            "step": self.step_count,
            "action": action_np.tolist(),
        }
        self.action_log_file.write(json.dumps(log_entry) + '\n')
        self.action_log_file.flush()
        
        # Readable log
        if self.step_count % 10 == 0 or self.step_count < 10:
            self.action_txt_file.write(f"\n[Step {self.step_count}]\n")
            if len(action_np) >= 3:
                self.action_txt_file.write(f"  Base: x={action_np[0]:7.4f}, y={action_np[1]:7.4f}, θ={action_np[2]:7.4f}\n")
            self.action_txt_file.flush()
    
    def __del__(self):
        if hasattr(self, 'action_log_file'):
            self.action_log_file.close()
        if hasattr(self, 'action_txt_file'):
            self.action_txt_file.close()


if __name__ == "__main__":
    # 复用 eval.py 的参数解析
    from omnigibson.eval.eval import parse_args, logger
    from omnigibson.eval.utils.eval_utils import seed_everything, DEFAULT_EVAL_SEED
    from omnigibson.eval.evaluator import resolve_instance_ids
    from omegaconf import OmegaConf
    from pathlib import Path
    
    args = parse_args()
    
    # ... (复制 eval.py 的 main 逻辑，但使用 LoggingEvaluator)
    
    with LoggingEvaluator(cfg) as evaluator:
        # ... 评估循环
        pass
```

---

## 📊 推荐方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|-----|------|------|--------|
| **A: Wrapper** | ✅ 最优雅<br>✅ 符合架构设计<br>✅ 可复用 | ⚠️ 需要创建新文件 | ⭐⭐⭐⭐⭐ |
| **B: Monkey Patch** | ✅ 快速<br>✅ 不需要新文件 | ❌ 不优雅<br>❌ 难以维护 | ⭐⭐⭐ |
| **C: 继承 Evaluator** | ✅ 灵活<br>✅ 可添加更多功能 | ⚠️ 需要复制 main 逻辑 | ⭐⭐⭐⭐ |

---

## 🚀 快速开始（推荐方案 A）

### 1. 创建 Wrapper

```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K

# 创建目录
mkdir -p OmniGibson/omnigibson/eval/wrappers

# 创建 __init__.py（如果不存在）
touch OmniGibson/omnigibson/eval/wrappers/__init__.py
```

将上面"方案 A"的代码保存为:
```
OmniGibson/omnigibson/eval/wrappers/action_logger.py
```

### 2. 修改 wrappers/__init__.py

```python
# 文件: OmniGibson/omnigibson/eval/wrappers/__init__.py
from omnigibson.eval.wrappers.action_logger import ActionLoggingWrapper

__all__ = ["ActionLoggingWrapper"]
```

### 3. 运行评估

```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K

# 使用自定义 wrapper
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --host 127.0.0.1 \
    --port 8000 \
    --output-dir ./eval_logs/turning_on_radio_action_debug \
    --write-video \
    --env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper \
    --max-steps 50
```

### 4. 查看结果

```bash
# 查看可读的日志
cat eval_logs/turning_on_radio_action_debug/actions_readable.txt

# 或者只看前几步
head -100 eval_logs/turning_on_radio_action_debug/actions_readable.txt

# 分析 JSON 数据
python -c "
import json
with open('eval_logs/turning_on_radio_action_debug/actions.jsonl') as f:
    actions = [json.loads(line) for line in f]
    
print(f'Total steps: {len(actions)}')
print(f'First action: {actions[0]}')

# 统计 base 移动
base_movements = [a['action'][:3] for a in actions if len(a['action']) >= 3]
print(f'\\nBase movements (first 10 steps):')
for i, move in enumerate(base_movements[:10]):
    print(f'  Step {i}: x={move[0]:.4f}, y={move[1]:.4f}, θ={move[2]:.4f}')
"
```

---

## 🔍 如何分析 Action 日志

### 检查点 1: Base 是否移动？

```bash
grep "Base command" eval_logs/turning_on_radio_action_debug/actions_readable.txt | head -20
```

**期望**: 如果机器人要导航，`Linear X` 或 `Linear Y` 应该有非零值

**实际（你的情况）**: 可能全是接近 0 的值

### 检查点 2: Action 的量级

```bash
grep "Stats:" eval_logs/turning_on_radio_action_debug/actions_readable.txt | head -10
```

**异常情况**:
- 全是 0 或接近 0 → Policy 没有输出有效指令
- 全是 NaN → Policy 有问题
- 值太大（>1.0）→ Action scaling 可能有问题

### 检查点 3: 对比人类 Demo

如果你有训练数据，可以对比：
```python
# 加载 demo 数据的 action
import h5py
# 对比 policy 输出和 demo 中的 action 分布
```

---

## 💡 下一步诊断

根据 action 日志，你会看到以下情况之一：

### 情况 1: Action 全是 0 或极小值
**原因**: Policy 没有正确加载或推理失败
**下一步**: 
- 检查 policy server 日志
- 验证 checkpoint 加载
- 检查观察空间是否匹配

### 情况 2: Action 有值但不合理（如一直后退）
**原因**: Policy 训练不足或训练数据问题
**下一步**:
- 对比训练数据的 action 分布
- 检查 action normalization
- 考虑继续训练

### 情况 3: Base action 是 0，只有 arm action
**原因**: Policy 学到了"原地操作"而不是"导航+操作"
**下一步**:
- 检查训练数据是否包含导航阶段
- 查看 demo 中机器人是否真的移动了

---

## 🎓 总结

**不修改源码的核心思路**:
1. ✅ **使用 Wrapper** - OmniGibson 设计了 `env_wrapper` 接口，正是为了这种需求
2. ✅ **继承而不是修改** - 创建子类而不是改原始代码
3. ✅ **利用现有接口** - `--env-wrapper` 参数就是官方提供的扩展点

**为什么推荐 Wrapper 方案**:
- 符合 OmniGibson 的架构设计
- 不会影响原始代码
- 易于维护和复用
- 可以随时启用/禁用

开始调试吧！🚀
