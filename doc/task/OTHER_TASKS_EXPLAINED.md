# 其他任务类型详解

本文档介绍除 BehaviorTask 外的其他任务类型。这些任务主要用于机器人基础能力的开发和测试。

---

## 任务类型概览

| 任务类型 | 继承关系 | 用途 | 场景类型 |
|---------|---------|------|---------|
| **DummyTask** | BaseTask | 测试、自由探索 | 任意 |
| **PointNavigationTask** | BaseTask | 导航到目标位置 | TraversableScene |
| **PointReachingTask** | PointNavigationTask | 末端执行器到达目标 | TraversableScene |
| **GraspTask** | BaseTask | 抓取指定物体 | 任意 |

---

## 1. DummyTask - 空任务

### 概述

最简单的任务类型，不定义任何目标、奖励或终止条件。用于自由探索或测试机器人控制。

**位置**: `OmniGibson/omnigibson/tasks/dummy_task.py`

### 实现

```python
class DummyTask(BaseTask):
    """空任务：无目标、无奖励、无终止条件"""
    
    def _load(self, env):
        pass  # 不加载任何东西
    
    def _create_termination_conditions(self):
        return dict()  # 无终止条件
    
    def _create_reward_functions(self):
        return dict()  # 无奖励
    
    def _get_obs(self, env):
        return dict(), dict()  # 无任务观察
    
    def _load_non_low_dim_observation_space(self):
        return dict()
    
    @classproperty
    def valid_scene_types(cls):
        return {Scene}  # 任意场景
    
    @classproperty
    def default_termination_config(cls):
        return {}
    
    @classproperty
    def default_reward_config(cls):
        return {}
```

### 使用场景

```python
# 创建自由探索环境
env = og.Environment(configs={
    "scene": {"type": "InteractiveTraversableScene", "scene_model": "Rs_int"},
    "robots": [{"type": "Fetch", ...}],
    "task": {
        "type": "DummyTask",
    }
})

# 没有任务目标，可以自由控制机器人
obs = env.reset()
for _ in range(1000):
    action = policy.get_action(obs)
    obs, reward, done, truncated, info = env.step(action)
    # reward 始终为 0
    # done 始终为 False（除非外部调用 env.reset()）
```

**适用场景**:
- 测试机器人控制器
- 收集探索数据
- 调试场景加载
- 演示机器人功能

---

## 2. PointNavigationTask - 点导航任务

### 概述

机器人需要导航到指定的目标位置（x, y 坐标），是经典的具身AI任务。

**位置**: `OmniGibson/omnigibson/tasks/point_navigation_task.py`

### 核心参数

```python
PointNavigationTask(
    robot_idn=0,              # 机器人索引
    floor=0,                  # 楼层
    initial_pos=None,         # 初始位置（None = 随机采样）
    initial_quat=None,        # 初始朝向（None = 随机）
    goal_pos=None,            # 目标位置（None = 随机）
    goal_tolerance=0.5,       # 目标容差（米）
    goal_in_polar=False,      # 是否用极坐标表示目标
    path_range=None,          # 路径长度范围 [min, max]
    visualize_goal=False,     # 是否可视化目标
    visualize_path=False,     # 是否可视化路径
    reward_type="l2",         # 奖励类型：l2 或 geodesic
    termination_config={
        "max_collisions": 500,
        "max_steps": 500,
        "fall_height": 0.03,
    },
    reward_config={
        "r_potential": 1.0,
        "r_collision": 0.1,
        "r_pointgoal": 10.0,
    },
)
```

---

### 终止条件

