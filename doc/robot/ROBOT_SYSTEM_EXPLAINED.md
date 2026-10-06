# Robot 系统详解

本文档详细讲解 OmniGibson 的 Robot 系统，包括架构设计、配置机制、控制器系统、传感器集成以及具体示例。

## 1. Robot 系统架构

### 1.1 核心类层次

```
USDObject (USD 场景对象基类)
    │
    └── Robot (机器人基类)
        ├── 继承 GymObservable (提供 Gym 观察接口)
        └── 组合多种能力 (通过 RobotDefinition 配置)
```

**关键特性**:
- **单一类设计**: 所有机器人使用同一个 `Robot` 类
- **能力组合**: 通过 YAML 定义配置不同能力（manipulation, locomotion, etc.）
- **模块化控制**: 控制器系统独立于机器人实现

### 1.2 机器人能力类型

机器人通过 `RobotDefinition` 配置以下能力：

```python
@dataclass
class RobotDefinition:
    # === 基础配置 ===
    raw_controller_order: List[str]           # 控制器执行顺序
    default_controllers: Dict[str, str]       # 默认控制器映射
    default_joint_pos: List[float]            # 默认关节位置
    disabled_collision_pairs: List[List[str]] # 禁用的碰撞对
    usd_path: str                             # USD 模型路径
    
    # === 能力模块（可选）===
    manipulation: ManipulationDefinition        # 操作能力
    locomotion: LocomotionDefinition            # 移动能力
    holonomic_base: HolonomicBaseDefinition     # 全向底盘
    two_wheel: TwoWheelDefinition               # 两轮差速
    articulated_trunk: ArticulatedTrunkDefinition # 可动躯干
    active_camera: ActiveCameraDefinition       # 主动相机
    mobile_manipulation: MobileManipulationDefinition # 移动操作
```

**能力组合示例**:

| 机器人 | 能力组合 | 描述 |
|--------|---------|------|
| **R1Pro** | locomotion + holonomic_base + manipulation + articulated_trunk | 全向移动 + 双臂操作 + 可动躯干 |
| **Fetch** | locomotion + two_wheel + manipulation + articulated_trunk | 差速驱动 + 单臂操作 + 可升降躯干 |
| **Turtlebot** | locomotion + two_wheel | 仅差速驱动移动 |
| **Franka** | manipulation | 仅固定底座机械臂 |

## 2. Robot 定义文件详解

### 2.1 R1Pro 定义示例

文件路径: `datasets/omnigibson-robot-assets/models/r1pro/r1pro.yaml`

```yaml
# === 基础配置 ===
raw_controller_order: ["base", "trunk", "arm_left", "gripper_left", "arm_right", "gripper_right"]
linear_velocity_gain_for_primitives: 0.3
angular_velocity_gain_for_primitives: 0.2

# === 默认控制器 ===
default_controllers:
  base: HolonomicBaseJointController
  trunk: JointController
  arm_left: InverseKinematicsController
  arm_right: InverseKinematicsController
  gripper_left: MultiFingerGripperController
  gripper_right: MultiFingerGripperController

# === 碰撞配置 ===
disabled_collision_pairs:
  - ["left_arm_link1", "torso_link4"]    # 左臂与躯干不检测碰撞
  - ["right_arm_link1", "torso_link4"]   # 右臂与躯干不检测碰撞
  - ["left_gripper_finger_link1", "left_gripper_finger_link2"]  # 抓手手指间不碰撞
  # ... 更多碰撞对

base_footprint_link_name: "base_link"

# === 全向底盘配置 ===
holonomic_base:
  force_sphere_wheel_approximation: true  # 强制使用球形轮近似

# === 移动能力配置 ===
locomotion:
  base_joint_names: ["base_footprint_x_joint", "base_footprint_y_joint", "base_footprint_rz_joint"]
  floor_touching_base_link_names: ["wheel_motor_link1", "wheel_motor_link2", "wheel_motor_link3"]

# === 可动躯干配置 ===
articulated_trunk:
  trunk_link_names: ["torso_link1", "torso_link2", "torso_link3", "torso_link4"]
  trunk_joint_names: ["torso_joint1", "torso_joint2", "torso_joint3", "torso_joint4"]

# === 移动操作配置 ===
mobile_manipulation:
  # 收起姿态（导航时使用）
  tucked_default_joint_pos: [0.0, 0.0, 0.005, -0.001, 0.0008, 0.0, ...]
  # 展开姿态（操作时使用）
  untucked_default_joint_pos: [0.0, 0.0, 0.005, -0.001, 0.0008, 0.0, 
                                0.0, 0.0, 0.0, 0.0, 0.0, 0.0,     # 基座 + 躯干
                                1.57, -1.57, 0.0, 0.0, -1.57, -1.57,  # 左臂（π/2姿态）
                                1.57, -1.57, 0.0, 0.0, 0.0, 0.0,      # 右臂
                                0.05, 0.05, 0.05, 0.05]               # 抓手

# === 操作能力配置 ===
manipulation:
  n_arms: 2
  arm_names: ["left", "right"]
  
  # 手臂链接
  arm_link_names:
    left: ["left_arm_link1", "left_arm_link2", ..., "left_arm_link7"]
    right: ["right_arm_link1", "right_arm_link2", ..., "right_arm_link7"]
  
  # 手臂关节
  arm_joint_names:
    left: ["left_arm_joint1", ..., "left_arm_joint7"]
    right: ["right_arm_joint1", ..., "right_arm_joint7"]
  
  # 末端执行器链接
  eef_link_names:
    left: "left_eef_link"
    right: "right_eef_link"
  
  # 抓手手指链接
  finger_link_names:
    left: ["left_gripper_finger_link1", "left_gripper_finger_link2"]
    right: ["right_gripper_finger_link1", "right_gripper_finger_link2"]
  
  # 抓手手指关节
  finger_joint_names:
    left: ["left_gripper_finger_joint1", "left_gripper_finger_joint2"]
    right: ["right_gripper_finger_joint1", "right_gripper_finger_joint2"]
  
  # 抓手整体链接（包括传感器）
  gripper_link_names:
    left: ["left_gripper_link", "left_realsense_link"]
    right: ["right_gripper_link", "right_realsense_link"]
  
  # 工作空间范围（度）
  arm_workspace_range:
    left: [-45, 45]
    right: [-45, 45]
```

