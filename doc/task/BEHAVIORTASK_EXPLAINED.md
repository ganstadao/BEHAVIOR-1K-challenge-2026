# BehaviorTask 类详解

## 概述

BehaviorTask 是 BEHAVIOR-1K 基准测试的核心任务类，继承自 BaseTask，负责将 **BDDL（Behavior Domain Definition Language）** 定义的符号任务转换为可在物理模拟中执行的具体任务。

**位置**: `OmniGibson/omnigibson/tasks/behavior_task.py`

**核心功能**:
- 加载和解析 BDDL 活动定义（1000+ 家庭任务）
- 管理对象范围（object_scope）：将符号实例映射到实际的模拟对象
- 评估 BDDL 谓词（如 `ontop`, `inside`, `cooked` 等）
- 支持在线/离线对象采样和状态初始化
- 提供基于任务完成度的奖励信号

---

## BDDL 基础知识

### BDDL 文件结构

以 `turning_on_radio/problem0.bddl` 为例：

```lisp
(define (problem turning_on_radio-0)
    (:domain behavior-1k)
    
    (:objects
        radio_receiver.n.01_1 - radio_receiver.n.01  ; 符号实例 - 类型
        table.n.02_1 - table.n.02
        floor.n.01_1 - floor.n.01
        agent.n.01_1 - agent.n.01
    )
    
    (:init  ; 初始条件
        (not (toggled_on radio_receiver.n.01_1))  ; 收音机未开启
        (ontop radio_receiver.n.01_1 table.n.02_1) ; 收音机在桌上
        (inroom table.n.02_1 living_room)          ; 桌子在客厅
        (inroom floor.n.01_1 living_room)
        (ontop agent.n.01_1 floor.n.01_1)          ; 机器人在地板上
    )
    
    (:goal  ; 目标条件
        (and 
            (toggled_on ?radio_receiver.n.01_1)  ; 收音机被打开
        )
    )
)
```

**关键概念**:
- **Synset** (类型): `radio_receiver.n.01` - WordNet 概念
- **Instance** (实例): `radio_receiver.n.01_1` - 具体的对象实例
- **Predicate** (谓词): `toggled_on`, `ontop`, `inside` - 描述对象状态和关系

---

## 类初始化

```python
def __init__(
    self,
    activity_name=None,              # 活动名称，如 "turning_on_radio"
    activity_definition_id=0,        # 活动定义ID（同一活动的不同变体）
    activity_instance_id=0,          # 实例ID（同一定义的不同初始配置）
    online_object_sampling=False,    # 是否在线采样对象位置
    use_presampled_robot_pose=True,  # 是否使用预采样的机器人姿态
    randomize_presampled_pose=False, # 是否随机选择预采样姿态
    sampling_whitelist=None,         # 对象采样白名单
    sampling_blacklist=None,         # 对象采样黑名单
    highlight_task_relevant_objects=False,  # 是否高亮任务相关对象
    termination_config=None,         # 终止条件配置
    reward_config=None,              # 奖励函数配置
    include_obs=True,                # 是否包含观察
):
```

### 核心属性

#### 活动相关

```python
# 活动标识
self.activity_name = "turning_on_radio"
self.activity_definition_id = 0
self.activity_instance_id = 0

# BDDL 编译结果
self.compiled_task = None  # 编译后的任务对象
self.activity_initial_conditions = None  # 初始条件列表
self.activity_goal_conditions = None     # 目标条件列表
self.ground_goal_state_options = None    # 目标状态选项

# 反馈信息
self.feedback = None  # 任务初始化的反馈信息
```

#### 对象范围 (Object Scope)

**最核心的数据结构**：将 BDDL 符号实例映射到模拟中的实际对象

```python
self.object_scope = {
    "agent.n.01_1": <Fetch robot object>,
    "radio_receiver.n.01_1": <DatasetObject: radio_wjqvxz>,
    "table.n.02_1": <DatasetObject: table_dining_kwxenz>,
    "floor.n.01_1": <DatasetObject: floors>,
}

# 实例到类别的映射
self.object_instance_to_category = {
    "radio_receiver.n.01_1": "radio_receiver.n.01",
    "table.n.02_1": "table.n.02",
    ...
}

# 未来对象（稍后生成的对象，如切片、烹饪产物）
self.future_obj_instances = {"sliced_apple.n.01_1", ...}
```

#### 场景相关

