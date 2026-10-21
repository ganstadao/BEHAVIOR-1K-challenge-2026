# Action Primitives 系统详解

本文档详细讲解 OmniGibson 的 Action Primitives 系统，包括 StarterSemanticActionPrimitives API、apply_ref 调用方式、连续参数采样以及 CuRobo 运动规划的使用。

## 1. Action Primitives 系统概览

### 1.1 什么是 Action Primitives？

**定义**: Action Primitives 是高层次的语义动作（如 GRASP, PLACE, NAVIGATE），将其分解为低层次的控制器指令序列。

```
高层次动作: "GRASP(apple)"
    ↓
Action Primitive
    ↓
低层次指令序列:
    1. Navigate to apple
    2. Move hand to pre-grasp pose
    3. Move hand to grasp pose
    4. Close gripper
    5. Verify grasp success
```

### 1.2 系统架构

```
BaseActionPrimitiveSet (抽象基类)
    ├── get_action_space()    # 定义动作空间
    ├── apply(action)         # 应用数值动作
    └── apply_ref(prim, args) # 应用语义动作
        ↓
StarterSemanticActionPrimitives (实现类)
    ├── 9 个语义动作
    ├── CuRoboMotionGenerator (运动规划器)
    └── 连续参数采样器
        ↓
SymbolicSemanticActionPrimitives (符号化版本)
    └── 从 BDDL 符号动作生成具体参数
```

## 2. StarterSemanticActionPrimitives API

### 2.1 支持的语义动作

```python
class StarterSemanticActionPrimitiveSet(IntEnum):
    GRASP = auto()          # 抓取物体
    PLACE_ON_TOP = auto()   # 放置在物体上方
    PLACE_INSIDE = auto()   # 放置在物体内部
    OPEN = auto()           # 打开物体（如抽屉、门）
    CLOSE = auto()          # 关闭物体
    NAVIGATE_TO = auto()    # 导航到物体附近
    TOGGLE_ON = auto()      # 打开开关
    TOGGLE_OFF = auto()     # 关闭开关
    RELEASE = auto()        # 释放物体
```

### 2.2 初始化

```python
from omnigibson.action_primitives import StarterSemanticActionPrimitives

# 创建 primitive set
primitives = StarterSemanticActionPrimitives(
    env,                              # OmniGibson 环境
    robot,                            # 机器人实例
    
    # === 可选参数 ===
    
    # 抓取控制
    enable_head_tracking=True,        # 启用头部追踪目标物体
    
    # 对象过滤
    task_relevant_objects_only=False, # 只考虑任务相关物体
    
    # CuRobo 配置
    curobo_batch_size=3,              # CuRobo 批量大小
    
    # 调试
    debug_visual_marker=None,         # 调试可视化标记物体
    skip_curobo_initilization=False,  # 跳过 CuRobo 初始化（测试用）
)
```

### 2.3 控制器映射

```python
# 内部映射表
self.controller_functions = {
    StarterSemanticActionPrimitiveSet.GRASP: self._grasp,
    StarterSemanticActionPrimitiveSet.PLACE_ON_TOP: self._place_on_top,
    StarterSemanticActionPrimitiveSet.PLACE_INSIDE: self._place_inside,
    StarterSemanticActionPrimitiveSet.OPEN: self._open,
    StarterSemanticActionPrimitiveSet.CLOSE: self._close,
    StarterSemanticActionPrimitiveSet.NAVIGATE_TO: self._navigate_to_obj,
    StarterSemanticActionPrimitiveSet.RELEASE: self._execute_release,
    StarterSemanticActionPrimitiveSet.TOGGLE_ON: self._toggle_on,
    StarterSemanticActionPrimitiveSet.TOGGLE_OFF: self._toggle_off,
}
```

## 3. 如何调用 Primitives (apply_ref)

### 3.1 apply() vs apply_ref()

```python
# === 方法 1: apply() - 数值动作 ===
action = 5  # 假设 5 对应 NAVIGATE_TO 第一个物体
for low_level_action in primitives.apply(action):
    obs, reward, done, info = env.step(low_level_action)

# === 方法 2: apply_ref() - 语义动作 ===
target_obj = env.scene.object_registry("name", "apple_1")
for low_level_action in primitives.apply_ref(
    StarterSemanticActionPrimitiveSet.GRASP,  # primitive
    target_obj                                 # *args
):
    obs, reward, done, info = env.step(low_level_action)
```

### 3.2 apply_ref() 详解

