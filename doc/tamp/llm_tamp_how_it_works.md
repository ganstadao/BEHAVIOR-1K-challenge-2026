# LLM-based TAMP 如何工作：从 BDDL 到可执行 Action

> **核心问题**：
> 1. 传统 PDDL 有固定的 action graph → 可以搜索
> 2. BDDL 只有初始和目标 → 如何找到中间的 subgoals？
> 3. LLM 如何确保生成的节点是可达的？
> 4. 如何生成和验证"表达式树"的正确性？

---

## 问题的本质

### 传统 PDDL-based TAMP 的工作原理

```
┌────────────────────────────────────────────────────────┐
│          传统 PDDL Planning (Search-based)              │
└────────────────────────────────────────────────────────┘

[Domain 定义] - 预先定义好的 action graph
    (:action navigate
        :parameters (?r - robot ?o - object)
        :precondition (exists (?l - location) (at ?o ?l))
        :effect (at ?r ?o)
    )
    (:action toggle_on
        :parameters (?r - robot ?o - object)
        :precondition (and (at ?r ?o) (has_button ?o))
        :effect (toggled_on ?o)
    )
         ↓
[Search Algorithm] - 在固定 graph 上搜索
    - A* / Dijkstra
    - 从 initial state 出发
    - 尝试所有 applicable actions（满足 precondition）
    - 计算 heuristic（距离 goal 的估计）
    - 回溯、剪枝
         ↓
[Action Sequence] - 保证正确的路径
    [navigate(robot, radio), toggle_on(robot, radio)]
         ↓
[执行] - 低层运动规划
    每个 action 调用 motion planner

优势：
✅ 完备性：如果有解，一定能找到
✅ 最优性：可以找到最短路径
✅ 正确性：precondition 保证每步都可达

劣势：
❌ 需要预先定义所有 actions
❌ 搜索空间随复杂度指数增长
❌ 难以处理新场景和边界情况
❌ 对于 BEHAVIOR-1K 的 1000+ 任务，domain 定义工作量巨大
```

### LLM-based TAMP 的工作原理

```
┌────────────────────────────────────────────────────────┐
│          LLM-based Planning (Generation-based)          │
└────────────────────────────────────────────────────────┘

[BDDL 定义] - 只有初始和目标
    (:init (not (toggled_on radio)))
    (:goal (toggled_on radio))
         ↓
[LLM Prompt] - 将问题编码为自然语言
    "Given: robot, radio on table, radio is off
     Goal: radio is on
     Available actions: navigate_to, grasp, toggle_on, ...
     Generate a plan."
         ↓
[LLM Generation] - 直接生成 subgoals（不搜索！）
    利用训练数据中的常识知识
    "To turn on radio, need to navigate then toggle"
         ↓
[Subgoal Sequence] - 不保证正确，但通常合理
    [navigate_to(radio), toggle_on(radio)]
         ↓
[执行 + 验证] - 在执行时发现问题
    执行 navigate_to → 成功 ✓
    执行 toggle_on → 可能失败 ✗
         ↓ (如果失败)
[Replanning] - 给 LLM 反馈，重新生成
    "toggle_on failed because robot too far.
     Generate new plan."

优势：
✅ 无需预先定义 actions
✅ 利用常识推理
✅ 可处理新场景
✅ 生成速度快（不搜索）

劣势：
❌ 不保证完备性
❌ 不保证最优性
❌ 可能生成不可达的 subgoals
❌ 依赖 LLM API
```

---

## 核心机制：LLM 如何"知道" Subgoals 是可达的？

**简短回答**：**它不知道！它只是基于训练数据中的模式进行概率推理。**

### 机制 1：Implicit Preconditions（隐式前置条件）

LLM 在训练时见过大量的任务规划数据，学到了**隐式的前置条件**：

