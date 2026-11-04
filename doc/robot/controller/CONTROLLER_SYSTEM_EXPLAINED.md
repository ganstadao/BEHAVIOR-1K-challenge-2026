# OmniGibson Controller 系统详解

本文档详细讲解 OmniGibson 的 Controller 系统架构、实现原理以及各种控制器的使用方法。

## 1. Controller 系统概览

### 1.1 什么是 Controller？

**Controller（控制器）** 是连接高层动作命令和底层关节控制的桥梁，负责将抽象的控制指令转换为具体的关节目标。

```
高层动作命令 (e.g., "向前移动", "抓取物体")
    ↓
Controller (转换)
    ↓
底层关节指令 (e.g., 关节位置/速度/力矩)
    ↓
物理引擎执行
```

### 1.2 Controller 类层次结构

```
BaseController (抽象基类)
├── 核心功能: 命令处理、限制裁剪、缩放
└── 子类分类:
    ├── LocomotionController (移动控制)
    │   ├── DifferentialDriveController (差速驱动)
    │   └── HolonomicBaseJointController (全向底盘)
    │
    ├── ManipulationController (操作控制)
    │   ├── InverseKinematicsController (IK)
    │   └── OperationalSpaceController (OSC)
    │
    └── GripperController (抓手控制)
        └── MultiFingerGripperController (多指抓手)

JointController (通用关节控制)
    └── 特殊: 同时继承所有三个类型
```

### 1.3 核心组件

```
Controller
├── 命令处理
│   ├── 输入限制 (command_input_limits)
│   ├── 输出限制 (command_output_limits)
│   └── 命令缩放/裁剪
│
├── 控制类型
│   ├── Position (位置控制)
│   ├── Velocity (速度控制)
│   └── Effort (力矩控制)
│
├── 增益参数
│   ├── isaac_kp, isaac_kd (Isaac Sim 底层)
│   ├── pos_kp, pos_kd (位置控制器)
│   └── vel_kp (速度控制器)
│
└── 高级功能
    ├── Impedance Control (阻抗控制)
    ├── Gravity Compensation (重力补偿)
    └── Smoothing Filter (平滑滤波)
```

## 2. BaseController 基类

### 2.1 核心接口