```python
def apply_ref(self, primitive, *args: Any, attempts=5):
    """
    应用语义动作（通过引用）
    
    Args:
        primitive (StarterSemanticActionPrimitiveSet): 要执行的 primitive
        *args: Primitive 特定的参数
            - GRASP(obj)
            - PLACE_ON_TOP(obj)
            - PLACE_INSIDE(obj)
            - OPEN(obj)
            - CLOSE(obj)
            - NAVIGATE_TO(obj)
            - TOGGLE_ON(obj)
            - TOGGLE_OFF(obj)
            - RELEASE() - 无参数
        attempts (int): 失败后重试次数（默认 5）
    
    Yields:
        th.tensor or None: 每步的低层次动作或 None（表示完成）
    
    Raises:
        ActionPrimitiveError: 如果 primitive 执行失败
    """
    # 1. 获取对应的控制器函数
    ctrl = self.controller_functions[primitive]
    
    errors = []
    for attempt in range(attempts):
        try:
            # 2. 执行 primitive（生成器）
            yield from ctrl(*args)
            success = True
            break  # 成功则退出重试循环
        
        except ActionPrimitiveError as e:
            errors.append(e)
            # 继续下一次尝试
        
        # 3. 每次尝试后清理
        try:
            # 如果没有抓取物体，释放手
            if not self._get_obj_in_hand():
                yield from self._execute_release()
        except ActionPrimitiveError:
            pass
        
        try:
            # 收起手臂
            yield from self._reset_robot()
        except ActionPrimitiveError:
            pass
    
    # 4. 如果所有尝试都失败
    if not success:
        raise ActionPrimitiveErrorGroup(errors)
```

### 3.3 完整使用示例

```python
import omnigibson as og
from omnigibson.action_primitives import StarterSemanticActionPrimitives

# 1. 创建环境
config = {...}  # 环境配置
env = og.Environment(configs=config)

# 2. 获取机器人
robot = env.robots[0]

# 3. 创建 action primitives
primitives = StarterSemanticActionPrimitives(env, robot)

# 4. 获取目标物体
apple = env.scene.object_registry("name", "apple_1")
table = env.scene.object_registry("name", "table_1")

# === 示例 1: 抓取 ===
print("Grasping apple...")
try:
    for action in primitives.apply_ref(
        StarterSemanticActionPrimitiveSet.GRASP,
        apple
    ):
        if action is not None:
            obs, reward, done, info = env.step(action)
        else:
            # action is None means primitive completed this step
            pass
    print("Grasp succeeded!")
except ActionPrimitiveError as e:
    print(f"Grasp failed: {e.reason} - {e.message}")

# === 示例 2: 放置 ===
print("Placing apple on table...")
try:
    for action in primitives.apply_ref(
        StarterSemanticActionPrimitiveSet.PLACE_ON_TOP,
        table
    ):
        if action is not None:
            obs, reward, done, info = env.step(action)
    print("Place succeeded!")
except ActionPrimitiveError as e:
    print(f"Place failed: {e.reason} - {e.message}")

# === 示例 3: 导航 ===
print("Navigating to table...")
try:
    for action in primitives.apply_ref(
        StarterSemanticActionPrimitiveSet.NAVIGATE_TO,
        table
    ):
        if action is not None:
            obs, reward, done, info = env.step(action)
    print("Navigation succeeded!")
except ActionPrimitiveError as e:
    print(f"Navigation failed: {e.reason} - {e.message}")
```

## 4. 连续参数采样

### 4.1 位置采样

#### 4.1.1 抓取位姿采样 (_sample_grasp_pose)

```python
def _sample_grasp_pose(self, obj):
    """
    采样物体的抓取位姿
    
    返回: (pre_grasp_pose, grasp_pose)
        - pre_grasp_pose: 接近位姿（距离物体 10cm）
        - grasp_pose: 实际抓取位姿（接触物体）
    """
    # Step 1: 更新 CuRobo 障碍物
    self._motion_generator.update_obstacles()
    
    for _ in range(m.MAX_ATTEMPTS_FOR_SAMPLING_POSE_WITH_OBJECT):
        # Step 2: 采样抓取位置（物体表面的一个点）
        grasp_position, grasp_quaternion = self._sample_position_on_object(obj)
        
        # Step 3: 对齐抓取方向
        # 使抓手的 approach 方向（通常是 -z）指向物体中心
        approach_direction = obj.get_position() - grasp_position
        approach_direction = approach_direction / th.norm(approach_direction)
        
        # 构建旋转矩阵
        # approach_direction -> gripper -z axis
        # up_vector -> gripper y axis
        grasp_rotation = T.euler2mat(
            self._align_gripper_with_direction(approach_direction)
        )
        grasp_quaternion = T.mat2quat(grasp_rotation)
        
        # Step 4: 预抓取位姿 = 抓取位姿 - 10cm along approach direction
        offset = -approach_direction * m.GRASP_APPROACH_DISTANCE  # 0.1m
        pre_grasp_position = grasp_position + offset
        
        pre_grasp_pose = (pre_grasp_position, grasp_quaternion)
        grasp_pose = (grasp_position, grasp_quaternion)
        
        # Step 5: 验证位姿可达性（使用 CuRobo）
        # 检查是否会与物体或其他障碍物碰撞
        if self._target_in_reach_of_robot(
            pre_grasp_pose, 
            skip_obstacle_update=True
        ):
            return pre_grasp_pose, grasp_pose
    
    # 如果所有尝试都失败
    raise ActionPrimitiveError(
        ActionPrimitiveError.Reason.SAMPLING_ERROR,
        "Failed to sample a valid grasp pose after maximum attempts",
    )
```