```python
# ==================== LLM 的隐式知识 ====================
# LLM 训练数据中的模式（简化表示）

# Pattern 1: "toggle" 类 action 需要先 "navigate"
{
    "context": "robot not near object, want to toggle object",
    "solution": ["navigate_to(object)", "toggle(object)"],
    "frequency": 10000+
}

# Pattern 2: "place" 类 action 需要先 "grasp"
{
    "context": "robot not holding object, want to place object",
    "solution": ["navigate_to(object)", "grasp(object)", "navigate_to(target)", "place(target)"],
    "frequency": 8000+
}

# Pattern 3: "grasp" 不需要其他前置（如果已经 navigate）
{
    "context": "robot near object, hands empty",
    "solution": ["grasp(object)"],
    "frequency": 15000+
}

# 当 LLM 看到 "turn on radio" 时：
# 1. 识别 "turn on" → 匹配 "toggle" pattern
# 2. 查找 pattern 中的 preconditions → "navigate"
# 3. 生成 subgoals: [navigate_to, toggle_on]
```

**关键洞察**：LLM 不是在**搜索** action graph，而是在**回忆**训练数据中的模式。

### 机制 2：Few-shot Learning（示例学习）

在 prompt 中提供示例，引导 LLM 生成正确的结构：

```python
# ==================== llm_planner.py 中的 few-shot example ====================
def _get_few_shot_examples(self) -> str:
    return """
**Example 1**: Turn on the radio
{
  "reasoning": "Need to navigate to radio first, then toggle it on",
  "subgoals": [
    {
      "description": "Navigate to the radio",
      "action_type": "navigate_to",
      "target_object": "radio_receiver.n.01_1",
      "preconditions": [],                           # ← 显式的前置条件
      "effects": ["near(robot, radio)"]              # ← 显式的效果
    },
    {
      "description": "Toggle on the radio",
      "action_type": "toggle_on",
      "target_object": "radio_receiver.n.01_1",
      "preconditions": ["near(robot, radio)"],       # ← 依赖上一步的效果
      "effects": ["toggled_on(radio)"]
    }
  ]
}

**Example 2**: Place apple on table
{
  "reasoning": "Need to navigate to apple, grasp it, navigate to table, then place it",
  "subgoals": [
    {
      "description": "Navigate to apple",
      "action_type": "navigate_to",
      "target_object": "apple.n.01_1",
      "preconditions": [],
      "effects": ["near(robot, apple)"]
    },
    {
      "description": "Grasp the apple",
      "action_type": "grasp",
      "target_object": "apple.n.01_1",
      "preconditions": ["near(robot, apple)", "hands_empty"],  # ← 多个前置条件
      "effects": ["holding(robot, apple)"]
    },
    {
      "description": "Navigate to table",
      "action_type": "navigate_to",
      "target_object": "table.n.02_1",
      "preconditions": ["holding(robot, apple)"],
      "effects": ["near(robot, table)"]
    },
    {
      "description": "Place apple on table",
      "action_type": "place_on_top",
      "target_object": "apple.n.01_1",
      "preconditions": ["holding(robot, apple)", "near(robot, table)"],
      "effects": ["ontop(apple, table)", "hands_empty"]
    }
  ]
}
"""
```

**LLM 学习的内容**：
1. Subgoals 的结构（description, action_type, target_object）
2. Preconditions 和 effects 的链式依赖
3. 常见的 action 序列模式

### 机制 3：Action Schema（动作模式）

在 prompt 中提供每个 action 的"模式"，帮助 LLM 理解可用操作：

```python
# ==================== llm_planner.py: _format_action_schemas() ====================
schemas = {
    "navigate_to": "Move the robot to be near an object. Args: target_object",
    
    "grasp": "Pick up an object. Args: target_object. "
             "Precondition: near object, hands empty",  # ← 隐式前置条件提示
    
    "place_on_top": "Place held object on another object. Args: target_surface. "
                    "Precondition: holding object",      # ← 明确依赖关系
    
    "toggle_on": "Turn on an object. Args: target_object",
    
    # ... 更多
}
```

**LLM 推理过程**（伪代码）：

```python
# 任务：turn on radio
# 目标：toggled_on(radio)

# LLM 的"思考"过程（简化）：
1. 查看目标：toggled_on(radio)
2. 找到匹配的 action：toggle_on
3. 查看 toggle_on 的 schema：没有明确的 precondition
4. 但从 few-shot examples 学到：toggle 类 action 通常需要 navigate
5. 检查当前状态：robot 不在 radio 附近（从 initial_state 推断）
6. 生成 subgoal 1：navigate_to(radio)
   - preconditions: []
   - effects: [near(robot, radio)]
7. 生成 subgoal 2：toggle_on(radio)
   - preconditions: [near(robot, radio)]  # 依赖 subgoal 1 的 effect
   - effects: [toggled_on(radio)]          # 满足最终目标
```