```python
self.scene_name = "Rs_int"  # 场景模型名称
self.sampler = None         # BDDLSampler 实例（用于对象采样）
```

---

## 核心方法详解

### 1. _load(env) - 加载任务

```python
def _load(self, env):
    """第一阶段：加载 BDDL 定义和初始化对象范围"""
    
    # 1. 加载活动定义
    self.update_activity(
        env=env,
        activity_name=self.activity_name,
        activity_definition_id=self.activity_definition_id,
    )
    
    # 2. 初始化活动（对象采样 + 状态设置）
    success, self.feedback = self.initialize_activity(env=env)
    
    # 3. 存储场景名称
    self.scene_name = env.scene.scene_model if isinstance(env.scene, TraversableScene) else None
    
    # 4. 可选：高亮任务相关对象
    if self.highlight_task_relevant_objs:
        for inst, entity in self.object_scope.items():
            if "agent.n." not in inst and entity is not None:
                entity.highlighted = True
    
    # 5. 注册回调函数（监听对象添加/删除事件）
    callback_name = f"{self.activity_name}_refresh"
    og.sim.add_callback_on_add_obj(name=callback_name, callback=self._update_bddl_scope_from_added_obj)
    og.sim.add_callback_on_remove_obj(name=callback_name, callback=self._update_bddl_scope_from_removed_obj)
    og.sim.add_callback_on_system_init(name=callback_name, callback=self._update_bddl_scope_from_system_init)
    og.sim.add_callback_on_system_clear(name=callback_name, callback=self._update_bddl_scope_from_system_clear)
```

---

### 2. update_activity() - 加载 BDDL 定义

```python
def update_activity(self, env, activity_name, activity_definition_id):
    """从 BDDL 文件加载任务定义"""
    
    self.activity_name = activity_name
    self.activity_definition_id = activity_definition_id
    
    # 1. 从知识库获取任务定义
    self._task_def = get_knowledge_base().get_task(f"{activity_name}-{activity_definition_id}")
    # 例如: "turning_on_radio-0" → 加载 bddl3/bddl/activity_definitions/turning_on_radio/problem0.bddl
    
    # 2. 解析基础范围（去除通配符）
    self._base_conditions, base_scope, self._base_inroom_assignments = self._task_def.parse_base_scope()
    # base_scope = ["radio_receiver.n.01_1", "table.n.02_1", "floor.n.01_1"]
    # _base_inroom_assignments = {"table.n.02_1": "living_room", "floor.n.01_1": "living_room"}
    
    self.compiled_task = None  # 稍后编译
    
    # 3. 初始化 object_scope（先设为 None，稍后分配实际对象）
    self.object_scope = {"agent.n.01_1": None}
    self.object_scope.update({name: None for name in base_scope})
    
    # 4. 构建实例到类别的映射
    self.object_instance_to_category = {
        obj_inst: obj_cat
        for obj_cat in self._base_conditions.parsed_objects
        for obj_inst in self._base_conditions.parsed_objects[obj_cat]
    }
```

**_task_def 对象**:
- 来自 `bddl3/bddl/` 包
- 包含解析后的 BDDL 定义
- 提供 `compile()` 方法生成可执行的条件检查器

---

### 3. initialize_activity() - 初始化对象和状态

这是 BehaviorTask 最复杂的方法，负责将符号定义转换为具体的物理场景。