```python
# omnigibson/controllers/controller_base.py

class BaseController(Serializable, Registerable, Recreatable):
    """
    所有控制器的基类
    
    核心职责:
        1. 命令处理: 裁剪、缩放
        2. 计算控制: compute_control()
        3. 状态管理: reset()
    """
    
    def __init__(
        self,
        control_freq,                    # 控制频率 (Hz)
        control_limits,                  # 控制限制
        dof_idx,                         # 控制的关节索引
        command_input_limits="default",  # 输入命令限制
        command_output_limits="default", # 输出命令限制
        isaac_kp=None,                   # Isaac Sim 刚度
        isaac_kd=None,                   # Isaac Sim 阻尼
    ):
        """
        Args:
            control_freq: 控制频率，例如 30Hz
            
            control_limits: 关节物理限制
                {
                    "position": [[min_per_joint], [max_per_joint]],
                    "velocity": [[min_per_joint], [max_per_joint]],
                    "effort": [[min_per_joint], [max_per_joint]],
                    "has_limit": [bool_per_joint],
                }
            
            dof_idx: 控制的关节索引数组
                例如: [7, 8, 9, 10, 11, 12, 13] (7个手臂关节)
            
            command_input_limits: 输入命令范围
                - None: 不裁剪
                - "default": 使用 (-1, 1)
                - (min, max): 自定义范围
            
            command_output_limits: 输出命令范围
                - None: 不缩放
                - "default": 使用 control_limits
                - (min, max): 自定义范围
            
            isaac_kp, isaac_kd: Isaac Sim 底层 PD 控制增益
        """
        self.control_freq = control_freq
        self.control_limits = control_limits
        self.dof_idx = dof_idx
        self.command_dim = len(dof_idx)
        
        # 处理命令限制
        self._command_input_limits = self._process_limits(command_input_limits)
        self._command_output_limits = self._process_limits(command_output_limits)
        
        # Isaac Sim 增益
        self.isaac_kp = isaac_kp
        self.isaac_kd = isaac_kd
    
    def compute_control(self, goal_dict, control_dict):
        """
        计算控制命令的核心方法
        
        Args:
            goal_dict: 目标状态字典
                {
                    "command": 高层命令,
                    "joint_position": 当前关节位置,
                    "joint_velocity": 当前关节速度,
                    ...
                }
            
            control_dict: 控制输出字典（修改此字典）
                {
                    "joint_position": 目标关节位置,
                    "joint_velocity": 目标关节速度,
                    "joint_effort": 目标关节力矩,
                }
        
        Returns:
            dict: 控制字典（与输入相同，但已修改）
        """
        # Step 1: 处理命令
        command = self._preprocess_command(goal_dict["command"])
        
        # Step 2: 子类实现的控制逻辑
        u = self._compute_control(command, goal_dict, control_dict)
        
        # Step 3: 裁剪到控制限制
        u = self._clip_control(u)
        
        # Step 4: 写入控制字典
        control_dict[self.control_type] = u
        
        return control_dict
    
    def _preprocess_command(self, command):
        """预处理命令: 裁剪 + 缩放"""
        # Step 1: 裁剪到输入范围
        if self._command_input_limits is not None:
            command = th.clip(
                command,
                self._command_input_limits[0],
                self._command_input_limits[1]
            )
        
        # Step 2: 缩放到输出范围
        if self._command_input_limits is not None and self._command_output_limits is not None:
            command = self._scale_command(
                command,
                from_range=self._command_input_limits,
                to_range=self._command_output_limits
            )
        
        return command
    
    @abstractmethod
    def _compute_control(self, command, goal_dict, control_dict):
        """
        子类实现的核心控制逻辑
        
        Returns:
            控制信号 (位置/速度/力矩)
        """
        raise NotImplementedError
    
    def reset(self):
        """重置控制器状态"""
        pass
    
    @property
    @abstractmethod
    def control_type(self):
        """
        控制类型: "position", "velocity", "effort"
        """
        raise NotImplementedError
    
    @property
    def command_dim(self):
        """命令维度 (通常等于 DOF 数量)"""
        return len(self.dof_idx)
```

### 2.2 命令处理流程

```
原始命令 [-1, 1] 范围
    ↓
_preprocess_command()
    ├─ Step 1: 裁剪到 command_input_limits
    │   command = clip(command, -1, 1)
    │
    └─ Step 2: 缩放到 command_output_limits
        command = scale(command, from=(-1,1), to=(vel_min, vel_max))
    ↓
处理后的命令 (物理单位)
    ↓
_compute_control()
    └─ 子类特定逻辑
    ↓
控制信号
    ↓
_clip_control()
    └─ 裁剪到 control_limits
    ↓
最终控制信号
```

## 3. JointController (关节控制器)

### 3.1 原理

**最简单的控制器**: 直接将命令传递给关节，支持位置、速度、力矩三种模式。

```python
# omnigibson/controllers/joint_controller.py

class JointController(LocomotionController, ManipulationController, GripperController):
    """
    通用关节控制器
    
    特点:
        - 支持三种控制类型: position, velocity, effort
        - 支持 delta 命令 (相对于当前状态)
        - 支持阻抗控制
        - 支持平滑滤波
    """
    
    def __init__(
        self,
        control_freq,
        motor_type,                      # "position", "velocity", "effort"
        control_limits,
        dof_idx,
        command_input_limits="default",
        command_output_limits="default",
        isaac_kp=None,
        isaac_kd=None,
        pos_kp=50.0,                     # 位置增益
        pos_damping_ratio=1.0,           # 阻尼比
        vel_kp=2.0,                      # 速度增益
        smoothing_filter_size=None,      # 平滑滤波窗口
        use_impedances=False,            # 使用阻抗控制
        use_gravity_compensation=False,  # 重力补偿
        use_cc_compensation=True,        # 科里奥利/离心力补偿
        use_delta_commands=False,        # 使用 delta 命令
    ):
        self._motor_type = motor_type
        self._use_delta_commands = use_delta_commands
        
        # 位置控制增益
        if motor_type == "position":
            self.pos_kp = pos_kp
            self.pos_kd = 2 * math.sqrt(pos_kp) * pos_damping_ratio
        
        # 速度控制增益
        elif motor_type == "velocity":
            self.vel_kp = vel_kp
        
        # 阻抗控制
        self._use_impedances = use_impedances
        
        super().__init__(...)
```

