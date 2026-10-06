# Metrics 系统详解

## 概述

Metrics 系统用于在 episode 执行过程中跟踪和评估机器人的性能指标。它提供了一个可扩展的框架来计算各种度量标准，如任务完成度、机器人移动距离、效率等。

**位置**: `OmniGibson/omnigibson/metrics/`

---

## 架构概览

```
MetricBase (抽象基类)
├── TaskMetric      # 任务相关指标（完成度、时间）
└── AgentMetric     # 机器人相关指标（移动距离）
```

**集成方式**:
```
Environment
    ↓ wrapped by
MetricsWrapper
    ↓ contains
Metric instances (TaskMetric, AgentMetric)
    ↓ tracks
Step-wise data → Episode-wise aggregation
```

---

## MetricBase - 基类

### 核心接口

```python
class MetricBase:
    """所有 Metric 的抽象基类"""
    
    def __init__(self):
        self.state = dict()  # {scene: {metric_data}}
    
    @classmethod
    def is_compatible(cls, env):
        """检查此 metric 是否与环境兼容"""
        return True
    
    def reset(self, env):
        """重置 metric 状态"""
        self.state[env.scene] = dict()
    
    def step(self, env, action, obs, reward, terminated, truncated, info):
        """每个时间步调用，收集数据"""
        step_metrics = self._compute_step_metrics(env, action, obs, reward, terminated, truncated, info)
        
        # 将数据追加到 state 中
        state = self.state[env.scene]
        for k, v in step_metrics.items():
            if k not in state:
                state[k] = []
            state[k].append(v)
    
    def aggregate(self, env):
        """聚合整个 episode 的数据"""
        if env.scene in self.state:
            return self._compute_episode_metrics(env=env, episode_info=self.state[env.scene])
        else:
            return dict()
    
    # 子类必须实现的方法
    def _compute_step_metrics(self, env, action, obs, reward, terminated, truncated, info):
        """计算单步指标"""
        raise NotImplementedError()
    
    def _compute_episode_metrics(self, env, episode_info):
        """计算 episode 聚合指标"""
        raise NotImplementedError()
```

---

## TaskMetric - 任务指标

### 功能

跟踪任务相关的性能指标：
- **Q-Score**: 任务完成度（0-1）
- **时间效率**: 相对于人类演示的时间比

### 实现

```python
class TaskMetric(MetricBase):
    def __init__(self, human_stats: Optional[dict] = None):
        super().__init__()
        self.timesteps = 0
        self.human_stats = human_stats
        
        if human_stats is not None:
            self.human_stats = {
                "steps": self.human_stats["length"],
            }
    
    def reset(self, env):
        """重置并记录初始谓词状态"""
        self.state[env.scene] = dict()
        self.timesteps = 0
        self.render_timestep = og.sim.get_rendering_dt()
        
        # 记录初始状态（用于计算 Q-Score）
        self.initial_predicate_states = [
            [pred.evaluate(env.task._evaluate_predicate) for pred in option]
            for option in env.task.ground_goal_state_options
        ]
    
    def _compute_step_metrics(self, env, action, obs, reward, terminated, truncated, info):
        """每步只记录时间步数"""
        self.timesteps += 1
        return {"timesteps": self.timesteps}
    
    def _compute_episode_metrics(self, env, episode_info):
        """计算 episode 结束时的指标"""
        timesteps = episode_info.get("timesteps", [])[-1] if episode_info.get("timesteps") else self.timesteps
        
        # 1. Q-Score 计算
        if env.task.success:
            # 任务完全成功
            final_q_score = 1.0
        else:
            # 部分完成：计算满足的新谓词比例
            final_q_score = max(
                sum(
                    int(not initially_true and pred.evaluate(env.task._evaluate_predicate))
                    for pred, initially_true in zip(option, option_previous_state)
                )
                / len(option)
                for option, option_previous_state in zip(
                    env.task.ground_goal_state_options, self.initial_predicate_states
                )
            )
        
        # 2. 时间指标
        return {
            "q_score": {
                "final": final_q_score
            },
            "time": {
                "simulator_steps": timesteps,
                "simulator_time": timesteps * self.render_timestep,
                "normalized_time": self.human_stats["steps"] / timesteps if timesteps > 0 else float("inf"),
            },
        }
```