```python
def _create_termination_conditions(self):
    terminations = dict()
    
    # 1. MaxCollision: 碰撞次数过多
    terminations["max_collision"] = MaxCollision(
        max_collisions=500  # 累计碰撞次数
    )
    
    # 2. Timeout: 超时
    terminations["timeout"] = Timeout(max_steps=500)
    
    # 3. Falling: 机器人掉落
    terminations["falling"] = Falling(
        robot_idn=self._robot_idn,
        fall_height=0.03  # 低于地面 3cm 算掉落
    )
    
    # 4. PointGoal: 到达目标（成功条件）
    terminations["pointgoal"] = PointGoal(
        robot_idn=self._robot_idn,
        distance_tol=self._goal_tolerance,  # 0.5m
        distance_axes="xy",  # 只考虑 xy 平面距离
    )
    
    return terminations
```

**终止逻辑**:
- 任何一个触发即结束 episode
- 只有 `PointGoal` 触发才算成功（`success=True`）

---

### 奖励函数

```python
def _create_reward_functions(self):
    rewards = dict()
    
    # 1. PotentialReward: 基于势能（距离减少）
    rewards["potential"] = PotentialReward(
        potential_fcn=self.get_potential,
        r_potential=1.0,
    )
    
    # 2. CollisionReward: 碰撞惩罚
    rewards["collision"] = CollisionReward(
        r_collision=0.1  # 每次碰撞 -0.1
    )
    
    # 3. PointGoalReward: 到达目标奖励
    rewards["pointgoal"] = PointGoalReward(
        pointgoal=self._termination_conditions["pointgoal"],
        r_pointgoal=10.0,  # 到达目标 +10.0
    )
    
    return rewards
```

**势能计算**:

```python
def get_potential(self, env):
    """计算势能：到目标的距离"""
    if self._reward_type == "l2":
        # 欧几里得距离
        potential = self._get_l2_potential(env)
    elif self._reward_type == "geodesic":
        # 测地距离（考虑障碍物）
        potential = self._get_geodesic_potential(env)
        if potential is None:  # 无路径则回退到 L2
            potential = self._get_l2_potential(env)
    return potential

def _get_l2_potential(self, env):
    robot_pos = env.robots[self._robot_idn].get_position()[:2]
    return T.l2_distance(robot_pos, self._goal_pos[:2])

def _get_geodesic_potential(self, env):
    """通过场景的导航图计算最短路径长度"""
    _, geodesic_dist = self.get_shortest_path_to_goal(env=env)
    return geodesic_dist
```

**奖励示例**:

```python
# 假设初始距目标 10m，目标容差 0.5m
# t=0: 距离 10.0m → potential = 10.0
# t=1: 距离  9.8m → potential = 9.8
#      reward = (10.0 - 9.8) * 1.0 = +0.2  (potential reward)
#             + 0                       (no collision)
#             + 0                       (not reached)
#             = +0.2

# t=50: 距离 0.4m → potential = 0.4
#       到达目标！
#       reward = (0.5 - 0.4) * 1.0 = +0.1  (potential)
#              + 0                      (no collision)
#              + 10.0                   (pointgoal!)
#              = +10.1
```

---

### 观察空间

```python
def _get_obs(self, env):
    """获取任务相关观察"""
    
    # 1. 目标的相对位置（机器人坐标系）
    xy_pos_to_goal = self._global_pos_to_robot_frame(env, self._goal_pos)[:2]
    if self._goal_in_polar:
        # 转换为极坐标 (r, θ)
        xy_pos_to_goal = th.tensor(T.cartesian_to_polar(*xy_pos_to_goal))
    
    # 2. 机器人速度（机器人坐标系）
    ori_t = T.quat2mat(env.robots[self._robot_idn].get_orientation()).T
    lin_vel = ori_t @ env.robots[self._robot_idn].get_linear_velocity()
    ang_vel = ori_t @ env.robots[self._robot_idn].get_angular_velocity()
    
    low_dim_obs = dict(
        xy_pos_to_goal=xy_pos_to_goal,  # (2,) - 相对目标位置
        robot_lin_vel=lin_vel,           # (3,) - 线速度
        robot_ang_vel=ang_vel,           # (3,) - 角速度
    )
    
    return low_dim_obs, dict()
```