### 3.2 控制逻辑

```python
def _compute_control(self, command, goal_dict, control_dict):
    """
    JointController 的核心逻辑
    """
    # Step 1: Delta 命令处理
    if self._use_delta_commands:
        # 将 delta 加到当前状态
        current_pos = goal_dict["joint_position"][self.dof_idx]
        command = current_pos + command
    
    # Step 2: 平滑滤波
    if self.control_filter is not None:
        command = self.control_filter.estimate(command)
    
    # Step 3: 根据控制类型计算
    if self._motor_type == "position":
        # 位置控制: 直接输出目标位置
        u = command
        
        # 如果使用阻抗控制，计算力矩
        if self._use_impedances:
            current_pos = goal_dict["joint_position"][self.dof_idx]
            current_vel = goal_dict["joint_velocity"][self.dof_idx]
            
            # PD 控制器
            pos_error = command - current_pos
            vel_error = -current_vel
            
            # u = Kp * e_pos + Kd * e_vel
            u_effort = self.pos_kp * pos_error + self.pos_kd * vel_error
            
            # 使用质量矩阵进行阻抗控制
            mass_matrix = goal_dict["mass_matrix"][self.dof_idx][:, self.dof_idx]
            u_effort = mass_matrix @ u_effort
            
            # 添加补偿项
            if self._use_gravity_compensation:
                u_effort += goal_dict["gravity_force"][self.dof_idx]
            
            if self._use_cc_compensation:
                u_effort += goal_dict["cc_force"][self.dof_idx]
            
            control_dict["joint_effort"] = u_effort
    
    elif self._motor_type == "velocity":
        # 速度控制: 直接输出目标速度
        u = command
        
        if self._use_impedances:
            current_vel = goal_dict["joint_velocity"][self.dof_idx]
            vel_error = command - current_vel
            
            # P 控制器
            u_effort = self.vel_kp * vel_error
            
            mass_matrix = goal_dict["mass_matrix"][self.dof_idx][:, self.dof_idx]
            u_effort = mass_matrix @ u_effort
            
            control_dict["joint_effort"] = u_effort
    
    else:  # effort
        # 力矩控制: 直接输出力矩
        u = command
    
    return u
```

### 3.3 使用示例

```python
# 位置控制 (绝对位置)
controller = JointController(
    control_freq=30,
    motor_type="position",
    control_limits=control_limits,
    dof_idx=[7, 8, 9, 10, 11, 12, 13],
    command_input_limits=(-1, 1),
    command_output_limits=(joint_min, joint_max),
    use_delta_commands=False,
)

# 命令: [-1, 1] 归一化空间
command = th.tensor([0.5, 0.3, -0.2, 0.8, 0.1, -0.5, 0.0])
goal_dict = {
    "command": command,
    "joint_position": current_joint_pos,
    "joint_velocity": current_joint_vel,
}
control_dict = {}

# 计算控制
controller.compute_control(goal_dict, control_dict)

# 结果: control_dict["joint_position"] = 目标关节位置 (物理单位)
```

```python
# 位置控制 (delta 位置)
controller = JointController(
    control_freq=30,
    motor_type="position",
    control_limits=control_limits,
    dof_idx=[7, 8, 9, 10, 11, 12, 13],
    command_input_limits=(-1, 1),
    command_output_limits=(-0.1, 0.1),  # 每步最多移动 0.1 rad
    use_delta_commands=True,             # 关键: 启用 delta
)

# 命令: delta 值
command = th.tensor([0.01, -0.02, 0.0, 0.03, -0.01, 0.0, 0.02])
```

## 4. InverseKinematicsController (IK 控制器)

### 4.1 原理

