# TAMP Implementation Summary

**Date**: 2026-10-11  
**Author**: LINJ0121  
**Status**: Prototype Complete ✓

## 项目概述

为BEHAVIOR-1K实现了一个现代化的TAMP (Task and Motion Planning) 系统，采用**LLM-based planning**而非传统的A*搜索。

## 核心决策

### 1. 为什么选择LLM而不是传统搜索？

- **传统方法（A*, PDDLStream）局限性**：
  - 需要显式定义所有PDDL actions和preconditions
  - 搜索空间随任务复杂度指数增长
  - 难以处理BEHAVIOR-1K的1000+任务的多样性
  - 2014年的技术，不适合现代复杂场景

- **LLM方法优势**：
  - 隐式包含常识推理能力
  - 可以通过few-shot learning适应新任务
  - 自然语言reasoning易于理解和调试
  - 失败后可以基于反馈进行replanning
  - 与现代AI生态系统兼容

### 2. 架构设计原则

- **模块化**: 每个组件独立，接口清晰
- **可扩展**: 通过抽象基类轻松添加新实现
- **LLM优先**: 但保留添加其他planner的能力
- **可观察**: 完整的日志和历史记录

## 实现的组件

### 目录结构
```
tamp/
├── core/                    # 核心数据结构
│   ├── symbols.py          # Predicate, Atom, State
│   └── subgoal.py          # Subgoal, SubgoalPlan
├── planners/                # 规划器
│   ├── base.py             # BasePlanner接口
│   └── llm_planner.py      # LLM规划器（GPT-4/Claude）
├── executors/               # 执行器
│   ├── base.py             # BaseExecutor接口
│   └── primitive_executor.py # OmniGibson primitives
├── utils/                   # 工具函数
│   └── bddl_utils.py       # BDDL解析
├── examples/                # 示例
│   └── turning_on_radio.py # 完整示例
├── tests/                   # 测试
│   └── test_basic.py       # 单元测试 ✓
├── config.py               # 配置
└── README.md               # 文档
```

### 1. Core (tamp/core/)

**symbols.py** - 符号状态表示
```python
Predicate("ontop", 2)  # 定义谓词
Atom("ontop", ("apple", "table"))  # 实例化
State = frozenset[Atom]  # 状态是原子的集合
```

**subgoal.py** - 高层子目标
```python
Subgoal(
    description="Navigate to radio",
    action_type="navigate_to",
    target_object="radio_receiver.n.01_1"
)

SubgoalPlan(
    subgoals=[...],
    task_description="Turn on the radio"
)
```

### 2. Planners (tamp/planners/)

**BasePlanner** - 抽象接口
```python
class BasePlanner(ABC):
    @abstractmethod
    def plan(self, task_description, initial_state, goal_state, ...) -> SubgoalPlan
    
    @abstractmethod
    def replan(self, original_plan, current_state, failure_info) -> SubgoalPlan
```

**LLMPlanner** - LLM实现
- 支持GPT-4、Claude等模型
- 基于prompt engineering生成subgoals
- 包含few-shot examples
- 失败时可以replan并提供错误反馈

### 3. Executors (tamp/executors/)

**BaseExecutor** - 抽象接口
```python
class BaseExecutor(ABC):
    @abstractmethod
    def execute_subgoal(self, subgoal) -> Generator[Any, None, bool]
    
    @abstractmethod
    def can_execute(self, subgoal) -> bool
```

**PrimitiveExecutor** - OmniGibson集成
- 映射subgoal action_type到SymbolicSemanticActionPrimitiveSet
- 自动解析object names
- 处理不同action的参数需求
- 支持retry和错误处理

### 4. Utils (tamp/utils/)

**bddl_utils.py** - BDDL处理
- `load_bddl_task()`: 加载BDDL任务定义
- `extract_initial_state()`: 提取初始状态
- `extract_goal_state()`: 提取目标状态
- `get_available_objects()`: 获取场景对象列表

## 工作流程

```
┌─────────────────┐
│  BDDL Task      │
│  (turning_on_   │
│   radio)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract State   │
│ - Initial atoms │
│ - Goal atoms    │
│ - Objects list  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Planner    │
│ Generate        │
│ Subgoals        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SubgoalPlan     │
│ 1. navigate_to  │
│ 2. toggle_on    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Primitive       │
│ Executor        │
│ (Action         │
│  Primitives)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Robot Actions   │
│ in Simulation   │
└─────────────────┘
         │
         │ if failed
         ▼
    ┌────────────┐
    │  Replan    │
    │  (LLM)     │
    └────────────┘
```

## 测试结果

### 单元测试 (test_basic.py)
```
✓ Symbol primitives (Predicate, Atom, State)
✓ Subgoal creation and tracking
✓ Plan management and serialization
✓ BDDL task loading
```

### 待测试
- [ ] LLM planner with real API
- [ ] Full execution in simulation (turning_on_radio)
- [ ] Replanning on failure
- [ ] Multiple tasks

## 与TANDEM的比较

