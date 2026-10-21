# BDDL vs PDDL 以及 TAMP 应用详解

> **回答三个核心问题**：
> 1. BDDL 是否就是去掉 action 的 PDDL？
> 2. BEHAVIOR 中有单独的 action 定义吗？
> 3. 如果要应用 TAMP 是否需要转换成 PDDL？

---

## 问题 1：BDDL 是否就是去掉 action 的 PDDL？

### 简短回答

**是的，但不完全是**。BDDL 确实是基于 PDDL 的简化版本，主要去掉了 `:action` 定义，但还做了其他重要改动。

### 详细对比

#### PDDL 的完整结构

```lisp
;; ==================== 标准 PDDL Domain ====================
(define (domain household)
    (:requirements :strips :adl :typing)
    
    (:types
        object location
        robot - object
        item - object
    )
    
    (:predicates 
        (at ?obj - object ?loc - location)
        (holding ?r - robot ?i - item)
        (ontop ?i1 - item ?i2 - item)
        (toggled_on ?i - item)
    )
    
    ;; ============ PDDL 的核心：Action 定义 ============
    (:action grasp
        :parameters (?r - robot ?i - item ?loc - location)
        :precondition (and 
            (at ?r ?loc)
            (at ?i ?loc)
            (not (exists (?x - item) (holding ?r ?x)))
        )
        :effect (and 
            (holding ?r ?i)
            (not (at ?i ?loc))
        )
    )
    
    (:action place
        :parameters (?r - robot ?i - item ?target - item)
        :precondition (and 
            (holding ?r ?i)
        )
        :effect (and 
            (not (holding ?r ?i))
            (ontop ?i ?target)
        )
    )
    
    (:action toggle_on
        :parameters (?r - robot ?i - item)
        :precondition (and 
            (at ?r ?loc)
            (at ?i ?loc)
        )
        :effect (toggled_on ?i)
    )
)

;; ==================== 标准 PDDL Problem ====================
(define (problem turn-on-radio)
    (:domain household)
    (:objects 
        robot1 - robot
        radio1 - item
        table1 - item
        living_room - location
    )
    (:init 
        (at robot1 living_room)
        (at radio1 living_room)
        (ontop radio1 table1)
        (not (toggled_on radio1))
    )
    (:goal 
        (toggled_on radio1)
    )
)
```

#### BDDL 的结构

```lisp
;; ==================== BDDL Domain ====================
(define (domain behavior-1k)
    (:requirements :strips :adl)
    
    ;; ❌ 没有 :types - BDDL 不使用类型系统
    
    (:predicates 
        (cooked ?obj1)
        (frozen ?obj1)
        (open ?obj1)
        (toggled_on ?obj1)
        (ontop ?obj1 ?obj2)
        (inside ?obj1 ?obj2)
        (touching ?obj1 ?obj2)
        ;; ... 更多谓词
    )
    
    ;; ❌ 没有 :action 定义 - 这是 BDDL 的核心特点！
)

;; ==================== BDDL Problem ====================
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
        (ontop agent.n.01_1 floor.n.01_1)
    )
    
    (:goal 
        (and 
            (toggled_on ?radio_receiver.n.01_1)
        )
    )
)
```

### 关键差异总结

| 方面 | PDDL | BDDL |
|------|------|------|
| **:action 定义** | ✅ 有（核心功能） | ❌ 无（刻意移除） |
| **:types** | ✅ 有类型系统 | ❌ 无（使用 WordNet synset） |
| **Preconditions** | ✅ 在 action 中定义 | ❌ 无（只有 :init） |
| **Effects** | ✅ 在 action 中定义 | ❌ 无（只有 :goal） |
| **对象命名** | 简单名称 | WordNet 语义名称（如 `radio_receiver.n.01_1`） |
| **房间表示** | 可选 | 内置 `inroom` 谓词 |
| **用途** | 规划（planning） | 任务目标定义 |

### 为什么 BDDL 去掉了 action？

**设计哲学差异**：

1. **PDDL 的目标**：自动规划（Automated Planning）
   - 给定初始状态和目标状态
   - 自动搜索 action 序列达到目标
   - 需要显式定义 action 的 precondition 和 effect