**采样空间**:
```python
# 物体表面采样
# 1. 获取物体 AABB
obj_aabb_center, obj_aabb_extent = obj.aabb_center, obj.aabb_extent

# 2. 在 AABB 表面均匀采样
# 6个面 × N个采样点
sample_candidates = []
for face in ["top", "bottom", "left", "right", "front", "back"]:
    for i in range(num_samples_per_face):
        # 在面上随机采样
        if face == "top":
            x = random.uniform(-extent_x/2, extent_x/2)
            y = random.uniform(-extent_y/2, extent_y/2)
            z = extent_z/2
        # ... 其他面类似
        
        sample = center + [x, y, z]
        sample_candidates.append(sample)

# 3. 过滤无效位置（穿透物体、太远等）
valid_samples = filter_invalid_samples(sample_candidates, obj)
```

#### 4.1.2 放置位姿采样 (_sample_pose_with_object_and_predicate)

```python
def _sample_pose_with_object_and_predicate(
    self, 
    predicate,      # OnTop 或 Inside
    obj_in_hand,    # 手中的物体
    target_obj,     # 目标物体（放置位置）
    world_aligned=True  # 是否对齐世界坐标系
):
    """
    采样满足谓词的放置位姿
    
    例如: OnTop(apple, table) - 苹果在桌子上
    """
    # Step 1: 使用 object_states 采样器
    # OnTop.sample() 会返回满足 "apple on top of table" 的位姿
    for _ in range(m.MAX_ATTEMPTS_FOR_SAMPLING_POSE_WITH_PREDICATE):
        # 采样器返回: (position, quaternion)
        sampled_pose = obj_in_hand.states[predicate].sample(
            target_obj,
            # 额外约束
            check_physics=True,      # 检查物理合理性
            check_overlap=True,      # 检查是否与其他物体重叠
        )
        
        if sampled_pose is None:
            continue
        
        position, quaternion = sampled_pose
        
        # Step 2: 如果需要，对齐到世界坐标系
        if world_aligned:
            # 保持位置，但旋转对齐到世界 z 轴
            # 这样物体会"平放"而不是倾斜
            euler = T.quat2euler(quaternion)
            euler[:2] = 0.0  # 清除 roll 和 pitch，只保留 yaw
            quaternion = T.euler2quat(euler)
        
        # Step 3: 验证位姿
        # 检查手能否到达这个位姿
        hand_pose = self._get_hand_pose_for_object_pose(sampled_pose)
        if self._target_in_reach_of_robot(hand_pose):
            return sampled_pose
    
    raise ActionPrimitiveError(
        ActionPrimitiveError.Reason.SAMPLING_ERROR,
        f"Failed to sample valid {predicate} pose",
    )
```

**OnTop 采样空间**:
```python
# object_states/on_top.py: OnTop.sample()

def sample(self, target_obj):
    """采样 OnTop 关系的位姿"""
    # 1. 获取目标物体的顶部表面
    target_aabb_center, target_aabb_extent = target_obj.aabb_center, target_obj.aabb_extent
    surface_height = target_aabb_center[2] + target_aabb_extent[2] / 2
    
    # 2. 在顶部表面上随机采样 x, y
    for _ in range(max_attempts):
        # 均匀采样 (避免边缘)
        margin = 0.05  # 5cm 边距
        x = random.uniform(
            target_aabb_center[0] - target_aabb_extent[0]/2 + margin,
            target_aabb_center[0] + target_aabb_extent[0]/2 - margin
        )
        y = random.uniform(
            target_aabb_center[1] - target_aabb_extent[1]/2 + margin,
            target_aabb_center[1] + target_aabb_extent[1]/2 - margin
        )
        
        # 3. 计算物体底部应该在的高度
        obj_aabb_extent = self.obj.aabb_extent
        z = surface_height + obj_aabb_extent[2] / 2 + 0.01  # 1cm 间隙
        
        position = th.tensor([x, y, z])
        
        # 4. 随机采样 yaw（保持水平）
        yaw = random.uniform(0, 2 * math.pi)
        quaternion = T.euler2quat([0, 0, yaw])
        
        # 5. 验证：没有碰撞、没有重叠
        if self._check_valid_placement(position, quaternion, target_obj):
            return (position, quaternion)
    
    return None  # 采样失败
```