**完整观察示例**:

```python
obs = {
    # 任务观察
    "task_obs": {
        "xy_pos_to_goal": tensor([3.2, -1.5]),  # 目标在右前方 3.2m，左偏 1.5m
        "robot_lin_vel": tensor([0.5, 0.0, 0.0]),  # 前进 0.5 m/s
        "robot_ang_vel": tensor([0.0, 0.0, 0.1]),  # 左转 0.1 rad/s
    },
    # 机器人观察（proprioception + sensors）
    "robot0": {
        "proprio": tensor([...]),  # 关节位置、速度
        "rgb": np.array([...]),    # 相机图像
        ...
    }
}
```

---

### 初始化和重置

```python
def _reset_agent(self, env):
    """重置机器人位置"""
    env.robots[self._robot_idn].reset()
    
    # 采样初始位置和目标位置
    initial_pos, initial_quat, goal_pos = self._sample_initial_pose_and_goal_pos(env)
    
    # 设置机器人位置
    env.robots[self._robot_idn].set_position_orientation(
        position=initial_pos,
        orientation=initial_quat
    )
    
    # 存储采样的值
    self._initial_pos = initial_pos
    self._initial_quat = initial_quat
    self._goal_pos = goal_pos
    
    # 更新可视化标记（如果启用）
    if self._visualize_goal:
        self._initial_pos_marker.set_position(self._initial_pos)
        self._goal_pos_marker.set_position(self._goal_pos)

def _sample_initial_pose_and_goal_pos(self, env, max_trials=100):
    """采样有效的初始和目标位置"""
    
    # 1. 采样初始位置（无碰撞）
    if self._randomize_initial_pos:
        _, initial_pos = env.scene.get_random_point(
            floor=self._floor,
            robot=env.robots[self._robot_idn]
        )
    else:
        initial_pos = self._initial_pos
    
    # 2. 采样初始朝向（绕 z 轴随机）
    if self._randomize_initial_quat:
        yaw = random.uniform(0, 2 * math.pi)
        initial_quat = T.euler2quat([0, 0, yaw])
    else:
        initial_quat = self._initial_quat
    
    # 3. 采样目标位置（满足路径长度约束）
    if self._randomize_goal_pos:
        for _ in range(max_trials):
            _, goal_pos = env.scene.get_random_point(
                floor=self._floor,
                reference_point=initial_pos,
                robot=env.robots[self._robot_idn]
            )
            
            # 检查路径长度
            _, dist = env.scene.get_shortest_path(
                self._floor, initial_pos[:2], goal_pos[:2],
                entire_path=False,
                robot=env.robots[self._robot_idn]
            )
            
            # 验证路径在指定范围内
            if dist is not None and (
                self._path_range is None or
                self._path_range[0] < dist < self._path_range[1]
            ):
                break
    else:
        goal_pos = self._goal_pos
    
    return initial_pos, initial_quat, goal_pos
```

---

### 可视化

```python
# 启用可视化
env = og.Environment(configs={
    "task": {
        "type": "PointNavigationTask",
        "visualize_goal": True,   # 显示起点/终点标记
        "visualize_path": True,   # 显示路径航点
        "n_vis_waypoints": 10,
    }
})
```

**可视化元素**:
- **初始位置标记**: 红色圆柱（半径 = goal_tolerance）
- **目标位置标记**: 蓝色圆柱
- **路径航点**: 绿色圆柱（沿最短路径放置）

---

### SPL 指标

PointNavigationTask 自动计算 **SPL (Success weighted by Path Length)** 指标：

```python
def _step_termination(self, env, action, info=None):
    done, info = super()._step_termination(env, action, info)
    
    # 添加路径长度和 SPL
    info["path_length"] = self._path_length
    info["spl"] = (
        float(info["success"]) * min(1.0, self._geodesic_dist / self._path_length)
        if done and self._path_length != 0.0
        else 0.0
    )
    
    return done, info
```