2. **BDDL 的目标**：任务规范（Task Specification）
   - 只定义"任务是什么"，不定义"如何完成"
   - 将规划问题留给具体的规划器（可以是 LLM、强化学习、传统规划器等）
   - 更灵活，不绑定特定的规划方法

**类比**：
- **PDDL** = 详细的菜谱（每步怎么做）
- **BDDL** = 菜品描述（要做成什么样）

---

## 问题 2：BEHAVIOR 中有单独的 action 定义吗？

### 简短回答

**有，但不在 BDDL 中**。BEHAVIOR 通过 **Action Primitives** 定义动作，这是一个独立的系统。

### Action Primitives 系统

**位置**：`OmniGibson/omnigibson/action_primitives/`

#### 1. 符号级 Action Primitives

```python
# ==================== StarterSemanticActionPrimitiveSet ====================
# 文件：starter_semantic_action_primitives.py

class StarterSemanticActionPrimitiveSet(IntEnum):
    """符号级的 action 定义"""
    
    GRASP = auto(), "Grasp an object"
    PLACE_ON_TOP = auto(), "Place the currently grasped object on top of another object"
    PLACE_INSIDE = auto(), "Place the currently grasped object inside another object"
    OPEN = auto(), "Open an object"
    CLOSE = auto(), "Close an object"
    NAVIGATE_TO = auto(), "Navigate to an object"
    RELEASE = auto(), "Release an object"
    TOGGLE_ON = auto(), "Toggle an object on"
    TOGGLE_OFF = auto(), "Toggle an object off"
```

#### 2. 更完整的 Action Primitives

```python
# ==================== SymbolicSemanticActionPrimitiveSet ====================
# 文件：symbolic_semantic_action_primitives.py

class SymbolicSemanticActionPrimitiveSet(IntEnum):
    """更完整的符号 action 集合"""
    
    # 导航
    NAVIGATE_TO_OBJ = auto()
    NAVIGATE_TO_POSE = auto()
    
    # 操纵
    GRASP = auto()
    PLACE_ON_TOP = auto()
    PLACE_INSIDE = auto()
    RELEASE = auto()
    
    # 状态改变
    OPEN = auto()
    CLOSE = auto()
    TOGGLE_ON = auto()
    TOGGLE_OFF = auto()
    
    # 复杂操作
    SOAK_UNDER = auto()
    SOAK_INSIDE = auto()
    WIPE = auto()
    CUT = auto()
    
    # 低层控制
    LEFT_GRASP = auto()
    RIGHT_GRASP = auto()
    # ... 更多
```

#### 3. Action Primitive 的实现

每个 action primitive 都有完整的实现，包含：

```python
class StarterSemanticActionPrimitives(BaseActionPrimitiveSet):
    """Action Primitives 的实现类"""
    
    def __init__(self, env, robot, ...):
        self.env = env
        self.robot = robot
        # 初始化运动规划器等
        self.curobo_mg = CuRoboMotionGenerator(...)
    
    # ==================== GRASP Action ====================
    def _grasp(self, obj):
        """
        Grasp an object
        
        实现步骤：
        1. 导航到对象附近
        2. 计算抓取姿态
        3. 规划运动轨迹（使用 CuRobo）
        4. 执行抓取
        5. 验证抓取成功
        
        Preconditions (隐式检查):
        - Robot 可以到达对象
        - 对象是可抓取的
        - Robot 的手是空的
        
        Effects (隐式实现):
        - Robot 持有对象
        - 对象不再在原位置
        """
        # 1. 导航到对象
        yield from self._navigate_to_obj(obj)
        
        # 2. 计算抓取姿态
        grasp_pose = get_grasp_poses_for_object_sticky(obj)
        
        # 3. 规划运动
        motion_plan = self.curobo_mg.plan_to_pose(grasp_pose)
        
        # 4. 执行运动
        yield from self._execute_motion(motion_plan)
        
        # 5. 闭合夹爪
        yield from self._close_gripper()
        
        # 6. 验证
        if self.robot.is_grasping(obj):
            return True
        else:
            raise ActionPrimitiveError("Grasp failed")
    
    # ==================== TOGGLE_ON Action ====================
    def _toggle_on(self, obj):
        """
        Toggle an object on
        
        实现步骤：
        1. 导航到对象
        2. 找到开关位置
        3. 执行按压/拨动动作
        4. 验证对象状态改变
        
        Preconditions (隐式):
        - 对象有 ToggledOn 状态
        - Robot 可以到达对象
        
        Effects (隐式):
        - 对象的 ToggledOn 状态变为 True
        """
        # 1. 导航
        yield from self._navigate_to_obj(obj)
        
        # 2. 获取开关位置
        button_position = self._get_button_position(obj)
        
        # 3. 移动手到按钮
        yield from self._move_hand_to_position(button_position)
        
        # 4. 按压
        yield from self._press_button()
        
        # 5. 验证状态改变
        from omnigibson.object_states import ToggledOn
        if obj.states[ToggledOn].get_value():
            return True
        else:
            raise ActionPrimitiveError("Toggle failed")
```