### 4.2 姿态采样

#### 4.2.1 导航位姿采样 (_sample_pose_near_object)

```python
def _sample_pose_near_object(
    self,
    obj,
    eef_pose=None,               # 期望的手部位姿
    plan_with_open_gripper=False,  # 是否用张开的抓手规划
    sampling_attempts=100,
    skip_obstacle_update=False,
):
    """
    在物体附近采样机器人的 2D 导航位姿
    
    返回: (x, y, theta) 或 None
    """
    # Step 1: 确定采样半径
    obj_aabb_center, obj_aabb_extent = obj.aabb_center, obj.aabb_extent
    obj_radius = th.norm(obj_aabb_extent[:2]) / 2
    
    # 采样范围: 物体半径 + 0.5m ~ 物体半径 + 2.0m
    min_distance = obj_radius + 0.5
    max_distance = obj_radius + 2.0
    
    # Step 2: 更新障碍物
    if not skip_obstacle_update:
        self._motion_generator.update_obstacles()
    
    for _ in range(sampling_attempts):
        # Step 3: 采样距离和角度
        distance = random.uniform(min_distance, max_distance)
        angle = random.uniform(0, 2 * math.pi)
        
        # Step 4: 计算 2D 位置
        x = obj_aabb_center[0] + distance * math.cos(angle)
        y = obj_aabb_center[1] + distance * math.sin(angle)
        
        # Step 5: 计算朝向（面向物体）
        theta = angle + math.pi  # 朝向物体
        theta = wrap_angle(theta)  # 归一化到 [-π, π]
        
        pose_2d = th.tensor([x, y, theta])
        
        # Step 6: 验证位姿
        # 6.1 检查基座位置是否与障碍物碰撞
        if self._check_base_collision(pose_2d):
            continue
        
        # 6.2 如果指定了 eef_pose，检查手能否到达
        if eef_pose is not None:
            # 设置机器人到采样位姿
            temp_base_pos = self.robot.get_position_orientation()
            self.robot.set_position_orientation(
                position=th.tensor([x, y, temp_base_pos[0][2]]),
                orientation=T.euler2quat([0, 0, theta])
            )
            
            # 检查 IK 可行性
            initial_joint_pos = self._get_joint_position_with_fingers_at_limit(
                "upper" if plan_with_open_gripper else "lower"
            )
            if self._target_in_reach_of_robot(
                eef_pose, 
                initial_joint_pos=initial_joint_pos,
                skip_obstacle_update=True
            ):
                # 恢复机器人位姿
                self.robot.set_position_orientation(*temp_base_pos)
                return pose_2d
            
            # 恢复机器人位姿
            self.robot.set_position_orientation(*temp_base_pos)
        else:
            # 如果没有指定 eef_pose，只检查基座碰撞
            return pose_2d
    
    # 所有尝试都失败
    return None
```

**采样空间可视化**:
```
        物体
         ●
       /   \
      /     \
     /       \
    /  采样   \
   / 圆环区域  \
  /___________\
  
  半径: [r+0.5m, r+2.0m]
  角度: [0, 2π]
  朝向: 面向物体中心
```

#### 4.2.2 手部位姿计算 (_get_hand_pose_for_object_pose)

```python
def _get_hand_pose_for_object_pose(self, obj_pose):
    """
    给定物体的目标位姿，计算手部应该在的位姿
    
    Args:
        obj_pose: (position, quaternion) - 物体目标位姿
    
    Returns:
        (position, quaternion) - 手部目标位姿
    """
    obj_position, obj_quaternion = obj_pose
    obj_in_hand = self._get_obj_in_hand()
    
    # Step 1: 获取物体当前相对于手的变换
    eef_position, eef_quaternion = self.robot.get_eef_position(self.arm)
    obj_in_eef_pose = T.relative_pose_transform(
        obj_in_hand.get_position(),
        obj_in_hand.get_orientation(),
        eef_position,
        eef_quaternion
    )
    # obj_in_eef_pose = T_eef^{-1} * T_obj
    
    # Step 2: 计算手部目标位姿
    # T_eef_target = T_obj_target * (T_eef^{-1} * T_obj)^{-1}
    # 即：T_eef_target = T_obj_target * T_obj^{-1} * T_eef
    hand_position, hand_quaternion = T.pose_transform(
        obj_position,
        obj_quaternion,
        *T.pose_inv(*obj_in_eef_pose)
    )
    
    return (hand_position, hand_quaternion)
```

