# BaseTask 类详解

## 概述

BaseTask 是 OmniGibson 中所有任务的抽象基类，定义了任务的核心接口和执行流程。它负责：
- 定义任务的成功/失败条件
- 计算奖励（用于强化学习）
- 管理任务的初始化和重置
- 提供任务相关的观察空间

**位置**: `OmniGibson/omnigibson/tasks/task_base.py`

---

## 类层次结构

```
BaseTask (抽象基类)
├── BehaviorTask (BEHAVIOR-1K 的 1000+ 家庭任务)
├── PointNavigationTask (导航任务)
├── PointReachingTask (到达任务)
├── GraspTask (抓取任务)
└── DummyTask (测试用空任务)
```

**继承的特性**:
- `GymObservable`: 提供 Gymnasium 兼容的观察空间
- `Registerable`: 注册模式，所有任务类自动注册到 `REGISTERED_TASKS` 字典

---

## 核心概念

### 1. Termination Conditions (终止条件)

终止条件决定 episode 何时结束，分为两类：
- **Success Condition** (成功条件): 触发时标记为成功完成
- **Failure Condition** (失败条件): 触发时标记为失败结束

**常见终止条件**:
- `Timeout`: 超过最大步数
- `PredicateGoal`: BDDL 谓词满足 (BehaviorTask 的核心)
- `Collision`: 碰撞检测
- `MaxDistanceFailure`: 超出允许范围

### 2. Reward Functions (奖励函数)

奖励函数为强化学习提供训练信号：
- **PotentialReward**: 基于势能的奖励（常用于 BEHAVIOR-1K）
- **PointGoalReward**: 基于距离目标的奖励
- **GraspReward**: 抓取成功奖励
- **CollisionReward**: 碰撞惩罚

---

## 初始化流程

```python
def __init__(self, termination_config=None, reward_config=None, include_obs=True):
    # 1. 合并配置：用户配置 + 默认配置
    self._termination_config = self.default_termination_config
    self._termination_config.update(termination_config)
    
    self._reward_config = self.default_reward_config
    self._reward_config.update(reward_config)
    
    # 2. 创建 termination 和 reward 实例
    self._termination_conditions = self._create_termination_conditions()  # 抽象方法
    self._reward_functions = self._create_reward_functions()              # 抽象方法
    
    # 3. 初始化状态变量
    self._loaded = False
    self._reward = None
    self._done = None
    self._success = None
    self._info = None
```

**配置示例** (BehaviorTask):
```python
# default_termination_config
{
    "max_steps": 500  # Timeout 的最大步数
}

# default_reward_config
{
    "r_potential": 1.0  # PotentialReward 的缩放系数
}
```

---

## 核心方法详解

### load(env) - 加载任务

```python
def load(self, env):
    """第一阶段初始化：在环境创建时调用"""
    # 1. 检查场景类型兼容性
    assert any([issubclass(env.scene.__class__, valid_cls) 
                for valid_cls in self.valid_scene_types])
    
    # 2. 调用子类的 _load() 实现
    self._load(env)  # 抽象方法 - 子类加载任务特定资源
    
    self._loaded = True
```

**BehaviorTask 的 _load() 实现**:
```python
def _load(self, env):
    # 1. 加载 BDDL 活动定义
    self.update_activity(env, activity_name, activity_definition_id)
    
    # 2. 初始化对象范围（object_scope）
    success, feedback = self.initialize_activity(env)
    
    # 3. 高亮任务相关对象（如果启用）
    if self.highlight_task_relevant_objs:
        for inst, entity in self.object_scope.items():
            entity.highlighted = True
```

---

### post_play_load(env) - 后加载

```python
def post_play_load(self, env):
    """第二阶段初始化：在模拟器开始运行后调用"""
    # 1. 重置场景到初始配置
    env.scene.reset(hard=False)
    
    # 2. 计算 low-dim 观察维度
    obs = self.get_obs(env, flatten_low_dim=False)
    if "low_dim" in obs:
        self._low_dim_obs_keys = list(obs["low_dim"].keys())
        self._low_dim_obs_dim = len(self._flatten_low_dim_obs(obs["low_dim"]))
```