```python
def initialize_activity(self, env):
    """
    初始化活动的完整流程：
    1. 为基础范围选择对象（采样或从缓存加载）
    2. 确定对象所在的房间实例
    3. 编译任务（展开通配符）
    4. 分配通配符扩展的实例
    """
    
    # 创建采样器（总是需要，用于在线/离线模式）
    self.sampler = BDDLSampler(
        env=env,
        activity_conditions=self._base_conditions,
        object_scope=self.object_scope,
    )
    
    if self.online_object_sampling:
        # ========== 在线采样模式 ==========
        
        # 阶段1：分配对象（使用未编译的条件）
        accept_scene, feedback = self.sampler.assign_objects(
            sampling_whitelist=self.sampling_whitelist,
            sampling_blacklist=self.sampling_blacklist,
        )
        if not accept_scene:
            return accept_scene, feedback
        
        # 现在 object_scope 已填充实际对象
        # object_scope["radio_receiver.n.01_1"] = <DatasetObject: radio_wjqvxz>
        
        # 编译任务（使用对象所在的正确房间）
        self._compile_with_rooms(env)
        
        # 阶段2：采样状态（使用编译后的条件）
        accept_scene, feedback = self.sampler.sample_states(self.compiled_task)
        if not accept_scene:
            return accept_scene, feedback
        
        # 分配通配符扩展的实例
        self._assign_wildcard_instances(env)
        
    else:
        # ========== 离线模式（从缓存加载）==========
        
        # 识别未来对象
        self.future_obj_instances = {
            cond[1] for cond in self._base_conditions.parsed_initial_conditions 
            if cond[0] == "future"
        }
        
        # 从缓存分配基础范围对象
        self.assign_object_scope_with_cache(env)
        
        # 编译任务
        self._compile_with_rooms(env)
        
        # 更新未来对象列表（可能在编译后扩展）
        self.future_obj_instances = {
            init_cond.body[1] for init_cond in self.activity_initial_conditions 
            if init_cond.body[0] == "future"
        }
        
        # 再次从缓存分配（包括通配符扩展的实例）
        self.assign_object_scope_with_cache(env)
        
        # 分配剩余的通配符实例
        self._assign_wildcard_instances(env)
        
        # 验证所有非未来对象都已分配
        for inst, entity in self.object_scope.items():
            if inst not in self.future_obj_instances and entity is None:
                raise ValueError(f"Object instance '{inst}' was not assigned!")
    
    return True, None
```

---

### 4. _compile_with_rooms() - 编译任务

```python
def _compile_with_rooms(self, env):
    """使用特定房间实例编译通配符任务"""
    
    # 1. 确定对象所在的房间实例
    room_instances = self._determine_room_instances(env)
    # room_instances = {"living_room": "living_room_0"}
    
    # 2. 从这些房间构建场景布局
    scene_layout = self._build_scene_layout_from_rooms(env.scene, room_instances)
    # scene_layout = {
    #     "living_room": {
    #         "table": 3,
    #         "sofa": 2,
    #         "lamp": 5,
    #         ...
    #     }
    # }
    
    # 3. 编译任务（展开通配符）
    self.compiled_task = self._task_def.compile(scene_layout=scene_layout)
    
    # 4. 保留现有对象分配
    old_scope = self.object_scope
    self._finalize_compiled_task()
    
    # 5. 重新应用之前分配的对象
    for inst, entity in old_scope.items():
        if inst in self.object_scope:
            self.object_scope[inst] = entity
```

**为什么需要编译？**

某些 BDDL 任务使用**通配符**来增加任务多样性：

```lisp
(:objects
    radio_receiver.n.01_1 - radio_receiver.n.01
    table.n.02_1 - table.n.02
    ?lamp.n.02_* - lamp.n.02  ; 通配符：任意数量的灯
)

(:init
    (ontop ?lamp.n.02_* table.n.02_1)  ; 所有灯都在桌上
)
```

编译过程：
1. 统计场景中 `living_room_0` 里有 5 盏灯
2. 展开通配符：生成 `lamp.n.02_1` 到 `lamp.n.02_5`
3. 为每盏灯生成初始条件

---

### 5. assign_object_scope_with_cache() - 从缓存加载对象

```python
def assign_object_scope_with_cache(self, env):
    """从场景元数据加载对象分配"""
    
    # 1. 读取缓存的实例到名称映射
    inst_to_name = env.scene.get_task_metadata(key="inst_to_name")
    # inst_to_name = {
    #     "radio_receiver.n.01_1": "radio_wjqvxz",
    #     "table.n.02_1": "table_dining_kwxenz",
    #     ...
    # }
    
    # 2. 为每个实例分配实际对象
    for obj_inst in self.object_scope:
        if obj_inst in self.future_obj_instances:
            entity = None  # 未来对象稍后生成
        elif obj_inst not in inst_to_name:
            continue  # 跳过未找到的实例（如通配符）
        else:
            name = inst_to_name[obj_inst]
            is_system = name in env.scene.available_systems.keys()
            
            if "agent.n." in obj_inst:
                # 机器人
                idx = int(obj_inst.split("_")[-1].lstrip("0")) - 1
                entity = env.robots[idx]
            else:
                # 对象或系统
                entity = env.scene.get_system(name) if is_system else env.scene.object_registry("name", name)
            
            self.object_scope[obj_inst] = entity
```

**inst_to_name 从哪来？**
- 在创建任务实例时通过 `save_task()` 保存
- 存储在场景的 JSON 文件中（`scene_metadata.task_metadata.inst_to_name`）
- 这就是 **TRO state 文件的核心部分**