---

### Q-Score 详解

**Q-Score** 衡量任务的部分完成度：

```python
# 示例任务：turning_on_radio
# 目标谓词：(toggled_on radio_receiver.n.01_1)

# 场景 1：任务成功
env.task.success = True
q_score = 1.0  # 完美！

# 场景 2：任务失败，但完成了部分目标
# 假设有 3 个子目标：A, B, C
initial_state = [False, False, False]  # 初始都未满足
final_state = [True, True, False]      # 完成了 A 和 B

# 计算：从 False 变为 True 的谓词数量 / 总谓词数
newly_satisfied = sum([
    not initial and final
    for initial, final in zip(initial_state, final_state)
])
q_score = newly_satisfied / len(initial_state) = 2 / 3 = 0.667
```

**多选项场景** (ground_goal_state_options):

某些任务有多种完成方式（如"打开任意一盏灯"）：

```python
# 任务：打开任意一盏灯
# 选项1：打开灯A
# 选项2：打开灯B
# 选项3：打开灯C

ground_goal_state_options = [
    [Predicate("toggled_on", "lamp_A")],
    [Predicate("toggled_on", "lamp_B")],
    [Predicate("toggled_on", "lamp_C")],
]

# 机器人打开了灯B
# Q-Score = max(0/1, 1/1, 0/1) = 1.0  # 选项2完全满足
```

---

### 时间效率

```python
# 人类演示平均用时
human_stats["length"] = 150  # 步

# 机器人执行
timesteps = 300  # 步

# 归一化时间效率
normalized_time = human_stats["length"] / timesteps
                = 150 / 300
                = 0.5  # 机器人慢2倍

# 如果机器人更快
timesteps = 100
normalized_time = 150 / 100 = 1.5  # 机器人快1.5倍
```

---

## AgentMetric - 机器人指标

### 功能

跟踪机器人的物理运动：
- **移动距离**: 底盘、左手臂末端、右手臂末端
- **归一化距离**: 相对于人类演示的运动效率

### 实现

```python
class AgentMetric(MetricBase):
    def __init__(self, human_stats: Optional[dict] = None):
        super().__init__()
        self.initialized = False
        self.human_stats = human_stats
        
        if human_stats is not None:
            self.human_stats = {
                "base": self.human_stats["distance_traveled"],
                "left": self.human_stats["left_eef_displacement"],
                "right": self.human_stats["right_eef_displacement"],
            }
    
    def reset(self, env):
        """重置状态"""
        self.state[env.scene] = dict()
        self.initialized = False
    
    def _compute_step_metrics(self, env, action, obs, reward, terminated, truncated, info):
        """计算每步的移动距离"""
        robot = env.robots[0]
        
        # 当前状态
        self.next_state_cache = {
            "base": {"position": robot.get_position_orientation()[0]},
            **{arm: {"position": robot.get_eef_position(arm)} for arm in robot.arm_names},
        }
        
        # 初始化
        if not self.initialized:
            self.delta_agent_distance = {part: [] for part in ["base"] + robot.arm_names}
            self.state_cache = copy.deepcopy(self.next_state_cache)
            self.initialized = True
        
        # 计算距离增量
        # 底盘移动距离
        distance = th.linalg.norm(
            self.next_state_cache["base"]["position"] - self.state_cache["base"]["position"]
        ).item()
        self.delta_agent_distance["base"].append(distance)
        
        # 每个手臂的 EEF 移动距离
        for arm in robot.arm_names:
            eef_distance = th.linalg.norm(
                self.next_state_cache[arm]["position"] - self.state_cache[arm]["position"]
            ).item()
            self.delta_agent_distance[arm].append(eef_distance)
        
        # 更新缓存
        self.state_cache = copy.deepcopy(self.next_state_cache)
        
        return self.delta_agent_distance
    
    def _compute_episode_metrics(self, env, episode_info):
        """聚合整个 episode 的距离"""
        all_distances = episode_info.get("delta_agent_distance", self.delta_agent_distance)
        
        # 总距离
        results = {
            "agent_distance": {k: sum(v) for k, v in all_distances.items()},
        }
        
        # 归一化距离（人类距离 / 机器人距离）
        results.update({
            "normalized_agent_distance": {
                k: (self.human_stats[k] / v if v != 0 else float("inf"))
                for k, v in results["agent_distance"].items()
            }
        })
        
        return results
```

