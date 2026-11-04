# Motion Planning与Robot执行完整指南

**日期**: 2026-10-11  
**目标**: TAMP下层Motion Planning的完整使用指南

---

## 一、Motion Planning在TAMP中的位置

### TAMP三层架构

```
┌─────────────────────────────────────────┐
│  Task Planning (High-Level)             │
│  - LLM生成action sequences              │
│  - 输出: skeleton = [action1, action2, ...]│
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Motion Planning (Mid-Level)            │
│  - 为每个action规划轨迹                  │
│  - 碰撞检测、IK求解、路径优化            │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Robot Control (Low-Level)              │
│  - 关节控制器执行轨迹                    │
│  - 反馈控制、误差修正                    │
└─────────────────────────────────────────┘
```

---

## 二、OmniGibson中可用的Motion Planning方法

### 2.1 概览

| 方法 | 适用场景 | 性能 | 需要CuRobo |
|------|---------|------|-----------|
| **SymbolicSemanticActionPrimitives** | TAMP高层规划 | 快速 | ❌ |
| **StarterSemanticActionPrimitives** | 物理执行 | 中等 | ✅ |
| **CuRobo Motion Generator** | 复杂轨迹规划 | 最优 | ✅ |
| **OMPL Base Planning** | 基座导航 | 慢 | ❌ |
| **Direct IK/Joint Control** | 简单运动 | 最快 | ❌ |

### 2.2 详细对比

#### A. SymbolicSemanticActionPrimitives（推荐用于TAMP）

**特点**：
- ✅ **直接teleport到目标状态**（符号化）
- ✅ **无需motion planning**（跳过物理）
- ✅ **适合高层规划和快速原型**
- ❌ 不考虑碰撞和轨迹
- ❌ 不适合真实机器人

**使用场景**：
```python
# TAMP高层规划验证
# 快速测试action sequences是否可行
from omnigibson.action_primitives.symbolic_semantic_action_primitives import (
    SymbolicSemanticActionPrimitives
)

primitives = SymbolicSemanticActionPrimitives(env, robot)
```

#### B. StarterSemanticActionPrimitives（推荐用于物理执行）

**特点**：
- ✅ **真实物理执行**（考虑碰撞、重力）
- ✅ **集成CuRobo**（GPU加速motion planning）
- ✅ **适合仿真评估和真实部署**
- ⚠️ 较慢（需要planning时间）
- ⚠️ 可能失败（碰撞、IK不可解）

**使用场景**：
```python
# 物理仿真执行
# BEHAVIOR Challenge评估
from omnigibson.action_primitives.starter_semantic_action_primitives import (
    StarterSemanticActionPrimitives
)

primitives = StarterSemanticActionPrimitives(
    env, robot,
    enable_head_tracking=True,
    curobo_batch_size=3
)
```

#### C. CuRobo Motion Generator（最底层）

**特点**：
- ✅ **NVIDIA官方GPU加速motion planner**
- ✅ **批量轨迹规划**（batch_size并行）
- ✅ **实时碰撞检测**
- ⚠️ 需要CUDA GPU
- ⚠️ 需要单独安装curobo

**使用场景**：
```python
# 低层轨迹规划（StarterPrimitives内部使用）
from omnigibson.action_primitives.curobo import CuRoboMotionGenerator

mg = CuRoboMotionGenerator(
    robot,
    device="cuda:0",
    batch_size=3,
    use_cuda_graph=True
)
```

---

## 三、从Task Planning到Robot执行的完整流程

### 3.1 工作流程

```python
# Step 1: Task Planning (LLM生成)
skeleton = [
    Subgoal("Navigate to radio", "navigate_to", "radio_receiver.n.01_1"),
    Subgoal("Toggle on radio", "toggle_on", "radio_receiver.n.01_1")
]

# Step 2: Grounding (映射到primitives)
for subgoal in skeleton:
    primitive = map_to_primitive(subgoal)  # "navigate_to" → NAVIGATE_TO
    obj = resolve_object(subgoal.target_object)  # "radio_receiver.n.01_1" → object instance
    
    # Step 3: Motion Planning + Execution
    yield from primitives.apply_ref(primitive, obj)
    # 内部：
    #   - CuRobo规划轨迹
    #   - IK求解关节角度
    #   - Controller执行轨迹
    #   - 碰撞检测
```

