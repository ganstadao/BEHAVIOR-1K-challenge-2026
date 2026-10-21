# TAMP 系统深度解析：从理论到实现

## 目录
1. [核心概念澄清](#核心概念澄清)
2. [当前实现的真相](#当前实现的真相)
3. [Action 和控制流程](#action-和控制流程)
4. [BDDL vs PDDL](#bddl-vs-pddl)
5. [TANDEM 的方法](#tandem-的方法)
6. [泛化性问题](#泛化性问题)
7. [VLA + Skeleton 的可能性](#vla-skeleton-的可能性)

---

## 核心概念澄清

### 什么是真正的 TAMP？

**Task and Motion Planning (TAMP)** 应该包含：

```
1. Task Planning (符号规划)
   - 输入：PDDL domain + PDDL problem
   - 输出：符号动作序列 [navigate(A), grasp(B), place(C)]
   - 工具：Fast-Forward, A*, STRIPS 等规划器

2. Motion Planning (运动规划)
   - 输入：符号动作 (如 grasp(B))
   - 输出：可执行的关节轨迹
   - 工具：RRT, PRM, CuRobo 等

3. 反馈循环
   - 如果运动规划失败 → 回到任务规划，重新规划
   - 这是 TAMP 的核心：符号层和几何层的交互
```

### 当前实现 ≠ TAMP

**当前实现**：
```
Fixed Skeleton → Motion Primitives → CuRobo → Joint Commands
```

**缺失的部分**：
- ❌ 没有符号规划器
- ❌ 没有 PDDL
- ❌ 没有反馈循环
- ❌ Skeleton 是硬编码的

**当前实现更像**：
- Hierarchical Planning with Fixed Skeleton
- 或者 Scripted Behaviors with Motion Primitives

---

## 当前实现的真相

### Skeleton 的结构

```python
skeleton = [
    Subgoal(
        action_type='navigate_to',
        target_object='radio_receiver.n.01_1',
        preconditions=['reachable(living_room)'],
        effects=['near(robot, radio_receiver.n.01_1)']
    ),
    Subgoal(
        action_type='press_button',
        target_object='radio_receiver.n.01_1',
        preconditions=['near(robot, radio_receiver.n.01_1)'],
        effects=['toggled_on(radio_receiver.n.01_1)']
    )
]
```

**注意**：
- `preconditions` 和 `effects` 只是**装饰**，当前没有被使用！
- 没有规划器检查这些条件
- Skeleton 是在 `FixedSkeletonPlanner` 中**手写**的

### 执行流程

```
1. TAMPEvaluator.run_evaluation()
   ↓
2. planner.plan() → 返回硬编码的 skeleton
   ↓
3. executor.execute_skeleton(skeleton)
   ↓
4. 对每个 subgoal:
   - primitive_wrapper.execute_navigate_to(target_obj)
     ↓
   - self.primitives.apply_ref(NAVIGATE_TO, target_obj)
     ↓
   - StarterSemanticActionPrimitives 内部：
     * CuRobo 规划路径
     * 生成关节轨迹
     * yield action (24维向量)
     ↓
   - env.step(action) → 执行一步
```

---

## Action 和控制流程

### Action 是什么？

**Action** 就是机器人的**关节目标位置**向量。

对于 R1Pro：
```python
action = [
    # Base (3): [x_vel, y_vel, yaw_vel] 或 [x_pos, y_pos, yaw_pos]
    0.1, 0.0, 0.0,
    
    # Trunk (1): trunk_joint position
    0.0,
    
    # Arm Left (7): 7个关节的目标位置
    0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7,
    
    # Gripper Left (2): 2个手指的位置
    0.0, 0.0,
    
    # Arm Right (7)
    0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7,
    
    # Gripper Right (2)
    0.0, 0.0
]
# 总共 24 维
```

### env.step() 的工作原理

```python
# 伪代码
def step(action):
    # 1. 将 action 分配给各个控制器
    base_action = action[0:3]
    trunk_action = action[3:4]
    arm_left_action = action[4:11]
    # ...
    
    # 2. 每个控制器计算力矩/速度
    base_controller.compute_control(base_action)
    arm_left_controller.compute_control(arm_left_action)
    # ...
    
    # 3. 物理仿真步进
    for _ in range(physics_steps_per_action):
        simulator.step()  # PhysX 物理引擎
    
    # 4. 获取新的观察
    obs = get_observations()
    
    return obs, reward, done, info
```

### 运动规划的层次

```
高层: navigate_to(radio)
  ↓ (StarterSemanticActionPrimitives)
中层: CuRobo 规划 → 轨迹 [q0, q1, ..., qN]
  ↓ (逐帧 yield)
低层: action = q_i (关节位置)
  ↓ (env.step)
物理: 控制器 + 物理引擎 → 机器人移动
```

---

## BDDL vs PDDL

### BDDL (Behavior Domain Definition Language)

**来源**: BEHAVIOR-1K 数据集

**特点**：
- 描述**具体任务实例**的初始状态和目标
- 面向对象：每个对象有类别、属性、关系
- 包含物理约束：`onTop`, `inside`, `under` 等
- 不包含动作定义

**示例**（turning_on_radio）:
```python
# BDDL (简化)
initial_conditions:
  - agent.n.01_1 in living_room
  - radio_receiver.n.01_1 in living_room
  - radio_receiver.n.01_1.states.ToggledOn = False

goal_conditions:
  - radio_receiver.n.01_1.states.ToggledOn = True
```

### PDDL (Planning Domain Definition Language)

**来源**: 经典 AI 规划

**特点**：
- 两部分：domain.pddl (动作定义) + problem.pddl (具体问题)
- 定义**通用**的动作模式
- 包含 preconditions 和 effects
- 可以被规划器直接使用

**示例**（turning_on_radio）:
```lisp
;; domain.pddl
(define (domain household)
  (:predicates
    (near ?robot ?obj)
    (toggleable ?obj)
    (toggled-on ?obj)
  )
  
  (:action navigate-to
    :parameters (?robot ?obj)
    :precondition (and)
    :effect (near ?robot ?obj)
  )
  
  (:action press-button
    :parameters (?robot ?obj)
    :precondition (and 
      (near ?robot ?obj)
      (toggleable ?obj)
      (not (toggled-on ?obj))
    )
    :effect (toggled-on ?obj)
  )
)

;; problem.pddl
(define (problem turn-on-radio)
  (:domain household)
  (:objects
    robot - agent
    radio - radio_receiver
  )
  (:init
    (toggleable radio)
  )
  (:goal
    (toggled-on radio)
  )
)
```

### 关键区别

| 特性 | BDDL | PDDL |
|------|------|------|
| 用途 | 描述任务实例 | 定义规划域 |
| 包含动作？ | ❌ | ✅ |
| 可被规划器用？ | ❌ | ✅ |
| 物理细节 | 丰富 | 抽象 |
| 泛化性 | 低（具体实例） | 高（通用模式） |

---

## BDDL 到 PDDL 的转换

### 为什么需要转换？

**BDDL**: "radio_receiver.n.01_1 应该被打开"
**PDDL Planner**: "我需要动作定义才能规划！"

### 转换的挑战

1. **动作定义缺失**
   - BDDL 只说"目标是什么"
   - 不说"如何达到目标"
   - 需要人工/AI 定义动作

2. **粒度不匹配**
   - BDDL: 物理细节（位置、姿态、状态）
   - PDDL: 符号抽象（near, on, in）
   - 需要抽象化

3. **开放词汇**
   - BDDL: 任意对象类别
   - PDDL: 预定义的 predicates
   - 需要映射

### 转换示例（手工）

```python
def bddl_to_pddl(bddl_task):
    # 1. 提取对象
    objects = extract_objects(bddl_task)
    # radio_receiver.n.01_1 → radio
    
    # 2. 提取初始状态
    init = []
    for obj in objects:
        if obj.category == "radio_receiver":
            init.append(f"(toggleable {obj.name})")
            if not obj.states.ToggledOn:
                init.append(f"(not (toggled-on {obj.name}))")
    
    # 3. 提取目标
    goal = []
    for condition in bddl_task.goal_conditions:
        if condition.type == "ToggledOn":
            goal.append(f"(toggled-on {condition.object})")
    
    # 4. 生成 PDDL (需要预定义的 domain!)
    return generate_pddl_problem(objects, init, goal)
```

**问题**：动作定义从哪来？
- 答案：**手工定义** 或 **从知识库学习**

---

## TANDEM 的方法

论文：[TANDEM: Transformers for Autonomous Navigation and Dexterous Manipulation](https://arxiv.org/abs/2303.04912)

### TANDEM 做了什么？

**NOT** BDDL → PDDL！

TANDEM 的流程：
```
Language Instruction
  ↓ (LLM)
Subgoal Sequence (natural language)
  ↓ (LLM + Visual Grounding)
Grounded Subgoals (object instances)
  ↓ (Learned Policies)
Low-level Actions
```

### 关键创新

1. **Open-Vocabulary Predicates**
   - 不预定义 predicates
   - 用 LLM 理解自然语言描述
   - 例如："the robot should be near the red mug"

2. **Learned Low-Level Policies**
   - 不用传统运动规划
   - 训练神经网络策略完成子目标
   - 输入：(subgoal, observation)
   - 输出：action

3. **No PDDL Planning**
   - 不用符号规划器
   - LLM 直接生成子目标序列
   - 类似于你当前的 FixedSkeletonPlanner！

### TANDEM vs 传统 TAMP

| 特性 | 传统 TAMP | TANDEM |
|------|-----------|--------|
| Task Planning | PDDL planner | LLM |
| Motion Planning | CuRobo/RRT | Learned policy |
| 泛化性 | 低（固定 domain） | 高（open-vocab） |
| 可解释性 | 高 | 中 |
| 数据需求 | 低 | 高（需要训练） |

---

## 泛化性问题

### 你的担忧是正确的！

**PDDL 的局限**：
1. 固定的动作集合
2. 固定的 predicates
3. 人工定义的 domain
4. 难以处理新对象/新场景

### 为什么 BEHAVIOR 不用 PDDL？

BEHAVIOR-1K 的设计哲学：
- 600+ 任务，多样性极高
- 开放词汇：任意对象组合
- 物理真实性：不是纯符号
- 评估 embodied AI，不是规划器

### 当前趋势

**从 PDDL 到学习**：
```
传统: 手工 PDDL → 符号规划
     ↓
混合: LLM生成 → 部分符号
     ↓
端到端: VLA → 直接输出 action
```

---

## VLA + Skeleton 的可能性

### 你的想法很有潜力！

**架构**：
```
High-Level: Skeleton Planning (符号/LLM)
  ↓
Mid-Level: Subgoal Decomposition
  ↓
Low-Level: VLA Policy (学习的)
```

### 优势

1. **Skeleton 提供结构**
   - 长期规划
   - 任务分解
   - 可解释性

2. **VLA 提供灵活性**
   - 泛化到新对象
   - 处理不确定性
   - 端到端学习

### 类似的工作

1. **SayCan** (Google, 2022)
   - LLM 生成高层计划
   - Learned policies 执行子任务
   - 在真实机器人上工作

2. **Inner Monologue** (Google, 2023)
   - LLM + 反馈循环
   - 环境反馈引导重规划

3. **RT-2** (Google, 2023)
   - VLA 直接理解语言指令
   - 端到端：language → action

### 在 BEHAVIOR-1K 上的可能实现

```python
# 高层：Skeleton (LLM 或手工)
skeleton = [
    "navigate to table",
    "grasp radio button",
    "press button"
]

# 低层：VLA Policy
for subgoal in skeleton:
    # VLA 输入：language + observation
    while not is_subgoal_complete(subgoal):
        action = vla_model(
            language=subgoal,
            observation=get_obs()
        )
        env.step(action)
```

**优势**：
- 不需要 PDDL
- 不需要 preconditions（VLA 自己判断）
- 泛化性好（VLA 在大规模数据上训练）

---

## 总结与建议

### 当前实现的定位

你的实现是：
- ✅ 分层控制系统
- ✅ 使用 Motion Primitives
- ❌ 不是完整的 TAMP（缺少符号规划）

### 下一步方向

#### 选项1：补全 TAMP
- 实现 BDDL → PDDL 转换器
- 集成 PDDL planner (Fast-Forward/PDDL4J)
- 添加反馈循环

**难度**：高
**泛化性**：低（PDDL 固定）
**适合**：研究 TAMP 算法本身

#### 选项2：LLM + Primitives (类似 TANDEM)
- 用 LLM 生成 skeleton
- 保持当前的 primitives
- 添加反馈和重规划

**难度**：中
**泛化性**：中（LLM 泛化，primitives 受限）
**适合**：快速原型，开放词汇

#### 选项3：VLA + Skeleton (你的想法)
- 保持高层 skeleton
- 替换低层为 VLA policy
- 端到端学习

**难度**：高（需要训练 VLA）
**泛化性**：高
**适合**：长期研究，追求 SOTA

### 我的建议

**对于 BEHAVIOR-1K**：
1. 先用当前实现（Fixed Skeleton + Primitives）跑通流程
2. 收集失败案例，分析瓶颈
3. 根据瓶颈决定：
   - 如果是规划问题 → 加 LLM/PDDL
   - 如果是执行问题 → 改进 primitives 或换 VLA

**不要陷入过度工程**：
- BEHAVIOR-1K 的难点是**执行**，不是规划
- 大部分任务的 skeleton 都很简单
- 重点应该是：如何可靠地完成每个 subgoal

---

## 参考资料

### TAMP
- [TAMP Tutorial](https://arxiv.org/abs/2010.01083)
- [PDDLStream](https://github.com/caelan/pddlstream)

### BDDL
- [BEHAVIOR-1K Paper](https://arxiv.org/abs/2403.09227)
- [BDDL Docs](https://behavior.stanford.edu/bddl/index.html)

### LLM + Planning
- [SayCan](https://arxiv.org/abs/2204.01691)
- [Inner Monologue](https://arxiv.org/abs/2207.05608)
- [TANDEM](https://arxiv.org/abs/2303.04912)

### VLA
- [RT-2](https://arxiv.org/abs/2307.15818)
- [OpenVLA](https://arxiv.org/abs/2406.09246)

---

*文档创建时间：2024-10-20*