## 5. CuRobo 运动规划的使用

### 5.1 CuRobo 简介

**CuRobo** (CUDA Robot) 是 NVIDIA 的 GPU 加速运动规划库，用于：
- **逆运动学 (IK)**: 计算关节角度
- **轨迹规划**: 生成无碰撞轨迹
- **碰撞检测**: 快速检查机器人配置是否碰撞

### 5.2 CuRoboMotionGenerator 初始化

```python
# action_primitives/curobo.py

class CuRoboMotionGenerator:
    def __init__(
        self,
        robot,                          # 机器人实例
        batch_size=3,                   # 批量规划大小
        collision_activation_distance=0.005,  # 碰撞激活距离
        robot_usd_path=None,            # 机器人 USD 路径
        ik_use_embodiment_default=True, # 使用默认 embodiment
    ):
        # Step 1: 设置 tensor args（设备和数据类型）
        self._tensor_args = lazy.curobo.types.base.TensorDeviceType(
            device=th.device("cuda:0"),
            dtype=th.float32,
        )
        
        # Step 2: 加载机器人配置
        # CuRobo 需要知道机器人的运动学和碰撞模型
        robot_cfg_path_dict = self._get_robot_config_paths(robot)
        # 例如: {
        #   CuRoboEmbodimentSelection.DEFAULT: "r1pro.yaml",
        #   CuRoboEmbodimentSelection.LEFT_ARM: "r1pro_left_arm.yaml",
        #   CuRoboEmbodimentSelection.RIGHT_ARM: "r1pro_right_arm.yaml",
        # }
        
        # Step 3: 创建世界碰撞检测器
        # 共享所有 MotionGen 实例
        world_coll_checker = create_world_mesh_collision(
            self._tensor_args,
            obb_cache_size=10,     # OBB 缓存大小
            mesh_cache_size=2048,  # Mesh 缓存大小
            max_distance=0.05,     # 最大碰撞检测距离
        )
        
        # Step 4: 为每个 embodiment 创建 MotionGen
        self.mg = {}
        for emb_sel, config_path in robot_cfg_path_dict.items():
            motion_gen_config = lazy.curobo.wrap.reacher.motion_gen.MotionGenConfig.load_from_robot_config(
                robot_cfg=config_path,
                world_model=world_coll_checker,
                tensor_args=self._tensor_args,
                collision_activation_distance=collision_activation_distance,
                # ... 其他参数
            )
            
            self.mg[emb_sel] = lazy.curobo.wrap.reacher.motion_gen.MotionGen(
                motion_gen_config
            )
```

**Embodiment Selection**:
```python
class CuRoboEmbodimentSelection(Enum):
    DEFAULT = "default"           # 全身（基座 + 躯干 + 双臂）
    LEFT_ARM = "left_arm"         # 仅左臂
    RIGHT_ARM = "right_arm"       # 仅右臂
    BIMANUAL = "bimanual"         # 双臂
    LEFT_ARM_AND_BASE = "left_arm_and_base"   # 左臂 + 基座
    RIGHT_ARM_AND_BASE = "right_arm_and_base" # 右臂 + 基座
```

### 5.3 碰撞检测