**为什么分两阶段？**
- `load()`: 创建对象、加载资源（模拟器可以暂停）
- `post_play_load()`: 需要物理模拟运行的操作（如获取观察）

---

### reset(env) - 重置任务

```python
def reset(self, env):
    """每个 episode 开始时调用"""
    # 1. 重置场景（放置对象、初始化物理）
    self._reset_scene(env)  # 默认: env.scene.reset()
    
    # 2. 重置机器人（设置初始姿态）
    self._reset_agent(env)  # 默认: no-op，子类可覆盖
    
    # 3. 重置任务内部变量
    self._reset_variables(env)  # 清空 _reward, _done, _success, _info
    
    # 4. 重置所有 termination conditions
    for termination_condition in self._termination_conditions.values():
        termination_condition.reset(self, env)
    
    # 5. 重置所有 reward functions
    for reward_function in self._reward_functions.values():
        reward_function.reset(self, env)
```

**BehaviorTask 的 reset() 扩展**:
```python
def reset(self, env):
    super().reset(env)
    
    # 使用预采样的机器人姿态
    if self.use_presampled_robot_pose:
        robot = self.get_agent(env)
        presampled_poses = env.scene.get_task_metadata(key="robot_poses")
        robot_pose = random.choice(presampled_poses) if self.randomize_presampled_pose else presampled_poses[0]
        robot.set_position_orientation(robot_pose["position"], robot_pose["orientation"])
    
    # 唤醒所有任务相关对象
    for obj in self.object_scope.values():
        if obj is not None and isinstance(obj, DatasetObject):
            obj.wake()
```

---

### step(env, action) - 执行一步

```python
def step(self, env, action):
    """每个时间步调用，返回 (reward, done, info)"""
    assert self._loaded, "Task must be loaded using load() before calling step()!"
    
    # 1. 先检查终止条件
    done, done_info = self._step_termination(env, action)
    
    # 2. 再计算奖励（奖励可能依赖终止条件的结果）
    reward, reward_info = self._step_reward(env, action)
    
    # 3. 更新内部状态
    self._reward = reward
    self._done = done
    self._success = done_info["success"]
    self._info = {
        "reward": reward_info,
        "done": done_info,
    }
    
    return self._reward, self._done, deepcopy(self._info)
```

**执行顺序很重要**：先检查终止条件，因为某些奖励函数可能依赖 `done` 状态。

---

### _step_termination(env, action) - 聚合终止条件

```python
def _step_termination(self, env, action, info=None):
    """检查所有终止条件并聚合结果"""
    dones = []
    successes = []
    info = dict() if info is None else info
    info["termination_conditions"] = dict()
    
    # 遍历所有终止条件
    for name, termination_condition in self._termination_conditions.items():
        d, s = termination_condition.step(self, env, action)
        dones.append(d)
        successes.append(s)
        info["termination_conditions"][name] = {
            "done": d,
            "success": s,
        }
    
    # 任何一个触发即为 done/success
    done = sum(dones) > 0
    success = sum(successes) > 0
    
    info["success"] = success
    return done, info
```

**聚合逻辑**：OR 操作 - 任何一个 termination condition 触发就结束。

**示例输出** (BehaviorTask):
```python
info["termination_conditions"] = {
    "timeout": {"done": False, "success": False},
    "predicate": {"done": True, "success": True}  # 目标达成
}
info["success"] = True  # 任务成功
```

---

### _step_reward(env, action) - 聚合奖励

```python
def _step_reward(self, env, action, info=None):
    """计算所有奖励函数并聚合结果"""
    total_info = dict() if info is None else info
    breakdown_dict = dict()
    total_reward = 0.0
    
    # 遍历所有奖励函数
    for reward_name, reward_function in self._reward_functions.items():
        reward, reward_info = reward_function.step(self, env, action)
        total_reward += reward
        breakdown_dict[reward_name] = reward
        total_info[reward_name] = reward_info
    
    # 存储奖励分解
    total_info["reward_breakdown"] = breakdown_dict
    
    return total_reward, total_info
```