### 机制 4：Runtime Validation（运行时验证）

**关键**：LLM 生成的 subgoals **不保证正确**，所以需要在执行时验证！

```python
# ==================== primitive_executor.py ====================
def execute_subgoal(self, subgoal: Subgoal) -> Generator[Any, None, bool]:
    """执行 subgoal，带运行时验证"""
    
    # 步骤 1：检查 action 是否存在
    if not self.can_execute(subgoal):
        subgoal.status = SubgoalStatus.FAILED
        subgoal.error_message = f"Unknown action type: {subgoal.action_type}"
        return False  # ← LLM 生成了不存在的 action
    
    # 步骤 2：解析对象（验证对象存在）
    try:
        target_obj = self._resolve_object(subgoal.target_object)
    except Exception as e:
        subgoal.status = SubgoalStatus.FAILED
        subgoal.error_message = f"Object not found: {subgoal.target_object}"
        return False  # ← LLM 引用了不存在的对象
    
    # 步骤 3：执行 primitive（这里会隐式检查前置条件）
    try:
        yield from self.primitives.apply_ref(primitive_enum, target_obj)
        
        # 步骤 4：验证效果（可选但推荐）
        if subgoal.action_type == "toggle_on":
            from omnigibson.object_states import ToggledOn
            if not target_obj.states[ToggledOn].get_value():
                raise Exception("Toggle action did not change state")
        
        return True  # ← 成功！
        
    except Exception as e:
        subgoal.status = SubgoalStatus.FAILED
        subgoal.error_message = str(e)
        return False  # ← 执行失败（可能前置条件不满足）
```

### 机制 5：Replanning on Failure（失败后重新规划）

当执行失败时，将错误信息反馈给 LLM，让它重新生成计划：

```python
# ==================== llm_planner.py: replan() ====================
def replan(
    self,
    original_plan: SubgoalPlan,
    current_state: State,
    failure_info: Dict[str, Any],
) -> SubgoalPlan:
    """失败后重新规划"""
    
    # 构建反馈 prompt
    prompt = f"""
**REPLANNING CONTEXT**:
The previous plan failed at step {failure_info['step']}:
- Failed action: {failure_info['action']}
- Error: {failure_info['error']}
- Current state: {current_state}

Please generate a new plan that avoids this failure.
"""
    
    # LLM 重新生成，考虑失败信息
    return self.plan(...)

# ==================== 示例 ====================
# 原始计划：
# 1. toggle_on(radio)  ← 直接尝试，忘记 navigate

# 执行：
# 1. toggle_on(radio) → FAILED: "robot too far from object"

# Replanning：
# LLM 收到错误："robot too far from object"
# LLM 推理："需要先 navigate"
# 新计划：
# 1. navigate_to(radio)
# 2. toggle_on(radio)
```

---

## 具体示例：Turning on Radio

### 完整的数据流