### Action Primitives vs PDDL Actions 对比

| 方面 | PDDL Action | BEHAVIOR Action Primitive |
|------|-------------|---------------------------|
| **定义位置** | Domain 文件 | Python 代码 |
| **Preconditions** | 显式声明（符号） | 隐式检查（代码） |
| **Effects** | 显式声明（符号） | 隐式实现（物理仿真） |
| **实现** | 无（由规划器解释） | 完整实现（运动规划+控制） |
| **连续参数** | 需要 streams | 直接采样/优化 |
| **执行** | 符号层 | 物理层 |
| **验证** | 符号检查 | 物理状态查询 |

### 为什么这样设计？

**优势**：
1. **灵活性**：Action 实现可以任意复杂（运动规划、视觉、学习）
2. **真实性**：直接在物理仿真中执行，不是符号抽象
3. **可扩展**：添加新 action 不需要修改 BDDL
4. **分离关注点**：任务定义（BDDL）与执行（Primitives）解耦

**对应关系**：

```
BDDL Goal: (toggled_on radio_receiver.n.01_1)
           ↓
需要执行的 Action: TOGGLE_ON
           ↓
Action Primitive 实现: _toggle_on(radio_obj)
           ↓
底层控制: 运动规划 + 关节控制 + 碰撞检测
           ↓
物理仿真: 机器人按下按钮
           ↓
状态更新: radio_obj.states[ToggledOn] = True
           ↓
目标检查: compiled_task.check_goal() → True
```

---

## 问题 3：如果要应用 TAMP 是否需要转换成 PDDL？

### 简短回答

**不一定需要转换，有三种方案**：

1. **方案 A（推荐）**：直接使用 BDDL + Action Primitives（现代 TAMP）
2. **方案 B**：转换为 PDDL（传统 TAMP）
3. **方案 C**：混合方案（BDDL + PDDLStream）

### 方案 A：现代 TAMP（无需转换 PDDL）

这是 **BEHAVIOR-1K 项目已经实现的方案**（见 `doc/tamp/TAMP_IMPLEMENTATION_SUMMARY.md`）

#### 架构

```
┌─────────────────────────────────────────────────────┐
│                 现代 LLM-based TAMP                   │
└─────────────────────────────────────────────────────┘

[Task 层] BDDL 定义
    ├─ Initial State: (ontop radio table), (not (toggled_on radio))
    ├─ Goal State: (toggled_on radio)
    └─ Objects: [radio, table, robot]
         ↓
[Planning 层] LLM Planner（无需 PDDL）
    └─ 输入: BDDL atoms + available actions
    └─ 输出: Subgoal sequence
         [
             Subgoal(action="navigate_to", target="radio"),
             Subgoal(action="toggle_on", target="radio")
         ]
         ↓
[Execution 层] Action Primitives
    └─ 每个 subgoal 映射到具体的 primitive
         navigate_to → _navigate_to_obj(radio)
         toggle_on → _toggle_on(radio)
         ↓
[Motion 层] CuRobo + IK
    └─ 运动规划、碰撞检测、轨迹优化
         ↓
[Control 层] Joint Controllers
    └─ 关节位置/速度控制
         ↓
[Simulation 层] OmniGibson
    └─ 物理仿真、状态更新
```