**聚合逻辑**：SUM 操作 - 所有奖励相加。

**示例输出** (BehaviorTask):
```python
total_reward = 0.15
total_info = {
    "reward_breakdown": {
        "potential": 0.15  # 势能变化 * r_potential
    },
    "potential": {
        "current_potential": 0.85,
        "previous_potential": 0.70,
        "delta": 0.15
    }
}
```

---

## BehaviorTask 特定实现

### _create_termination_conditions()

```python
def _create_termination_conditions(self):
    terminations = dict()
    
    # 1. Timeout: 防止无限循环
    terminations["timeout"] = Timeout(max_steps=self._termination_config["max_steps"])
    
    # 2. PredicateGoal: BDDL 目标检查
    terminations["predicate"] = PredicateGoal(
        check_goal_fn=lambda: self.compiled_task.check_goal(self._evaluate_predicate),
    )
    
    return terminations
```

**PredicateGoal 工作原理**:
```python
# 在 _step() 中调用 check_goal_fn
def _step(self, task, env, action):
    done, goal_status = self._check_goal_fn()
    # goal_status = {
    #     "satisfied": [0, 2],      # 满足的谓词索引
    #     "unsatisfied": [1, 3, 4]  # 未满足的谓词索引
    # }
    return done  # 所有谓词都满足时为 True
```

---

### _create_reward_functions()

```python
def _create_reward_functions(self):
    rewards = dict()
    
    # PotentialReward: 基于完成度的奖励
    rewards["potential"] = PotentialReward(
        potential_fcn=self.get_potential,
        r_potential=self._reward_config["r_potential"],
    )
    
    return rewards
```

**PotentialReward 原理**:
```python
# 势能 = 满足的谓词数量 / 总谓词数量
def get_potential(self, env):
    all_satisfied, goal_status = self.compiled_task.check_goal(self._evaluate_predicate)
    n_satisfied = len(goal_status["satisfied"])
    n_total = n_satisfied + len(goal_status["unsatisfied"])
    return n_satisfied / n_total

# 奖励 = (当前势能 - 上一步势能) * r_potential
reward = (potential_t - potential_t-1) * 1.0
```

**奖励示例**:
- 初始状态: 0/5 谓词满足 → potential = 0.0
- 完成一个子目标: 1/5 → potential = 0.2, reward = +0.2
- 完成第二个: 2/5 → potential = 0.4, reward = +0.2
- 任务完成: 5/5 → potential = 1.0, reward = +0.6

---

## 观察空间

### get_obs(env, flatten_low_dim=True)

```python
def get_obs(self, env, flatten_low_dim=True):
    """获取任务相关观察"""
    if not self._include_obs:
        return dict()
    
    # 1. 调用子类的 _get_obs() 获取原始观察
    low_dim_obs, obs = self._get_obs(env=env)  # 抽象方法
    
    # 2. 可选：展平低维观察
    if low_dim_obs:
        obs["low_dim"] = self._flatten_low_dim_obs(low_dim_obs) if flatten_low_dim else low_dim_obs
    
    return obs
```

**BehaviorTask 的观察**:
```python
def _get_obs(self, env):
    # BehaviorTask 不提供额外的任务观察
    # 所有观察来自 robot (proprioception, cameras)
    return dict(), dict()
```

**其他任务的观察示例** (PointNavigationTask):
```python
def _get_obs(self, env):
    low_dim_obs = {
        "target_pos": self.target_pos,  # 目标位置 (3,)
        "robot_pos": env.robots[0].get_position(),  # 机器人位置 (3,)
    }
    return low_dim_obs, dict()
```

---

## 任务与环境的交互流程