### 3.2 详细流程（以GRASP为例）

```python
def execute_grasp(obj):
    """
    完整的GRASP执行流程
    """
    # === 1. Task Planning层 (已完成) ===
    action = "grasp"
    target = obj
    
    # === 2. Motion Planning层 ===
    
    # 2.1 规划导航路径 (如果需要)
    if not near(robot, obj):
        # OMPL规划base motion
        base_path = plan_base_motion(
            robot,
            target_pose=obj.position[:2],
            planning_time=15.0
        )
        
        # 执行base navigation
        for waypoint in base_path:
            yield execute_base_motion(waypoint)
    
    # 2.2 采样抓取姿态
    grasp_poses = sample_grasp_poses(obj)
    
    # 2.3 为每个姿态规划arm motion (CuRobo)
    for grasp_pose in grasp_poses:
        try:
            # IK求解目标关节角度
            target_joints = solve_ik(robot.arm, grasp_pose)
            
            # CuRobo规划碰撞free轨迹
            trajectory = curobo.plan_motion(
                start_joints=robot.get_joint_positions(),
                goal_joints=target_joints,
                check_collision=True
            )
            
            if trajectory.success:
                break
        except:
            continue
    
    # === 3. Robot Control层 ===
    
    # 3.1 执行arm轨迹
    for waypoint in trajectory.waypoints:
        # Controller发送关节目标
        action = robot.controller.compute_action(
            current_joints=robot.get_joint_positions(),
            target_joints=waypoint
        )
        
        # 仿真步进
        obs, reward, done, info = env.step(action)
        yield action
    
    # 3.2 闭合gripper
    yield close_gripper()
    
    # 3.3 验证抓取成功
    if not robot.is_grasping(obj):
        raise ExecutionError("Grasp failed")
```

---

## 四、环境和Robot配置

### 4.1 基础环境配置

```python
# tamp/examples/env_config.py

import omnigibson as og
from omnigibson.macros import gm

def create_tamp_environment(
    task_name="turning_on_radio",
    robot_type="Tiago",
    use_primitives=True,
    headless=True
):
    """
    创建适合TAMP的OmniGibson环境
    """
    # 全局设置
    gm.HEADLESS = headless
    gm.USE_GPU_DYNAMICS = True
    gm.ENABLE_FLATCACHE = False  # 更好的物理精度
    
    # 环境配置
    config = {
        "env": {
            "action_frequency": 30,      # 控制频率
            "physics_frequency": 120,     # 物理频率
            "device": "cuda:0",
            "automatic_reset": False,
            "flatten_action_space": False,
        },
        
        "scene": {
            "type": "InteractiveTraversableScene",
            "scene_model": "Rs_int",  # 简单场景
            "load_task_relevant_only": True,  # 只加载任务相关对象
        },
        
        "robots": [get_robot_config(robot_type, use_primitives)],
        
        "task": {
            "type": "BehaviorTask",
            "activity_name": task_name,
            "activity_definition": 0,
            "online_object_sampling": False,
        }
    }
    
    # 创建环境
    env = og.Environment(configs=config)
    return env
```

### 4.2 Robot配置

#### A. Tiago（推荐用于研究）