#### 代码示例

```python
# ==================== 无需 PDDL 的 TAMP 实现 ====================
from tamp.planners.llm_planner import LLMPlanner
from tamp.executors.primitive_executor import PrimitiveExecutor
from tamp.utils.bddl_utils import load_bddl_task

# 1. 加载 BDDL 任务
task_info = load_bddl_task("turning_on_radio", instance_id=0)

# task_info = {
#     "initial_state": {
#         Atom("ontop", ("radio_receiver.n.01_1", "table.n.02_1")),
#         Atom("not_toggled_on", ("radio_receiver.n.01_1",))
#     },
#     "goal_state": {
#         Atom("toggled_on", ("radio_receiver.n.01_1",))
#     },
#     "objects": ["radio_receiver.n.01_1", "table.n.02_1", "agent.n.01_1"]
# }

# 2. 创建 LLM Planner（不需要 PDDL actions）
planner = LLMPlanner(
    model="gpt-4",
    api_key=os.getenv("OPENAI_API_KEY")
)

# 3. 生成高层计划
plan = planner.plan(
    task_description="Turn on the radio",
    initial_state=task_info["initial_state"],
    goal_state=task_info["goal_state"],
    available_objects=task_info["objects"],
    available_actions=[
        "navigate_to", "grasp", "place_on_top", 
        "toggle_on", "open", "close"
    ]
)

# plan = SubgoalPlan(
#     subgoals=[
#         Subgoal(action_type="navigate_to", target_object="radio_receiver.n.01_1"),
#         Subgoal(action_type="toggle_on", target_object="radio_receiver.n.01_1")
#     ]
# )

# 4. 执行计划（使用 Action Primitives）
executor = PrimitiveExecutor(env, robot)

for subgoal in plan.subgoals:
    print(f"Executing: {subgoal}")
    
    # 自动映射到对应的 primitive
    # navigate_to → StarterSemanticActionPrimitiveSet.NAVIGATE_TO
    # toggle_on → StarterSemanticActionPrimitiveSet.TOGGLE_ON
    
    success = yield from executor.execute_subgoal(subgoal)
    
    if not success:
        # 失败后重新规划
        current_state = extract_current_state(env)
        plan = planner.replan(
            original_plan=plan,
            current_state=current_state,
            failure_info={"subgoal": subgoal, "reason": "execution_failed"}
        )

# 5. 验证目标达成
goal_satisfied = env.task.compiled_task.check_goal(
    env.task._evaluate_predicate
)
print(f"Task completed: {goal_satisfied}")
```

#### 优势

✅ **无需转换**：直接使用 BDDL，不需要写 PDDL actions  
✅ **LLM 规划**：利用大模型的常识推理能力  
✅ **现成的 primitives**：BEHAVIOR-1K 已有 50+ action primitives  
✅ **自然语言**：可解释性强，易于调试  
✅ **灵活**：可以处理 1000+ 多样化任务  

#### 劣势

❌ **依赖 LLM API**：需要 API key 和网络连接  
❌ **不保证最优**：没有搜索保证  
❌ **成本**：每次规划都调用 API  

---

### 方案 B：转换为 PDDL（传统 TAMP）

如果你坚持使用传统 TAMP 规划器（如 FastDownward、PDDLStream），需要转换。

#### 转换步骤

##### 1. 从 BDDL 提取信息

```python
# ==================== 从 BDDL 提取 ====================
def bddl_to_pddl_info(bddl_task):
    """从 BDDL 提取 PDDL 需要的信息"""
    
    # 1. 提取对象和类型
    objects = {}
    for synset, instances in bddl_task.parsed_objects.items():
        # WordNet synset → PDDL type
        pddl_type = synset.split('.')[0]  # "radio_receiver.n.01" → "radio_receiver"
        for inst in instances:
            objects[inst] = pddl_type
    
    # 2. 提取初始状态
    initial_predicates = []
    for cond in bddl_task.parsed_initial_conditions:
        if cond[0] == "ontop":
            initial_predicates.append(f"(ontop {cond[1]} {cond[2]})")
        elif cond[0] == "not":
            if cond[1][0] == "toggled_on":
                initial_predicates.append(f"(not (toggled_on {cond[1][1]}))")
    
    # 3. 提取目标
    goal_predicates = []
    for cond in bddl_task.parsed_goal_conditions:
        # 递归处理嵌套结构
        goal_predicates.extend(extract_goal_atoms(cond))
    
    return {
        "objects": objects,
        "init": initial_predicates,
        "goal": goal_predicates
    }
```