**SPL 公式**:
```
SPL = Success * min(1, shortest_path_length / actual_path_length)
```

- 成功且路径最优 → SPL = 1.0
- 成功但绕路 → SPL ∈ (0, 1)
- 失败 → SPL = 0.0

---

### 使用示例

```python
# 固定起点和终点
env = og.Environment(configs={
    "scene": {"type": "InteractiveTraversableScene", "scene_model": "Rs_int"},
    "robots": [{"type": "Fetch"}],
    "task": {
        "type": "PointNavigationTask",
        "initial_pos": [0.0, 0.0, 0.0],
        "initial_quat": [0, 0, 0, 1],
        "goal_pos": [5.0, 3.0, 0.0],
        "goal_tolerance": 0.5,
        "visualize_goal": True,
    }
})

# 随机起点和终点，但约束路径长度
env = og.Environment(configs={
    "task": {
        "type": "PointNavigationTask",
        "path_range": [5.0, 15.0],  # 路径长度在 5-15m 之间
        "reward_type": "geodesic",   # 使用测地距离作为势能
    }
})

# Episode 循环
obs = env.reset()
for step in range(500):
    action = navigation_policy(obs)
    obs, reward, done, truncated, info = env.step(action)
    
    if done:
        print(f"Success: {info['done']['success']}")
        print(f"Path length: {info['path_length']:.2f}m")
        print(f"SPL: {info['spl']:.3f}")
        break
```

---

## 3. PointReachingTask - 点到达任务

### 概述

继承自 PointNavigationTask，但目标是用**机器人的末端执行器（EEF）**到达 3D 空间中的目标点，而不是机器人底盘。

**位置**: `OmniGibson/omnigibson/tasks/point_reaching_task.py`

### 与 PointNavigationTask 的区别

| 特性 | PointNavigationTask | PointReachingTask |
|------|---------------------|-------------------|
| 控制对象 | 机器人底盘 | 末端执行器 |
| 距离计算 | 底盘到目标 (xy) | EEF 到目标 (xyz) |
| 目标维度 | 2D (x, y) | 3D (x, y, z) |
| 观察 | `xy_pos_to_goal` | `eef_to_goal` (3D) |
| reward_type | l2 或 geodesic | 仅 l2 |

---

### 核心修改

#### 1. 终止条件：3D 距离

```python
def _create_termination_conditions(self):
    # 继承父类的所有终止条件
    terminations = super()._create_termination_conditions()
    
    # 替换 PointGoal：使用 xyz 轴而不是 xy
    terminations["pointgoal"] = PointGoal(
        robot_idn=self._robot_idn,
        distance_tol=self._goal_tolerance,  # 默认 0.1m（更小）
        distance_axes="xyz",  # 3D 距离！
    )
    
    return terminations
```

#### 2. 势能：从 EEF 计算

```python
def _get_l2_potential(self, env):
    """距离从机器人末端执行器计算，而不是底盘"""
    eef_pos = env.robots[self._robot_idn].get_eef_position()
    return T.l2_distance(eef_pos, self._goal_pos)
```

#### 3. 目标采样：包含高度

```python
def _sample_initial_pose_and_goal_pos(self, env, max_trials=100):
    # 先调用父类采样（底盘 xy + z=地面高度）
    initial_pos, initial_ori, goal_pos = super()._sample_initial_pose_and_goal_pos(
        env=env, max_trials=max_trials
    )
    
    # 添加高度随机化
    if self._height_range is not None:
        height_offset = random.uniform(self._height_range[0], self._height_range[1])
        goal_pos[2] += height_offset
    
    return initial_pos, initial_ori, goal_pos
```

#### 4. 观察：EEF 相关