**逆运动学控制器**: 将末端执行器 (EEF) 的目标位姿转换为关节角度。

```python
# omnigibson/controllers/ik_controller.py

class InverseKinematicsController(JointController, ManipulationController):
    """
    IK 控制器
    
    输入: 末端执行器位姿 (x, y, z, ax, ay, az)
    输出: 关节位置/速度
    
    支持模式:
        - absolute_pose: 绝对位姿
        - pose_absolute_ori: 位置delta + 绝对朝向
        - pose_delta_ori: 位置delta + 朝向delta
        - position_fixed_ori: 只控制位置
        - position_compliant_ori: 位置控制,朝向自由
    """
    
    def __init__(
        self,
        control_freq,
        reset_joint_pos,              # reset 时的关节位置
        control_limits,
        dof_idx,
        mode="pose_delta_ori",        # IK 模式
        workspace_pose_limiter=None,  # 工作空间限制器
        link_name=None,               # EEF link 名称
        **kwargs
    ):
        self.mode = mode
        self.workspace_pose_limiter = workspace_pose_limiter
        self.reset_joint_pos = reset_joint_pos[dof_idx]
        self._link_name = link_name
        
        super().__init__(
            control_freq=control_freq,
            motor_type="position",  # IK 输出是关节位置
            control_limits=control_limits,
            dof_idx=dof_idx,
            **kwargs
        )
```

### 4.2 IK 模式详解

```python
# 模式 1: absolute_pose (绝对位姿)
# 命令: [x, y, z, ax, ay, az] (世界坐标系)
command = th.tensor([1.5, 0.3, 1.2, 0.0, 1.57, 0.0])

# 模式 2: pose_delta_ori (位姿 delta)
# 命令: [dx, dy, dz, dax, day, daz] (相对当前位姿)
command = th.tensor([0.01, 0.0, -0.02, 0.0, 0.0, 0.1])

# 模式 3: position_fixed_ori (只控制位置)
# 命令: [dx, dy, dz] (朝向保持初始值)
command = th.tensor([0.01, 0.0, -0.02])
```

### 4.3 IK 求解流程

```python
def _compute_control(self, command, goal_dict, control_dict):
    """
    IK 控制核心逻辑
    """
    # Step 1: 解析命令
    if self.mode == "absolute_pose":
        target_pos = command[:3]
        target_ori = command[3:]  # axis-angle
    
    elif self.mode == "pose_delta_ori":
        # 当前 EEF 位姿
        current_pos, current_quat = goal_dict["eef_pose"]
        
        # Delta 位置
        target_pos = current_pos + command[:3]
        
        # Delta 朝向 (axis-angle)
        delta_ori = command[3:]
        delta_quat = axis_angle_to_quat(delta_ori)
        target_quat = quat_multiply(current_quat, delta_quat)
    
    elif self.mode == "position_fixed_ori":
        current_pos, _ = goal_dict["eef_pose"]
        target_pos = current_pos + command[:3]
        target_quat = self._fixed_quat_target  # 固定朝向
    
    # Step 2: 工作空间限制
    if self.workspace_pose_limiter is not None:
        target_pos, target_quat = self.workspace_pose_limiter(target_pos, target_quat)
    
    # Step 3: 调用 IK 求解器
    target_joint_pos = self._solve_ik(
        target_pos=target_pos,
        target_quat=target_quat,
        current_joint_pos=goal_dict["joint_position"][self.dof_idx],
        reset_joint_pos=self.reset_joint_pos,
    )
    
    # Step 4: 平滑滤波
    if self.control_filter is not None:
        target_joint_pos = self.control_filter.estimate(target_joint_pos)
    
    return target_joint_pos

def _solve_ik(self, target_pos, target_quat, current_joint_pos, reset_joint_pos):
    """
    求解 IK (使用数值方法)
    
    优化目标:
        min ||FK(q) - target_pose||^2 + λ||q - q_reset||^2
        
        第一项: 末端位姿误差
        第二项: Nullspace 约束 (倾向于 reset 位置)
    """
    # 使用 Levenberg-Marquardt 或梯度下降
    # 这里简化表示
    joint_pos = optimize_ik(
        target_pos=target_pos,
        target_quat=target_quat,
        initial_guess=current_joint_pos,
        nullspace_target=reset_joint_pos,
    )
    
    return joint_pos
```