### 2.2 配置文件加载流程

```python
# OmniGibson/omnigibson/robots/robot.py

def __init__(self, name, model, ...):
    # 1. 构建定义文件路径
    definition_path = os.path.join(
        get_dataset_path("omnigibson-robot-assets"),  # ~/.local/share/omnigibson/...
        "models", 
        self.model,                                    # e.g., "r1pro"
        self.model + ".yaml"                           # e.g., "r1pro.yaml"
    )
    
    # 2. 使用 OmegaConf 加载和验证
    yaml_definition = OmegaConf.load(definition_path)
    schema = OmegaConf.structured(RobotDefinition)
    merged_definition = OmegaConf.merge(schema, yaml_definition)
    
    # 3. 转换为 Python 对象
    self._definition: RobotDefinition = OmegaConf.to_object(merged_definition)
    
    # 4. 根据定义检查能力
    if self._definition.manipulation is not None:
        # 初始化操作相关变量
        self._ag_obj_in_hand = {arm: None for arm in self.arm_names}
        self._ag_obj_constraints = {arm: None for arm in self.arm_names}
        # ...
```

**能力属性检查**:
```python
@property
def is_manipulation(self) -> bool:
    return self._definition.manipulation is not None

@property
def is_locomotion(self) -> bool:
    return self.is_holonomic_base or self.is_two_wheel or self._definition.locomotion is not None

@property
def is_holonomic_base(self) -> bool:
    return self._definition.holonomic_base is not None

@property
def is_mobile_manipulation(self) -> bool:
    return self._definition.mobile_manipulation is not None
```

## 3. 控制器系统

### 3.1 控制器架构

OmniGibson 使用 **ControllerView** 模式实现批量控制：

```
ControllerView (全局管理器)
    │
    ├── Group "base_holonomic_joint" 
    │   ├── HolonomicBaseJointController (共享实例)
    │   ├── Robot1 (member_idx=0)
    │   ├── Robot2 (member_idx=1)
    │   └── ...
    │
    ├── Group "arm_inverse_kinematics"
    │   ├── InverseKinematicsController (共享实例)
    │   ├── Robot1_left_arm (member_idx=0)
    │   ├── Robot1_right_arm (member_idx=1)
    │   └── Robot2_left_arm (member_idx=2)
    │
    └── Group "gripper_multi_finger"
        ├── MultiFingerGripperController (共享实例)
        ├── Robot1_left_gripper (member_idx=0)
        └── ...
```

**关键优势**:
- **批量计算**: 同类型控制器共享计算，提高效率
- **GPU加速**: 支持批量 Isaac Sim Fabric API 调用
- **统一接口**: 所有控制器实现相同接口

### 3.2 控制器类型

#### 3.2.1 底盘控制器

**HolonomicBaseJointController** (全向底盘):
```python
# 输入：[vx, vy, vyaw] - 3D速度指令
# 输出：[x_joint_pos, y_joint_pos, rz_joint_pos] - 虚拟关节目标位置

# 使用场景：R1Pro, R1, G1
```

**DifferentialDriveController** (差速驱动):
```python
# 输入：[v_linear, v_angular] - 2D速度指令
# 输出：[left_wheel_vel, right_wheel_vel] - 两轮目标速度

# 公式：
# left_wheel_vel = (v_linear - v_angular * axle_length / 2) / wheel_radius
# right_wheel_vel = (v_linear + v_angular * axle_length / 2) / wheel_radius

# 使用场景：Fetch, TurtleBot, Locobot
```