```python
def get_tiago_config(use_primitives=True):
    """
    Tiago robot配置
    - 双臂机器人
    - Holonomic base (全向移动)
    - 适合室内操作任务
    """
    config = {
        "type": "Tiago",
        "obs_modalities": ["rgb", "proprio"],
        "scale": 1.0,
        "self_collisions": True,  # 自碰撞检测
        "action_normalize": False,
        "action_type": "continuous",
        "grasping_mode": "sticky",  # 或 "physical"
        
        # 控制器配置
        "controller_config": {
            # Base controller (导航)
            "base": {
                "name": "HolonomicBaseJointController",
                "motor_type": "position",
                "command_input_limits": None,
                "use_impedances": False,
            },
            
            # Arm controllers (操作)
            "arm_left": {
                "name": "JointController",  # 或 "InverseKinematicsController"
                "motor_type": "position",
                "command_input_limits": None,
                "use_delta_commands": False,
                "use_impedances": False,
            },
            "arm_right": {
                "name": "JointController",
                "motor_type": "position",
            },
            
            # Gripper controllers
            "gripper_left": {
                "name": "MultiFingerGripperController",
                "motor_type": "position",
            },
            "gripper_right": {
                "name": "MultiFingerGripperController",
                "motor_type": "position",
            },
        }
    }
    
    return config
```

#### B. R1/R1Pro（BEHAVIOR Challenge官方）

```python
def get_r1pro_config(use_primitives=True):
    """
    R1Pro robot配置
    - 单臂机器人
    - Differential drive base
    - BEHAVIOR Challenge官方使用
    """
    config = {
        "type": "R1Pro",
        "obs_modalities": ["rgb", "proprio"],
        "action_normalize": False,
        "action_type": "continuous",
        "grasping_mode": "sticky",
        
        "controller_config": {
            "base": {
                "name": "DifferentialDriveController",  # 差速驱动
            },
            "arm": {
                "name": "JointController",
                "motor_type": "position",
            },
            "gripper": {
                "name": "MultiFingerGripperController",
            },
        }
    }
    
    return config
```

### 4.3 Controller选择

| Controller | 用途 | 输入 | 优点 | 缺点 |
|-----------|------|------|------|------|
| **JointController** | 关节位置控制 | 关节角度 | 精确、快速 | 需要IK |
| **InverseKinematicsController** | 末端位置控制 | (x,y,z,quat) | 直观 | IK可能失败 |
| **OperationalSpaceController** | 力/力矩控制 | 力/力矩 | 柔顺 | 复杂 |
| **HolonomicBaseJointController** | 全向移动 | (x,y,yaw) | 灵活 | 仅Tiago |
| **DifferentialDriveController** | 差速驱动 | (v,ω) | 真实 | 转弯限制 |

---

## 五、Motion Planning组件使用

### 5.1 CuRobo使用（推荐）

#### 安装
```bash
# 在behavior conda环境中
conda activate behavior
pip install curobo
```

#### 基础使用
```python
from omnigibson.action_primitives.curobo import CuRoboMotionGenerator

# 初始化
mg = CuRoboMotionGenerator(
    robot=robot,
    device="cuda:0",
    batch_size=3,  # 并行规划3条轨迹
    use_cuda_graph=True,  # GPU优化
    collision_activation_distance=0.005,  # 碰撞距离阈值
)

# 规划motion
result = mg.plan_to_joint_configuration(
    target_joints=target_joints,
    current_joints=robot.get_joint_positions(),
    embodiment=CuRoboEmbodimentSelection.ARM,  # 或 BASE, DEFAULT
)

if result.success:
    trajectory = result.path  # List of joint configurations
    for waypoint in trajectory:
        action = controller.compute_action(waypoint)
        obs, _, _, _ = env.step(action)
else:
    print(f"Planning failed: {result.error}")
```

#### 进阶配置
```python
# 自定义motion配置
motion_cfg_kwargs = {
    "interpolation_dt": 0.02,  # 插值时间步
    "max_acceleration": 10.0,   # 最大加速度
    "max_jerk": 100.0,          # 最大jerk
    "collision_check_freq": 0.02,  # 碰撞检测频率
}

mg = CuRoboMotionGenerator(
    robot=robot,
    motion_cfg_kwargs=motion_cfg_kwargs,
    batch_size=5,  # 更多候选轨迹
)
```