```python
def _get_obs(self, env):
    # 获取父类观察
    low_dim_obs, obs = super()._get_obs(env=env)
    
    # 移除 xy_pos_to_goal，替换为 3D eef_to_goal
    low_dim_obs.pop("xy_pos_to_goal")
    low_dim_obs["eef_to_goal"] = self._global_pos_to_robot_frame(
        env=env, pos=self._goal_pos
    )  # (3,) - EEF 到目标的相对位置
    
    # 添加 EEF 的局部位置
    low_dim_obs["eef_local_pos"] = self._global_pos_to_robot_frame(
        env=env, pos=env.robots[self._robot_idn].get_eef_position()
    )  # (3,) - EEF 在机器人坐标系中的位置
    
    return low_dim_obs, obs
```

---

### 使用示例

```python
# 到达桌面上方的点
env = og.Environment(configs={
    "scene": {"type": "InteractiveTraversableScene", "scene_model": "Rs_int"},
    "robots": [{"type": "Fetch"}],
    "task": {
        "type": "PointReachingTask",
        "goal_tolerance": 0.1,      # 10cm 容差（比导航更精确）
        "height_range": [0.5, 1.5], # 目标高度在 0.5-1.5m
        "visualize_goal": True,
    }
})

obs = env.reset()
for step in range(500):
    # 需要控制机器人底盘 + 手臂
    action = manipulation_policy(obs)
    obs, reward, done, truncated, info = env.step(action)
    
    if done:
        print(f"EEF reached target: {info['done']['success']}")
        break
```

---

## 4. GraspTask - 抓取任务

### 概述

机器人需要抓取指定的物体。任务专注于测试和训练抓取能力。

**位置**: `OmniGibson/omnigibson/tasks/grasp_task.py`

### 核心参数

```python
GraspTask(
    obj_name="apple",             # 目标物体名称
    precached_reset_pose_path=None,  # 预缓存的重置姿态
    objects_config=[              # 场景中的物体配置
        {
            "type": "DatasetObject",
            "name": "apple",
            "category": "apple",
            "model": "agveuv",
            "position": [0.0, 0.5, 1.0],
            "orientation": [0, 0, 0, 1],
        }
    ],
    termination_config={"max_steps": 100000},
    reward_config={
        "dist_coeff": 0.1,
        "grasp_reward": 1.0,
        "collision_penalty": 1.0,
        "eef_position_penalty_coef": 0.01,
        "eef_orientation_penalty_coef": 0.001,
        "regularization_coef": 0.01,
    },
)
```

---

### 终止条件

```python
def _create_termination_conditions(self):
    terminations = dict()
    
    # 只有 Timeout，没有成功条件
    terminations["timeout"] = Timeout(max_steps=100000)
    
    return terminations
```

**注意**: GraspTask 没有显式的成功终止条件，通常由外部控制器决定何时结束。

---

### 奖励函数

```python
def _create_reward_functions(self):
    rewards = dict()
    
    # GraspReward: 复合奖励
    rewards["grasp"] = GraspReward(
        self.obj_name,
        dist_coeff=0.1,                    # EEF 到物体距离的系数
        grasp_reward=1.0,                  # 成功抓取的奖励
        collision_penalty=1.0,             # 碰撞惩罚
        eef_position_penalty_coef=0.01,    # EEF 移动惩罚
        eef_orientation_penalty_coef=0.001, # EEF 旋转惩罚
        regularization_coef=0.01,          # 关节正则化
    )
    
    return rewards
```

**GraspReward 计算**:

```python
# 内部实现（简化版）
reward = 0.0

# 1. 距离奖励（越近越好）
dist_to_obj = np.linalg.norm(eef_pos - obj_pos)
reward += -dist_coeff * dist_to_obj

# 2. 抓取成功
if robot.is_grasping(obj):
    reward += grasp_reward

# 3. 碰撞惩罚
if collision_detected:
    reward -= collision_penalty

# 4. 运动平滑惩罚
eef_movement = np.linalg.norm(eef_pos - prev_eef_pos)
reward -= eef_position_penalty_coef * eef_movement

# 5. 关节正则化（避免极端姿态）
joint_deviation = np.sum((joint_pos - neutral_pos)**2)
reward -= regularization_coef * joint_deviation
```