---

### 距离计算示例

```python
# Episode 执行过程
# t=0: base=[0, 0, 0], left_eef=[1, 0, 1.2], right_eef=[1, 0, 1.2]
# t=1: base=[0.1, 0, 0], left_eef=[1.05, 0, 1.25], right_eef=[1, 0, 1.2]
#      Δbase = 0.1m, Δleft = 0.058m, Δright = 0m
# t=2: base=[0.2, 0, 0], left_eef=[1.1, 0, 1.3], right_eef=[1, 0.1, 1.2]
#      Δbase = 0.1m, Δleft = 0.058m, Δright = 0.1m
# ...
# t=300: 累计移动

# 聚合结果
agent_distance = {
    "base": 15.5,   # 底盘移动了 15.5m
    "left": 8.2,    # 左臂末端移动了 8.2m
    "right": 3.1,   # 右臂末端移动了 3.1m
}

# 人类演示数据
human_stats = {
    "base": 10.0,
    "left": 5.0,
    "right": 2.0,
}

# 归一化（越接近 1.0 越好）
normalized_agent_distance = {
    "base": 10.0 / 15.5 = 0.645,   # 机器人绕路了
    "left": 5.0 / 8.2 = 0.610,     # 手臂运动不够高效
    "right": 2.0 / 3.1 = 0.645,
}
```

---

## MetricsWrapper - 集成层

### 功能

将 Metrics 集成到环境中，自动在每步收集数据并在 episode 结束时聚合。

### 实现

```python
class MetricsWrapper(EnvironmentWrapper):
    """Metrics 的环境包装器"""
    
    def __init__(self, env: Environment):
        self.metrics = dict()  # {name: MetricBase}
        super().__init__(env=env)
    
    def add_metric(self, name: str, metric: MetricBase):
        """添加 metric"""
        assert metric.is_compatible(self), f"Metric {metric.__class__.__name__} is not compatible!"
        self.metrics[name] = metric
    
    def remove_metric(self, name: str):
        """移除 metric"""
        self.metrics.pop(name)
    
    def reset(self):
        """重置所有 metrics"""
        ret = super().reset()
        
        for name, metric in self.metrics.items():
            metric.reset(self)
        
        return ret
    
    def step(self, action, n_render_iterations=1):
        """每步更新所有 metrics"""
        obs, reward, terminated, truncated, info = super().step(action, n_render_iterations)
        
        # 更新所有 metrics
        for name, metric in self.metrics.items():
            metric.step(self.env, action, obs, reward, terminated, truncated, info)
        
        return obs, reward, terminated, truncated, info
    
    def aggregate_metrics(self, flatten: bool = True):
        """聚合所有 metrics"""
        results = dict()
        for name, metric in self.metrics.items():
            results[name] = metric.aggregate(self)
        
        if flatten:
            # 展平嵌套字典
            results = recursively_generate_flat_dict(dic=results)
        
        return results
```

---

## 在 Evaluator 中的使用

### 初始化

```python
class Evaluator:
    def __init__(self, cfg):
        # 1. 加载人类统计数据
        self.human_stats = load_human_stats(task_name)
        # human_stats = {
        #     "length": 150.5,                  # 平均步数
        #     "distance_traveled": 10.2,        # 底盘移动距离
        #     "left_eef_displacement": 5.1,     # 左臂移动距离
        #     "right_eef_displacement": 2.3,    # 右臂移动距离
        # }
        
        # 2. 创建环境（带 MetricsWrapper）
        env = og.Environment(configs=cfg)
        self.env = MetricsWrapper(env=env)
        
        # 3. 加载 metrics
        self.metrics = self.load_metrics()
        for metric in self.metrics:
            self.env.add_metric(metric.__class__.__name__, metric)
    
    def load_metrics(self):
        """创建 metric 实例"""
        return [
            AgentMetric(self.human_stats),
            TaskMetric(self.human_stats),
        ]
```