#### 3.2.2 手臂控制器

**InverseKinematicsController** (IK控制):
```python
# 输入：[dx, dy, dz, droll, dpitch, dyaw] - 6D末端执行器增量
# 输出：[joint1_pos, ..., joint7_pos] - 关节目标位置

# 特点：
# - 使用 Jacobian 伪逆求解
# - 支持关节限制
# - 可选择性控制子集（位置或姿态）

# 使用场景：精细操作任务
```

**OperationalSpaceController** (OSC控制):
```python
# 输入：[dx, dy, dz, droll, dpitch, dyaw] - 6D末端执行器增量
# 输出：[joint1_torque, ..., joint7_torque] - 关节力矩

# 特点：
# - 基于动力学模型
# - 更好的力控制
# - 需要精确的惯性参数

# 使用场景：力控制、顺应控制
```

**JointController** (关节位置控制):
```python
# 输入：[joint1_delta, ..., jointn_delta] - 关节增量
# 输出：[joint1_pos, ..., jointn_pos] - 关节目标位置

# 特点：
# - 直接关节空间控制
# - 最简单、最稳定
# - 需要用户自行规划轨迹

# 使用场景：躯干关节、相机关节
```

#### 3.2.3 抓手控制器

**MultiFingerGripperController** (多指抓手):
```python
# 输入：[gripper_command] - 1D标量 [-1, 1]
#   -1: 完全打开
#   +1: 完全闭合
# 输出：[finger1_pos, finger2_pos] - 手指目标位置

# 使用场景：R1Pro, Fetch（2指）
```

**GripperController** (单指抓手):
```python
# 输入：[gripper_command] - 1D标量
# 输出：[finger_pos] - 单个手指目标位置

# 使用场景：简单平行抓手
```

### 3.3 控制器配置示例

**Fetch 机器人配置** (`configs/robots/fetch.yaml`):

```yaml
controller_config:
  # 底盘：差速驱动
  base:
    name: DifferentialDriveController
    # (其他参数使用默认值)
  
  # 躯干：关节控制
  trunk:
    name: JointController
    # 躯干可升降，用于调整手臂高度
  
  # 手臂：IK控制
  arm_0:
    name: InverseKinematicsController
    subsume_controllers: [trunk]  # IK求解时考虑躯干关节
    # command_input_limits: "default"  # 自动归一化到 [-1, 1]
  
  # 抓手：多指抓手
  gripper_0:
    name: MultiFingerGripperController
  
  # 相机：关节控制
  camera:
    name: JointController
```

### 3.4 控制器初始化流程

```python
# Robot.__init__() 中

def _load_controllers(self, controller_config):
    # 1. 生成完整的控制器配置
    controller_config = self._generate_controller_config(controller_config)
    
    # 2. 按照 raw_controller_order 顺序初始化
    for name in self._raw_controller_order:
        cfg = controller_config[name]
        
        # 3. 处理 subsume_controllers（IK/OSC 需要）
        if "subsume_controllers" in cfg:
            for subsumed in cfg["subsume_controllers"]:
                # 合并被包含控制器的 DOF
                cfg["dof_idx"] = torch.cat([
                    controller_config[subsumed]["dof_idx"],
                    cfg["dof_idx"]
                ])
        
        # 4. 归一化配置
        if self._action_normalize:
            cfg["command_input_limits"] = "default"  # [-1, 1]
        
        # 5. 注册到 ControllerView
        group_key, controller_idx = ControllerView.register(
            body_part=name,
            controller_cfg=cfg,
            articulation_root_path=self.articulation_root_path,
            link_name=link_name,  # IK/OSC 需要
            control_enabled=self.control_enabled,
        )
        
        # 6. 保存控制器引用
        self._controllers[name] = (group_key, controller_idx)
    
    # 7. 更新关节控制模式（PD gains）
    self.update_controller_mode()
```

## 4. 动作空间与执行

### 4.1 动作空间构建

```python
def _create_continuous_action_space(self):
    """创建连续动作空间"""
    low, high = [], []
    
    # 按照控制器顺序拼接动作维度
    for group_key, _ in self._controllers.values():
        limits = ControllerView.get_command_input_limits(group_key)
        cmd_dim = ControllerView.get_command_dim(group_key)
        
        if limits is None:
            # 无限制（通常不会发生）
            low.append([-inf] * cmd_dim)
            high.append([inf] * cmd_dim)
        else:
            # 使用控制器定义的限制
            low.append(limits[0])
            high.append(limits[1])
    
    return gym.spaces.Box(
        shape=(self.action_dim,),
        low=torch.cat(low).numpy(),
        high=torch.cat(high).numpy(),
        dtype=np.float32,
    )
```