```python
# ==================== 1. BDDL 输入 ====================
bddl_task = {
    "initial_state": {
        Atom("ontop", ("radio_receiver.n.01_1", "table.n.02_1")),
        Atom("not_toggled_on", ("radio_receiver.n.01_1",)),
        Atom("not_near", ("agent.n.01_1", "radio_receiver.n.01_1")),
    },
    "goal_state": {
        Atom("toggled_on", ("radio_receiver.n.01_1",))
    },
    "available_objects": ["radio_receiver.n.01_1", "table.n.02_1", "agent.n.01_1"],
    "available_actions": ["navigate_to", "grasp", "place_on_top", "toggle_on", ...]
}

# ==================== 2. LLM Prompt ====================
prompt = f"""
Task: Turn on the radio

Current State:
- robot is not near radio_receiver.n.01_1
- radio_receiver.n.01_1 is on table.n.02_1
- radio_receiver.n.01_1 is not toggled on

Goal State:
- radio_receiver.n.01_1 is toggled on

Available Objects: radio_receiver.n.01_1, table.n.02_1, agent.n.01_1
Available Actions:
  - navigate_to: Move robot to be near an object
  - grasp: Pick up an object (Precondition: near object, hands empty)
  - toggle_on: Turn on an object
  - ...

Instructions:
Generate a step-by-step plan in JSON format.

Example: [few-shot examples...]
"""

# ==================== 3. LLM 生成 ====================
llm_response = {
    "reasoning": "Robot needs to be near radio to toggle it. First navigate, then toggle.",
    "subgoals": [
        {
            "description": "Navigate to the radio",
            "action_type": "navigate_to",
            "target_object": "radio_receiver.n.01_1",
            "preconditions": [],
            "effects": ["near(agent, radio_receiver.n.01_1)"]
        },
        {
            "description": "Toggle on the radio",
            "action_type": "toggle_on",
            "target_object": "radio_receiver.n.01_1",
            "preconditions": ["near(agent, radio_receiver.n.01_1)"],
            "effects": ["toggled_on(radio_receiver.n.01_1)"]
        }
    ]
}

# ==================== 4. 解析为 Subgoal 对象 ====================
subgoal_1 = Subgoal(
    description="Navigate to the radio",
    action_type="navigate_to",
    target_object="radio_receiver.n.01_1",
    preconditions=[],
    effects=["near(agent, radio_receiver.n.01_1)"]
)

subgoal_2 = Subgoal(
    description="Toggle on the radio",
    action_type="toggle_on",
    target_object="radio_receiver.n.01_1",
    preconditions=["near(agent, radio_receiver.n.01_1)"],
    effects=["toggled_on(radio_receiver.n.01_1)"]
)

plan = SubgoalPlan(
    subgoals=[subgoal_1, subgoal_2],
    task_description="Turn on the radio",
    reasoning="Robot needs to be near radio to toggle it..."
)

# ==================== 5. 执行 Subgoal 1 ====================
executor = PrimitiveExecutor(env, robot)

# 执行 navigate_to
success_1 = yield from executor.execute_subgoal(subgoal_1)
# 内部流程：
# 1. 映射 "navigate_to" → SymbolicSemanticActionPrimitiveSet.NAVIGATE_TO
# 2. 解析 "radio_receiver.n.01_1" → <DatasetObject: radio_wjqvxz>
# 3. 调用 primitives.apply_ref(NAVIGATE_TO, radio_obj)
# 4. Primitive 内部：
#    - 路径规划（使用 CuRobo）
#    - 运动控制（关节控制器）
#    - 碰撞检测
# 5. 验证：检查 robot 是否在 radio 附近
# → success_1 = True ✓

# ==================== 6. 执行 Subgoal 2 ====================
success_2 = yield from executor.execute_subgoal(subgoal_2)
# 内部流程：
# 1. 映射 "toggle_on" → SymbolicSemanticActionPrimitiveSet.TOGGLE_ON
# 2. 解析 "radio_receiver.n.01_1" → <DatasetObject: radio_wjqvxz>
# 3. 调用 primitives.apply_ref(TOGGLE_ON, radio_obj)
# 4. Primitive 内部：
#    - 找到按钮位置
#    - 移动手到按钮
#    - 按压动作
# 5. 验证：检查 radio_obj.states[ToggledOn].get_value()
# → success_2 = True ✓

# ==================== 7. 最终验证 ====================
goal_satisfied = env.task.compiled_task.check_goal(
    env.task._evaluate_predicate
)
# compiled_task.check_goal() 评估：
# - (toggled_on radio_receiver.n.01_1) → True
# → goal_satisfied = True ✓

print("Task completed successfully!")
```

---

## 关键问题的回答

### Q1: 如何得到中间的 subgoals？

**A: 通过 LLM 的模式匹配和推理，而不是搜索**

- **传统方法**：在预定义的 action graph 上搜索
- **LLM 方法**：从训练数据中学习的隐式知识直接生成

```python
# 传统方法：搜索
for action in available_actions:
    if precondition_satisfied(current_state, action):
        new_state = apply_effect(current_state, action)
        if closer_to_goal(new_state):
            search_queue.add(new_state)

# LLM 方法：生成
prompt = f"Given {current_state}, goal {goal_state}, generate plan"
plan = llm.generate(prompt)  # 一次生成，不搜索
```

### Q2: 如何确保 subgoals 是可达的？

**A: 不能确保！只能通过以下方式增加成功率**