```python
def check_collisions(
    self,
    q,                          # [N, D] 关节配置
    initial_joint_pos=None,     # 初始关节位置
    self_collision_check=True,  # 检查自碰撞
    skip_obstacle_update=False, # 跳过障碍物更新
    attached_obj=None,          # 附加物体（抓取的物体）
    attached_obj_scale=None,    # 附加物体缩放
):
    """
    检查机器人关节配置是否与环境碰撞
    
    Returns:
        th.tensor: [N,] bool，True 表示碰撞
    """
    emb_sel = CuRoboEmbodimentSelection.DEFAULT
    
    # Step 1: 更新障碍物
    if not skip_obstacle_update:
        self.update_obstacles()
    
    # Step 2: 创建 JointState
    q_pos = self.robot.get_joint_positions() if initial_joint_pos is None else initial_joint_pos
    cu_joint_state = lazy.curobo.types.state.JointState(
        position=self._tensor_args.to_device(q_pos.unsqueeze(0)),
        joint_names=self.robot_joint_names,
    )
    
    # Step 3: 更新 locked joints（非控制关节）
    self.update_locked_joints(cu_joint_state, emb_sel)
    
    # Step 4: 计算运动学（获取球体表示）
    cu_js = lazy.curobo.types.state.JointState(
        position=self.tensor_args.to_device(q),
        joint_names=self.robot_joint_names,
    ).get_ordered_joint_state(self.mg[emb_sel].kinematics.joint_names)
    
    # Step 5: 附加物体（如果有）
    if attached_obj is not None:
        attached_info = self._attach_objects_to_robot(
            attached_obj=attached_obj,
            attached_obj_scale=attached_obj_scale,
            cu_js_batch=cu_js,
            emb_sel=emb_sel,
        )
    
    # Step 6: 计算机器人球体
    robot_spheres = self.mg[emb_sel].compute_kinematics(cu_js).robot_spheres
    # Shape: [N, n_spheres, 4]  (x, y, z, radius)
    robot_spheres = robot_spheres.unsqueeze(dim=1)  # [N, 1, n_spheres, 4]
    
    # Step 7: 碰撞检测
    with th.no_grad():
        # 环境碰撞
        collision_dist = self.mg[emb_sel].rollout_fn.primitive_collision_constraint.forward(
            robot_spheres
        ).squeeze(1)
        collision_results = collision_dist > 0.0  # [N,] bool
        
        # 自碰撞
        if self_collision_check:
            self_collision_dist = self.mg[emb_sel].rollout_fn.robot_self_collision_constraint.forward(
                robot_spheres
            ).squeeze(1)
            self_collision_results = self_collision_dist > 0.0
            collision_results = collision_results | self_collision_results
    
    # Step 8: 清理附加物体
    if attached_obj is not None:
        self._detach_objects_from_robot(attached_info, emb_sel)
    
    return collision_results  # [N,] bool
```

**机器人球体表示**:
```
机器人被近似为一系列球体：

   ●  ← 头部
   |
  ●●● ← 躯干
  / \
 ●●● ●●● ← 手臂
 |    |
●●   ●● ← 手部

每个球体: (x, y, z, radius)
碰撞检测: 检查任意球体是否与障碍物相交
```

### 5.4 逆运动学 (IK)

```python
def compute_ik(
    self,
    target_pose,                # 目标位姿 (position, quaternion)
    max_attempts=10,            # 最大尝试次数
    attached_obj=None,          # 附加物体
    ignore_obstacles=False,     # 忽略障碍物
):
    """
    计算到达目标位姿的关节配置
    
    Returns:
        th.tensor or None: [D,] 关节角度，或 None（失败）
    """
    # Step 1: 准备目标位姿
    target_position, target_quaternion = target_pose
    target_position = self._tensor_args.to_device(target_position)
    target_quaternion = self._tensor_args.to_device(target_quaternion)
    # xyzw -> wxyz (CuRobo format)
    target_quaternion = target_quaternion[[3, 0, 1, 2]]
    
    # Step 2: 创建 Pose 对象
    goal_pose = lazy.curobo.types.math.Pose(
        position=target_position,
        quaternion=target_quaternion,
    )
    
    # Step 3: IK 求解
    emb_sel = self._select_embodiment()  # 选择 embodiment
    
    for attempt in range(max_attempts):
        # 3.1 准备 IK 查询
        cu_joint_state = self._get_current_joint_state()
        self.update_locked_joints(cu_joint_state, emb_sel)
        
        # 3.2 调用 IK solver
        ik_result = self.mg[emb_sel].compute_ik(
            goal_pose=goal_pose,
            start_state=cu_joint_state,
            # ... 其他参数
        )
        
        # 3.3 检查结果
        if ik_result.success[0]:
            joint_positions = ik_result.js_solution.position[0]
            
            # 3.4 碰撞检测（如果需要）
            if not ignore_obstacles:
                collision = self.check_collisions(
                    joint_positions.unsqueeze(0),
                    attached_obj=attached_obj,
                    skip_obstacle_update=True,
                )
                if not collision[0]:
                    return joint_positions
            else:
                return joint_positions
    
    # 所有尝试都失败
    return None
```

### 5.5 轨迹规划