**R1Pro 动作空间维度**:
```python
action_dim = 23

# 分解：
base: 3D       # [vx, vy, vyaw]
trunk: 0D      # (被 arm IK 包含)
arm_left: 6D   # [dx, dy, dz, droll, dpitch, dyaw]
gripper_left: 1D   # [open/close]
arm_right: 6D  # [dx, dy, dz, droll, dpitch, dyaw]
gripper_right: 1D  # [open/close]
# 注意：head 不在默认控制器列表中

# 总计: 3 + 6 + 1 + 6 + 1 = 17D  (?)
# 实际可能包含更多，取决于具体配置
```

### 4.2 动作执行流程

```python
def apply_action(self, action):
    """
    将高层动作转换为低层控制信号
    注意：此方法只更新控制器目标，不执行物理步进
    """
    # 1. 预处理（holonomic base 特殊处理）
    if self.is_holonomic_base:
        # 将 rz joint 角度包裹到 [-π, π]
        rz_joint_dof_indices = self.joints["base_footprint_rz_joint"].dof_indices
        j_pos = self.get_joint_positions()[rz_joint_dof_indices]
        if j_pos < -math.pi or j_pos > math.pi:
            j_pos = wrap_angle(j_pos)
            self.set_joint_positions(j_pos, indices=rz_joint_dof_indices, drive=False)
    
    # 2. 保存动作
    self._last_action = action
    
    # 3. 离散动作转换（如果需要）
    if self._action_type == "discrete":
        action = torch.tensor(self.discrete_action_list[action], dtype=torch.float32)
    
    # 4. 验证动作维度
    assert len(action) == self.action_dim
    
    # 5. 分配动作到各控制器
    idx = 0
    for group_key, controller_idx in self._controllers.values():
        command_dim = ControllerView.get_command_dim(group_key)
        
        # 为这个机器人在批量控制器中的槽位设置命令
        ControllerView.update_goal(
            group_key, 
            controller_idx, 
            action[idx:idx + command_dim]
        )
        
        idx += command_dim

# 注意：apply_action() 只设置目标，实际控制在 step() 中执行
```

**完整控制循环**:
```python
# 在环境的 step() 中
obs, reward, done, info = env.step(action)

# 内部调用顺序：
1. robot.apply_action(action)              # 更新控制器目标
2. simulator.step()                        # 执行物理步进
   ├── ControllerView.compute_control()    # 批量计算控制信号
   │   ├── IK: 计算关节位置目标
   │   ├── OSC: 计算关节力矩
   │   └── Joint: 直接使用目标
   ├── Apply PD control                    # Isaac Sim 内部 PD 控制
   └── Physics step                        # 物理引擎步进
3. robot.get_obs()                         # 获取观察
```

## 5. 传感器系统

### 5.1 传感器类型

Robot 自动发现和初始化场景中的传感器：

```python
# OmniGibson/omnigibson/robots/robot.py

def _load_sensors(self):
    """自动加载机器人上的所有传感器"""
    # 1. 搜索传感器 prims
    sensor_prims = self._find_sensor_prims()
    
    # 2. 根据 prim 类型创建传感器
    for prim in sensor_prims:
        prim_type = prim.GetTypeName()
        
        if prim_type in SENSOR_PRIMS_TO_SENSOR_CLS:
            sensor_cls = SENSOR_PRIMS_TO_SENSOR_CLS[prim_type]
            
            # 3. 应用传感器配置
            sensor_config = self._get_sensor_config(sensor_cls)
            
            # 4. 创建传感器实例
            sensor = create_sensor(
                prim_path=prim.GetPath(),
                sensor_type=sensor_cls,
                **sensor_config
            )
            
            # 5. 添加到传感器字典
            self._sensors[sensor.name] = sensor
```

**主要传感器类型**:

| 传感器类 | USD Prim 类型 | 输出模态 | 描述 |
|---------|--------------|---------|------|
| **VisionSensor** | Camera | rgb, depth, seg_semantic, seg_instance, normal, flow | RGB-D相机 |
| **ScanSensor** | LaserScan | scan | 2D 激光雷达 |
| **ContactSensor** | ContactSensor | contact | 接触传感器 |
| **IMUSensor** | IMU | imu | 惯性测量单元 |

### 5.2 观察空间

```python
def get_obs(self):
    """
    获取机器人观察，包括：
    1. 传感器观察（视觉、扫描等）
    2. 本体感觉（关节状态、位姿等）
    """
    obs_dict = {}
    
    # 1. 传感器观察
    for sensor in self._sensors.values():
        if sensor.modalities & self._obs_modalities:
            sensor_obs = sensor.get_obs()
            obs_dict.update(sensor_obs)
    
    # 2. 本体感觉
    proprio_obs = self.get_proprioception()
    obs_dict["proprio"] = proprio_obs
    
    return obs_dict
```