---

### 机器人重置

GraspTask 的重置比较复杂，因为需要将机器人放置在合适的抓取位置：

```python
def _reset_agent(self, env):
    robot = env.robots[0]
    
    # 1. 释放所有抓取
    for arm in robot.arm_names:
        robot.release_grasp_immediately(arm=arm)
    
    # 2. 使用预缓存姿态（快速）
    if self._reset_poses is not None:
        robot_pose = random.choice(self._reset_poses)
        robot.set_joint_positions(robot_pose["joint_pos"], joint_control_idx)
        robot.set_position_orientation(
            position=robot_pose["base_pos"],
            orientation=robot_pose["base_ori"]
        )
    
    # 3. 使用动作原语采样（慢但灵活）
    else:
        # a. 随机化关节位置（检测碰撞）
        for _ in range(MAX_JOINT_RANDOMIZATION_ATTEMPTS):
            joint_pos = self._get_random_joint_position(robot)
            if not self._primitive_controller.check_collisions(joint_pos):
                robot.set_joint_positions(joint_pos, joint_control_idx)
                break
        
        # b. 在物体附近采样 2D 姿态
        obj = env.scene.object_registry("name", self.obj_name)
        grasp_poses = get_grasp_poses_for_object_sticky(obj)
        grasp_pose = random.choice(grasp_poses)
        sampled_pose_2d = self._primitive_controller._sample_pose_near_object(
            obj, pose_on_obj=grasp_pose
        )
        robot_pose = self._primitive_controller._get_robot_pose_from_2d_pose(
            sampled_pose_2d
        )
        robot.set_position_orientation(*robot_pose)
        
        # c. 稳定物理（等待机器人静止）
        for _ in range(100):
            og.sim.step()
            if (np.linalg.norm(robot.get_linear_velocity()) < 1e-2 and
                np.linalg.norm(robot.get_angular_velocity()) < 1e-2):
                break
```

---

### 观察空间

```python
def _get_obs(self, env):
    """提供物体相对位置"""
    obj = env.scene.object_registry("name", self.obj_name)
    robot = env.robots[0]
    
    # 物体相对于机器人的位置
    relative_pos, _ = T.relative_pose_transform(
        *obj.get_position_orientation(),
        *robot.get_position_orientation()
    )
    
    return {"obj_pos": relative_pos}, dict()
```

---

### 使用示例

```python
# 定义要抓取的物体
objects_config = [
    {
        "type": "DatasetObject",
        "name": "apple_target",
        "category": "apple",
        "model": "agveuv",
        "position": [1.0, 0.0, 0.8],
        "orientation": [0, 0, 0, 1],
    }
]

env = og.Environment(configs={
    "scene": {"type": "Scene"},
    "robots": [{"type": "Fetch"}],
    "task": {
        "type": "GraspTask",
        "obj_name": "apple_target",
        "objects_config": objects_config,
        "termination_config": {"max_steps": 1000},
    }
})

obs = env.reset()
for step in range(1000):
    action = grasp_policy(obs)
    obs, reward, done, truncated, info = env.step(action)
    
    # 检查是否成功抓取
    if env.robots[0].is_grasping(obj_name="apple_target"):
        print("Successfully grasped the object!")
        break
```

---

## 任务对比总结

### 功能对比

| 特性 | DummyTask | PointNavigationTask | PointReachingTask | GraspTask |
|------|-----------|---------------------|-------------------|-----------|
| 终止条件 | 无 | 4 个 | 4 个 | 1 个 |
| 奖励函数 | 无 | 3 个 | 3 个 | 1 个 |
| 观察维度 | 0 | 8 | 9 | 3 |
| 成功条件 | - | 到达目标 (xy) | 到达目标 (xyz) | 抓取物体 |
| 可视化 | - | ✓ | ✓ | - |
| 场景要求 | 任意 | TraversableScene | TraversableScene | 任意 |