---

### 6. reset(env) - 重置任务

```python
def reset(self, env):
    """每个 episode 开始时调用"""
    
    # 1. 调用父类 reset（重置场景、变量、terminations、rewards）
    super().reset(env)
    
    # 2. 使用预采样的机器人姿态
    if self.use_presampled_robot_pose:
        robot = self.get_agent(env)
        presampled_poses = env.scene.get_task_metadata(key="robot_poses")
        
        # 转换为小写
        presampled_poses = {k.lower(): v for k, v in presampled_poses.items()}
        
        # 选择通用或特定于模型的姿态
        if "robot" in presampled_poses:
            available_poses = presampled_poses["robot"]
        elif robot.model in presampled_poses:
            available_poses = presampled_poses[robot.model]
        else:
            raise KeyError(f"No presampled robot pose found for {robot.model}!")
        
        # 选择姿态（随机或固定）
        if self.randomize_presampled_pose:
            robot_pose = random.choice(available_poses)
        else:
            robot_pose = available_poses[0]
        
        # 设置机器人姿态
        robot.set_position_orientation(robot_pose["position"], robot_pose["orientation"])
    
    # 3. 唤醒所有任务相关对象
    for obj in self.object_scope.values():
        if obj is not None and isinstance(obj, DatasetObject):
            obj.wake()  # 启用物理模拟
```

**与 Evaluator 的 load_task_instance 的关系**:
- `reset()` 设置机器人姿态
- `load_task_instance()` 恢复对象状态（通过 `object_scope`）

---

### 7. _evaluate_predicate() - 评估谓词

```python
def _evaluate_predicate(self, predicate_name, *entities):
    """评估 BDDL 谓词是否为真"""
    from omnigibson.utils.bddl_utils import evaluate_bddl_predicate
    
    # 将符号实例转换为实际对象
    return evaluate_bddl_predicate(
        predicate_name, 
        *[self.object_scope[ent] for ent in entities]
    )
```

**示例**:
```python
# BDDL: (toggled_on radio_receiver.n.01_1)
self._evaluate_predicate("toggled_on", "radio_receiver.n.01_1")
# → evaluate_bddl_predicate("toggled_on", <DatasetObject: radio_wjqvxz>)
# → radio_wjqvxz.states[ToggledOn].get_value() == True

# BDDL: (ontop radio_receiver.n.01_1 table.n.02_1)
self._evaluate_predicate("ontop", "radio_receiver.n.01_1", "table.n.02_1")
# → evaluate_bddl_predicate("ontop", <radio object>, <table object>)
# → radio.states[OnTop].get_value(table) == True
```

**谓词类型**:
- **Unary** (单元): `cooked`, `sliced`, `toggled_on`, `open`, `folded`
- **Binary** (二元): `ontop`, `inside`, `touching`, `nextto`
- **系统相关**: `contains` (粒子系统), `saturated` (吸收)

---

### 8. _create_termination_conditions() - 创建终止条件

```python
def _create_termination_conditions(self):
    """BehaviorTask 的终止条件"""
    terminations = dict()
    
    # 1. Timeout: 防止无限循环
    terminations["timeout"] = Timeout(max_steps=self._termination_config["max_steps"])
    
    # 2. PredicateGoal: 检查 BDDL 目标是否达成
    terminations["predicate"] = PredicateGoal(
        check_goal_fn=lambda: self.compiled_task.check_goal(self._evaluate_predicate),
    )
    
    return terminations
```

**PredicateGoal 的工作流程**:

```python
# 在每个 step() 中调用
done, goal_status = self.compiled_task.check_goal(self._evaluate_predicate)

# compiled_task.check_goal() 内部：
for i, goal_condition in enumerate(self.goal_conditions):
    # goal_condition 是一个 Predicate 对象
    # 例如: Predicate(name="toggled_on", entities=["radio_receiver.n.01_1"])
    
    if goal_condition.evaluate(evaluate_fn):  # 调用 _evaluate_predicate
        satisfied.append(i)
    else:
        unsatisfied.append(i)

all_satisfied = len(unsatisfied) == 0
goal_status = {"satisfied": satisfied, "unsatisfied": unsatisfied}

return all_satisfied, goal_status
```

---

### 9. _create_reward_functions() - 创建奖励函数