### 5.3 本体感觉 (Proprioception)

```python
def _get_proprioception_dict(self):
    """获取所有可用的本体感觉观察"""
    joint_positions = self.get_joint_positions()
    joint_velocities = self.get_joint_velocities()
    pos, quat = self.get_position_orientation()
    
    dic = {
        # 基础关节信息
        "joint_qpos": joint_positions,
        "joint_qpos_sin": torch.sin(joint_positions),
        "joint_qpos_cos": torch.cos(joint_positions),
        "joint_qvel": joint_velocities,
        "joint_qeffort": self.get_joint_efforts(),
        
        # 机器人位姿
        "robot_pos": pos,
        "robot_ori_cos": torch.cos(T.quat2euler(quat)),
        "robot_ori_sin": torch.sin(T.quat2euler(quat)),
        "robot_2d_ori": T.z_angle_from_quat(quat),
        
        # 速度
        "robot_lin_vel": self.get_linear_velocity(),
        "robot_ang_vel": self.get_angular_velocity(),
    }
    
    # 操作相关
    if self.is_manipulation:
        for arm in self.arm_names:
            # 手臂关节
            dic[f"arm_{arm}_qpos"] = joint_positions[self.arm_control_idx[arm]]
            dic[f"arm_{arm}_qpos_sin"] = torch.sin(...)
            dic[f"arm_{arm}_qpos_cos"] = torch.cos(...)
            dic[f"arm_{arm}_qvel"] = joint_velocities[self.arm_control_idx[arm]]
            
            # 末端执行器位姿（相对于基座）
            eef_pos, eef_quat = self.get_relative_eef_pose(arm=arm)
            dic[f"eef_{arm}_pos"] = eef_pos
            dic[f"eef_{arm}_quat"] = eef_quat
            
            # 抓取状态
            dic[f"grasp_{arm}"] = torch.tensor([self.is_grasping(arm)])
            
            # 抓手关节
            dic[f"gripper_{arm}_qpos"] = joint_positions[self.gripper_control_idx[arm]]
            dic[f"gripper_{arm}_qvel"] = joint_velocities[self.gripper_control_idx[arm]]
    
    # 躯干相关
    if self.is_articulated_trunk:
        dic["trunk_qpos"] = joint_positions[self.trunk_control_idx]
        dic["trunk_qvel"] = joint_velocities[self.trunk_control_idx]
    
    # 底盘相关
    if self.is_locomotion:
        dic["base_qpos"] = joint_positions[self.base_control_idx]
        dic["base_qvel"] = joint_velocities[self.base_control_idx]
    
    # 相机相关
    if self.is_active_camera:
        dic["camera_qpos"] = joint_positions[self.camera_control_idx]
        dic["camera_qvel"] = joint_velocities[self.camera_control_idx]
    
    return dic
```

**配置本体感觉观察** (`configs/robots/fetch.yaml`):
```yaml
proprio_obs:
  - eef_0_pos          # 末端执行器位置
  - eef_0_quat         # 末端执行器姿态
  - trunk_qpos         # 躯干关节位置
  - arm_0_qpos_sin     # 手臂关节位置（sin）
  - arm_0_qpos_cos     # 手臂关节位置（cos）
  - gripper_0_qpos     # 抓手关节位置
  - grasp_main         # 抓取状态（deprecated，使用 grasp_0）
```

## 6. 抓取系统

### 6.1 抓取模式

OmniGibson 支持三种抓取模式：

```python
AG_MODES = {"physical", "assisted", "sticky"}
```

#### 6.1.1 Physical Mode (物理抓取)

```python
grasping_mode = "physical"

# 特点：
# - 完全依赖物理接触摩擦
# - 需要足够的手指力和摩擦系数
# - 最真实，但也最难

# 影响因素：
# - finger_static_friction: 手指静摩擦系数（建议 > 1.0）
# - finger_dynamic_friction: 手指动摩擦系数
# - gripper_force: 抓手闭合力
# - 物体质量和形状
```

#### 6.1.2 Assisted Mode (辅助抓取)

```python
grasping_mode = "assisted"

# 特点：
# - 当物体在抓手内且至少两个手指接触时，创建约束
# - 更稳定，但仍需要合理的抓取姿态
# - 适合大部分任务

# 工作原理：
# 1. 检测手指与物体的接触
# 2. 如果 >= 2 个手指接触且物体在抓手内
# 3. 创建 FixedJoint 约束连接物体和抓手
# 4. 松开时删除约束
```

#### 6.1.3 Sticky Mode (粘性抓取)

```python
grasping_mode = "sticky"

# 特点：
# - 任何一个手指接触物体即可抓取
# - 非常宽容，几乎不会失败
# - 适合快速原型和演示

# 使用场景：
# - 数据收集（不关心抓取细节）
# - 行为克隆（简化抓取）
# - 调试和验证
```