### Episode 执行

```python
def evaluate_episode(self):
    """运行一个 episode 并收集 metrics"""
    
    # 1. 重置（自动重置所有 metrics）
    obs = self.env.reset()
    
    # 2. Episode 循环
    for step in range(max_steps):
        action = self.policy.act(obs)
        obs, reward, terminated, truncated, info = self.env.step(action)
        # 每步自动调用 metric.step()
        
        if terminated or truncated:
            break
    
    # 3. 聚合 metrics
    metrics = self.env.aggregate_metrics(flatten=True)
    
    return metrics
```

### Metrics 输出示例

```python
metrics = {
    # TaskMetric 输出
    "TaskMetric/q_score/final": 0.85,
    "TaskMetric/time/simulator_steps": 320,
    "TaskMetric/time/simulator_time": 10.67,  # 秒
    "TaskMetric/time/normalized_time": 0.47,  # 人类时间 / 机器人时间
    
    # AgentMetric 输出
    "AgentMetric/agent_distance/base": 15.5,
    "AgentMetric/agent_distance/left": 8.2,
    "AgentMetric/agent_distance/right": 3.1,
    "AgentMetric/normalized_agent_distance/base": 0.645,
    "AgentMetric/normalized_agent_distance/left": 0.610,
    "AgentMetric/normalized_agent_distance/right": 0.645,
}
```

---

## Human Stats 数据格式

### 来源

人类演示数据存储在 `task.jsonl` 文件中：

```
{gm.DATA_PATH}/2026-challenge-task-instances/metadata/task.jsonl
```

### 格式

```jsonl
{"task_name": "turning_on_radio", "task_index": 0, "length": 150.5, "distance_traveled": 10.2, "left_eef_displacement": 5.1, "right_eef_displacement": 2.3}
{"task_name": "cleaning_windows", "task_index": 1, "length": 320.8, "distance_traveled": 25.6, "left_eef_displacement": 12.3, "right_eef_displacement": 8.7}
...
```

**字段说明**:
- `task_name`: 任务名称
- `task_index`: 任务索引（0-99）
- `length`: 平均完成步数
- `distance_traveled`: 机器人底盘平均移动距离（米）
- `left_eef_displacement`: 左手臂末端执行器平均移动距离（米）
- `right_eef_displacement`: 右手臂末端执行器平均移动距离（米）

### 加载

```python
def load_human_stats(task_name: str, task_jsonl_path: str | None = None) -> dict[str, float]:
    """从 JSONL 文件加载人类统计数据"""
    task_jsonl_path = task_jsonl_path or default_task_jsonl_path()
    task_idx = TASK_NAMES_TO_INDICES[task_name]
    
    with open(task_jsonl_path, "r") as f:
        for line in f:
            task_stats = json.loads(line)
            if task_stats.get("task_name") == task_name or task_stats.get("task_index") == task_idx:
                return {
                    "length": task_stats["length"],
                    "distance_traveled": task_stats["distance_traveled"],
                    "left_eef_displacement": task_stats["left_eef_displacement"],
                    "right_eef_displacement": task_stats["right_eef_displacement"],
                }
    
    raise ValueError(f"Could not find human stats for task {task_name}")
```

---

## 自定义 Metric

### 示例：碰撞计数

```python
from omnigibson.metrics.metric_base import MetricBase

class CollisionMetric(MetricBase):
    """跟踪碰撞次数"""
    
    def __init__(self):
        super().__init__()
        self.collision_count = 0
    
    def reset(self, env):
        super().reset(env)
        self.collision_count = 0
    
    def _compute_step_metrics(self, env, action, obs, reward, terminated, truncated, info):
        """检查是否发生碰撞"""
        robot = env.robots[0]
        
        # 检查机器人是否与环境碰撞
        is_colliding = robot.contact_list() != []
        
        if is_colliding:
            self.collision_count += 1
        
        return {
            "collision": int(is_colliding),
            "collision_count": self.collision_count,
        }
    
    def _compute_episode_metrics(self, env, episode_info):
        """聚合碰撞统计"""
        collisions = episode_info.get("collision", [])
        total_collisions = episode_info.get("collision_count", [])[-1] if episode_info.get("collision_count") else 0
        
        return {
            "total_collisions": total_collisions,
            "collision_rate": sum(collisions) / len(collisions) if collisions else 0.0,
        }

# 使用
collision_metric = CollisionMetric()
env.add_metric("CollisionMetric", collision_metric)
```