```python
def _create_reward_functions(self):
    """BehaviorTask 的奖励函数"""
    rewards = dict()
    
    # PotentialReward: 基于任务完成度
    rewards["potential"] = PotentialReward(
        potential_fcn=self.get_potential,
        r_potential=self._reward_config["r_potential"],
    )
    
    return rewards

def get_potential(self, env):
    """计算当前任务完成度（势能）"""
    _, satisfied_predicates = self.compiled_task.check_goal(self._evaluate_predicate)
    
    n_satisfied = len(satisfied_predicates["satisfied"])
    n_total = n_satisfied + len(satisfied_predicates["unsatisfied"])
    
    success_score = n_satisfied / n_total
    
    # 返回负值，这样完成度越高，势能越低（符合物理直觉）
    return -success_score
```

**奖励计算示例**:

```python
# 任务有 5 个目标谓词
# t=0: 0/5 满足 → potential = -0.0 = 0.0
# t=1: 1/5 满足 → potential = -0.2 = -0.2
#      reward = (potential_t - potential_t-1) * r_potential
#             = (-0.2 - 0.0) * 1.0 = -0.2

# 等等，这看起来是负奖励！

# 查看 PotentialReward 的实现：
class PotentialReward:
    def _step(self, task, env, action):
        current_potential = self.potential_fcn(env)
        reward = (self.previous_potential - current_potential) * self.r_potential
        self.previous_potential = current_potential
        return reward
    
# 所以实际上：
# reward = (previous - current) * r_potential
#        = (0.0 - (-0.2)) * 1.0 = +0.2  ✓ 正奖励！
```

**奖励设计哲学**:
- 势能函数返回负的完成度
- 奖励 = 势能减少量
- 完成更多目标 → 势能降低 → 正奖励
- 未完成任何目标 → 势能不变 → 零奖励

---

### 10. _get_obs(env) - 获取观察

```python
def _get_obs(self, env):
    """获取任务特定的低维观察"""
    low_dim_obs = dict()
    
    # 1. 收集所有非系统对象
    obj_entries = []
    for inst, obj in self.object_scope.items():
        if not is_system_bddl_inst(inst):
            obj_entries.append((inst, obj, obj is not None))
    
    # 2. 批量计算旋转（效率优化）
    objs_rpy = T.quat2euler(th.stack([
        obj.states[Pose].get_value()[1] if obj_exist else th.tensor([0,0,0,1.0])
        for _, obj, obj_exist in obj_entries
    ]))
    objs_rpy_cos = th.cos(objs_rpy)
    objs_rpy_sin = th.sin(objs_rpy)
    
    # 3. 为每个对象添加观察
    agent = self.get_agent(env)
    
    for (inst, obj, obj_exist), obj_rpy, obj_rpy_cos, obj_rpy_sin in zip(
        obj_entries, objs_rpy, objs_rpy_cos, objs_rpy_sin
    ):
        if obj_exist:
            low_dim_obs[f"{inst}_real"] = th.tensor([1.0])  # 对象存在
            low_dim_obs[f"{inst}_pos"] = obj.states[Pose].get_value()[0]  # 位置 (3,)
            low_dim_obs[f"{inst}_ori_cos"] = obj_rpy_cos  # 旋转 cos (3,)
            low_dim_obs[f"{inst}_ori_sin"] = obj_rpy_sin  # 旋转 sin (3,)
            
            # 检查每个手臂是否抓住该对象
            if obj.name != agent.name:
                for arm in agent.arm_names:
                    grasping = agent.is_grasping(arm=arm, candidate_obj=obj)
                    low_dim_obs[f"{inst}_in_gripper_{arm}"] = th.tensor([float(grasping)])
        else:
            # 对象不存在（未来对象或未分配）→ 填充零
            low_dim_obs[f"{inst}_real"] = th.zeros(1)
            low_dim_obs[f"{inst}_pos"] = th.zeros(3)
            low_dim_obs[f"{inst}_ori_cos"] = th.zeros(3)
            low_dim_obs[f"{inst}_ori_sin"] = th.zeros(3)
            for arm in agent.arm_names:
                low_dim_obs[f"{inst}_in_gripper_{arm}"] = th.zeros(1)
    
    return low_dim_obs, dict()
```

**观察示例** (turning_on_radio):