```python
# 1. 环境创建时
env = og.Environment(configs={
    "scene": {...},
    "robots": [{...}],
    "task": {
        "type": "BehaviorTask",
        "activity_name": "turning_on_radio",
        "activity_definition_id": 0,
        "activity_instance_id": 0,
        "termination_config": {"max_steps": 500},
        "reward_config": {"r_potential": 1.0},
    }
})

# 内部调用顺序：
# a. task = BehaviorTask(...)  # 构造函数
# b. task.load(env)            # 加载任务
# c. og.sim.play()             # 启动模拟器
# d. task.post_play_load(env)  # 后加载

# 2. Episode 循环
obs = env.reset()  # 内部调用 task.reset(env)

for step in range(max_steps):
    # 获取动作
    action = policy.act(obs)
    
    # 执行一步
    obs, reward, done, truncated, info = env.step(action)
    # 内部调用：
    #   og.sim.step()           # 物理模拟
    #   reward, done, info = task.step(env, action)
    
    if done:
        break
```

---

## 与 Evaluator 的关系

```python
class Evaluator:
    def __init__(self, cfg):
        # 创建环境（包含 task）
        self.env = og.Environment(configs=cfg.env)
        self.task = self.env.task  # 引用
    
    def load_task_instance(self, instance_id):
        """加载任务实例（不同的初始配置）"""
        # 1. 读取 TRO state 文件
        tro_state = load_tro_file(instance_id)
        
        # 2. 恢复场景状态（通过 task.object_scope）
        for obj_name, obj_state in tro_state.items():
            self.task.object_scope[obj_name].load_state(obj_state)
        
        # 3. 稳定物理
        for _ in range(25):
            og.sim.step_physics()
    
    def evaluate_episode(self):
        """运行一个 episode"""
        obs = self.env.reset()  # → task.reset()
        
        for step in range(self.max_steps):
            action = self.policy.act(obs)
            obs, reward, done, truncated, info = self.env.step(action)
            # → task.step() 计算 reward 和 done
            
            if done:
                success = info["done"]["success"]  # 从 task.step() 返回
                break
        
        return success, reward_total
```

---

## 关键属性和状态

### 运行时状态

```python
# 加载状态
self._loaded = False  # load() 后变为 True

# 步进状态（每次 step() 更新）
self._reward = None    # 当前奖励
self._done = False     # 是否结束
self._success = False  # 是否成功
self._info = None      # 详细信息

# 观察空间
self._low_dim_obs_dim = None   # 低维观察维度（post_play_load 后计算）
self._low_dim_obs_keys = None  # 低维观察的键名列表
```

### 配置

```python
self._termination_config = {...}  # 终止条件配置
self._reward_config = {...}       # 奖励函数配置
self._include_obs = True          # 是否包含观察
```

### 子组件

```python
self._termination_conditions = {
    "timeout": Timeout(...),
    "predicate": PredicateGoal(...),
    ...
}

self._reward_functions = {
    "potential": PotentialReward(...),
    "collision": CollisionReward(...),
    ...
}
```

---

## 属性访问器

```python
@property
def reward(self):
    """当前奖励（必须在 step() 后访问）"""
    assert self._reward is not None
    return self._reward

@property
def done(self):
    """是否结束（必须在 step() 后访问）"""
    assert self._done is not None
    return self._done

@property
def success(self):
    """是否成功（必须在 step() 后访问）"""
    assert self._success is not None
    return self._success

@property
def info(self):
    """详细信息（必须在 step() 后访问）"""
    assert self._info is not None
    return self._info

@property
def name(self):
    """任务名称（默认为类名）"""
    return self.__class__.__name__
```

---

## 抽象方法（子类必须实现）