### 6.2 抓取检测

```python
def is_grasping(self, arm="default", candidate_obj=None):
    """
    检测指定手臂是否正在抓取物体
    
    Args:
        arm: 手臂名称（"left", "right", "default"）
        candidate_obj: 可选，检查是否抓取特定物体
    
    Returns:
        bool or IsGraspingState: 抓取状态
    """
    # Physical mode: 检测是否有物体在手指间且保持静止
    if self._grasping_mode == "physical":
        return self._is_grasping_physical(arm, candidate_obj)
    
    # Assisted/Sticky mode: 检查约束是否存在
    else:
        obj_in_hand = self._ag_obj_in_hand[arm]
        if candidate_obj is None:
            return obj_in_hand is not None
        else:
            return obj_in_hand == candidate_obj
```

### 6.3 辅助抓取实现

```python
def _handle_assisted_grasping(self):
    """
    每步更新辅助抓取状态
    在 env.step() 中自动调用（除非 disable_grasp_handling=True）
    """
    for arm in self.arm_names:
        obj_in_hand = self._ag_obj_in_hand[arm]
        
        # === 场景 1: 当前未抓取，尝试抓取 ===
        if obj_in_hand is None:
            # 1. 检测手指闭合程度
            if self._is_gripper_closing(arm):
                self._ag_grasp_counter[arm] += 1
            else:
                self._ag_grasp_counter[arm] = 0
            
            # 2. 手指闭合足够久才尝试抓取（避免误触发）
            if self._ag_grasp_counter[arm] < m.GRASP_WINDOW / og.sim.get_sim_step_dt():
                continue
            
            # 3. 检测接触的物体
            contacted_objs = self._get_contacted_objects(arm)
            
            # 4. 根据模式过滤候选物体
            if self._grasping_mode == "assisted":
                # 至少2个手指接触
                candidates = [obj for obj, n_contacts in contacted_objs.items() 
                             if n_contacts >= 2]
            else:  # sticky
                # 至少1个手指接触
                candidates = [obj for obj in contacted_objs.keys()]
            
            # 5. 选择最近的候选物体
            if candidates:
                closest_obj = self._find_closest_object(arm, candidates)
                
                # 6. 创建固定约束
                self._create_grasp_constraint(arm, closest_obj)
        
        # === 场景 2: 当前正在抓取，检查是否松开 ===
        else:
            # 1. 检测手指打开程度
            if self._is_gripper_opening(arm):
                self._ag_release_counter[arm] += 1
            else:
                self._ag_release_counter[arm] = 0
            
            # 2. 手指打开足够久才松开（避免误触发）
            if self._ag_release_counter[arm] >= m.RELEASE_WINDOW / og.sim.get_sim_step_dt():
                # 3. 删除约束
                self._remove_grasp_constraint(arm)

def _create_grasp_constraint(self, arm, obj):
    """创建抓取约束"""
    # 1. 记录物体
    self._ag_obj_in_hand[arm] = obj
    
    # 2. 计算相对位姿
    eef_pos, eef_quat = self.get_eef_pose(arm)
    obj_pos, obj_quat = obj.get_position_orientation()
    rel_pos, rel_quat = T.relative_pose_transform(obj_pos, obj_quat, eef_pos, eef_quat)
    
    # 3. 创建 USD FixedJoint
    joint_prim = create_joint(
        prim_type="FixedJoint",
        body0=self.eef_link_names[arm],
        body1=obj.root_link.prim_path,
        local_pos0=rel_pos,
        local_rot0=rel_quat,
        enabled=True,
    )
    
    # 4. 保存约束参数（用于序列化）
    self._ag_obj_constraints[arm] = joint_prim
    self._ag_obj_constraint_params[arm] = (rel_pos, rel_quat)

def _remove_grasp_constraint(self, arm):
    """移除抓取约束"""
    # 1. 删除 USD joint
    if self._ag_obj_constraints[arm] is not None:
        delete_or_deactivate_prim(self._ag_obj_constraints[arm])
    
    # 2. 清空记录
    self._ag_obj_in_hand[arm] = None
    self._ag_obj_constraints[arm] = None
    self._ag_obj_constraint_params[arm] = None
```

## 7. Reset 与状态管理

### 7.1 Reset 流程

```python
def reset(self):
    """重置机器人到初始状态"""
    # 1. 全向底盘特殊处理：保存当前基座位置
    if self.is_holonomic_base:
        base_joint_positions = self.get_joint_positions()[self.base_idx]
    
    # 2. 调用父类 reset（USDObject）
    super().reset()
    
    # 3. 设置关节位置
    self.set_joint_positions(positions=self._reset_joint_pos, drive=False)
    
    # 4. 全向底盘：恢复基座位置（避免被覆盖）
    if self.is_holonomic_base:
        self.set_joint_positions(base_joint_positions, indices=self.base_idx)
```