##### 2. 手动定义 PDDL Actions

```lisp
;; ==================== 手动编写 PDDL Domain ====================
(define (domain behavior-household)
    (:requirements :strips :typing)
    
    (:types
        object
        robot item - object
        location
    )
    
    (:predicates 
        (at ?obj - object ?loc - location)
        (holding ?r - robot ?i - item)
        (ontop ?i1 - item ?i2 - item)
        (inside ?i1 - item ?i2 - item)
        (toggled_on ?i - item)
        (open ?i - item)
        (cooked ?i - item)
        (hand_empty ?r - robot)
    )
    
    ;; ==================== 需要手动定义每个 action ====================
    (:action navigate_to_obj
        :parameters (?r - robot ?obj - object ?loc - location)
        :precondition (at ?obj ?loc)
        :effect (at ?r ?loc)
    )
    
    (:action grasp
        :parameters (?r - robot ?i - item ?loc - location)
        :precondition (and 
            (at ?r ?loc)
            (at ?i ?loc)
            (hand_empty ?r)
        )
        :effect (and 
            (holding ?r ?i)
            (not (at ?i ?loc))
            (not (hand_empty ?r))
        )
    )
    
    (:action place_on_top
        :parameters (?r - robot ?i - item ?target - item)
        :precondition (holding ?r ?i)
        :effect (and 
            (ontop ?i ?target)
            (not (holding ?r ?i))
            (hand_empty ?r)
        )
    )
    
    (:action toggle_on
        :parameters (?r - robot ?i - item ?loc - location)
        :precondition (and 
            (at ?r ?loc)
            (at ?i ?loc)
        )
        :effect (toggled_on ?i)
    )
    
    ;; 需要为所有可能的操作定义 action...
    ;; 对于 BEHAVIOR-1K 的 1000+ 任务，这是巨大的工作量！
)
```

##### 3. 生成 PDDL Problem 文件

```python
def generate_pddl_problem(bddl_task, task_name):
    """从 BDDL 生成 PDDL problem 文件"""
    
    info = bddl_to_pddl_info(bddl_task)
    
    pddl_content = f"""
(define (problem {task_name})
    (:domain behavior-household)
    
    (:objects
"""
    
    # 添加对象
    for obj, obj_type in info["objects"].items():
        pddl_content += f"        {obj} - {obj_type}\n"
    
    pddl_content += "    )\n\n    (:init\n"
    
    # 添加初始状态
    for pred in info["init"]:
        pddl_content += f"        {pred}\n"
    
    pddl_content += "    )\n\n    (:goal\n        (and\n"
    
    # 添加目标
    for pred in info["goal"]:
        pddl_content += f"            {pred}\n"
    
    pddl_content += "        )\n    )\n)"
    
    return pddl_content
```

##### 4. 使用传统 TAMP 规划器

```python
# ==================== 使用 PDDLStream ====================
from pddlstream.language.constants import print_solution
from pddlstream.algorithms.focused import solve_focused

# 1. 定义 streams（处理连续参数）
def get_grasp_pose_stream():
    """生成抓取姿态的 stream"""
    def generator(obj):
        # 采样抓取姿态
        for i in range(10):
            grasp_pose = sample_grasp_pose(obj)
            yield (grasp_pose,)
    return generator

# 2. 定义 PDDL+ 问题（带 streams）
pddl_problem = {
    'domain': load_pddl('behavior_domain.pddl'),
    'problem': generate_pddl_problem(bddl_task, 'turning_on_radio'),
    'streams': [
        ('grasp-pose', get_grasp_pose_stream()),
        # 更多 streams...
    ]
}

# 3. 规划
solution = solve_focused(pddl_problem)
print_solution(solution)

# 4. 执行（映射 PDDL action → Action Primitive）
for action in solution:
    action_name = action[0]
    params = action[1:]
    
    if action_name == "grasp":
        robot, obj, pose = params
        yield from primitives._grasp(obj)
    elif action_name == "toggle_on":
        robot, obj = params
        yield from primitives._toggle_on(obj)
```