### 4.4 使用示例

```python
# 创建 IK 控制器
ik_controller = InverseKinematicsController(
    control_freq=30,
    reset_joint_pos=robot.reset_joint_pos,
    control_limits=robot.control_limits,
    dof_idx=robot.arm_dof_idx,
    mode="pose_delta_ori",
    link_name="eef_link",
)

# Delta 位姿命令
command = th.tensor([
    0.01, 0.0, -0.02,  # dx, dy, dz (向前1cm, 向下2cm)
    0.0, 0.0, 0.1      # dax, day, daz (绕z轴旋转0.1rad)
])

goal_dict = {
    "command": command,
    "joint_position": current_joint_pos,
    "joint_velocity": current_joint_vel,
    "eef_pose": (eef_pos, eef_quat),
}

# 计算控制 (输出关节位置)
control_dict = {}
ik_controller.compute_control(goal_dict, control_dict)
```

## 5. OperationalSpaceController (OSC 控制器)

### 5.1 原理

**操作空间控制器**: 在笛卡尔空间直接控制 EEF，输出关节力矩。

```python
# omnigibson/controllers/osc_controller.py

class OperationalSpaceController(ManipulationController):
    """
    OSC 控制器
    
    特点:
        - 在笛卡尔空间计算控制
        - 输出关节力矩
        - 支持阻抗控制
        - 考虑动力学模型
    
    控制律:
        τ = J^T * (Kp * e_pos + Kd * e_vel) + nullspace + compensation
    """
    
    def __init__(
        self,
        control_freq,
        reset_joint_pos,
        control_limits,
        dof_idx,
        kp=150.0,                # 笛卡尔空间刚度
        damping_ratio=1.0,       # 阻尼比
        kp_null=10.0,            # Nullspace 刚度
        kd_null=2.0,             # Nullspace 阻尼
        mode="pose_delta_ori",
        link_name=None,
        **kwargs
    ):
        self.kp = kp
        self.kd = 2 * math.sqrt(kp) * damping_ratio
        self.kp_null = kp_null
        self.kd_null = kd_null
        
        super().__init__(
            control_freq=control_freq,
            motor_type="effort",  # OSC 输出是力矩
            ...
        )
```

### 5.2 OSC 控制律

```python
def _compute_control(self, command, goal_dict, control_dict):
    """
    OSC 核心算法
    """
    # Step 1: 计算目标位姿 (同 IK)
    target_pos, target_quat = self._compute_target_pose(command, goal_dict)
    
    # Step 2: 计算笛卡尔空间误差
    current_pos, current_quat = goal_dict["eef_pose"]
    
    pos_error = target_pos - current_pos
    ori_error = orientation_error(target_quat, current_quat)
    
    # 组合为 6D 误差
    pose_error = th.cat([pos_error, ori_error])  # [6]
    
    # Step 3: 计算笛卡尔空间速度误差
    J = goal_dict["jacobian"][self.dof_idx]  # Jacobian [6, DOF]
    joint_vel = goal_dict["joint_velocity"][self.dof_idx]
    eef_vel = J @ joint_vel  # 笛卡尔速度 [6]
    
    vel_error = -eef_vel  # 目标速度为 0
    
    # Step 4: 笛卡尔空间 PD 控制
    # F = Kp * e_pos + Kd * e_vel
    desired_force = self.kp * pose_error + self.kd * vel_error  # [6]
    
    # Step 5: 映射到关节空间
    # τ = J^T * F
    u_task = J.T @ desired_force  # [DOF]
    
    # Step 6: Nullspace 控制 (保持关节接近 reset 位置)
    # 计算 nullspace 投影矩阵
    # N = I - J^+ * J
    J_inv = th.linalg.pinv(J)
    N = th.eye(len(self.dof_idx)) - J_inv @ J
    
    # Nullspace PD 控制
    joint_pos = goal_dict["joint_position"][self.dof_idx]
    null_error = self.reset_joint_pos - joint_pos
    null_vel = -joint_vel
    
    u_null = N @ (self.kp_null * null_error + self.kd_null * null_vel)
    
    # Step 7: 组合
    mass_matrix = goal_dict["mass_matrix"][self.dof_idx][:, self.dof_idx]
    u = mass_matrix @ (u_task + u_null)
    
    # Step 8: 添加补偿
    u += goal_dict["cc_force"][self.dof_idx]  # 科里奥利/离心力
    
    return u
```