---

### 示例：能量消耗

```python
class EnergyMetric(MetricBase):
    """跟踪能量消耗"""
    
    def _compute_step_metrics(self, env, action, obs, reward, terminated, truncated, info):
        """计算动作的能量消耗"""
        robot = env.robots[0]
        
        # 简化模型：能量 ∝ |关节速度|
        joint_velocities = robot.get_joint_velocities()
        energy = th.sum(th.abs(joint_velocities)).item()
        
        return {"energy": energy}
    
    def _compute_episode_metrics(self, env, episode_info):
        """总能量消耗"""
        energies = episode_info.get("energy", [])
        
        return {
            "total_energy": sum(energies),
            "average_energy_per_step": sum(energies) / len(energies) if energies else 0.0,
        }
```

---

## 完整流程示例

```python
# ========== 1. 创建环境和 Metrics ==========
env = og.Environment(configs=cfg)
env = MetricsWrapper(env=env)

# 加载人类统计数据
human_stats = load_human_stats("turning_on_radio")

# 添加 metrics
env.add_metric("TaskMetric", TaskMetric(human_stats))
env.add_metric("AgentMetric", AgentMetric(human_stats))
env.add_metric("CollisionMetric", CollisionMetric())

# ========== 2. 运行 Episode ==========
obs = env.reset()  # 自动重置所有 metrics

for step in range(500):
    action = policy.act(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    # 每步自动调用所有 metric.step()
    
    if terminated:
        break

# ========== 3. 聚合结果 ==========
metrics = env.aggregate_metrics(flatten=True)

print(f"Q-Score: {metrics['TaskMetric/q_score/final']:.2f}")
print(f"Steps: {metrics['TaskMetric/time/simulator_steps']}")
print(f"Base distance: {metrics['AgentMetric/agent_distance/base']:.2f}m")
print(f"Collisions: {metrics['CollisionMetric/total_collisions']}")

# ========== 4. 输出示例 ==========
# Q-Score: 0.85
# Steps: 320
# Base distance: 15.50m
# Collisions: 12
```

---

## 关键设计模式

### 1. 状态追踪

Metrics 通过 `self.state[env.scene]` 存储每个场景的独立状态：

```python
# 支持多场景同时跟踪
self.state = {
    scene_A: {"timesteps": [1, 2, 3, ...]},
    scene_B: {"timesteps": [1, 2, 3, ...]},
}
```

### 2. 两阶段计算

- **Step-wise**: 每步收集原始数据
- **Episode-wise**: Episode 结束时聚合和计算最终指标

这种设计避免了重复计算，提高效率。

### 3. 归一化对比

所有指标都提供归一化版本（相对于人类演示），便于跨任务比较：

```python
# 任务A：机器人用时 300 步，人类 150 步 → normalized = 0.5
# 任务B：机器人用时 200 步，人类 400 步 → normalized = 2.0
# 结论：机器人在任务A表现不好，在任务B表现很好
```

---

## 总结

**Metrics 系统的核心价值**:

1. **标准化评估**: 提供统一的性能度量标准
2. **人类基准**: 通过归一化指标与人类演示对比
3. **可扩展性**: 易于添加自定义 metrics
4. **自动化**: 与环境无缝集成，无需手动调用
5. **多维度**: 同时跟踪任务完成度和执行效率

**关键指标**:
- **Q-Score**: 任务完成度（0-1）
- **Normalized Time**: 时间效率（越大越好）
- **Normalized Distance**: 运动效率（越接近1越好）

**在 BEHAVIOR-1K 中的作用**:
- 评估策略性能
- 对比不同方法
- 识别改进方向
- 生成排行榜