```python
{
    "radio_receiver.n.01_1_real": tensor([1.0]),
    "radio_receiver.n.01_1_pos": tensor([2.3, 1.5, 0.8]),
    "radio_receiver.n.01_1_ori_cos": tensor([1.0, 0.0, 0.0]),
    "radio_receiver.n.01_1_ori_sin": tensor([0.0, 0.0, 0.0]),
    "radio_receiver.n.01_1_in_gripper_left": tensor([0.0]),
    "radio_receiver.n.01_1_in_gripper_right": tensor([0.0]),
    
    "table.n.02_1_real": tensor([1.0]),
    "table.n.02_1_pos": tensor([2.5, 1.0, 0.0]),
    "table.n.02_1_ori_cos": tensor([1.0, 0.0, 0.0]),
    "table.n.02_1_ori_sin": tensor([0.0, 0.0, 0.0]),
    "table.n.02_1_in_gripper_left": tensor([0.0]),
    "table.n.02_1_in_gripper_right": tensor([0.0]),
    
    ...
}
```

**为什么使用 cos/sin 表示旋转？**
- 避免角度的不连续性（-π 和 +π 是同一个角度）
- 神经网络更容易学习连续的 cos/sin 值

---

### 11. _step_termination() - 扩展终止检查

```python
def _step_termination(self, env, action, info=None):
    """添加目标状态信息到 info"""
    
    # 1. 调用父类方法
    done, info = super()._step_termination(env=env, action=action, info=info)
    
    # 2. 添加目标状态详情
    info["goal_status"] = self._termination_conditions["predicate"].goal_status
    
    return done, info
```

**返回的 info 结构**:

```python
info = {
    "success": True,  # 任务是否成功
    "termination_conditions": {
        "timeout": {"done": False, "success": False},
        "predicate": {"done": True, "success": True}
    },
    "goal_status": {  # BehaviorTask 特有
        "satisfied": [0],     # 满足的目标索引
        "unsatisfied": []     # 未满足的目标索引
    }
}
```

---

## 对象范围管理

### 动态更新回调

BehaviorTask 注册回调来自动更新 `object_scope`：

```python
def _update_bddl_scope_from_added_obj(self, obj):
    """对象被添加到场景时调用"""
    for inst, entity in self.object_scope.items():
        if (entity is None and 
            not is_system_bddl_inst(inst) and
            obj.category in set(og_categories_from_bddl_inst(inst))):
            self.object_scope[inst] = obj
            return

def _update_bddl_scope_from_removed_obj(self, obj):
    """对象被移除时调用"""
    for inst, entity in self.object_scope.items():
        if entity is not None and not is_system_bddl_inst(inst) and obj.name == entity.name:
            self.object_scope[inst] = None
            return
```

**使用场景**:
- 切片操作：原对象消失，生成多个切片
- 烹饪：生成新的烹饪产物
- 动态对象生成

---

## 任务保存和加载

### save_task() - 保存任务实例

```python
def save_task(self, env, save_dir=None, override=False, task_relevant_only=False, suffix=None):
    """将当前场景配置保存到 JSON 文件"""
    
    # 1. 构建保存路径
    save_dir = save_dir or os.path.join(
        get_dataset_path("2026-challenge-task-instances"),
        "scenes", self.scene_name, "json"
    )
    
    fname = self.get_cached_activity_scene_filename(
        scene_model=self.scene_name,
        activity_name=self.activity_name,
        activity_definition_id=self.activity_definition_id,
        activity_instance_id=self.activity_instance_id,
    )
    # 例如: "Rs_int_task_turning_on_radio_0_0_template"
    
    path = os.path.join(save_dir, f"{fname}.json")
    if task_relevant_only:
        path = path.replace(".json", "-tro_state.json")
    if suffix is not None:
        path = path.replace(".json", f"-{suffix}.json")
    
    # 2. 保存
    if task_relevant_only:
        # 只保存任务相关对象的状态（TRO state）
        task_relevant_state_dict = {
            bddl_name: bddl_obj.dump_state(serialized=False)
            for bddl_name, bddl_obj in env.task.object_scope.items()
            if bddl_obj is not None and "agent" not in bddl_name
        }
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        with open(path, "w+") as f:
            json.dump(task_relevant_state_dict, f, cls=TorchEncoder, indent=4)
    else:
        # 保存整个场景状态
        self.update_bddl_scope_metadata(env)
        env.scene.save(json_path=path)
```

**TRO state 文件示例**:

```json
{
    "radio_receiver.n.01_1": {
        "name": "radio_wjqvxz",
        "pos": [2.3, 1.5, 0.8],
        "quat": [0, 0, 0, 1],
        "joint_positions": {...},
        "states": {
            "ToggledOn": false,
            "OnTop": {"table_dining_kwxenz": true}
        }
    },
    "table.n.02_1": {
        "name": "table_dining_kwxenz",
        "pos": [2.5, 1.0, 0.0],
        "quat": [0, 0, 0, 1],
        ...
    }
}
```

---

## 与其他组件的交互

### 1. 与 Evaluator 的关系

```python
class Evaluator:
    def load_task_instance(self, instance_id):
        """加载任务实例"""
        # 1. 读取 TRO state 文件
        tro_file_path = get_task_instance_path(
            scene_model, filename, mode=self.mode
        )
        with open(tro_file_path, "r") as f:
            tro_state = json.load(f)
        
        # 2. 通过 task.object_scope 恢复对象状态
        for obj_name, obj_state in tro_state.items():
            self.env.task.object_scope[obj_name].load_state(obj_state)
        
        # 3. 稳定物理
        for _ in range(25):
            og.sim.step_physics()
            entity.keep_still()
```

**关键点**:
- Evaluator 不直接操作场景对象
- 通过 `task.object_scope` 间接访问
- `object_scope` 是 BDDL 实例和模拟对象的桥梁

---

### 2. 与 BDDL 的关系

```
BDDL 文件 (符号层)
    ↓ parse_base_scope()
_base_conditions (条件对象)
    ↓ compile(scene_layout)
compiled_task (可执行任务)
    ↓ check_goal(_evaluate_predicate)
bool (目标是否达成)
    ↑ 
object_scope (物理层)
```

**数据流**:
1. BDDL 定义了符号实例和谓词
2. `object_scope` 将符号实例映射到物理对象
3. `_evaluate_predicate` 在物理对象上评估谓词
4. `compiled_task.check_goal()` 汇总所有谓词结果

---

### 3. 完整的执行流程

```python
# ===== 环境创建 =====
env = og.Environment(configs={
    "task": {
        "type": "BehaviorTask",
        "activity_name": "turning_on_radio",
        "activity_definition_id": 0,
        "activity_instance_id": 0,
    }
})

# 内部调用：
# 1. task = BehaviorTask(...)
# 2. task.load(env)
#    → task.update_activity()        # 加载 BDDL
#    → task.initialize_activity()    # 分配对象
# 3. og.sim.play()
# 4. task.post_play_load(env)        # 计算观察维度

# ===== Episode 循环 =====
obs = env.reset()
# → task.reset(env)
#   → 设置机器人姿态
#   → 唤醒对象

for step in range(max_steps):
    action = policy.act(obs)
    obs, reward, done, truncated, info = env.step(action)
    
    # 内部调用：
    # 1. og.sim.step()                    # 物理模拟
    # 2. reward, done, info = task.step(env, action)
    #    → done, info = task._step_termination()
    #       → self.compiled_task.check_goal(self._evaluate_predicate)
    #    → reward, info = task._step_reward()
    #       → potential = task.get_potential(env)
    
    if done:
        success = info["done"]["success"]
        goal_status = info["goal_status"]
        print(f"Success: {success}")
        print(f"Satisfied goals: {goal_status['satisfied']}")
        break
```

---

## 高级特性

### 1. 通配符支持

某些任务使用通配符来增加灵活性：

```lisp
(:objects
    ?plate.n.04_* - plate.n.04  ; 任意数量的盘子
    table.n.02_1 - table.n.02
)

(:goal
    (and
        (forall
            (?plate.n.04 - plate.n.04)
            (ontop ?plate.n.04 table.n.02_1)  ; 所有盘子都在桌上
        )
    )
)
```

**编译过程**:
1. 扫描场景：找到 `dining_room_0` 中有 4 个盘子
2. 展开实例：`plate.n.04_1` 到 `plate.n.04_4`
3. 展开目标：为每个盘子生成 `(ontop plate.n.04_i table.n.02_1)`

---

### 2. 房间分配

```python
# BDDL 指定房间类型
(:init
    (inroom table.n.02_1 living_room)
)

# 场景可能有多个客厅实例
scene.rooms = {
    "living_room_0": [...],
    "living_room_1": [...],
    "bedroom_0": [...],
}

# BehaviorTask 确定使用哪个实例
room_instances = task._determine_room_instances(env)
# → {"living_room": "living_room_0"}  # 基于对象实际位置
```