### 5.2 OMPL Base Planning

```python
from omnigibson.utils.motion_planning_utils import plan_base_motion

# 规划base导航
path = plan_base_motion(
    robot=robot,
    end_conf=[target_x, target_y, target_yaw],  # 目标2D pose
    context=planning_context,
    planning_time=15.0,  # 规划时间限制
)

# 执行路径
for waypoint in path:
    # waypoint = [x, y, yaw]
    action = navigate_to_waypoint(waypoint)
    obs, _, _, _ = env.step(action)
```

### 5.3 IK Solver

```python
from omnigibson.utils.control_utils import IKSolver

# 创建IK solver
ik_solver = IKSolver(
    robot=robot,
    arm_name="arm_left",
    ee_link_name=robot.eef_link_names["arm_left"]
)

# 求解IK
target_pose = (position, quaternion)  # (np.array[3], np.array[4])
joint_positions = ik_solver.solve(
    target_pose=target_pose,
    initial_guess=robot.get_joint_positions()
)

if joint_positions is not None:
    # IK成功
    action = move_to_joints(joint_positions)
else:
    # IK失败，尝试其他姿态
    print("IK failed for target pose")
```

---

## 六、轨迹执行与碰撞检测

### 6.1 轨迹执行

```python
def execute_trajectory(robot, controller, trajectory, env):
    """
    执行一条关节空间轨迹
    
    Args:
        robot: Robot instance
        controller: Joint controller
        trajectory: List of joint configurations
        env: Environment
    """
    for i, waypoint in enumerate(trajectory):
        # 计算控制动作
        action = controller.compute_action(
            current_joints=robot.get_joint_positions(),
            target_joints=waypoint
        )
        
        # 执行一步
        obs, reward, done, info = env.step(action)
        
        # 碰撞检测
        if detect_collision(robot):
            print(f"Collision detected at waypoint {i}")
            return False
        
        # 检查是否到达目标
        joint_error = np.linalg.norm(
            robot.get_joint_positions() - waypoint
        )
        if joint_error < 0.01:  # 阈值
            continue
    
    return True
```

### 6.2 碰撞检测

```python
from omnigibson.utils.motion_planning_utils import detect_robot_collision_in_sim

# 实时碰撞检测
if detect_robot_collision_in_sim(robot):
    print("Robot is in collision!")
    # 停止运动或重新规划
```

#### 碰撞检测方法对比

| 方法 | 速度 | 精度 | 使用场景 |
|------|------|------|---------|
| **CuRobo collision check** | 最快 | 高 | Planning阶段 |
| **detect_robot_collision_in_sim** | 快 | 最高 | 执行时验证 |
| **Physics contacts** | 慢 | 最高 | 详细分析 |

### 6.3 错误处理

```python
def safe_execute_action(primitive, obj, max_retries=3):
    """
    带错误处理的action执行
    """
    for attempt in range(max_retries):
        try:
            yield from primitive.apply_ref(
                primitive_enum,
                obj,
                attempts=1
            )
            return True  # 成功
            
        except ActionPrimitiveError as e:
            if e.reason == ActionPrimitiveError.Reason.PRE_CONDITION_ERROR:
                # 前置条件不满足，无法重试
                print(f"Precondition failed: {e}")
                return False
            
            elif e.reason == ActionPrimitiveError.Reason.EXECUTION_ERROR:
                # 执行失败，可以重试
                print(f"Execution failed (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    # 小幅度随机扰动重试
                    perturb_robot_pose(robot, noise=0.05)
                    continue
            
            elif e.reason == ActionPrimitiveError.Reason.POST_CONDITION_ERROR:
                # 后置条件不满足，可能需要重新规划
                print(f"Postcondition failed: {e}")
                return False
    
    return False
```

---

## 七、完整示例

### 7.1 TAMP执行完整示例

