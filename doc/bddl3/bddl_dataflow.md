# BDDL 数据流详解：从符号语言到物理仿真

> **深入源码级别的 BDDL 处理流程分析**  
> 本文档详细解析 BEHAVIOR-1K 中 BDDL (Behavior Domain Definition Language) 的完整数据流，从 BDDL 文件的符号定义到物理仿真中的状态评估。

---

## 📋 目录

1. [整体架构概览](#整体架构概览)
2. [阶段一：BDDL 文件加载与解析](#阶段一bddl-文件加载与解析)
3. [阶段二：对象范围创建与编译](#阶段二对象范围创建与编译)
4. [阶段三：任务实例加载](#阶段三任务实例加载)
5. [阶段四：运行时评估](#阶段四运行时评估)
6. [核心数据结构](#核心数据结构)
7. [完整代码示例](#完整代码示例)
8. [常见问题](#常见问题)

---

## 整体架构概览

BDDL 数据流是一个**多层转换过程**，将高层符号语言逐步转换为可执行的物理状态检查：

```
┌─────────────────────────────────────────────────────────────────┐
│                     BDDL 数据流全景图                              │
└─────────────────────────────────────────────────────────────────┘

[1] BDDL 文件 (符号层)
    📄 bddl3/bddl/activity_definitions/turning_on_radio/problem0.bddl
    ↓ parse_problem()
    
[2] 解析后的条件 (结构化数据)
    📦 Conditions.parsed_objects
    📦 Conditions.parsed_initial_conditions  
    📦 Conditions.parsed_goal_conditions
    ↓ BehaviorTask._load() → update_activity()
    
[3] 对象范围骨架 (符号 → None)
    🗺️ object_scope = {"radio_receiver.n.01_1": None, ...}
    ↓ initialize_activity() → assign_object_scope_with_cache()
    
[4] 对象范围填充 (符号 → 物理对象)
    🗺️ object_scope = {"radio_receiver.n.01_1": <DatasetObject>, ...}
    ↓ _compile_with_rooms()
    
[5] 编译后的任务 (可执行表达式树)
    🌲 compiled_task.initial_conditions = [HEAD(...), HEAD(...)]
    🌲 compiled_task.goal_conditions = [HEAD(...)]
    ↓ Evaluator.load_task_instance()
    
[6] 恢复物理状态 (TRO state)
    📂 从 TRO state 文件加载对象位置/姿态/状态
    ↓ env.step() → task._step_termination()
    
[7] 运行时评估 (物理 → 布尔值)
    ✓ compiled_task.check_goal(_evaluate_predicate)
    ↓ _evaluate_predicate
    
[8] 谓词评估 (对象状态查询)
    🔍 object_scope[inst].states[StateClass].get_value()
    ↓
    
[9] 任务结果
    ✅ success: True/False
    📊 satisfied_predicates / unsatisfied_predicates
```

---

## 阶段一：BDDL 文件加载与解析

### 1.1 BDDL 文件结构

**文件路径**：`bddl3/bddl/activity_definitions/<activity_name>/problem<id>.bddl`

**示例**（`turning_on_radio/problem0.bddl`）：

```lisp
(define (problem turning_on_radio-0)
    (:domain behavior-1k)
    
    (:objects
        radio_receiver.n.01_1 - radio_receiver.n.01
        table.n.02_1 - table.n.02
        floor.n.01_1 - floor.n.01
        agent.n.01_1 - agent.n.01
    )
    
    (:init
        (not (toggled_on radio_receiver.n.01_1))
        (ontop radio_receiver.n.01_1 table.n.02_1)
        (inroom table.n.02_1 living_room)
        (inroom floor.n.01_1 living_room)
        (ontop agent.n.01_1 floor.n.01_1)
    )
    
    (:goal
        (and 
            (toggled_on ?radio_receiver.n.01_1)
        )
    )
)
```

**关键概念**：
- **Synset (类型)**：`radio_receiver.n.01` - 来自 WordNet 的语义概念
- **Instance (实例)**：`radio_receiver.n.01_1` - 具体的对象实例（后缀 `_1` 是实例编号）
- **Predicate (谓词)**：`toggled_on`, `ontop` - 描述对象状态或关系

### 1.2 解析流程

**源码位置**：`bddl3/bddl/activity.py` + `bddl3/bddl/parsing.py`

```python
# ==================== bddl3/bddl/activity.py ====================
class Conditions(object):
    def __init__(
        self,
        behavior_activity,           # "turning_on_radio"
        activity_definition,         # 0
        simulator_name,              # "behavior-1k"
        predefined_problem=None,
    ):
        self.behavior_activity = behavior_activity
        self.activity_definition = activity_definition
        
        # 1. 解析 domain 文件（获取谓词定义）
        domain_name, *__ = parse_domain(simulator_name)
        # domain_name = "behavior-1k"
        
        # 2. 解析 problem 文件（获取对象、初始条件、目标条件）
        (
            __,
            self.parsed_objects,           # dict[synset, list[instances]]
            self.parsed_initial_conditions,# list of nested lists
            self.parsed_goal_conditions,   # nested list
        ) = parse_problem(
            self.behavior_activity,
            self.activity_definition,
            domain_name,
            predefined_problem=predefined_problem,
        )
```

**解析结果示例**：

```python
# parsed_objects: synset → instance list
{
    "radio_receiver.n.01": ["radio_receiver.n.01_1"],
    "table.n.02": ["table.n.02_1"],
    "floor.n.01": ["floor.n.01_1"],
    "agent.n.01": ["agent.n.01_1"],
}

# parsed_initial_conditions: 初始条件的嵌套列表表示
[
    ["not", ["toggled_on", "radio_receiver.n.01_1"]],
    ["ontop", "radio_receiver.n.01_1", "table.n.02_1"],
    ["inroom", "table.n.02_1", "living_room"],
    ["inroom", "floor.n.01_1", "living_room"],
    ["ontop", "agent.n.01_1", "floor.n.01_1"],
]

# parsed_goal_conditions: 目标条件的嵌套列表表示
[
    ["and",
        ["toggled_on", "?radio_receiver.n.01_1"]
    ]
]
```

### 1.3 BehaviorTask 加载 BDDL

**源码位置**：`OmniGibson/omnigibson/tasks/behavior_task.py:194-221`

```python
# ==================== BehaviorTask.update_activity() ====================
def update_activity(self, env, activity_name, activity_definition_id):
    """从 BDDL 文件加载任务定义"""
    
    self.activity_name = activity_name
    self.activity_definition_id = activity_definition_id
    
    # 1. 从知识库获取任务定义（这会触发 BDDL 解析）
    from omnigibson.utils.bddl_utils import get_knowledge_base
    
    self._task_def = get_knowledge_base().get_task(
        f"{activity_name}-{activity_definition_id}"
    )
    # 返回的 _task_def 是一个 Task 对象，内部包含 Conditions 实例
    # 实际路径：bddl3/bddl/activity_definitions/turning_on_radio/problem0.bddl
    
    # 2. 解析基础范围（移除通配符、提取房间分配）
    (
        self._base_conditions,        # Conditions 对象
        base_scope,                   # list of instance names
        self._base_inroom_assignments # dict: instance → room_type
    ) = self._task_def.parse_base_scope()
    
    # 示例：
    # base_scope = [
    #     "radio_receiver.n.01_1",
    #     "table.n.02_1", 
    #     "floor.n.01_1"
    # ]
    # _base_inroom_assignments = {
    #     "table.n.02_1": "living_room",
    #     "floor.n.01_1": "living_room"
    # }
    
    self.compiled_task = None  # 稍后编译
    
    # 3. 初始化 object_scope（所有值先设为 None）
    self.object_scope = {"agent.n.01_1": None}
    self.object_scope.update({name: None for name in base_scope})
    # object_scope = {
    #     "agent.n.01_1": None,
    #     "radio_receiver.n.01_1": None,
    #     "table.n.02_1": None,
    #     "floor.n.01_1": None,
    # }
    
    # 4. 构建实例到类别的映射
    self.object_instance_to_category = {
        obj_inst: obj_cat
        for obj_cat in self._base_conditions.parsed_objects
        for obj_inst in self._base_conditions.parsed_objects[obj_cat]
    }
    # {
    #     "radio_receiver.n.01_1": "radio_receiver.n.01",
    #     "table.n.02_1": "table.n.02",
    #     "floor.n.01_1": "floor.n.01",
    #     "agent.n.01_1": "agent.n.01",
    # }
```

**关键点**：
1. `get_knowledge_base()` 返回一个全局单例 `KnowledgeBase` 对象
2. `get_task()` 内部调用 `parse_problem()` 解析 BDDL 文件
3. `object_scope` 在这个阶段只是一个骨架（所有值为 `None`）

---

## 阶段二：对象范围创建与编译

### 2.1 对象范围填充（离线模式）

在评估时，我们使用**离线模式**，从预先保存的 TRO state 文件中加载对象映射。

**源码位置**：`OmniGibson/omnigibson/tasks/behavior_task.py:349-397`

```python
# ==================== BehaviorTask.assign_object_scope_with_cache() ====================
def assign_object_scope_with_cache(self, env):
    """从场景元数据加载对象分配"""
    
    # 1. 读取缓存的实例到名称映射
    # 这个映射在任务实例创建时保存（通过 save_task()）
    inst_to_name = env.scene.get_task_metadata(key="inst_to_name")
    
    # inst_to_name 示例：
    # {
    #     "radio_receiver.n.01_1": "radio_wjqvxz",
    #     "table.n.02_1": "table_dining_kwxenz",
    #     "floor.n.01_1": "floors",
    # }
    
    # 2. 为每个实例分配实际对象
    for obj_inst in self.object_scope:
        if obj_inst in self.future_obj_instances:
            # 未来对象（运行时生成，如切片）
            entity = None
        elif obj_inst not in inst_to_name:
            # 跳过未找到的实例（可能是通配符，稍后处理）
            continue
        else:
            name = inst_to_name[obj_inst]
            is_system = name in env.scene.available_systems.keys()
            
            if "agent.n." in obj_inst:
                # 机器人实例
                idx = int(obj_inst.split("_")[-1].lstrip("0")) - 1
                entity = env.robots[idx]
            else:
                # 对象或粒子系统
                if is_system:
                    entity = env.scene.get_system(name)
                else:
                    entity = env.scene.object_registry("name", name)
            
            # 填充 object_scope！
            self.object_scope[obj_inst] = entity
    
    # 填充后的 object_scope：
    # {
    #     "agent.n.01_1": <Fetch robot>,
    #     "radio_receiver.n.01_1": <DatasetObject: radio_wjqvxz>,
    #     "table.n.02_1": <DatasetObject: table_dining_kwxenz>,
    #     "floor.n.01_1": <DatasetObject: floors>,
    # }
```

**关键点**：
- `inst_to_name` 是连接符号层和物理层的桥梁
- 这个映射来自场景元数据，在任务实例创建时保存
- 对象通过 `scene.object_registry("name", name)` 获取

### 2.2 任务编译（处理通配符和房间）

**源码位置**：`OmniGibson/omnigibson/tasks/behavior_task.py:293-329`

```python
# ==================== BehaviorTask._compile_with_rooms() ====================
def _compile_with_rooms(self, env):
    """使用特定房间实例编译通配符任务"""
    
    # 1. 确定对象所在的房间实例
    room_instances = self._determine_room_instances(env)
    # room_instances = {"living_room": "living_room_0"}
    # 从 BDDL 的房间类型 → 场景中的具体房间实例
    
    # 2. 从这些房间构建场景布局（统计每个房间的对象数量）
    scene_layout = self._build_scene_layout_from_rooms(env.scene, room_instances)
    # scene_layout = {
    #     "living_room": {
    #         "table": 3,
    #         "sofa": 2,
    #         "lamp": 5,
    #         "radio": 1,
    #     }
    # }
    
    # 3. 编译任务（展开通配符）
    # 这是关键步骤！将符号定义转换为可执行的表达式树
    self.compiled_task = self._task_def.compile(scene_layout=scene_layout)
    
    # compiled_task 是一个 CompiledTask 对象，包含：
    # - initial_conditions: list[HEAD]
    # - goal_conditions: list[HEAD]
    # - ground_goal_state_options: 所有可能的目标状态组合
    
    # 4. 保留现有对象分配
    old_scope = self.object_scope
    self._finalize_compiled_task()
    
    # 5. 重新应用之前分配的对象
    for inst, entity in old_scope.items():
        if inst in self.object_scope:
            self.object_scope[inst] = entity
```

**编译过程详解**：

```python
# ==================== 编译内部流程 ====================
# _task_def.compile() 调用的是 bddl3/bddl/activity.py

# 步骤1：创建对象范围（符号层）
from bddl.activity import get_object_scope
scope = get_object_scope(self._base_conditions)
# scope = {
#     "radio_receiver.n.01_1": "radio_receiver.n.01_1",
#     "table.n.02_1": "table.n.02_1",
#     ...
# }
# 此时还是符号到符号的映射

# 步骤2：编译条件为表达式树
from bddl.condition_evaluation import compile_state

initial_conditions = compile_state(
    self._base_conditions.parsed_initial_conditions,
    scope=scope,
    object_map=self._base_conditions.parsed_objects,
    generate_ground_options=True,
)

goal_conditions = compile_state(
    self._base_conditions.parsed_goal_conditions,
    scope=scope,
    object_map=self._base_conditions.parsed_objects,
    generate_ground_options=True,
)

# 编译结果：将嵌套列表转换为表达式树
# 例如：["and", ["toggled_on", "radio_receiver.n.01_1"]]
# 变成：HEAD(child=Conjunction(children=[Predicate(...)]))
```

**表达式树结构**：

```python
# ==================== 表达式树示例 ====================
# 源码：bddl3/bddl/condition_evaluation.py

# 编译前（嵌套列表）：
["and",
    ["toggled_on", "radio_receiver.n.01_1"],
    ["ontop", "radio_receiver.n.01_1", "table.n.02_1"]
]

# 编译后（表达式树）：
HEAD(
    children=[
        Conjunction(
            children=[
                ToggledOn(
                    body=["radio_receiver.n.01_1"],
                    STATE_NAME="toggled_on"
                ),
                OnTop(
                    body=["radio_receiver.n.01_1", "table.n.02_1"],
                    STATE_NAME="ontop"
                )
            ]
        )
    ]
)

# 每个节点都有 evaluate() 方法，可以递归评估
```

**通配符展开示例**：

```lisp
;; 编译前的 BDDL（带通配符）
(:objects
    table.n.02_1 - table.n.02
    ?lamp.n.02_* - lamp.n.02  ; 通配符：任意数量的灯
)

(:init
    (ontop ?lamp.n.02_* table.n.02_1)  ; 所有灯都在桌上
)
```

```python
# 编译过程：
# 1. 从 scene_layout 读取：living_room 有 5 盏灯
# 2. 展开通配符：
#    lamp.n.02_1, lamp.n.02_2, lamp.n.02_3, lamp.n.02_4, lamp.n.02_5
# 3. 为每盏灯生成条件：
#    (ontop lamp.n.02_1 table.n.02_1)
#    (ontop lamp.n.02_2 table.n.02_1)
#    ...
#    (ontop lamp.n.02_5 table.n.02_1)

# 编译后的 object_scope 会包含所有展开的实例：
# {
#     "table.n.02_1": <table object>,
#     "lamp.n.02_1": <lamp object 1>,
#     "lamp.n.02_2": <lamp object 2>,
#     ...
# }
```

### 2.3 finalize_compiled_task

**源码位置**：`OmniGibson/omnigibson/tasks/behavior_task.py:331-347`

```python
def _finalize_compiled_task(self):
    """从编译后的任务中提取条件和选项"""
    
    # 1. 提取条件列表
    self.activity_initial_conditions = self.compiled_task.initial_conditions
    self.activity_goal_conditions = self.compiled_task.goal_conditions
    self.ground_goal_state_options = self.compiled_task.ground_goal_state_options
    
    # 2. 更新 object_scope（包含编译后展开的通配符实例）
    self.object_scope = {
        inst: self.object_scope.get(inst, None)
        for inst in self.compiled_task.object_scope.keys()
    }
    
    # 3. 更新实例到类别的映射
    self.object_instance_to_category = self.compiled_task.object_instance_to_synset
```

**关键点**：
- 编译后的 `object_scope` 可能包含更多实例（通配符展开）
- `ground_goal_state_options` 包含所有可能满足目标的状态组合

---

## 阶段三：任务实例加载

### 3.1 TRO State 文件结构

**文件路径**：`<OMNIGIBSON_DATA_PATH>/2026-challenge-task-instances/<mode>/<scene>_task_<activity>_instances/<filename>-tro_state`

**示例**（`turning_on_radio_301-tro_state`）：

```json
{
  "robot_poses": {
    "robot": [
      {
        "position": [2.5, 1.3, 0.0],
        "orientation": [0.0, 0.0, 0.707, 0.707]
      }
    ],
    "r1pro": [
      {
        "position": [2.6, 1.4, 0.0],
        "orientation": [0.0, 0.0, 0.7, 0.714]
      }
    ]
  },
  "radio_receiver.n.01_1": {
    "name": "radio_wjqvxz",
    "root_link": {
      "pos": [2.3, 1.5, 0.8],
      "ori": [0, 0, 0, 1],
      "lin_vel": [0, 0, 0],
      "ang_vel": [0, 0, 0]
    },
    "joint_positions": {},
    "states": {
      "ToggledOn": {"value": false},
      "OnTop": {"value": {"table_dining_kwxenz": true}}
    }
  },
  "table.n.02_1": {
    "name": "table_dining_kwxenz",
    "root_link": {
      "pos": [2.5, 1.0, 0.0],
      "ori": [0, 0, 0, 1]
    }
  }
}
```

### 3.2 Evaluator 加载任务实例

**源码位置**：`OmniGibson/omnigibson/eval/evaluator.py` + 文档

```python
# ==================== Evaluator.load_task_instance() ====================
def load_task_instance(self, instance_id: int) -> None:
    """加载特定任务实例的初始配置"""
    
    # ========================================
    # 步骤 1：构建 TRO state 文件路径
    # ========================================
    
    # 1.1 获取场景名称
    scene_model = self.env.task.scene_name
    # 例如：scene_model = "Rs_int"
    
    # 1.2 构建任务缓存文件名
    tro_filename = self.env.task.get_cached_activity_scene_filename(
        scene_model=scene_model,
        activity_name=self.env.task.activity_name,
        activity_definition_id=self.env.task.activity_definition_id,
        activity_instance_id=instance_id,
    )
    # 返回：Rs_int_task_turning_on_radio_0_0_301_template
    
    # 1.3 获取模式（train/public_test/hidden_test）
    mode = self.cfg.get("mode", "public_test")
    
    # 1.4 构建完整文件路径
    from omnigibson.utils.asset_utils import get_task_instance_path
    
    tro_file_path = get_task_instance_path(
        scene_model,
        f"{scene_model}_task_{self.env.task.activity_name}_instances/{tro_filename}-tro_state",
        mode=mode,
    )
    # 完整路径：
    # /data/2026-challenge-task-instances/public_test/
    # Rs_int_task_turning_on_radio_instances/
    # Rs_int_task_turning_on_radio_0_0_301-tro_state
    
    if tro_file_path is None:
        raise FileNotFoundError(
            f"Could not find {mode} task instance {instance_id}"
        )
    
    # ========================================
    # 步骤 2：加载任务实例的状态
    # ========================================
    
    import json
    from omnigibson.utils.python_utils import recursively_convert_to_torch
    
    with open(tro_file_path, "r") as f:
        tro_state = recursively_convert_to_torch(json.load(f))
    
    # tro_state 是一个字典，包含：
    # {
    #     "robot_poses": {...},
    #     "radio_receiver.n.01_1": {...},
    #     "table.n.02_1": {...},
    #     ...
    # }
    
    # ========================================
    # 步骤 3：恢复对象和机器人的状态
    # ========================================
    
    for tro_key, tro_value in tro_state.items():
        if tro_key == "robot_poses":
            # 3.1 处理机器人姿态（稍后在 reset() 中设置）
            presampled_robot_poses = {
                key.lower(): value 
                for key, value in tro_value.items()
            }
            self.env.scene.write_task_metadata(
                key=tro_key, 
                data=presampled_robot_poses
            )
        else:
            # 3.2 加载其他对象的状态
            # 关键：通过 task.object_scope 找到实际对象！
            obj = self.env.task.object_scope[tro_key]
            
            # load_state() 恢复：
            # - 对象位置和姿态
            # - 关节位置
            # - 物理属性（速度、角速度）
            # - 对象状态（ToggledOn、OnTop 等）
            obj.load_state(tro_value, serialized=False)
    
    # ========================================
    # 步骤 4：同步灯光（某些任务需要）
    # ========================================
    
    if self.should_sync_lights:
        from omnigibson.eval.utils.light_utils import set_light_control_toggles
        set_light_control_toggles(
            self.env.task.object_scope.values(), 
            True
        )
    
    # ========================================
    # 步骤 5：稳定物理场景
    # ========================================
    
    # 加载状态后需要运行几步物理模拟来"稳定"场景
    import omnigibson as og
    
    og.sim.update_handles()  # 更新物理句柄
    
    for _ in range(25):
        og.sim.step_physics()
        
        # 同时保持所有任务相关对象静止
        for inst, entity in self.env.task.object_scope.items():
            if not is_system_bddl_inst(inst) and entity is not None:
                entity.keep_still()  # 防止对象移动
    
    # ========================================
    # 步骤 6：保存初始状态并重置
    # ========================================
    
    self.env.scene.update_initial_file()  # 更新初始状态文件
    self.env.scene.reset()                 # 重置场景到初始状态
    self._reset_light_synchronizer()       # 重置灯光同步器
```

**关键点**：
1. TRO state 文件使用 **BDDL 实例名** 作为键
2. 通过 `task.object_scope[tro_key]` 找到实际对象
3. `object.load_state()` 恢复所有状态（位置、姿态、对象状态）
4. 物理稳定步骤确保对象不会抖动或漂移

---

## 阶段四：运行时评估

### 4.1 评估循环

**源码位置**：整合自多个文件

```python
# ==================== 评估主循环 ====================
# 在 omnigibson/eval/eval.py 或类似文件中

# 初始化
obs = env.reset()

for step in range(max_steps):
    # 1. 获取动作（从策略网络）
    action = policy.get_action(obs)
    
    # 2. 执行动作
    obs, reward, done, truncated, info = env.step(action)
    
    # env.step() 内部调用：
    # - og.sim.step()  # 物理模拟步进
    # - task.step()    # 任务更新
    
    if done:
        success = info["success"]
        goal_status = info["goal_status"]
        break
```

### 4.2 任务步进和终止检查

**源码位置**：`OmniGibson/omnigibson/tasks/behavior_task.py:172-180` + `task_base.py`

```python
# ==================== BehaviorTask._step_termination() ====================
def _step_termination(self, env, action, info=None):
    """检查任务是否完成"""
    
    # 1. 调用父类方法（检查所有终止条件）
    done, info = super()._step_termination(env=env, action=action, info=info)
    
    # super()._step_termination() 会调用所有终止条件的 step()
    # 包括 Timeout 和 PredicateGoal
    
    # 2. 添加目标状态详情到 info
    info["goal_status"] = self._termination_conditions["predicate"].goal_status
    
    return done, info

# ==================== PredicateGoal 的实现 ====================
# 源码：omnigibson/termination_conditions/predicate_goal.py

class PredicateGoal(BaseTerminationCondition):
    def __init__(self, check_goal_fn):
        self.check_goal_fn = check_goal_fn
        self.goal_status = None
        super().__init__()
    
    def _step(self, task, env, action):
        # 调用 check_goal_fn，它是：
        # lambda: self.compiled_task.check_goal(self._evaluate_predicate)
        
        done, self.goal_status = self.check_goal_fn()
        
        # done: True if all goals satisfied
        # goal_status: {
        #     "satisfied": [0, 2, 3],    # 满足的目标索引
        #     "unsatisfied": [1]          # 未满足的目标索引
        # }
        
        return done, {"success": done}
```

### 4.3 目标检查流程

**源码位置**：`bddl3/bddl/` + `OmniGibson/omnigibson/tasks/behavior_task.py`

```python
# ==================== compiled_task.check_goal() ====================
# 这个方法在 bddl3/bddl/ 的某个模块中

class CompiledTask:
    def check_goal(self, evaluate_fn):
        """检查所有目标条件是否满足"""
        
        satisfied = []
        unsatisfied = []
        
        # 遍历所有目标条件（HEAD 节点列表）
        for i, goal_condition in enumerate(self.goal_conditions):
            # goal_condition 是一个 HEAD 对象，包含表达式树
            
            # 评估这个条件
            if goal_condition.evaluate(evaluate_fn):
                satisfied.append(i)
            else:
                unsatisfied.append(i)
        
        all_satisfied = len(unsatisfied) == 0
        goal_status = {
            "satisfied": satisfied, 
            "unsatisfied": unsatisfied
        }
        
        return all_satisfied, goal_status
```

**表达式树评估示例**：

```python
# ==================== 表达式树的 evaluate() ====================
# 源码：bddl3/bddl/condition_evaluation.py

# 假设目标条件是：
# (and (toggled_on radio_receiver.n.01_1) (ontop apple.n.01_1 table.n.02_1))

# 表达式树：
HEAD(
    children=[
        Conjunction(  # and
            children=[
                ToggledOn(...),  # Predicate
                OnTop(...)       # Predicate
            ]
        )
    ]
)

# 评估流程：
# 1. HEAD.evaluate(evaluate_fn)
#    └─> Conjunction.evaluate(evaluate_fn)
#        ├─> ToggledOn.evaluate(evaluate_fn)
#        │   └─> evaluate_fn("toggled_on", "radio_receiver.n.01_1")
#        │       └─> _evaluate_predicate("toggled_on", "radio_receiver.n.01_1")
#        │           └─> evaluate_bddl_predicate(ToggledOn, <radio object>)
#        │               └─> radio_obj.states[ToggledOn].get_value()
#        │                   └─> True/False
#        │
#        └─> OnTop.evaluate(evaluate_fn)
#            └─> evaluate_fn("ontop", "apple.n.01_1", "table.n.02_1")
#                └─> _evaluate_predicate("ontop", "apple.n.01_1", "table.n.02_1")
#                    └─> evaluate_bddl_predicate(OnTop, <apple>, <table>)
#                        └─> apple_obj.states[OnTop].get_value(table_obj)
#                            └─> True/False
#
# 2. Conjunction.evaluate() 返回 all([True, False]) = False
# 3. HEAD.evaluate() 返回 False
```

### 4.4 谓词评估

**源码位置**：`OmniGibson/omnigibson/utils/bddl_utils.py:207-236`

```python
# ==================== _evaluate_predicate ====================
# 在 BehaviorTask 中定义

def _evaluate_predicate(self, predicate_name, *entities):
    """评估 BDDL 谓词是否为真"""
    from omnigibson.utils.bddl_utils import evaluate_bddl_predicate
    
    # 将符号实例转换为实际对象
    actual_objects = [self.object_scope[ent] for ent in entities]
    
    # 调用通用谓词评估函数
    return evaluate_bddl_predicate(predicate_name, *actual_objects)

# ==================== evaluate_bddl_predicate ====================
# 源码：omnigibson/utils/bddl_utils.py

# 谓词类到状态类的映射
PREDICATE_TO_STATE = {
    bddl_predicates.ToggledOn: object_states.ToggledOn,
    bddl_predicates.OnTop: object_states.OnTop,
    bddl_predicates.Inside: object_states.Inside,
    bddl_predicates.Cooked: object_states.Cooked,
    bddl_predicates.Open: object_states.Open,
    # ... 更多映射
}

def evaluate_bddl_predicate(predicate_cls, *entities):
    """评估 BDDL 谓词对应的物理对象状态
    
    Args:
        predicate_cls: BDDL 谓词类（如 bddl_predicates.ToggledOn）
        *entities: 物理对象（如 <DatasetObject>）
    
    Returns:
        bool: 谓词是否满足
    """
    
    # 特殊谓词处理
    if predicate_cls is bddl_predicates.InSource:
        return True
    if predicate_cls is bddl_predicates.Future:
        return entities[0] is None
    if predicate_cls is bddl_predicates.Real:
        return entities[0] is not None
    
    # 获取对应的对象状态类
    state_class = PREDICATE_TO_STATE[predicate_cls]
    
    # 根据谓词元数（arity）评估
    if predicate_cls.arity == 2:
        # 二元谓词（如 ontop, inside）
        obj1, obj2 = entities[0], entities[1]
        
        # 检查对象是否存在和已初始化
        if obj1 is None or not obj1.initialized:
            return False
        if obj2 is None or not obj2.initialized:
            return False
        
        # 评估二元状态
        return obj1.states[state_class].get_value(obj2)
    else:
        # 一元谓词（如 cooked, toggled_on）
        obj = entities[0]
        
        # 检查对象是否存在和已初始化
        if obj is None or not obj.initialized:
            return False
        
        # 评估一元状态
        return obj.states[state_class].get_value()
```

**具体示例**：

```python
# ==================== 示例 1：一元谓词 ====================
# BDDL: (toggled_on radio_receiver.n.01_1)

# 评估流程：
_evaluate_predicate("toggled_on", "radio_receiver.n.01_1")
↓
evaluate_bddl_predicate(
    bddl_predicates.ToggledOn,
    <DatasetObject: radio_wjqvxz>
)
↓
state_class = object_states.ToggledOn
obj = <DatasetObject: radio_wjqvxz>
↓
obj.states[ToggledOn].get_value()
↓
# 内部调用：检查对象的 ToggledOn 状态
# 可能会检查关节状态、按钮状态等
↓
True/False

# ==================== 示例 2：二元谓词 ====================
# BDDL: (ontop radio_receiver.n.01_1 table.n.02_1)

# 评估流程：
_evaluate_predicate("ontop", "radio_receiver.n.01_1", "table.n.02_1")
↓
evaluate_bddl_predicate(
    bddl_predicates.OnTop,
    <DatasetObject: radio_wjqvxz>,
    <DatasetObject: table_dining_kwxenz>
)
↓
state_class = object_states.OnTop
obj1 = <radio>
obj2 = <table>
↓
obj1.states[OnTop].get_value(obj2)
↓
# 内部调用：检查 radio 是否在 table 上
# 通过物理碰撞检测、位置关系等判断
↓
True/False
```

### 4.5 对象状态系统

**源码位置**：`OmniGibson/omnigibson/object_states/` 目录

对象状态系统是连接 BDDL 谓词和物理仿真的关键层：

```python
# ==================== 对象状态基类 ====================
# omnigibson/object_states/object_state_base.py

class BaseObjectState:
    """所有对象状态的基类"""
    
    def __init__(self, obj):
        self.obj = obj  # 关联的对象
    
    def get_value(self, *args, **kwargs):
        """获取状态值（子类实现）"""
        raise NotImplementedError
    
    def set_value(self, *args, **kwargs):
        """设置状态值（子类实现）"""
        raise NotImplementedError

# ==================== 示例：ToggledOn 状态 ====================
# omnigibson/object_states/toggled_on.py

class ToggledOn(AbsoluteObjectState):
    """对象的开关状态"""
    
    def _get_value(self):
        """检查对象是否被打开"""
        
        # 1. 检查对象是否有关节
        if not self.obj.joints:
            return False
        
        # 2. 检查特定关节（如开关）的位置
        # 不同对象有不同的实现逻辑
        # 例如收音机可能检查 "button_joint" 的位置
        
        for joint_name, joint in self.obj.joints.items():
            if "button" in joint_name or "switch" in joint_name:
                # 检查关节是否在"打开"位置
                position = joint.get_state()[0]  # 关节位置
                if position > 0.5:  # 阈值可能不同
                    return True
        
        return False
    
    def _set_value(self, new_value):
        """设置对象的开关状态"""
        
        # 找到开关关节并设置位置
        for joint_name, joint in self.obj.joints.items():
            if "button" in joint_name or "switch" in joint_name:
                target_position = 1.0 if new_value else 0.0
                joint.set_state(target_position, 0.0)  # (位置, 速度)
                return True
        
        return False

# ==================== 示例：OnTop 状态 ====================
# omnigibson/object_states/on_top.py

class OnTop(RelativeObjectState):
    """对象是否在另一个对象上"""
    
    def _get_value(self, other):
        """检查 self.obj 是否在 other 上"""
        
        # 1. 获取两个对象的 AABB（轴对齐包围盒）
        obj_aabb_center, obj_aabb_extent = self.obj.aabb_center, self.obj.aabb_extent
        other_aabb_center, other_aabb_extent = other.aabb_center, other.aabb_extent
        
        # 2. 检查垂直关系（obj 在 other 上方）
        obj_bottom = obj_aabb_center[2] - obj_aabb_extent[2] / 2
        other_top = other_aabb_center[2] + other_aabb_extent[2] / 2
        
        vertical_distance = obj_bottom - other_top
        if vertical_distance > 0.1:  # 太远
            return False
        if vertical_distance < -0.05:  # 穿透
            return False
        
        # 3. 检查水平重叠
        obj_xy = obj_aabb_center[:2]
        other_xy = other_aabb_center[:2]
        horizontal_distance = th.norm(obj_xy - other_xy)
        
        if horizontal_distance > (obj_aabb_extent[:2].sum() + other_aabb_extent[:2].sum()) / 4:
            return False
        
        # 4. 检查物理接触（更精确）
        contact_pairs = og.sim.psim.get_contact_pairs(self.obj, other)
        if len(contact_pairs) == 0:
            return False
        
        return True
    
    def _set_value(self, other, new_value):
        """设置 self.obj 在 other 上（采样）"""
        
        if new_value:
            # 在 other 表面随机采样一个有效位置
            valid_position = self._sample_position_on_surface(other)
            if valid_position is not None:
                self.obj.set_position(valid_position)
                return True
        
        return False
```

---

## 核心数据结构

### 5.1 object_scope

**定义**：`Dict[str, BaseObject | BaseSystem | None]`

**作用**：BDDL 符号实例到物理对象的映射

**生命周期**：

```python
# 阶段 1：初始化（update_activity）
object_scope = {
    "radio_receiver.n.01_1": None,
    "table.n.02_1": None,
}

# 阶段 2：填充（assign_object_scope_with_cache）
object_scope = {
    "radio_receiver.n.01_1": <DatasetObject: radio_wjqvxz>,
    "table.n.02_1": <DatasetObject: table_dining_kwxenz>,
}

# 阶段 3：编译后可能扩展（_compile_with_rooms）
object_scope = {
    "radio_receiver.n.01_1": <DatasetObject: radio_wjqvxz>,
    "table.n.02_1": <DatasetObject: table_dining_kwxenz>,
    "lamp.n.02_1": <DatasetObject: lamp_abc123>,  # 通配符展开
    "lamp.n.02_2": <DatasetObject: lamp_def456>,
}

# 阶段 4：运行时使用（_evaluate_predicate）
obj = object_scope["radio_receiver.n.01_1"]
result = obj.states[ToggledOn].get_value()
```

### 5.2 compiled_task

**定义**：`CompiledTask` 对象

**属性**：

```python
class CompiledTask:
    object_scope: Dict[str, str]  # 符号层的 scope
    object_instance_to_synset: Dict[str, str]
    
    initial_conditions: List[HEAD]  # 初始条件的表达式树列表
    goal_conditions: List[HEAD]     # 目标条件的表达式树列表
    ground_goal_state_options: Tensor  # 所有可能的目标状态组合
    
    def check_goal(self, evaluate_fn):
        """评估所有目标条件"""
        # 返回 (all_satisfied: bool, goal_status: dict)
```

### 5.3 表达式树节点类型

**源码位置**：`bddl3/bddl/condition_evaluation.py` + `bddl3/bddl/predicates.py`

```python
# 基类
class Expression:
    def __init__(self, scope, body, object_map):
        self.scope = scope              # 对象范围
        self.body = body                # 表达式体
        self.object_map = object_map    # 对象映射
        self.children = []              # 子节点
    
    def evaluate(self, evaluate_fn):
        """评估表达式（子类实现）"""
        raise NotImplementedError

# 逻辑连接词
class Conjunction(Expression):  # and
    def evaluate(self, evaluate_fn):
        return all(child.evaluate(evaluate_fn) for child in self.children)

class Disjunction(Expression):  # or
    def evaluate(self, evaluate_fn):
        return any(child.evaluate(evaluate_fn) for child in self.children)

class Negation(Expression):     # not
    def evaluate(self, evaluate_fn):
        return not self.children[0].evaluate(evaluate_fn)

# 量词
class Universal(Expression):    # forall
    def evaluate(self, evaluate_fn):
        # 所有实例都必须满足
        return all(child.evaluate(evaluate_fn) for child in self.children)

class Existential(Expression):  # exists
    def evaluate(self, evaluate_fn):
        # 至少一个实例满足
        return any(child.evaluate(evaluate_fn) for child in self.children)

# 谓词（叶子节点）
class Predicate(Expression):
    STATE_NAME: str  # 谓词名称（如 "toggled_on"）
    arity: int       # 元数（1 或 2）
    
    def evaluate(self, evaluate_fn):
        # 调用用户提供的评估函数
        return evaluate_fn(self.__class__, *self.body)

# 具体谓词类
class ToggledOn(Predicate):
    STATE_NAME = "toggled_on"
    arity = 1

class OnTop(Predicate):
    STATE_NAME = "ontop"
    arity = 2

class Inside(Predicate):
    STATE_NAME = "inside"
    arity = 2

# ... 更多谓词类
```

### 5.4 TRO State 数据结构

```python
# TRO State 的 Python 表示
tro_state = {
    # 机器人姿态（特殊键）
    "robot_poses": {
        "robot": [  # 通用机器人姿态
            {
                "position": [x, y, z],
                "orientation": [qx, qy, qz, qw]  # 四元数
            }
        ],
        "r1pro": [  # R1Pro 专用姿态
            {"position": [...], "orientation": [...]}
        ],
        "fetch": [  # Fetch 专用姿态
            {"position": [...], "orientation": [...]}
        ],
    },
    
    # 对象状态（键 = BDDL 实例名）
    "radio_receiver.n.01_1": {
        "name": "radio_wjqvxz",  # 对象名称（在场景中的唯一标识）
        "root_link": {
            "pos": [x, y, z],
            "ori": [qx, qy, qz, qw],
            "lin_vel": [vx, vy, vz],
            "ang_vel": [wx, wy, wz]
        },
        "joint_positions": {
            "joint_name": position,
            ...
        },
        "states": {
            "ToggledOn": {"value": False},
            "OnTop": {"value": {"table_dining_kwxenz": True}},
            "Cooked": {"value": False},
            # ... 其他状态
        }
    },
    
    # 更多对象...
}
```

---

## 完整代码示例

### 6.1 从 BDDL 到评估的完整流程

```python
# ==================== 完整示例：turning_on_radio ====================

import omnigibson as og
from omnigibson.utils.config_utils import parse_config

# ============================================================
# 阶段 1：创建环境（触发 BDDL 加载）
# ============================================================

config = {
    "scene": {
        "type": "TraversableScene",
        "scene_model": "Rs_int",
        "scene_file": None,  # 将自动查找缓存的任务实例
    },
    "robots": [
        {
            "type": "Fetch",
            "obs_modalities": ["rgb", "depth"],
        }
    ],
    "task": {
        "type": "BehaviorTask",
        "activity_name": "turning_on_radio",
        "activity_definition_id": 0,
        "activity_instance_id": 0,
        "online_object_sampling": False,  # 使用离线模式
    },
}

# 创建环境
env = og.Environment(configs=config)

# 内部发生了什么：
# 1. BehaviorTask.__init__() 被调用
# 2. BehaviorTask._load(env) 被调用
#    a. task.update_activity() 加载 BDDL
#       - get_knowledge_base().get_task("turning_on_radio-0")
#       - 解析 BDDL 文件，得到 parsed_objects, parsed_initial_conditions, parsed_goal_conditions
#       - 创建 object_scope 骨架
#    b. task.initialize_activity() 初始化对象
#       - assign_object_scope_with_cache() 从场景元数据填充 object_scope
#       - _compile_with_rooms() 编译任务为表达式树
#       - _assign_wildcard_instances() 分配通配符实例
# 3. og.sim.play() 启动仿真
# 4. task.post_play_load(env) 计算观察维度

print("Environment created successfully!")
print(f"Object scope: {env.task.object_scope}")

# ============================================================
# 阶段 2：加载任务实例（恢复物理状态）
# ============================================================

from omnigibson.eval.evaluator import Evaluator

# 假设我们在 Evaluator 中
evaluator = Evaluator(cfg=...)
evaluator.load_task_instance(instance_id=301)

# 内部发生了什么：
# 1. 构建 TRO state 文件路径
# 2. 加载 JSON 文件
# 3. 遍历 tro_state，恢复每个对象的状态
#    for tro_key, tro_value in tro_state.items():
#        if tro_key == "robot_poses":
#            # 保存机器人姿态（稍后使用）
#        else:
#            obj = env.task.object_scope[tro_key]
#            obj.load_state(tro_value)
# 4. 稳定物理场景（25 步）
# 5. 重置场景到初始状态

# ============================================================
# 阶段 3：重置环境（设置机器人姿态）
# ============================================================

obs = env.reset()

# BehaviorTask.reset() 被调用：
# 1. 从元数据读取预采样的机器人姿态
# 2. 设置机器人位置和朝向
# 3. 唤醒所有任务相关对象

# ============================================================
# 阶段 4：执行评估循环
# ============================================================

for step in range(500):
    # 4.1 获取动作（从策略或随机）
    action = env.action_space.sample()
    
    # 4.2 执行动作
    obs, reward, done, truncated, info = env.step(action)
    
    # env.step() 内部：
    # a. og.sim.step() - 物理模拟步进
    # b. task.step(env, action) - 任务更新
    #    - task._step_reward() - 计算奖励
    #    - task._step_termination() - 检查终止条件
    #       · PredicateGoal.step()
    #         → compiled_task.check_goal(_evaluate_predicate)
    #         → 遍历 goal_conditions，调用 HEAD.evaluate()
    #         → 递归评估表达式树
    #         → 叶子节点调用 _evaluate_predicate()
    #         → evaluate_bddl_predicate()
    #         → object.states[StateClass].get_value()
    #         → 返回 True/False
    
    # 4.3 检查是否完成
    if done:
        success = info["success"]
        goal_status = info["goal_status"]
        
        print(f"\nTask completed at step {step}")
        print(f"Success: {success}")
        print(f"Satisfied goals: {goal_status['satisfied']}")
        print(f"Unsatisfied goals: {goal_status['unsatisfied']}")
        
        break

# ============================================================
# 阶段 5：手动检查谓词（可选）
# ============================================================

# 获取收音机对象
radio_inst = "radio_receiver.n.01_1"
radio_obj = env.task.object_scope[radio_inst]

# 手动评估谓词
from omnigibson.object_states import ToggledOn

is_toggled_on = radio_obj.states[ToggledOn].get_value()
print(f"\nRadio is toggled on: {is_toggled_on}")

# 或者通过 BehaviorTask 的接口
result = env.task._evaluate_predicate("toggled_on", radio_inst)
print(f"Via _evaluate_predicate: {result}")

# ============================================================
# 清理
# ============================================================

og.shutdown()
```

### 6.2 调试：打印表达式树

```python
# ==================== 打印编译后的表达式树 ====================

def print_expression_tree(node, indent=0):
    """递归打印表达式树"""
    prefix = "  " * indent
    
    if hasattr(node, "STATE_NAME"):
        # Predicate 节点
        print(f"{prefix}Predicate: {node.STATE_NAME}")
        print(f"{prefix}  Body: {node.body}")
    elif isinstance(node, list):
        # 多个 HEAD 节点
        for i, child in enumerate(node):
            print(f"{prefix}[{i}]")
            print_expression_tree(child, indent + 1)
    elif hasattr(node, "children"):
        # 逻辑节点
        class_name = node.__class__.__name__
        print(f"{prefix}{class_name}")
        for child in node.children:
            print_expression_tree(child, indent + 1)
    else:
        print(f"{prefix}{node}")

# 使用
env = og.Environment(configs=config)

print("=== Initial Conditions ===")
print_expression_tree(env.task.activity_initial_conditions)

print("\n=== Goal Conditions ===")
print_expression_tree(env.task.activity_goal_conditions)

# 输出示例：
# === Goal Conditions ===
# [0]
#   HEAD
#     Conjunction
#       Predicate: toggled_on
#         Body: ['radio_receiver.n.01_1']
```

---

## 常见问题

### Q1: object_scope 什么时候被填充？

**A**: 分阶段填充：

1. **update_activity()**：创建空的 `object_scope`（所有值为 `None`）
2. **initialize_activity()**：
   - 离线模式：通过 `assign_object_scope_with_cache()` 填充
   - 在线模式：通过 `sampler.assign_objects()` 填充
3. **_compile_with_rooms()**：可能添加通配符展开的实例
4. **_assign_wildcard_instances()**：填充剩余的通配符实例

### Q2: inst_to_name 从哪来？

**A**: 从任务实例创建时保存：

```python
# 创建任务实例时（通常在数据集生成阶段）
task.save_task(env, task_relevant_only=True)

# 内部调用：
task_relevant_state_dict = {}
for bddl_name, bddl_obj in env.task.object_scope.items():
    task_relevant_state_dict[bddl_name] = bddl_obj.dump_state()

# 这个字典被保存为 TRO state 文件
# 同时，inst_to_name 被保存到场景元数据：
env.scene.write_task_metadata(
    key="inst_to_name",
    data={
        bddl_name: bddl_obj.name
        for bddl_name, bddl_obj in env.task.object_scope.items()
    }
)
```

### Q3: 如何添加新的 BDDL 谓词？

**A**: 需要三步：

1. **在 BDDL 中定义谓词**（`bddl3/bddl/predicates.py`）：
```python
class MyNewPredicate(Predicate):
    STATE_NAME = "my_new_predicate"
    arity = 1  # 或 2
```

2. **实现对应的对象状态**（`OmniGibson/omnigibson/object_states/my_new_state.py`）：
```python
class MyNewState(AbsoluteObjectState):
    def _get_value(self):
        # 实现状态检查逻辑
        return True/False
    
    def _set_value(self, new_value):
        # 实现状态设置逻辑
        return True/False
```

3. **添加映射**（`OmniGibson/omnigibson/utils/bddl_utils.py`）：
```python
PREDICATE_TO_STATE = {
    # ... 现有映射
    bddl_predicates.MyNewPredicate: object_states.MyNewState,
}
```

### Q4: 如何理解 ground_goal_state_options？

**A**: 它包含所有可能满足目标的具体状态组合：

```python
# 假设目标是：
# (or
#     (and (ontop apple.n.01_1 table.n.02_1) (cooked apple.n.01_1))
#     (and (ontop apple.n.01_1 plate.n.04_1) (sliced apple.n.01_1))
# )

# ground_goal_state_options 会包含两个选项：
# Option 1: [
#     (ontop apple.n.01_1 table.n.02_1),
#     (cooked apple.n.01_1)
# ]
# Option 2: [
#     (ontop apple.n.01_1 plate.n.04_1),
#     (sliced apple.n.01_1)
# ]

# 任一选项的所有谓词都满足 → 任务成功
```

### Q5: 为什么需要编译步骤？

**A**: 编译有三个主要目的：

1. **展开通配符**：将 `?lamp.n.02_*` 展开为具体实例
2. **确定房间**：将房间类型映射到场景中的具体房间实例
3. **构建表达式树**：将嵌套列表转换为可高效评估的树结构

### Q6: 如何调试谓词评估失败？

**A**: 逐层检查：

```python
# 1. 检查 object_scope
print(env.task.object_scope)

# 2. 检查对象是否存在
obj = env.task.object_scope["radio_receiver.n.01_1"]
print(f"Object exists: {obj is not None}")
print(f"Object initialized: {obj.initialized if obj else False}")

# 3. 检查状态类是否可用
from omnigibson.object_states import ToggledOn
print(f"State available: {ToggledOn in obj.states}")

# 4. 手动评估状态
result = obj.states[ToggledOn].get_value()
print(f"State value: {result}")

# 5. 检查表达式树
print_expression_tree(env.task.activity_goal_conditions)

# 6. 单步评估目标
done, goal_status = env.task.compiled_task.check_goal(
    env.task._evaluate_predicate
)
print(f"Done: {done}")
print(f"Goal status: {goal_status}")
```

---

## 总结

BDDL 数据流是一个精心设计的多层转换系统：

1. **符号层（BDDL 文件）**：人类可读的任务定义
2. **结构化数据（解析后）**：嵌套列表表示
3. **对象映射（object_scope）**：符号到物理对象的桥梁
4. **表达式树（compiled_task）**：可执行的条件检查结构
5. **物理评估（对象状态）**：实际的仿真状态查询

这个设计使得：
- **任务定义与仿真解耦**：BDDL 文件独立于具体仿真器
- **高效评估**：编译后的表达式树避免重复解析
- **灵活扩展**：新谓词只需添加状态类和映射
- **可重现性**：TRO state 文件保证相同的初始配置

理解这个数据流是开发和调试 BEHAVIOR-1K 任务的关键！