---

### 3. 演示收集支持

```python
# 逐步显示目标指令
instruction, color, objects = task.show_instruction()
# instruction = "Turn on the radio"
# color = [255, 51, 51]  # 红色（未完成）
# objects = [<radio object>]

# 迭代到下一个指令
task.iterate_instruction()
```

**用途**:
- 人类演示收集
- 可视化当前子目标
- 逐步完成复杂任务

---

## 配置和属性

### 默认配置

```python
@classproperty
def default_termination_config(cls):
    return {
        "max_steps": 500,
    }

@classproperty
def default_reward_config(cls):
    return {
        "r_potential": 1.0,
    }

@classproperty
def valid_scene_types(cls):
    return {Scene}  # 任何场景都可以
```

### 任务名称

```python
@property
def name(self):
    """返回完整的任务名称"""
    name_base = super().name  # "BehaviorTask"
    return f"{name_base}_{self.activity_name}_{self.activity_definition_id}_{self.activity_instance_id}"
    # 例如: "BehaviorTask_turning_on_radio_0_0"
```

---

## 常见问题

### Q1: object_scope 什么时候被填充？

**A**: 分阶段填充

1. `update_activity()`: 创建空的 `object_scope`（所有值为 `None`）
2. `initialize_activity()`:
   - 在线模式：通过 `sampler.assign_objects()` 填充
   - 离线模式：通过 `assign_object_scope_with_cache()` 填充
3. `_compile_with_rooms()`: 可能添加通配符实例
4. `_assign_wildcard_instances()`: 填充剩余的通配符实例

---

### Q2: 为什么需要两种模式（在线/离线）？

**A**: 不同的使用场景

- **在线采样** (`online_object_sampling=True`):
  - 用于生成新的任务实例
  - 随机放置对象和设置状态
  - 用于数据集创建

- **离线模式** (`online_object_sampling=False`):
  - 用于评估和训练
  - 从预先保存的配置加载
  - 保证可重现性

---

### Q3: 谓词评估如何工作？

**A**: 通过 object states 系统

```python
# BDDL 谓词: (cooked apple.n.01_1)
task._evaluate_predicate("cooked", "apple.n.01_1")

# 内部流程：
# 1. 获取对象
obj = task.object_scope["apple.n.01_1"]  # <DatasetObject: apple_fvzlbq>

# 2. 调用 evaluate_bddl_predicate
evaluate_bddl_predicate("cooked", obj)

# 3. 映射到 object state
from omnigibson.object_states import Cooked
return obj.states[Cooked].get_value()  # True/False
```

**谓词到状态的映射**:
- `cooked` → `Cooked` state
- `sliced` → `Sliced` state
- `ontop` → `OnTop` state
- `inside` → `Inside` state
- `toggled_on` → `ToggledOn` state

---

### Q4: 未来对象是什么？

**A**: 运行时生成的对象

```lisp
(:init
    (future sliced_apple.n.01_1)  ; 这个对象稍后生成
)

(:goal
    (sliced apple.n.01_1)  ; 切苹果
    (cooked sliced_apple.n.01_1)  ; 烹饪切片
)
```

- 初始时 `object_scope["sliced_apple.n.01_1"] = None`
- 当 `apple.n.01_1` 被切片时，生成切片对象
- 回调函数自动更新 `object_scope`

---

## 总结

**BehaviorTask 的核心职责**:

1. **符号到物理的桥梁**: 将 BDDL 符号定义映射到物理模拟
2. **对象管理**: 维护 `object_scope` 作为实例注册表
3. **谓词评估**: 通过 object states 评估 BDDL 谓词
4. **任务编译**: 处理通配符和房间分配
5. **可重现性**: 支持保存和加载任务实例

**关键数据结构**:
```python
object_scope: Dict[str, BaseObject]  # BDDL 实例 → 模拟对象
compiled_task: CompiledTask          # 编译后的任务定义
activity_goal_conditions: List[Predicate]  # 目标谓词列表
```

**与其他组件的关系**:
- **BDDL**: 提供符号定义
- **Evaluator**: 通过 `object_scope` 加载实例
- **Object States**: 评估谓词
- **Scene**: 提供对象和元数据
- **Sampler**: 分配对象和状态

BehaviorTask 是 BEHAVIOR-1K 的核心，它让机器人能够理解和执行复杂的家庭任务！