```python
@abstractmethod
def _load(self, env):
    """加载任务特定资源"""
    raise NotImplementedError()

@abstractmethod
def _create_termination_conditions(self):
    """创建终止条件"""
    raise NotImplementedError()

@abstractmethod
def _create_reward_functions(self):
    """创建奖励函数"""
    raise NotImplementedError()

@abstractmethod
def _get_obs(self, env):
    """获取任务特定观察"""
    raise NotImplementedError()

@abstractmethod
def _load_non_low_dim_observation_space(self):
    """加载非低维观察空间（如图像）"""
    raise NotImplementedError()

@classproperty
def valid_scene_types(cls):
    """兼容的场景类型"""
    raise NotImplementedError()

@classproperty
def default_reward_config(cls):
    """默认奖励配置"""
    raise NotImplementedError()

@classproperty
def default_termination_config(cls):
    """默认终止配置"""
    raise NotImplementedError()
```

---

## 设计模式

### 1. 模板方法模式

BaseTask 定义算法骨架，子类实现具体步骤：

```python
# 骨架（BaseTask）
def reset(self, env):
    self._reset_scene(env)      # 可覆盖
    self._reset_agent(env)      # 可覆盖
    self._reset_variables(env)  # 可覆盖
    # ... 重置 terminations 和 rewards

# 具体实现（BehaviorTask）
def reset(self, env):
    super().reset(env)  # 调用骨架
    # 添加特定逻辑：设置机器人姿态、唤醒对象
```

### 2. 策略模式

Termination conditions 和 reward functions 是可插拔的策略：

```python
# 可以动态组合不同的终止条件和奖励函数
task = BehaviorTask(
    termination_config={
        "max_steps": 1000,
        "add_collision_check": True,  # 假设支持
    },
    reward_config={
        "r_potential": 2.0,
        "r_collision": -0.1,  # 假设支持
    }
)
```

### 3. 组合模式

Task 由多个 termination conditions 和 reward functions 组合而成：

```python
# 聚合多个组件的结果
done = any(tc.done for tc in termination_conditions)
reward = sum(rf.reward for rf in reward_functions)
```

---

## 常见使用场景

### 1. 创建自定义任务

```python
from omnigibson.tasks.task_base import BaseTask
from omnigibson.termination_conditions.timeout import Timeout
from omnigibson.reward_functions.potential_reward import PotentialReward

class MyCustomTask(BaseTask):
    def _load(self, env):
        # 加载任务特定对象
        pass
    
    def _create_termination_conditions(self):
        return {
            "timeout": Timeout(max_steps=500),
            # 添加自定义终止条件
        }
    
    def _create_reward_functions(self):
        return {
            "my_reward": MyRewardFunction(...),
        }
    
    def _get_obs(self, env):
        return {}, {}
    
    def _load_non_low_dim_observation_space(self):
        return {}
    
    @classproperty
    def valid_scene_types(cls):
        from omnigibson.scenes.scene_base import Scene
        return {Scene}
    
    @classproperty
    def default_reward_config(cls):
        return {"r_scale": 1.0}
    
    @classproperty
    def default_termination_config(cls):
        return {"max_steps": 500}
```

### 2. 修改现有任务行为

```python
# 使用更长的 timeout
env = og.Environment(configs={
    "task": {
        "type": "BehaviorTask",
        "activity_name": "cleaning_windows",
        "termination_config": {
            "max_steps": 1000  # 默认 500
        },
        "reward_config": {
            "r_potential": 2.0  # 增强奖励信号
        }
    }
})
```

---

## 总结

**BaseTask 的核心职责**:
1. **定义任务目标**: 通过 termination conditions 指定成功/失败条件
2. **提供训练信号**: 通过 reward functions 指导强化学习
3. **管理生命周期**: load → reset → step 循环
4. **标准化接口**: 所有任务遵循统一的 API

**与其他组件的关系**:
- **Environment**: 持有 task 实例，每步调用 `task.step()`
- **Evaluator**: 使用 `task.object_scope` 加载实例，读取 `task.success`
- **BDDL (BehaviorTask)**: `task.compiled_task` 包含谓词定义
- **Scene**: task 在 reset 时操作场景对象

**关键设计思想**:
- 分离关注点：任务逻辑与物理模拟分离
- 可组合性：多个 terminations/rewards 灵活组合
- 可扩展性：通过继承添加新任务类型