```python
def plan_to_pose(
    self,
    target_pose,                # 目标位姿
    max_attempts=10,
    attached_obj=None,
    motion_constraint=None,     # 运动约束 [1,1,1,1,1,0] = 只沿 z 移动
):
    """
    规划从当前配置到目标位姿的无碰撞轨迹
    
    Returns:
        th.tensor or None: [T, D] 轨迹，或 None（失败）
    """
    # Step 1: 准备目标
    goal_pose = self._prepare_pose(target_pose)
    
    # Step 2: 应用运动约束
    if motion_constraint is not None:
        # motion_constraint = [1,1,1,1,1,0]
        # 表示: x, y, z, roll, pitch 可以变化，yaw 固定
        goal_pose = self._apply_motion_constraint(
            goal_pose,
            motion_constraint
        )
    
    # Step 3: 轨迹规划
    emb_sel = self._select_embodiment()
    
    for attempt in range(max_attempts):
        # 3.1 准备起始状态
        cu_joint_state = self._get_current_joint_state()
        self.update_locked_joints(cu_joint_state, emb_sel)
        
        # 3.2 调用 motion planner
        plan_result = self.mg[emb_sel].plan_single(
            start_state=cu_joint_state,
            goal_pose=goal_pose,
            # ... 其他参数
        )
        
        # 3.3 检查结果
        if plan_result.success[0]:
            trajectory = plan_result.optimized_plan.position
            # Shape: [T, D]，T=轨迹长度，D=关节数
            
            # 3.4 验证轨迹（碰撞检测）
            if self._validate_trajectory(
                trajectory,
                attached_obj=attached_obj
            ):
                return trajectory
    
    # 所有尝试都失败
    return None
```

## 6. 完整的 GRASP Primitive 流程

让我们以 `_grasp()` 为例，展示完整的执行流程：

```python
def _grasp(self, obj):
    """抓取物体的完整流程"""
    
    # ========== Step 1: 前置条件检查 ==========
    if obj is None or not isinstance(obj, USDObject):
        raise ActionPrimitiveError(
            ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
            "Invalid object",
        )
    
    if self.robot.grasping_mode not in ["sticky", "assisted"]:
        raise ActionPrimitiveError(
            ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
            "Unsupported grasping mode",
        )
    
    obj_in_hand = self._get_obj_in_hand()
    if obj_in_hand is not None:
        if obj_in_hand == obj:
            return  # 已经抓取了
        else:
            raise ActionPrimitiveError(
                ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                "Hand is already full",
            )
    
    # ========== Step 2: 打开抓手 ==========
    print("Opening gripper...")
    yield from self._execute_release()
    
    # ========== Step 3: 采样抓取位姿 ==========
    print("Sampling grasp pose...")
    pregrasp_pose, grasp_pose = self._sample_grasp_pose(obj)
    # pregrasp_pose: 距离物体 10cm
    # grasp_pose: 接触物体
    
    # ========== Step 4: 导航（如果需要）==========
    print("Navigating if needed...")
    yield from self._navigate_if_needed(obj, eef_pose=pregrasp_pose)
    # 内部逻辑:
    # - 检查 pregrasp_pose 是否在手臂可达范围内
    # - 如果不在，调用 _navigate_to_obj() 移动基座
    
    # ========== Step 5: 移动手到预抓取位姿 ==========
    print("Moving to pre-grasp pose...")
    yield from self._move_hand(pregrasp_pose)
    # 内部逻辑:
    # - 使用 CuRobo IK 计算关节角度
    # - 使用 CuRobo 规划无碰撞轨迹
    # - 执行轨迹（yield 低层次动作）
    
    # ========== Step 6: 抓取 ==========
    if self.robot.grasping_mode == "sticky":
        # Sticky 模式: 先闭合抓手，再接近
        print("Sticky: closing gripper...")
        yield from self._execute_grasp()
        
        print("Sticky: approaching...")
        # 沿 approach 方向移动（motion_constraint=[1,1,1,1,1,0]）
        yield from self._move_hand(
            grasp_pose,
            motion_constraint=[1, 1, 1, 1, 1, 0],  # 只沿 z 移动
            stop_on_ag=True,                       # 检测到抓取就停止
            ignore_objects=[obj],                  # 忽略目标物体碰撞
        )
    
    elif self.robot.grasping_mode == "assisted":
        # Assisted 模式: 先接近，再闭合
        print("Assisted: approaching...")
        yield from self._move_hand(
            grasp_pose,
            motion_constraint=[1, 1, 1, 1, 1, 0],
        )
        
        print("Assisted: closing gripper...")
        yield from self._execute_grasp()
    
    # ========== Step 7: Settle（等待稳定）==========
    print("Settling...")
    yield from self._settle_robot()
    # 执行几步空动作，让物理引擎稳定
    
    # ========== Step 8: 验证抓取 ==========
    print("Verifying grasp...")
    obj_in_hand = self._get_obj_in_hand()
    
    if obj_in_hand is None:
        raise ActionPrimitiveError(
            ActionPrimitiveError.Reason.POST_CONDITION_ERROR,
            "Grasp completed but no object in hand",
        )
    
    if obj_in_hand != obj:
        raise ActionPrimitiveError(
            ActionPrimitiveError.Reason.POST_CONDITION_ERROR,
            "Wrong object grasped",
        )
    
    print("Grasp successful!")
```

## 7. 高级用法

### 7.1 自定义采样器