1. **Few-shot examples**：教 LLM 正确的模式
2. **Action schemas**：明确 preconditions
3. **Runtime validation**：执行时检查
4. **Replanning**：失败后重新生成

```python
# 成功率来源
成功率 = f(
    LLM 的训练数据质量,        # 见过类似任务吗？
    Few-shot examples 的质量,  # 示例是否相关？
    Action schemas 的清晰度,   # 说明是否明确？
    Execution feedback,        # 失败能否恢复？
)

# 不保证 100%，但在实践中通常 > 80%
```

### Q3: 表达式树如何生成？

**A: 不生成！LLM-based TAMP 使用扁平的 subgoal 序列，不是树**

```python
# ==================== 对比 ====================

# PDDL Planning: 生成 search tree（表达式树）
#        root (initial state)
#       /    |    \
#    act1  act2  act3
#    /  \    |
#  s1   s2  s3
#       |
#     goal

# LLM Planning: 生成 linear sequence（扁平序列）
# [subgoal1, subgoal2, subgoal3, ...]
# 每个 subgoal 只是一个结构体，不是树节点

# ==================== SubgoalPlan 的结构 ====================
class SubgoalPlan:
    subgoals: List[Subgoal]  # 线性列表，不是树！
    task_description: str
    reasoning: str

class Subgoal:
    description: str
    action_type: str
    target_object: str
    preconditions: List[str]  # 仅用于 LLM 推理，不用于搜索
    effects: List[str]        # 仅用于 LLM 推理，不用于验证
```

**为什么不需要树？**
- LLM 直接生成**线性序列**（基于常识推理）
- 不需要**回溯**（如果失败，直接重新生成整个序列）
- 不需要**剪枝**（不进行搜索）

### Q4: 如何验证正确性？

**A: 分层验证**

```python
# ==================== 验证层次 ====================

# 层次 1：语法验证（生成时）
def validate_syntax(plan):
    """检查 plan 的 JSON 结构"""
    for subgoal in plan.subgoals:
        assert "action_type" in subgoal
        assert "target_object" in subgoal
        assert subgoal.action_type in available_actions

# 层次 2：语义验证（执行前 - 可选）
def validate_semantics(plan, env):
    """检查 objects 和 actions 是否存在"""
    for subgoal in plan.subgoals:
        # 对象存在？
        obj = env.scene.object_registry("name", subgoal.target_object)
        assert obj is not None
        
        # Action 可执行？
        assert executor.can_execute(subgoal)
        
        # Preconditions 满足？（可选，依赖 symbolic state）
        for pre in subgoal.preconditions:
            assert check_predicate(pre, current_state)

# 层次 3：执行验证（执行时）
def validate_execution(subgoal, result):
    """检查执行结果"""
    if result.success:
        # 验证 effects 是否达成
        for effect in subgoal.effects:
            assert check_predicate(effect, current_state)
    else:
        # 记录失败，触发 replanning
        trigger_replan(subgoal, result.error)

# 层次 4：最终验证（任务结束）
def validate_goal(env):
    """检查最终目标是否达成"""
    return env.task.compiled_task.check_goal(
        env.task._evaluate_predicate
    )
```

**实际中的权衡**：
- ✅ **层次 1**：总是做（必需）
- ⚠️ **层次 2**：部分做（对象存在检查，action 可执行性检查）
- ✅ **层次 3**：总是做（执行必然会验证）
- ✅ **层次 4**：总是做（任务目标）

---

## 实际表现和局限性

### 成功案例（简单任务）

```python
# 任务：Turn on radio
# LLM 生成：[navigate_to(radio), toggle_on(radio)]
# 执行：✓ 成功
# 原因：模式简单，训练数据中常见

# 任务：Place apple on table
# LLM 生成：[navigate_to(apple), grasp(apple), navigate_to(table), place_on_top(table)]
# 执行：✓ 成功
# 原因：标准 pick-and-place 模式
```

### 失败案例和恢复