**Reset 关节位置的选择**:
```python
# 优先级：
1. 用户指定: reset_joint_pos 参数
2. 默认模式: default_reset_mode ("tuck" or "untuck")
3. 定义文件: default_joint_pos

# 示例：
robot = Robot(
    name="robot0",
    model="r1pro",
    reset_joint_pos=None,            # 使用默认
    default_reset_mode="untuck",     # 使用 untuck 姿态
)

# 内部逻辑：
if self._reset_joint_pos is None:
    if self.is_mobile_manipulation:
        if self.default_reset_mode == "tuck":
            self._reset_joint_pos = self._definition.mobile_manipulation.tucked_default_joint_pos
        else:  # untuck
            self._reset_joint_pos = self._definition.mobile_manipulation.untucked_default_joint_pos
    else:
        self._reset_joint_pos = self._definition.default_joint_pos
```

### 7.2 状态序列化

Robot 支持完整的状态序列化和反序列化，用于：
- Episode 重播
- 分布式训练
- 调试和验证

```python
def dump_state(self, serialized=False):
    """
    导出机器人完整状态
    
    Returns:
        dict or torch.Tensor: 状态字典或序列化张量
    """
    state = super().dump_state(serialized=False)
    
    # 添加机器人特定状态
    state["last_action"] = self._last_action
    state["control_enabled"] = self._control_enabled
    
    # 辅助抓取状态
    if self.is_manipulation and self._grasping_mode in ["assisted", "sticky"]:
        for arm in self.arm_names:
            state[f"ag_obj_in_hand_{arm}"] = self._ag_obj_in_hand[arm]
            state[f"ag_constraint_params_{arm}"] = self._ag_obj_constraint_params[arm]
    
    # 序列化为张量（可选）
    if serialized:
        return self._serialize_state(state)
    return state

def load_state(self, state):
    """从状态字典恢复机器人"""
    super().load_state(state)
    
    self._last_action = state["last_action"]
    self._control_enabled = state["control_enabled"]
    
    # 恢复辅助抓取
    if self.is_manipulation and self._grasping_mode in ["assisted", "sticky"]:
        for arm in self.arm_names:
            obj = state[f"ag_obj_in_hand_{arm}"]
            if obj is not None:
                params = state[f"ag_constraint_params_{arm}"]
                self._create_grasp_constraint(arm, obj, params)
```

## 8. 使用示例

### 8.1 创建和加载机器人

```python
import omnigibson as og
from omnigibson.robots import Robot

# 1. 启动模拟器
og.sim.launch()

# 2. 创建场景
scene = og.Scene(scene_model="Rs_int")

# 3. 创建机器人
robot = Robot(
    name="robot0",
    model="r1pro",
    
    # 控制配置
    control_freq=30.0,           # 30 Hz 控制频率
    action_normalize=True,        # 归一化动作到 [-1, 1]
    
    # 观察配置
    obs_modalities=["rgb", "depth", "proprio"],
    proprio_obs=[
        "eef_left_pos", "eef_left_quat",
        "eef_right_pos", "eef_right_quat",
        "arm_left_qpos", "arm_right_qpos",
        "gripper_left_qpos", "gripper_right_qpos",
        "base_qpos", "trunk_qpos",
    ],
    
    # 抓取配置
    grasping_mode="assisted",
    finger_static_friction=1.5,
    
    # Reset 配置
    default_reset_mode="untuck",
)

# 4. 加载到场景
scene.add_object(robot)

# 5. 初始化场景
og.sim.stop()
og.sim.play()
```

### 8.2 控制机器人

```python
# 获取动作空间
print(f"Action space: {robot.action_space}")
# Box(23,) for R1Pro: [base(3), arm_left(6), gripper_left(1), arm_right(6), gripper_right(1)]

# 示例动作：前进 + 左臂向前伸 + 右臂保持 + 抓手打开
action = np.zeros(23)
action[0] = 0.5      # base vx (前进)
action[3] = 0.3      # left arm dx (前伸)
action[9] = -1.0     # left gripper (打开)
action[16] = -1.0    # right gripper (打开)

# 执行动作
robot.apply_action(action)
og.sim.step()

# 获取观察
obs = robot.get_obs()
print(f"RGB shape: {obs['rgb'].shape}")
print(f"Proprio shape: {obs['proprio'].shape}")
print(f"Left EEF pos: {obs['eef_left_pos']}")
```

### 8.3 检查抓取状态

```python
# 闭合左抓手
action = np.zeros(23)
action[9] = 1.0  # left gripper close
robot.apply_action(action)

# 执行多步让抓手完全闭合
for _ in range(30):
    og.sim.step()

# 检查抓取
if robot.is_grasping(arm="left"):
    obj = robot._ag_obj_in_hand["left"]
    print(f"Left arm is grasping: {obj.name}")
else:
    print("Left arm is not grasping anything")
```