```python
# tamp/examples/complete_execution_example.py

import omnigibson as og
from omnigibson.macros import gm
from omnigibson.action_primitives.starter_semantic_action_primitives import (
    StarterSemanticActionPrimitives,
    StarterSemanticActionPrimitiveSet
)

from tamp.planners.llm_planner import LLMPlanner
from tamp.utils.bddl_utils import load_bddl_task, extract_initial_state

def main():
    # === 1. 环境设置 ===
    gm.HEADLESS = True
    gm.USE_GPU_DYNAMICS = True
    
    config = {
        "scene": {"type": "InteractiveTraversableScene", "scene_model": "Rs_int"},
        "robots": [{
            "type": "Tiago",
            "action_type": "continuous",
            "grasping_mode": "sticky",
            "controller_config": {
                "base": {"name": "HolonomicBaseJointController"},
                "arm_left": {"name": "JointController"},
            }
        }],
        "task": {
            "type": "BehaviorTask",
            "activity_name": "turning_on_radio",
        }
    }
    
    env = og.Environment(configs=config)
    robot = env.robots[0]
    
    # === 2. 初始化Motion Planning ===
    primitives = StarterSemanticActionPrimitives(
        env=env,
        robot=robot,
        enable_head_tracking=True,
        curobo_batch_size=3,  # CuRobo批量规划
    )
    
    # === 3. Task Planning (LLM) ===
    planner = LLMPlanner(model="gpt-4")
    conditions, _ = load_bddl_task("turning_on_radio")
    initial_state = extract_initial_state(conditions)
    
    plan = planner.plan(
        task_description="Turn on the radio",
        initial_state=initial_state,
        goal_state=frozenset(),
        available_objects=["radio_receiver.n.01_1"],
        available_actions=["navigate_to", "toggle_on"]
    )
    
    print(f"Generated plan with {len(plan)} subgoals:")
    for i, sg in enumerate(plan.subgoals):
        print(f"  {i+1}. {sg.description}")
    
    # === 4. 执行Plan ===
    for subgoal in plan.subgoals:
        print(f"\n→ Executing: {subgoal.description}")
        
        # 映射到primitive
        primitive_enum = map_action_to_primitive(subgoal.action_type)
        target_obj = env.scene.object_registry("name", subgoal.target_object)
        
        # Motion Planning + Execution
        try:
            gen = primitives.apply_ref(primitive_enum, target_obj, attempts=3)
            
            # 逐步执行（generator）
            for action in gen:
                # action是low-level控制信号
                obs, reward, done, info = env.step(action)
                
                # 可选：监控执行
                if done:
                    break
            
            print(f"  ✓ Success!")
            subgoal.status = SubgoalStatus.SUCCESS
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            subgoal.status = SubgoalStatus.FAILED
            
            # Replanning
            print("  Replanning...")
            new_plan = planner.replan(plan, initial_state, {"error": str(e)})
            plan = new_plan
    
    # === 5. 验证Goal ===
    radio = env.scene.object_registry("name", "radio_receiver.n.01_1")
    success = radio.states[ToggledOn].get_value()
    print(f"\n{'='*50}")
    print(f"Task {'SUCCESS' if success else 'FAILED'}")
    print(f"{'='*50}")
    
    env.close()


def map_action_to_primitive(action_type):
    """映射action type到primitive enum"""
    mapping = {
        "navigate_to": StarterSemanticActionPrimitiveSet.NAVIGATE_TO,
        "grasp": StarterSemanticActionPrimitiveSet.GRASP,
        "toggle_on": StarterSemanticActionPrimitiveSet.TOGGLE_ON,
        # ... 其他映射
    }
    return mapping[action_type]


if __name__ == "__main__":
    main()
```

### 7.2 轨迹可视化（可选）