#### 优势

✅ **理论保证**：搜索算法保证找到解（如果存在）  
✅ **最优性**：可以找到最优或近似最优解  
✅ **成熟工具**：FastDownward、PDDLStream 等工具链完善  

#### 劣势

❌ **工作量大**：需要为每个 action 写 precondition 和 effect  
❌ **搜索空间爆炸**：复杂任务难以处理  
❌ **不灵活**：难以处理新任务和边界情况  
❌ **连续参数**：需要额外的 stream 定义  

---

### 方案 C：混合方案

结合两者优势：

```python
# ==================== 混合方案 ====================

# 1. 用 LLM 生成粗粒度计划（无需 PDDL）
coarse_plan = llm_planner.plan(...)
# → ["navigate_to_radio", "toggle_on"]

# 2. 对每个子任务用 PDDL 规划细粒度动作
for subgoal in coarse_plan:
    if subgoal.needs_detailed_planning:
        # 生成 PDDL problem
        pddl_problem = subgoal_to_pddl(subgoal)
        
        # 用传统规划器
        detailed_plan = pddl_planner.solve(pddl_problem)
        
        # 执行
        execute_detailed_plan(detailed_plan)
    else:
        # 直接用 primitive
        execute_primitive(subgoal)
```

---

## 实践建议

### 对于 BEHAVIOR-1K 项目

**推荐方案 A（无需 PDDL）**，理由：

1. ✅ **已经实现**：项目中已有 TAMP 实现（`doc/tamp/`）
2. ✅ **现成的 primitives**：50+ action primitives 可直接使用
3. ✅ **适合 1000+ 任务**：LLM 能处理多样化任务
4. ✅ **易于扩展**：添加新任务不需要修改 domain

### 什么时候需要转换为 PDDL？

只在以下情况下考虑：

1. 需要**最优性保证**（如机器人竞赛）
2. 需要**正式验证**（如安全关键系统）
3. 有**现成的 PDDL domain**可复用
4. 任务**结构简单、规则明确**

### 实际工作流程建议

```
阶段 1：快速原型（方案 A）
    ├─ 用 LLM planner + BDDL
    ├─ 测试 10-20 个任务
    └─ 评估成功率

阶段 2：问题分析
    ├─ LLM 失败的任务 → 考虑传统规划器
    ├─ Primitive 失败 → 改进 motion planning
    └─ 目标定义问题 → 修改 BDDL

阶段 3：混合优化（可选）
    ├─ 简单任务 → LLM
    ├─ 复杂任务 → PDDL + LLM
    └─ 学习哪些任务适合哪种方法
```

---

## 总结

### 核心答案

1. **BDDL vs PDDL**：
   - BDDL = PDDL - :action - :types + WordNet语义
   - 设计目标不同：任务规范 vs 自动规划

2. **Action 定义**：
   - ✅ 有，在 Action Primitives 系统中（Python 代码）
   - ❌ 不在 BDDL 中（刻意分离）

3. **TAMP 应用**：
   - **推荐**：直接用 BDDL + Action Primitives + LLM Planner
   - **可选**：转换为 PDDL（工作量大，不推荐）
   - **最佳**：混合方案（根据任务选择）

### 关键洞察

BEHAVIOR-1K 的设计理念是：
- **任务定义与执行分离**
- **灵活性优于最优性**
- **可扩展性优于完备性**

这使得它更适合：
- 大规模、多样化的任务集
- 快速原型和实验
- 与现代 AI（LLM、RL）结合

而传统 PDDL-based TAMP 更适合：
- 小规模、结构化的任务
- 需要正式保证的场景
- 工业机器人应用

**你的 TAMP 实现已经在 `doc/tamp/` 中采用了现代方案，这是正确的选择！** 🎯