### 5.3 OSC vs IK

| 特性 | IK Controller | OSC Controller |
|------|---------------|----------------|
| **输出** | 关节位置 | 关节力矩 |
| **控制空间** | 关节空间 | 操作空间 |
| **动力学** | 不考虑 | 完全考虑 |
| **阻抗控制** | 可选 | 原生支持 |
| **计算复杂度** | 中等 (IK求解) | 高 (动力学计算) |
| **柔顺性** | 较差 | 优秀 |
| **适用场景** | 快速移动 | 精细操作、接触任务 |

## 6. 其他控制器

### 6.1 HolonomicBaseJointController (全向底盘)

```python
class HolonomicBaseJointController(JointController):
    """
    全向底盘控制器
    
    命令: [vx, vy, w] (前进、侧移、旋转速度)
    输出: 虚拟关节目标 (x, y, theta)
    """
    
    def _compute_control(self, command, goal_dict, control_dict):
        # 积分速度命令得到位置
        dt = 1.0 / self.control_freq
        
        vx, vy, w = command
        current_x, current_y, current_theta = goal_dict["base_pos"]
        
        target_x = current_x + vx * dt
        target_y = current_y + vy * dt
        target_theta = current_theta + w * dt
        
        return th.tensor([target_x, target_y, target_theta])
```

### 6.2 DifferentialDriveController (差速驱动)

```python
class DifferentialDriveController(LocomotionController):
    """
    差速驱动控制器 (如 TurtleBot)
    
    命令: [v, w] (线速度、角速度)
    输出: 左右轮速度 [v_left, v_right]
    """
    
    def _compute_control(self, command, goal_dict, control_dict):
        v, w = command
        wheel_base = self.wheel_base
        
        # 差速运动学
        v_left = v - w * wheel_base / 2
        v_right = v + w * wheel_base / 2
        
        return th.tensor([v_left, v_right])
```

### 6.3 MultiFingerGripperController (多指抓手)

```python
class MultiFingerGripperController(GripperController):
    """
    多指抓手控制器
    
    命令: [gripper_state] (1=闭合, -1=张开)
    输出: 所有手指关节目标
    """
    
    def _compute_control(self, command, goal_dict, control_dict):
        gripper_command = command[0]  # [-1, 1]
        
        if gripper_command > 0:
            # 闭合: 移动到 closed 位置
            target = self.closed_joint_pos
        else:
            # 张开: 移动到 opened 位置
            target = self.opened_joint_pos
        
        return target
```

## 7. ControllerView (批量控制)

### 7.1 原理

**ControllerView**: 高效的批量控制器，用于同时控制多个机器人或多个控制组。

```python
# omnigibson/controllers/controller_view.py

class ControllerView:
    """
    批量控制器视图
    
    优势:
        - 批量计算 (GPU 加速)
        - 共享计算 (Jacobian, Mass Matrix)
        - 内存效率高
    
    用途:
        - 多机器人仿真
        - 双臂机器人 (左臂 + 右臂)
        - 完整机器人 (底盘 + 躯干 + 左臂 + 右臂 + 抓手)
    """
    
    def __init__(self, controller_cls, *args, **kwargs):
        """
        Args:
            controller_cls: 控制器类 (e.g., JointController)
            *args, **kwargs: 传递给控制器的参数
        """
        self.controller_cls = controller_cls
        self.args = args
        self.kwargs = kwargs
        
        # 批量状态
        self._batch_size = 0
        self._members = []  # 每个成员是一个虚拟控制器
    
    def add_member(self, member_id):
        """添加成员到批量"""
        self._members.append(member_id)
        self._batch_size += 1
    
    def compute_control(self, goal_dicts, control_dicts):
        """
        批量计算控制
        
        Args:
            goal_dicts: List[dict] - 每个成员的目标字典
            control_dicts: List[dict] - 每个成员的控制字典
        
        Returns:
            List[dict] - 更新后的控制字典
        """
        # Step 1: 堆叠所有成员的数据
        commands = th.stack([g["command"] for g in goal_dicts])  # [B, D]
        joint_positions = th.stack([g["joint_position"] for g in goal_dicts])
        # ...
        
        # Step 2: 批量计算 (GPU 加速)
        controls = self._batched_compute(
            commands=commands,
            joint_positions=joint_positions,
            # ...
        )  # [B, D]
        
        # Step 3: 分发结果
        for i, control_dict in enumerate(control_dicts):
            control_dict[self.control_type] = controls[i]
        
        return control_dicts
```