### 8.4 自定义控制器配置

```python
# 高级用法：自定义控制器
custom_controller_config = {
    "arm_left": {
        "name": "OperationalSpaceController",  # 使用 OSC 代替 IK
        "kp": 300.0,                           # 位置增益
        "kd": 50.0,                            # 阻尼增益
        "control_limits": {
            "position": [0.1, 0.1, 0.1],       # 位置限制 (m)
            "orientation": [0.5, 0.5, 0.5],    # 姿态限制 (rad)
        },
    },
    "gripper_left": {
        "name": "MultiFingerGripperController",
        "command_input_limits": [-1.0, 1.0],
    },
}

robot = Robot(
    name="robot0",
    model="r1pro",
    controller_config=custom_controller_config,
)
```

## 9. 常见问题与调试

### 9.1 控制不稳定

**问题**: 机器人关节抖动或振荡

**原因**:
- PD gains 不合适
- 控制频率太低
- 动作变化太大

**解决**:
```python
# 1. 调整 PD gains（在控制器配置中）
controller_config = {
    "arm_left": {
        "kp": 150.0,   # 降低 kp (默认通常是 300)
        "kd": 30.0,    # 增加 kd (增加阻尼)
    }
}

# 2. 提高控制频率
control_freq = 60.0  # 从 30 Hz 提高到 60 Hz

# 3. 平滑动作
action_smoothed = 0.7 * action_prev + 0.3 * action_new
```

### 9.2 抓取失败

**问题**: Physical mode 下抓不住物体

**解决**:
```python
# 1. 增加手指摩擦
robot = Robot(
    name="robot0",
    model="fetch",
    finger_static_friction=2.0,    # 增加到 2.0
    finger_dynamic_friction=1.5,
)

# 2. 或者使用 assisted mode
robot = Robot(
    grasping_mode="assisted",  # 更容易抓取
)

# 3. 检查抓取姿态
# 确保物体在手指之间，而不是在手掌上
```

### 9.3 IK 求解失败

**问题**: 末端执行器无法到达目标位置

**原因**:
- 目标超出工作空间
- IK 求解陷入局部最优
- 关节限制过严

**解决**:
```python
# 1. 检查目标是否可达
eef_pos, _ = robot.get_eef_pose(arm="left")
target_pos = [0.5, 0.3, 0.8]

if np.linalg.norm(target_pos - eef_pos) > 0.8:  # 超出工作空间
    print("Target out of reach!")

# 2. 使用渐进式目标
delta = (target_pos - eef_pos) * 0.1  # 每步只移动 10%
action[:3] = delta

# 3. 切换到 Joint 控制（如果 IK 不稳定）
controller_config = {
    "arm_left": {
        "name": "JointController",  # 直接关节控制
    }
}
```

### 9.4 性能优化

**问题**: 控制计算太慢

**优化**:
```python
# 1. 使用批量处理（如果有多个机器人）
# ControllerView 自动批量处理同类型控制器

# 2. 降低传感器分辨率
sensor_config = {
    "VisionSensor": {
        "sensor_kwargs": {
            "image_height": 128,  # 从 256 降到 128
            "image_width": 128,
        }
    }
}

# 3. 减少观察模态
obs_modalities = ["proprio"]  # 只要本体感觉，不要视觉

# 4. 使用 action_repeat
for _ in range(4):  # 同一动作执行 4 步
    og.sim.step()
```

## 10. 总结

### 10.1 关键要点

1. **统一架构**: 所有机器人使用同一个 `Robot` 类，通过 YAML 定义配置能力

2. **能力组合**: 机器人能力（manipulation, locomotion, etc.）通过 `RobotDefinition` 模块化组合

3. **批量控制**: `ControllerView` 模式实现高效的批量控制器计算

4. **灵活抓取**: 支持 physical, assisted, sticky 三种抓取模式

5. **完整观察**: 自动集成传感器（视觉、扫描等）和本体感觉

### 10.2 设计优势

- **可扩展**: 添加新机器人只需创建 YAML 定义
- **高性能**: 批量控制和 GPU 加速
- **易调试**: 完整的状态序列化和重播
- **灵活配置**: 控制器、传感器、抓取模式都可配置

### 10.3 进一步学习

- **控制器细节**: 阅读 `OmniGibson/omnigibson/controllers/` 下的各控制器实现
- **传感器细节**: 阅读 `OmniGibson/omnigibson/sensors/` 了解传感器系统
- **示例代码**: 运行 `OmniGibson/omnigibson/examples/robots/` 下的示例
- **自定义机器人**: 参考现有 YAML 文件创建自己的机器人定义