| 方面 | TANDEM | 我们的实现 |
|------|---------|-----------|
| 目标 | 数据收集（人类演示） | 任务执行（自主规划） |
| 高层规划 | LLM + human teleoperation | 纯LLM |
| 底层执行 | 真实机器人 | OmniGibson simulation |
| 状态表示 | 自定义symbols | 兼容BDDL predicates |
| 适用场景 | 实体机器人数据收集 | 仿真环境任务评估 |

**借鉴**：
- 符号表示设计（Predicate, Atom, State）
- 避免interning的问题
- LLM prompt结构

**差异**：
- 我们直接用BDDL而不是自定义domain
- 我们的executor直接用现有primitives
- 我们专注于BEHAVIOR-1K的1000+任务

## 与传统TAMP的比较

| 方面 | PDDLStream/cuTAMP | 我们的LLM-TAMP |
|------|-------------------|---------------|
| 高层规划 | A*搜索 + PDDL | LLM生成subgoals |
| 领域知识 | 显式PDDL actions | 隐式在LLM中 |
| 可扩展性 | 受搜索空间限制 | 受LLM能力限制 |
| 可解释性 | 符号trace | 自然语言reasoning |
| 失败处理 | Backtracking | LLM replanning |
| 连续参数 | Sampling streams | 可集成（未完成） |

## 已知问题和TODO

### 短期 (1-2周)
- [ ] 修复BDDL状态提取的list hashable问题
- [ ] 在真实环境测试turning_on_radio
- [ ] 实现从simulation观察当前状态
- [ ] 测试replanning功能
- [ ] 扩展到3-5个简单任务

### 中期 (1个月)
- [ ] 添加连续参数采样（place位置、grasp姿态）
- [ ] 改进LLM prompts（更多few-shot examples）
- [ ] 实现execution feedback到LLM
- [ ] 添加search-based planner进行对比
- [ ] 支持更复杂的任务（多物体、多步骤）

### 长期 (2-3个月)
- [ ] Fine-tune小模型在planning data上
- [ ] 集成CuRobo进行motion planning
- [ ] 多agent协作
- [ ] 学习from execution experience
- [ ] Benchmark在BEHAVIOR-1K的100+任务上

## 关键文件

**启动入口**：
- `tamp/examples/turning_on_radio.py` - 完整示例
- `tamp/tests/test_basic.py` - 单元测试

**核心组件**：
- `tamp/planners/llm_planner.py` - LLM规划逻辑
- `tamp/executors/primitive_executor.py` - 执行逻辑
- `tamp/utils/bddl_utils.py` - BDDL解析

**文档**：
- `tamp/README.md` - 完整文档
- `doc/notes/2026_10_11.txt` - 开发日志

## 使用示例

### 基础测试
```bash
cd /home/msai/linj0121/project/BEHAVIOR-1K
/home/msai/linj0121/.conda/envs/behavior/bin/python tamp/tests/test_basic.py
```

### 完整示例（需要GPU + API key）
```bash
export OPENAI_API_KEY="your-key"
conda activate behavior
python tamp/examples/turning_on_radio.py
```

### 在代码中使用
```python
from tamp.planners.llm_planner import LLMPlanner
from tamp.executors.primitive_executor import PrimitiveExecutor

# 创建planner
planner = LLMPlanner(model="gpt-4", api_key="...")

# 生成plan
plan = planner.plan(
    task_description="Turn on the radio",
    initial_state=initial_state,
    goal_state=goal_state,
    available_objects=objects,
    available_actions=actions,
)

# 执行plan
executor = PrimitiveExecutor(env, robot)
for subgoal in plan.subgoals:
    success = yield from executor.execute_subgoal(subgoal)
```

## 设计优势

### 1. 模块化
每个组件可以独立替换：
- Planner: LLM → Search → Hybrid
- Executor: Symbolic primitives → CuRobo → Learned policy
- State: BDDL atoms → Vision features → Learned representations

### 2. 可扩展
添加新planner只需：
```python
class MyPlanner(BasePlanner):
    def plan(self, ...): ...
    def replan(self, ...): ...
```

### 3. 可观察
所有操作都有日志：
```python
planner.get_planning_stats()  # 规划统计
executor.get_execution_stats()  # 执行统计
plan.to_dict()  # 完整plan序列化
```

## 参考资源

**代码参考**：
- TANDEM: https://github.com/SamratSahoo/TANDEM
- BEHAVIOR-1K primitives: `OmniGibson/omnigibson/action_primitives/`
- BDDL: `bddl3/bddl/`

**论文**：
- TANDEM: Task and Motion Planning with As-Needed Demonstrations
- Tom Silver推荐: https://arxiv.org/pdf/2604.25788 (Table 1列举了很多benchmarks)

## 总结

成功搭建了一个**现代化、模块化、可扩展**的TAMP系统：
- ✅ 核心架构完成
- ✅ 基础测试通过
- ✅ LLM planner实现
- ✅ Primitive executor集成
- ✅ 文档和示例完整

下一步是在真实环境测试和迭代改进。