### 复杂度对比

```
DummyTask         ★☆☆☆☆  最简单，无任务逻辑
PointNavigation   ★★★☆☆  导航 + 路径规划
PointReaching     ★★★★☆  导航 + 操作 + 3D 控制
GraspTask         ★★★★★  精细操作 + 接触力控制
BehaviorTask      ★★★★★★ 多步骤 + 符号推理 + 物理交互
```

### 使用建议

**开发阶段**:
1. **DummyTask**: 测试场景加载、机器人控制
2. **PointNavigationTask**: 开发导航策略
3. **PointReachingTask**: 开发导航 + 操作策略
4. **GraspTask**: 开发抓取策略
5. **BehaviorTask**: 集成完整的家庭任务

**研究方向**:
- **导航**: PointNavigationTask
- **操作**: GraspTask, PointReachingTask
- **具身AI**: BehaviorTask

---

## 自定义任务示例

### 创建简单的"触碰物体"任务

```python
from omnigibson.tasks.task_base import BaseTask
from omnigibson.termination_conditions.timeout import Timeout
from omnigibson.reward_functions.potential_reward import PotentialReward
from omnigibson.object_states import Touching

class TouchObjectTask(BaseTask):
    """触碰指定物体的任务"""
    
    def __init__(self, obj_name, robot_idn=0, **kwargs):
        self.obj_name = obj_name
        self.robot_idn = robot_idn
        super().__init__(**kwargs)
    
    def _load(self, env):
        # 验证物体存在
        assert env.scene.object_registry("name", self.obj_name) is not None
    
    def _create_termination_conditions(self):
        return {
            "timeout": Timeout(max_steps=500),
            # 可以添加自定义终止条件
        }
    
    def _create_reward_functions(self):
        return {
            "potential": PotentialReward(
                potential_fcn=self.get_potential,
                r_potential=1.0,
            ),
        }
    
    def get_potential(self, env):
        """距离物体越近，势能越小"""
        obj = env.scene.object_registry("name", self.obj_name)
        eef_pos = env.robots[self.robot_idn].get_eef_position()
        obj_pos = obj.get_position()
        return np.linalg.norm(eef_pos - obj_pos)
    
    def _get_obs(self, env):
        obj = env.scene.object_registry("name", self.obj_name)
        robot = env.robots[self.robot_idn]
        
        # 物体相对 EEF 的位置
        relative_pos = obj.get_position() - robot.get_eef_position()
        
        # 是否正在触碰
        is_touching = obj.states[Touching].get_value(robot)
        
        low_dim_obs = {
            "obj_relative_pos": relative_pos,
            "is_touching": float(is_touching),
        }
        
        return low_dim_obs, dict()
    
    def _load_non_low_dim_observation_space(self):
        return dict()
    
    @classproperty
    def valid_scene_types(cls):
        return {Scene}
    
    @classproperty
    def default_termination_config(cls):
        return {"max_steps": 500}
    
    @classproperty
    def default_reward_config(cls):
        return {"r_potential": 1.0}
```

---

## 总结

**关键要点**:

1. **任务层次**:
   - DummyTask: 无目标基线
   - PointNavigationTask: 基础导航
   - PointReachingTask: 导航 + 操作
   - GraspTask: 精细操作
   - BehaviorTask: 复杂多步骤任务

2. **设计模式**:
   - 所有任务继承 BaseTask
   - 通过组合不同的 terminations 和 rewards 定制行为
   - 观察空间提供任务特定的状态信息

3. **扩展方法**:
   - 继承现有任务类
   - 覆盖特定方法（如 `_get_obs`, `get_potential`）
   - 添加自定义 termination conditions 和 reward functions

4. **最佳实践**:
   - 从简单任务开始（DummyTask）
   - 逐步增加复杂度
   - 充分利用可视化辅助调试
   - 使用合适的奖励塑形引导学习
