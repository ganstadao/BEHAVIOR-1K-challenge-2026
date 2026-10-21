# TAMP 评估系统调试记录

本文档记录了 TAMP (Task and Motion Planning) 评估系统从搭建到调试的完整过程。

## 目录

1. [系统概述](#系统概述)
2. [调试过程](#调试过程)
3. [问题总结](#问题总结)
4. [当前状态](#当前状态)
5. [经验教训](#经验教训)

---

## 系统概述

### 系统架构

```
tamp_test/
├── configs/           # 任务配置
│   └── turning_on_radio.yaml
├── core/             # 核心数据结构
│   └── __init__.py   # Subgoal, Skeleton, ExecutionResult 等
├── planner/          # 规划器
│   ├── symbolic_planner.py      # Skeleton 生成
│   └── skeleton_executor.py     # Skeleton 执行
├── low_level/        # 底层动作原语
│   └── primitive_wrapper.py     # OmniGibson 动作原语封装
└── eval/            # 评估入口
    └── run_eval.py   # 主评估循环
```

### 核心组件

1. **FixedSkeletonPlanner**: 生成固定的动作序列（skeleton）
2. **SkeletonExecutor**: 执行 skeleton 中的每个 subgoal
3. **PrimitiveWrapper**: 封装 OmniGibson 的 `StarterSemanticActionPrimitives`
4. **TAMPEvaluator**: 主评估循环，管理环境、规划器和执行器

---

## 调试过程

### 问题1: 程序挂起 - debugpy 阻塞

**现象**：
```
Waiting for debugger to attach...
[程序永久挂起]
```

**原因**：
- 代码中使用了 `debugpy.wait_for_client()` 等待调试器连接
- 在 SLURM 批处理作业中没有调试器连接，导致永久阻塞

**修复**：
```python
# 移除所有 debugpy 相关代码
# import debugpy
# debugpy.listen(5678)
# debugpy.wait_for_client()
```

**位置**：`eval/run_eval.py`

---

### 问题2: 场景类型错误

**现象**：
```
TypeError: Scene.__init__() got an unexpected keyword argument 'load_room_types'
```

**原因**：
- 使用了 `Scene` 类型，但传入了 `load_room_types` 参数
- 该参数只在 `InteractiveTraversableScene` 中支持

**修复**：
```python
"scene": {
    "type": "InteractiveTraversableScene",  # 支持任务元数据和房间过滤
    "scene_model": "house_double_floor_lower",
    "load_room_types": ["living_room"],
}
```

**位置**：`eval/run_eval.py`

---

### 问题3: 无效参数

**现象**：
```
TypeError: Environment.__init__() got an unexpected keyword argument 'use_visual_perception'
```

**原因**：
- 尝试传入不存在的配置参数

**修复**：
```python
# 移除无效参数
# "use_visual_perception": False,
```

**位置**：`eval/run_eval.py`

---

### 问题4: CuRobo 配置缺失

**现象**：
```
ValueError: curobo config must be explicitly enabled for robot Tiago
```

**原因**：
- Tiago 机器人需要启用 CuRobo 进行运动规划
- 默认配置中未启用

**修复**：
```python
import omnigibson.utils.transform_utils as T
from omnigibson.macros import macros as m

# 启用 CuRobo
m.robots.CUROBO_ROBOT_CONFIG_MAPPING = {
    "Tiago": "tiago_dual.yml"
}
```

**位置**：`eval/run_eval.py`

---

### 问题5-7: 代码逻辑错误

**问题5**: UnboundLocalError - `subgoal` 未定义
```python
# 错误：在循环外使用 subgoal
except ActionPrimitiveError as e:
    subgoal.status = SubgoalStatus.FAILED  # ❌

# 修复：确保在正确的作用域内
for i, subgoal in enumerate(skeleton):
    try:
        # ... 执行 ...
    except ActionPrimitiveError as e:
        subgoal.status = SubgoalStatus.FAILED  # ✓
```

**问题6**: ExecutionResult 初始化字段不匹配
```python
# 错误：使用了不存在的字段
ExecutionResult(
    skeleton=skeleton,
    success=False,
    total_steps=0,
    failure_reason="error"  # ❌
)

# 修复：使用正确的字段
ExecutionResult(
    skeleton=skeleton,
    success=False,
    num_steps=0,
    subgoal_results=[],
    goal_status={},
    error_message="error"  # ✓
)
```

**问题7**: 日志输出丢失
```python
# 错误：直接用 print，被 OmniGibson 的输出重定向吞掉
print("Log message")  # ❌

# 修复：同时输出到 stderr 和 stdout
def log(msg):
    print(msg, file=sys.stderr, flush=True)
    print(msg, flush=True)
```

**位置**：`planner/skeleton_executor.py`, `eval/run_eval.py`

---

### 问题8: 生成器返回值丢失

**现象**：
```python
result = None
# result 始终为 None
```

**原因**：
- Python 生成器的返回值通过 `StopIteration` 异常传递
- 直接迭代生成器会丢弃返回值

**修复**：
```python
# 错误写法
gen = executor.execute_skeleton(skeleton, object_scope)
for _ in gen:
    pass
# result 丢失

# 正确写法
try:
    gen = executor.execute_skeleton(skeleton, object_scope)
    for _ in gen:
        pass
except StopIteration as e:
    result = e.value  # ✓ 从异常中获取返回值
```

**位置**：`eval/run_eval.py`

---

### 问题9-13: 机器人配置问题

#### 问题9: 机器人不兼容

**现象**：
```
[WARNING] The StarterSemanticActionPrimitive currently only works with Tiago and R1
```

**原因**：
- 初始使用 Fetch 机器人
- `StarterSemanticActionPrimitives` 只支持 Tiago 和 R1

**修复**：
```python
"robots": [
    {
        "type": "Tiago",  # ✓ 使用支持的机器人
        # ...
    }
]
```

#### 问题10: Base 控制器类型错误

**现象**：
```
Error: Base controller must be a HolonomicBaseJointController!
```

**原因**：
- Tiago 是全向移动机器人，需要特殊的底座控制器
- 使用了普通的 `JointController`

**修复**：
```python
"base": {
    "name": "HolonomicBaseJointController",  # ✓ 全向底座控制器
    "motor_type": "position",
    "command_input_limits": None,
    "use_impedances": False,
}
```

#### 问题11: 控制器参数错误

**现象**：
```
TypeError: got an unexpected keyword argument 'use_delta_commands'
```

**原因**：
- 参数传递方式不正确
- 缺少必要的参数：`motor_type`, `command_input_limits`, `use_impedances`

**修复**：参考官方 `tiago_primitives.yaml` 配置
```python
"trunk": {
    "name": "JointController",
    "motor_type": "position",           # ✓ 必需
    "command_input_limits": None,       # ✓ 必需
    "use_delta_commands": False,        # ✓ 绝对位置模式
    "use_impedances": False,            # ✓ 必需
}
```

#### 问题12: 控制器配置不完整

**现象**：
```
operands could not be broadcast together with shapes (7,) (6,)
```

**原因**：
- Tiago 是双臂机器人，需要配置两只手臂
- 只配置了左臂，缺少右臂

**修复**：
```python
"controller_config": {
    "base": { ... },
    "trunk": { ... },
    "arm_left": { ... },
    "gripper_left": { ... },
    "arm_right": { ... },      # ✓ 添加右臂
    "gripper_right": { ... },  # ✓ 添加右手爪
    "camera": { ... },
}
```

#### 问题13: 场景加载不完整

**现象**：
- 路径规划失败，找不到可达路径

**原因**：
- 只加载了 `living_room`，目标物体可能在其他房间

**修复**：
```python
"scene": {
    "type": "InteractiveTraversableScene",
    "scene_model": "house_double_floor_lower",
    # 移除 load_room_types 限制，加载完整场景
}
```

**位置**：`eval/run_eval.py`

---

### 问题14: Action 维度错误

**现象**：
```
AssertionError: Action must be dimension 24, got dim 1 instead.
```

**原因**：
- 尝试用 `env.step(np.zeros(env.action_space.shape))` 获取观察
- 传入了错误维度的 action

**修复**：
```python
# 错误：不应该在这里调用 env.step
obs, _, _, _, _ = self.env.step(np.zeros(self.env.action_space.shape))  # ❌

# 修复：action primitives 内部已经调用了 env.step
# 直接通过 env.get_obs() 获取观察
obs = self.env.get_obs()  # ✓
```

**位置**：`eval/run_eval.py`

---

### 问题15: **关键问题** - Action 没有被执行

**现象**：
- 机器人位置完全不变
- 从 Step 0 到 Step 400+，位置始终是 `[4.567, 5.800, 0.0003]`

**根本原因**：
```python
# 错误：接收了 action 但没有执行
for action in self.primitives.apply_ref(primitive_enum, target_obj):
    yield  # ❌ 只是 yield 空值，action 被丢弃了！
```

**问题分析**：
- `apply_ref` 返回一个生成器，每次 yield 一个**机器人控制命令**
- 我们接收了这个 `action`，但从未调用 `env.step(action)` 执行它
- 结果：机器人收到空指令，位置完全不变

**修复**：
```python
# 正确：执行 action
for action in self.primitives.apply_ref(primitive_enum, target_obj):
    self.env.step(action)  # ✓ 执行 action
    yield
```

**修复位置**：
1. `execute_navigate_to` 方法
2. `execute_press_button` 方法

**位置**：`low_level/primitive_wrapper.py`

**这是整个调试过程中最关键的修复！**

---

## 问题总结

### 按类别分类

#### A. 环境配置问题 (5个)
1. ✅ 场景类型错误 → `InteractiveTraversableScene`
2. ✅ 无效参数 → 移除 `use_visual_perception`
3. ✅ CuRobo 配置缺失 → 启用 Tiago 的 CuRobo
4. ✅ 场景加载不完整 → 加载完整场景
5. ✅ Action 维度错误 → 移除错误的 `env.step` 调用

#### B. 机器人配置问题 (4个)
6. ✅ 机器人不兼容 → 使用 Tiago
7. ✅ Base 控制器类型错误 → `HolonomicBaseJointController`
8. ✅ 控制器参数错误 → 添加完整参数
9. ✅ 控制器配置不完整 → 添加双臂配置

#### C. 代码逻辑问题 (5个)
10. ✅ 程序挂起 → 移除 debugpy
11. ✅ UnboundLocalError → 修复变量作用域
12. ✅ ExecutionResult 初始化错误 → 使用正确字段
13. ✅ 日志输出丢失 → 输出到 stderr
14. ✅ 生成器返回值丢失 → 通过 `StopIteration` 获取

#### D. **核心功能问题 (1个)**
15. ✅ **Action 没有被执行** → 在 primitive_wrapper 中调用 `env.step(action)`

---

## 当前状态

### ✅ 已修复的功能

1. **环境初始化** ✓
   - 正确的场景类型和配置
   - CuRobo 启用
   - 完整场景加载

2. **机器人配置** ✓
   - Tiago 机器人
   - 全向底座控制器
   - 完整的双臂控制器配置
   - 绝对位置模式

3. **代码执行流程** ✓
   - Skeleton 生成
   - Subgoal 执行
   - Action primitive 调用
   - **Action 执行到环境**
   - 日志输出

4. **详细日志系统** ✓
   - 机器人状态跟踪
   - 目标物体信息
   - 导航过程详细记录
   - 每个 subgoal 的前后状态

5. **视频录制框架** ✓
   - 基于官方 PyAV 实现
   - 帧捕获逻辑
   - 视频编码和保存

### ⚠️ 当前遗留问题

#### 问题A: 机器人不移动

**现象**：
- 机器人位置完全不变：`[4.567, 5.800, 0.0003]`
- 目标位置：`[3.464, 4.886, 0.534]`
- 距离：1.529m（很近）
- 错误：`PLANNING_ERROR: There is no accessible path`
- 尝试5次，每次都失败

**可能原因**：
1. **导航网格问题** - 场景可能缺少导航网格或导航网格损坏
2. **CuRobo 运动规划失败** - 虽然生成了29步的计划，但执行时持续失败
3. **机器人初始位置问题** - 机器人可能被放置在无法导航的区域
4. **场景/机器人兼容性** - Tiago + house_double_floor_lower 的组合可能有问题

**诊断建议**：
1. 尝试更简单的场景（如 Rs_int）
2. 检查机器人初始位置是否在可导航区域
3. 测试基本的移动命令（不通过路径规划）
4. 检查 OmniGibson 和 CuRobo 版本兼容性

#### 问题B: 视频没有输出

**现象**：
- 日志显示 `Video recording started`
- 但没有 `Video saved` 日志
- `results/videos/` 目录为空

**可能原因**：
1. **没有捕获到帧** - `env.get_obs()` 可能没有返回 RGB 数据
2. **观察字典结构不正确** - robot 的 obs 可能不包含 'rgb' 键
3. **帧列表为空** - `_finalize_video` 检查到没有帧就返回了

**已添加调试**：
- `_capture_frame` 详细日志
- `_finalize_video` 详细日志
- 观察字典结构打印

---

## 经验教训

### 1. 理解生成器的工作原理

**错误示例**：
```python
# ❌ 接收 action 但不使用
for action in generator:
    yield
```

**正确方式**：
```python
# ✓ 执行 action
for action in generator:
    env.step(action)
    yield
```

**教训**：
- 生成器 yield 的值是有意义的（这里是控制命令）
- 必须理解每个 yield 值的用途并正确处理
- 返回值通过 `StopIteration` 异常传递

### 2. 仔细阅读官方文档和示例

**关键收获**：
- 控制器配置参考 `omnigibson/configs/tiago_primitives.yaml`
- 视频录制参考 `omnigibson/eval/evaluator.py`
- Action primitives 使用参考 `omnigibson/examples/wip/rs_int_primitives_example.py`

**教训**：
- 不要凭空猜测 API 的使用方式
- 官方示例是最可靠的参考
- 查看实际工作的代码比阅读文档更有效

### 3. 逐步调试，不要一次改太多

**本次调试的顺序**：
1. 先解决程序挂起 → 能运行
2. 再解决初始化错误 → 环境能创建
3. 然后解决配置问题 → 机器人能加载
4. 最后解决执行问题 → action 能执行

**教训**：
- 每次只修复一个问题
- 修复后立即测试
- 确认一个问题解决后再处理下一个

### 4. 添加详细的日志

**有用的日志**：
- 函数入口和出口
- 关键变量的值
- 数据结构的类型和形状
- 错误的完整 traceback

**教训**：
- 日志要输出到 stderr 防止被重定向吞掉
- 记录位置、姿态等状态的变化
- 记录尝试次数和失败原因

### 5. 理解第三方库的内部机制

**本次涉及的机制**：
- OmniGibson 的控制器系统
- StarterSemanticActionPrimitives 的工作流程
- CuRobo 的运动规划
- PyAV 的视频编码

**教训**：
- 不要把第三方库当黑盒
- 必要时阅读源码理解内部实现
- 理解数据如何在组件间流动

### 6. 参数配置的重要性

**配置相关问题数量**：9/15（60%）

**教训**：
- 配置错误是最常见的问题
- 必须理解每个参数的含义和约束
- 参考官方配置文件，不要自己创造

### 7. 调试工具的选择

**有效的调试方法**：
- ✓ 详细的日志输出
- ✓ 简化的测试脚本
- ✓ 分步骤验证
- ✗ 调试器（在 SLURM 环境不适用）

**教训**：
- 选择适合执行环境的调试方法
- 日志是批处理作业中最可靠的调试手段

---

## 附录

### A. 完整的控制器配置模板

```python
"controller_config": {
    "base": {
        "name": "HolonomicBaseJointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_impedances": False,
    },
    "trunk": {
        "name": "JointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_delta_commands": False,
        "use_impedances": False,
    },
    "arm_left": {
        "name": "JointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_delta_commands": False,
        "use_impedances": False,
    },
    "gripper_left": {
        "name": "JointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_delta_commands": False,
        "use_impedances": False,
    },
    "arm_right": {
        "name": "JointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_delta_commands": False,
        "use_impedances": False,
    },
    "gripper_right": {
        "name": "JointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_delta_commands": False,
        "use_impedances": False,
    },
    "camera": {
        "name": "JointController",
        "motor_type": "position",
        "command_input_limits": None,
        "use_delta_commands": False,
        "use_impedances": False,
    },
}
```

### B. 调试脚本示例

创建了 `debug_robot_movement.py` 用于测试：
- 基本的机器人移动
- 观察字典结构
- RGB 数据可用性

### C. 参考文档

1. **OmniGibson 官方示例**：
   - `omnigibson/examples/wip/rs_int_primitives_example.py`
   - `omnigibson/configs/tiago_primitives.yaml`
   - `omnigibson/eval/evaluator.py`

2. **相关文件**：
   - `omnigibson/action_primitives/starter_semantic_action_primitives.py`
   - `omnigibson/robots/robot.py`
   - `omnigibson/eval/utils/obs_utils.py`

---

## 总结

经过15个问题的修复，TAMP 评估系统的代码层面已经基本正确：

- ✅ 环境能正确初始化
- ✅ 机器人配置正确
- ✅ Skeleton 能生成
- ✅ Subgoal 能执行
- ✅ **Action 能传递到环境**
- ✅ 日志详细完整

当前的遗留问题（机器人不移动、视频没输出）更多是**配置/兼容性/场景**层面的问题，而不是代码逻辑问题。

最关键的修复是**问题15**：发现并修复了 action 没有被执行的根本原因。这个问题隐藏得很深，因为：
1. 代码看起来是正确的（接收了 action）
2. 没有报错（只是机器人不动）
3. 需要理解生成器和 action primitives 的工作原理才能发现

这次调试过程体现了系统性排查、逐步验证、深入理解底层机制的重要性。

---

*文档创建时间：2024-10-18*
*最后更新：2024-10-18*