```python
def visualize_trajectory(robot, trajectory):
    """
    可视化机器人轨迹
    """
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    
    # 提取end-effector轨迹
    ee_positions = []
    for waypoint in trajectory:
        robot.set_joint_positions(waypoint)
        ee_pos = robot.get_eef_position()
        ee_positions.append(ee_pos)
    
    ee_positions = np.array(ee_positions)
    
    # 3D plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot(ee_positions[:, 0], ee_positions[:, 1], ee_positions[:, 2])
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    plt.title("End-Effector Trajectory")
    plt.show()
```

---

## 八、常见问题与解决方案

### 8.1 CuRobo安装问题

```bash
# 问题：CUDA版本不匹配
# 解决：检查CUDA版本
nvcc --version
python -c "import torch; print(torch.cuda.is_available())"

# 重新安装匹配的curobo
pip install curobo --no-cache-dir
```

### 8.2 Motion Planning失败

**原因**：
1. IK无解
2. 碰撞无法避免
3. 规划超时

**解决**：
```python
# 增加采样次数
mg = CuRoboMotionGenerator(batch_size=10)  # 更多候选

# 放宽碰撞阈值
mg = CuRoboMotionGenerator(collision_activation_distance=0.01)

# 增加规划时间
result = mg.plan_motion(planning_time=30.0)
```

### 8.3 轨迹执行不精确

**原因**：
1. Controller频率太低
2. 关节阻尼太大
3. 物理不稳定

**解决**：
```python
# 提高控制频率
config["env"]["action_frequency"] = 60  # 从30提高到60

# 降低阻尼
robot.set_joint_damping(damping=0.1)

# 使用impedance control
controller_config = {
    "arm": {
        "use_impedances": True,
        "kp": 50.0,  # 比例增益
        "kd": 10.0,  # 微分增益
    }
}
```

### 8.4 自碰撞问题

```python
# 启用自碰撞检测
robot_config = {
    "self_collisions": True,
}

# 在CuRobo中考虑自碰撞
mg = CuRoboMotionGenerator(
    robot=robot,
    check_self_collision=True,
)
```

---

## 九、性能优化建议

### 9.1 Motion Planning优化

```python
# 1. 使用CUDA Graph（GPU优化）
mg = CuRoboMotionGenerator(use_cuda_graph=True)

# 2. 批量规划
results = mg.plan_batch(
    target_poses=[pose1, pose2, pose3],
    batch_size=3
)

# 3. Warm start
mg.warmup()  # 预热，加速后续规划
```

### 9.2 仿真优化

```python
# 降低物理精度（更快）
gm.ENABLE_FLATCACHE = True
config["env"]["physics_frequency"] = 60  # 从120降低

# 减少碰撞检测
gm.COLLISION_MARGIN = 0.01  # 更大的碰撞裕度
```

### 9.3 并行执行

```python
# 使用VecEnv并行多个任务
from omnigibson.envs import VecEnvBase

vec_env = VecEnvBase(configs=[config1, config2, config3])
```

---

## 十、总结

### 核心要点

1. **三层架构清晰**：
   - Task Planning (LLM) → skeleton
   - Motion Planning (CuRobo) → trajectory
   - Robot Control (Controllers) → execution

2. **选择合适的Primitives**：
   - 原型/验证：SymbolicSemanticActionPrimitives
   - 仿真评估：StarterSemanticActionPrimitives
   - 低层控制：CuRobo + Controllers

3. **无需额外代码**：
   - ✅ 轨迹规划：CuRobo自动处理
   - ✅ 碰撞检测：内置功能
   - ✅ 关节控制：Controller封装

4. **关键配置**：
   - Robot config：选择合适的controllers
   - CuRobo：batch_size, collision_distance
   - 环境：physics_frequency, action_frequency

### 下一步行动

1. **立即测试**：运行完整示例（Section 7.1）
2. **验证primitives**：测试10个简单任务
3. **性能调优**：根据Section 9优化
4. **扩展支持**：添加更多action mappings

**你不需要**：
- ❌ 手写轨迹规划代码
- ❌ 手写碰撞检测代码
- ❌ 手写关节控制代码
- ✅ 只需配置和调用现有接口！