```python
class MyActionPrimitives(StarterSemanticActionPrimitives):
    def _sample_grasp_pose(self, obj):
        """自定义抓取位姿采样"""
        # 例如：总是从顶部抓取
        obj_pos = obj.get_position()
        obj_aabb_extent = obj.aabb_extent
        
        # 顶部中心
        grasp_position = obj_pos + th.tensor([0, 0, obj_aabb_extent[2]/2])
        
        # 朝向：从上往下
        grasp_quaternion = T.euler2quat([math.pi, 0, 0])
        
        # 预抓取：上方 10cm
        pregrasp_position = grasp_position + th.tensor([0, 0, 0.1])
        
        return (
            (pregrasp_position, grasp_quaternion),
            (grasp_position, grasp_quaternion)
        )
```

### 7.2 添加新的 Primitive

```python
class MyActionPrimitiveSet(IntEnum):
    # 继承原有的
    GRASP = auto()
    PLACE_ON_TOP = auto()
    # ... 其他
    
    # 添加新的
    PUSH = auto()
    PULL = auto()

class MyActionPrimitives(StarterSemanticActionPrimitives):
    def __init__(self, env, robot, **kwargs):
        super().__init__(env, robot, **kwargs)
        
        # 添加新的控制器函数
        self.controller_functions[MyActionPrimitiveSet.PUSH] = self._push
        self.controller_functions[MyActionPrimitiveSet.PULL] = self._pull
    
    def _push(self, obj):
        """推动物体"""
        # 1. 导航到物体附近
        yield from self._navigate_to_obj(obj)
        
        # 2. 采样接触点
        contact_pose = self._sample_contact_pose(obj)
        
        # 3. 移动手到接触点
        yield from self._move_hand(contact_pose)
        
        # 4. 沿推动方向移动
        push_direction = ...  # 计算推动方向
        push_distance = 0.2   # 20cm
        
        for step in range(int(push_distance / 0.01)):
            # 每步移动 1cm
            current_pos = self.robot.get_eef_position(self.arm)
            target_pos = current_pos + push_direction * 0.01
            yield from self._move_hand_direct_ik(
                (target_pos, contact_pose[1]),
                stop_on_contact=True
            )
```

## 8. 调试技巧

### 8.1 可视化采样位姿

```python
# 启用调试标记
debug_marker = create_primitive_object(
    "sphere",
    scale=0.05,  # 5cm 球体
    rgba=[1, 0, 0, 0.5],  # 半透明红色
)

primitives = StarterSemanticActionPrimitives(
    env, robot,
    debug_visual_marker=debug_marker
)

# 内部会自动移动 debug_marker 到采样位姿
```

### 8.2 打印详细信息

```python
# 在 action_primitives 代码中添加 indented_print
from omnigibson.utils.python_utils import indented_print

def _grasp(self, obj):
    indented_print("=== Starting grasp ===")
    indented_print(f"Target object: {obj.name}")
    
    pregrasp_pose, grasp_pose = self._sample_grasp_pose(obj)
    indented_print(f"Pre-grasp pose: {pregrasp_pose}")
    indented_print(f"Grasp pose: {grasp_pose}")
    
    # ...
```

### 8.3 检查 CuRobo 状态

```python
# 检查碰撞
q = robot.get_joint_positions()
collisions = primitives._motion_generator.check_collisions(
    q.unsqueeze(0)
)
print(f"In collision: {collisions[0]}")

# 检查 IK 可行性
target_pose = (th.tensor([1.0, 0.5, 1.0]), T.euler2quat([0, 0, 0]))
joint_pos = primitives._motion_generator.compute_ik(target_pose)
if joint_pos is None:
    print("IK failed!")
else:
    print(f"IK solution: {joint_pos}")
```

## 9. 总结

### 9.1 关键要点

1. **Action Primitives** 提供高层次语义动作接口
2. **apply_ref()** 是主要调用方式，接受 enum + 参数
3. **连续采样** 用于生成位姿、导航点等
4. **CuRobo** 提供 GPU 加速的 IK、规划和碰撞检测
5. **Generator 模式** 允许逐步执行和中断

### 9.2 最佳实践

- 使用 `try-except` 捕获 `ActionPrimitiveError`
- 利用 `attempts` 参数自动重试
- 自定义采样器以适应特定任务
- 使用调试标记可视化采样结果
- 检查 `grasping_mode` 兼容性

### 9.3 性能考虑

- CuRobo 需要 GPU（推荐 RTX 2080 Ti 以上）
- `batch_size` 影响规划速度和质量
- 采样尝试次数影响成功率和时间
- `skip_obstacle_update` 可以减少重复计算

这个系统为机器人操作提供了强大而灵活的高层次接口！