### 7.2 使用示例

```python
# 创建批量控制器
controller_view = ControllerView(
    controller_cls=JointController,
    control_freq=30,
    motor_type="position",
    control_limits=control_limits,
    dof_idx=[0, 1, 2, 3, 4, 5, 6],
)

# 添加3个机器人
controller_view.add_member("robot_0")
controller_view.add_member("robot_1")
controller_view.add_member("robot_2")

# 批量控制
goal_dicts = [
    {"command": command_0, "joint_position": pos_0, ...},
    {"command": command_1, "joint_position": pos_1, ...},
    {"command": command_2, "joint_position": pos_2, ...},
]

control_dicts = [{}, {}, {}]

# 一次调用控制所有机器人
controller_view.compute_control(goal_dicts, control_dicts)
```

## 8. 实际使用示例

### 8.1 Robot 中的 Controller 配置

```python
# 机器人配置文件 (YAML)
controllers:
  # 底盘控制器
  base:
    name: HolonomicBaseJointController
    control_freq: 30
    motor_type: velocity
    command_input_limits: [-1, 1]
    command_output_limits: [-0.5, 0.5]  # m/s
  
  # 左臂控制器
  left_arm:
    name: InverseKinematicsController
    control_freq: 30
    mode: pose_delta_ori
    command_output_limits: 
      - [-0.2, -0.2, -0.2, -0.5, -0.5, -0.5]
      - [0.2, 0.2, 0.2, 0.5, 0.5, 0.5]
  
  # 左抓手控制器
  left_gripper:
    name: MultiFingerGripperController
    control_freq: 30
    motor_type: position
```

### 8.2 在 Policy 中使用

```python
class MyPolicy:
    def act(self, obs):
        # 高层决策
        target_eef_delta = self.model(obs)  # [dx, dy, dz, dax, day, daz]
        gripper_state = self.decide_gripper(obs)  # 1 or -1
        
        # 组合动作
        action = {
            "left_arm": target_eef_delta,
            "left_gripper": gripper_state,
            "base": [0.1, 0.0, 0.0],  # 向前移动
        }
        
        return action

# Environment 内部会调用对应的控制器
# left_arm_controller.compute_control(...)
# left_gripper_controller.compute_control(...)
# base_controller.compute_control(...)
```

## 9. 总结

### 9.1 控制器选择指南

| 任务类型 | 推荐控制器 | 原因 |
|---------|-----------|------|
| 导航 | HolonomicBaseJointController | 支持全向移动 |
| 快速抓取 | IK + JointController | 快速、稳定 |
| 精细操作 | OSC | 柔顺、考虑动力学 |
| 接触任务 | OSC | 力控制、阻抗控制 |
| 抓手 | MultiFingerGripperController | 简化接口 |

### 9.2 关键概念

1. **命令处理**: 裁剪、缩放
2. **控制类型**: position, velocity, effort
3. **增益调整**: kp, kd 影响响应速度和稳定性
4. **Delta vs Absolute**: 相对命令 vs 绝对命令
5. **阻抗控制**: 使用质量矩阵的柔顺控制
6. **批量控制**: ControllerView 提高效率

Controller 系统是 OmniGibson 机器人控制的核心，提供了从高层命令到低层执行的完整桥梁！
