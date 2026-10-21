# TAMP Test: Turning On Radio

> **目标**：测试 TAMP 方法在单个任务上的效果，手动定义 skeleton，使用 OmniGibson primitives 执行。

---

## 测试范围

- **任务**：`turning_on_radio` (单一任务)
- **Skeleton**：手动定义，固定为 `[navigate_to_radio, press_button]`
- **Domain**：手动编写 PDDL domain（包括 preconditions/effects）
- **Low-level Planner**：OmniGibson 的 action primitives（CuRobo 运动规划）
- **评估**：生成完整视频，计算成功率

---

## 目录结构

```
tamp_test/
├── README.md                    # 本文件
├── outline.md                   # 详细的实现 outline
├── domain/                      # PDDL domain 定义
│   ├── turning_on_radio.pddl   # 手动定义的 domain
│   └── problem.pddl             # 从 BDDL 提取的 problem
├── planner/                     # 高层规划器
│   ├── symbolic_planner.py     # 符号规划器（基于 PDDL）
│   └── skeleton_executor.py    # Skeleton 执行器
├── low_level/                   # 低层运动规划
│   ├── primitive_wrapper.py    # Action primitives 包装器
│   └── motion_sampler.py       # 连续参数采样器
├── eval/                        # 评估脚本
│   ├── run_eval.py             # 主评估脚本
│   └── video_generator.py      # 视频生成
├── configs/                     # 配置文件
│   └── turning_on_radio.yaml   # 任务配置
└── results/                     # 结果输出
    ├── videos/                 # 生成的视频
    ├── logs/                   # 日志
    └── metrics.json            # 评估指标
```

---

## 快速开始

```bash
# 1. 运行测试
cd tamp_test
python eval/run_eval.py --config configs/turning_on_radio.yaml

# 2. 查看结果
ls results/videos/
cat results/metrics.json
```

---

## 核心组件说明

### 1. PDDL Domain (domain/turning_on_radio.pddl)

手动定义的符号 domain，包含：
- **Types**: robot, object, location
- **Predicates**: at, near, holding, toggled_on
- **Actions**: navigate_to, press_button

### 2. Symbolic Planner (planner/symbolic_planner.py)

- 输入：BDDL initial state + goal state
- 输出：High-level skeleton (list of subgoals)
- 方法：固定 skeleton（不搜索）

### 3. Primitive Wrapper (low_level/primitive_wrapper.py)

- 包装 OmniGibson 的 action primitives
- 处理连续参数采样
- 调用 CuRobo 运动规划

### 4. Skeleton Executor (planner/skeleton_executor.py)

- 执行 skeleton 中的每个 subgoal
- 调用 primitive wrapper
- 记录执行状态

### 5. Evaluator (eval/run_eval.py)

- 加载 BEHAVIOR-1K 环境
- 运行 skeleton executor
- 生成视频和指标

---

## 与官方 Baseline 的对比

| 方面 | 官方 VLA (Pi0.5/GR00T) | 本 TAMP 测试 |
|------|------------------------|--------------|
| **输入** | 图像 + 语言 + 状态 | BDDL + 场景 |
| **规划** | 无（端到端） | 符号规划 + 运动规划 |
| **动作** | 连续动作（神经网络输出）| Primitives（CuRobo） |
| **知识** | 隐式（神经网络权重） | 显式（PDDL + primitives） |
| **可解释性** | 低 | 高 |
| **泛化性** | 高（学习） | 低（手写规则） |

---

## 下一步

1. ✅ 实现核心框架
2. ✅ 在 `turning_on_radio` 上测试
3. 🔲 分析成功/失败案例
4. 🔲 扩展到其他任务
5. 🔲 与 VLA baseline 对比