```python
# ==================== 案例 1：遗漏 navigate ====================
# 任务：Open refrigerator
# LLM 生成（错误）：[open(refrigerator)]
# 执行：✗ 失败 - "robot too far from object"
# Replanning：[navigate_to(refrigerator), open(refrigerator)]
# 执行：✓ 成功

# ==================== 案例 2：忘记先 grasp ====================
# 任务：Place book inside drawer
# LLM 生成（错误）：[navigate_to(drawer), place_inside(drawer)]
# 执行：✗ 失败 - "robot not holding any object"
# Replanning：[navigate_to(book), grasp(book), navigate_to(drawer), open(drawer), place_inside(drawer)]
# 执行：✓ 成功

# ==================== 案例 3：复杂依赖 ====================
# 任务：Heat soup (需要先把汤放进微波炉，关门，再打开微波炉)
# LLM 生成（部分正确）：
#   [navigate_to(soup), grasp(soup), navigate_to(microwave), place_inside(microwave), toggle_on(microwave)]
# 执行：✗ 失败 - "microwave door is open, cannot toggle on"
# Replanning：
#   [..., place_inside(microwave), close(microwave), toggle_on(microwave)]
# 执行：✓ 成功
```

### 无法恢复的失败

```python
# ==================== 案例 1：物理不可达 ====================
# 任务：Place heavy object on high shelf
# LLM 生成：[..., place_on_top(shelf)]
# 执行：✗ 失败 - "motion planning failed, target unreachable"
# Replanning：尝试其他方法，仍失败
# 原因：物理限制，不是规划问题

# ==================== 案例 2：缺失工具 ====================
# 任务：Cut apple (但场景中没有刀)
# LLM 生成：[navigate_to(knife), grasp(knife), ..., cut(apple)]
# 执行：✗ 失败 - "object 'knife' not found"
# Replanning：无法恢复，任务无法完成
# 原因：场景限制

# ==================== 案例 3：复杂因果链 ====================
# 任务：需要 10+ 步的复杂任务
# LLM 生成：可能遗漏中间步骤
# 执行：多次 replan 后仍失败
# 原因：超出 LLM 的规划深度
```

---

## 总结：LLM-TAMP vs PDDL-TAMP

| 方面 | PDDL-TAMP | LLM-TAMP |
|------|-----------|----------|
| **Subgoal 来源** | 搜索 action graph | LLM 生成（基于模式） |
| **可达性保证** | ✅ 保证（precondition） | ❌ 不保证（概率） |
| **正确性** | ✅ 逻辑正确 | ⚠️ 通常正确 |
| **完备性** | ✅ 如果有解必找到 | ❌ 可能找不到解 |
| **最优性** | ✅ 可保证 | ❌ 不保证 |
| **可扩展性** | ❌ 需要定义 actions | ✅ 利用常识 |
| **适用范围** | 小规模、结构化 | 大规模、多样化 |
| **恢复能力** | 回溯搜索 | Replanning |

### 何时选择 LLM-TAMP？

✅ **推荐使用**：
- 任务多样化（如 BEHAVIOR-1K 的 1000+ 任务）
- 难以预先定义所有 actions
- 需要快速原型
- 有 LLM API 访问

❌ **不推荐**：
- 需要正式验证（安全关键系统）
- 需要最优性保证
- 没有网络连接
- 成本敏感

### 混合方案

**最佳实践**：结合两者优势

```python
# 高层规划：LLM（快速、灵活）
coarse_plan = llm_planner.plan(task)

# 低层规划：PDDL or Motion Planner（精确、可靠）
for subgoal in coarse_plan:
    if subgoal.needs_precise_planning:
        detailed_plan = pddl_planner.plan(subgoal)
    else:
        detailed_plan = [subgoal]
    
    execute(detailed_plan)
```

---

## 最终答案

**你的直觉部分正确**："turning on radio" 的 subgoal 确实很简单，可能只需要 `[navigate_to, toggle_on]`。

**关键区别**：
1. **传统 PDDL**：通过搜索**发现**这个序列（保证正确）
2. **LLM-based**：通过推理**生成**这个序列（通常正确）

**表达式树**：
- **PDDL**：需要构建搜索树（表达式树）
- **LLM**：不需要树，直接生成线性序列

**正确性保证**：
- **PDDL**：逻辑保证（preconditions）
- **LLM**：概率保证（训练数据 + 执行验证 + replanning）

对于 BEHAVIOR-1K 这样的大规模、多样化任务集，**LLM-based TAMP 是更实用的选择**，尽管它不提供传统规划器的理论保证。
