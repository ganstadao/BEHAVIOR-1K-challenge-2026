# 🤖 BEHAVIOR-1K Policy 系统详解

## 📚 什么是 Policy？

**Policy（策略）** 是决定机器人如何行动的"大脑"。它接收观察（observation），输出动作（action）。

```python
观察 (obs) → [Policy] → 动作 (action)
```

---

## 🎯 Policy 的核心接口

所有 Policy 都必须实现两个方法：

```python
class Policy:
    def act(self, obs: dict) -> torch.Tensor:
        """根据观察返回动作"""
        pass
    
    def reset(self) -> None:
        """重置策略状态（新 episode 开始时）"""
        pass
```

---

## 🔧 BEHAVIOR-1K 的两种 Policy

### 1. LocalPolicy - 本地策略

**用途**：在评估器进程内直接运行策略，或输出零动作（baseline）

```python
class LocalPolicy:
    def __init__(self, action_dim: Optional[int] = None):
        self.policy = None  # 可以设置为实际的策略模型
        self.action_dim = action_dim
    
    def act(self, obs: dict) -> th.Tensor:
        if self.policy is not None:
            # 有实际策略：调用它
            return self.policy.act(obs).detach().cpu()
        else:
            # 没有策略：返回零动作（机器人不动）
            return th.zeros(self.action_dim, dtype=th.float32)
    
    def reset(self) -> None:
        if self.policy is not None:
            self.policy.reset()
```

**使用场景**：

#### A. 零动作基准测试
```python
# 测试环境是否正常（机器人保持初始姿态）
policy = LocalPolicy(action_dim=23)  # R1Pro 有 23 个动作维度
action = policy.act(obs)
# 输出：tensor([0., 0., 0., ..., 0.])  # 23个零
```

#### B. 嵌入实际策略
```python
# 创建本地策略
local_policy = LocalPolicy(action_dim=23)

# 加载训练好的模型
my_model = torch.load("my_policy.pt")
local_policy.policy = my_model  # 替换内部策略

# 使用
action = local_policy.act(obs)  # 现在调用你的模型
```

---

### 2. WebsocketPolicy - 远程策略

**用途**：通过 WebSocket 连接到远程服务器，策略模型在服务器上运行

```python
class WebsocketPolicy:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, allow_reconnect: bool = False):
        self.policy = WebsocketClientPolicy(host=host, port=port, allow_reconnect=allow_reconnect)
        self.last_action = None
    
    def forward(self, obs: dict) -> th.Tensor:
        # 1. 检查是否需要新动作
        if "need_new_action" in obs and not obs["need_new_action"]:
            return self.last_action  # 重用上一个动作
        
        # 2. 从服务器获取新动作
        self.last_action = self.policy.act(obs).detach().cpu()
        return self.last_action
    
    def reset(self) -> None:
        if self.policy is not None:
            self.policy.reset()
        self.last_action = None
```

**为什么需要远程策略？**

| 需求 | 原因 |
|------|------|
| **GPU 资源分离** | 策略模型（GPU 0）+ 仿真渲染（GPU 1）分别运行 |
| **大模型支持** | 100GB 的 VLM 模型无法和仿真共享显存 |
| **语言隔离** | 策略用 Python，评估器也用 Python，但可以解耦 |
| **竞赛标准** | BEHAVIOR-1K Challenge 的标准接口 |

---

## 🌐 WebSocket 通信详解

### 架构图

```
┌─────────────────────────────┐         ┌──────────────────────────┐
│  OmniGibson 评估器           │         │  策略服务器               │
│  (GPU 1 - 仿真渲染)          │         │  (GPU 0 - 模型推理)       │
├─────────────────────────────┤         ├──────────────────────────┤
│                             │         │                          │
│  1. 执行 action             │         │  1. 加载模型             │
│  2. 获取 obs                │         │     - VLM               │
│  3. 通过 WebSocket 发送 obs │────────>│     - RL Policy         │
│                             │         │     - 规划器            │
│  4. 接收 action             │<────────│  2. 接收 obs            │
│  5. 执行下一步              │         │  3. 推理 action         │
│                             │         │  4. 返回 action         │
└─────────────────────────────┘         └──────────────────────────┘
        ↓                                           ↑
        └───────── 网络连接 (ws://host:port) ──────┘
```

### 通信协议

#### 消息格式（使用 MessagePack）

**1. 连接建立**
```python
# 客户端连接
WebSocket → ws://127.0.0.1:8000

# 服务器发送元数据
Server → Client: {
    "model_name": "GR00T-1.7B",
    "version": "1.0",
    "action_space": {"dim": 23, "type": "continuous"}
}
```

**2. 观察发送**
```python
Client → Server: {
    "robot0::eyes::rgb": [720, 720, 3] tensor,
    "robot0::eyes::depth": [720, 720] tensor,
    "robot0::proprio": [61] tensor,
    "task_id": 42
}
```

**3. 动作接收**
```python
Server → Client: {
    "action": [23] numpy array  # 机器人的 23 维动作
}
```

**4. 重置信号**
```python
Client → Server: {
    "reset": True
}
```

### WebsocketClientPolicy 工作流程

```python
class WebsocketClientPolicy:
    def __init__(self, host: str, port: int):
        self._uri = f"ws://{host}:{port}"
        self._ws = None  # WebSocket 连接
        self._packer = Packer()  # MessagePack 打包器
    
    def act(self, obs: dict) -> th.Tensor:
        # 1️⃣ 如果还没连接，先建立连接
        if self._ws is None:
            self._ws, self._server_metadata = self._wait_for_server()
        
        # 2️⃣ 打包观察数据
        data = self._packer.pack(obs)
        
        # 3️⃣ 发送到服务器
        self._ws.send(data)
        
        # 4️⃣ 接收响应
        response = self._ws.recv()
        
        # 5️⃣ 解包动作
        action_dict = unpackb(response)
        action = th.from_numpy(action_dict["action"]).to(th.float32)
        
        return action
    
    def _wait_for_server(self):
        # 1. 等待健康检查通过
        health_url = f"http://{host}:{port}/healthz"
        while True:
            try:
                response = requests.get(health_url, timeout=2)
                if response.ok:
                    break
            except Exception:
                pass
            time.sleep(5)
        
        # 2. 建立 WebSocket 连接
        conn = websockets.sync.client.connect(self._uri)
        
        # 3. 接收服务器元数据
        metadata = unpackb(conn.recv())
        
        return conn, metadata
```

---

## 🎮 完整使用示例

### 示例 1：使用 LocalPolicy（零动作）

```python
from omnigibson.eval.policies import LocalPolicy

# 创建零动作策略
policy = LocalPolicy(action_dim=23)

# 评估循环
for step in range(500):
    obs = env.get_observation()
    action = policy.act(obs)  # 全零动作
    obs, reward, done, truncated, info = env.step(action)
    
    if done or truncated:
        policy.reset()
        obs = env.reset()
```

### 示例 2：使用 WebsocketPolicy（远程模型）

#### 终端 1：启动策略服务器

```python
# policy_server.py
import torch
from omnigibson.eval.utils.network_utils import WebsocketPolicyServer

class MyPolicy:
    def __init__(self):
        self.model = torch.load("my_model.pt")
        self.model.eval()
    
    def act(self, obs):
        """
        obs: {
            "robot0::eyes::rgb": tensor([720, 720, 3]),
            "robot0::proprio": tensor([61]),
            ...
        }
        """
        with torch.no_grad():
            # 预处理观察
            rgb = obs["robot0::eyes::rgb"]
            proprio = obs["robot0::proprio"]
            
            # 推理
            action = self.model(rgb, proprio)
        
        return action  # [23] tensor
    
    def reset(self):
        # 重置隐藏状态（如果是 RNN）
        pass

# 创建服务器
policy = MyPolicy()
server = WebsocketPolicyServer(
    policy=policy,
    host="0.0.0.0",
    port=8000,
    metadata={"model_name": "MyModel-v1"}
)

print("Starting policy server on port 8000...")
server.serve_forever()
```

运行：
```bash
CUDA_VISIBLE_DEVICES=0 python policy_server.py
```

#### 终端 2：运行评估器

```bash
CUDA_VISIBLE_DEVICES=1 python -m omnigibson.eval.eval \
    --task-name boil_water \
    --policy websocket \
    --host 127.0.0.1 \
    --port 8000 \
    --instance-indices 0 \
    --output-dir ~/outputs/my_eval \
    --write-video \
    --headless
```

**评估器内部**：
```python
# eval.py 自动创建 WebsocketPolicy
policy = WebsocketPolicy(host="127.0.0.1", port=8000)

# 评估循环
for step in range(500):
    obs = env.get_observation()
    
    # 通过 WebSocket 获取动作
    action = policy.forward(obs)  
    # → 发送 obs 到服务器
    # → 服务器推理
    # → 接收 action
    
    obs, reward, done, truncated, info = env.step(action)
```

---

## 📊 动作空间详解

### R1Pro 机器人的 23 维动作

```python
action = [
    # 底座移动 (3 维)
    0.0,  # base_x_vel      - 前后速度
    0.0,  # base_y_vel      - 左右速度
    0.0,  # base_yaw_vel    - 旋转速度
    
    # 躯干 (4 维)
    0.0,  # trunk_joint_0
    0.0,  # trunk_joint_1
    0.0,  # trunk_joint_2
    0.0,  # trunk_joint_3
    
    # 左臂 (7 维)
    0.0,  # left_arm_joint_0
    0.0,  # left_arm_joint_1
    0.0,  # left_arm_joint_2
    0.0,  # left_arm_joint_3
    0.0,  # left_arm_joint_4
    0.0,  # left_arm_joint_5
    0.0,  # left_arm_joint_6
    
    # 左夹爪 (1 维)
    0.0,  # left_gripper     - [0, 1]: 0=闭合, 1=打开
    
    # 右臂 (7 维)
    0.0,  # right_arm_joint_0
    0.0,  # right_arm_joint_1
    0.0,  # right_arm_joint_2
    0.0,  # right_arm_joint_3
    0.0,  # right_arm_joint_4
    0.0,  # right_arm_joint_5
    0.0,  # right_arm_joint_6
    
    # 右夹爪 (1 维)
    0.0,  # right_gripper
]
# 总计：3 + 4 + 7 + 1 + 7 + 1 = 23 维
```

### 动作归一化

```python
# 如果 action_normalize=True（配置文件中）
action_normalized = [-1, 1]  # 所有维度归一化到 [-1, 1]

# 控制器会自动映射到实际范围
# 例如：base_x_vel: [-1, 1] → [-0.75, 0.75] m/s
```

---

## 🔄 观察空间详解

Policy 接收的 `obs` 是一个字典：

```python
obs = {
    # RGB 图像（多个相机）
    "robot0::eyes::rgb": torch.Tensor([720, 720, 3]),           # 头部相机
    "robot0::left_wrist::rgb": torch.Tensor([480, 480, 3]),     # 左手腕
    "robot0::right_wrist::rgb": torch.Tensor([480, 480, 3]),    # 右手腕
    
    # 深度图
    "robot0::eyes::depth": torch.Tensor([720, 720]),
    
    # 本体感觉（proprioception）
    "robot0::proprio": torch.Tensor([61]),
    # 包含：
    # - base_qvel (3)          - 底座速度
    # - arm_left_qpos (7)      - 左臂关节角度
    # - arm_left_qvel (7)      - 左臂关节速度
    # - eef_left_pos (3)       - 左末端位置
    # - eef_left_quat (4)      - 左末端朝向
    # - gripper_left_qpos (2)  - 左夹爪状态
    # - gripper_left_qvel (2)  - 左夹爪速度
    # - (右侧同理)
    # - trunk_qpos (4)         - 躯干状态
    # - trunk_qvel (4)         - 躯干速度
    
    # 相机相对位姿（如果启用）
    "robot0::cam_rel_poses": torch.Tensor([21]),  # 3个相机 × 7 (pos + quat)
    
    # 任务 ID
    "task_id": torch.Tensor([42]),  # 当前任务的唯一标识
    
    # 控制信号（可选）
    "need_new_action": bool,  # 是否需要新动作（降低推理频率）
}
```

---

## 🎨 高级特性

### 1. 动作缓存（WebsocketPolicy）

```python
def forward(self, obs: dict) -> th.Tensor:
    # 检查是否需要新动作
    if "need_new_action" in obs and not obs["need_new_action"]:
        return self.last_action  # 重用上一个动作
    
    # 获取新动作
    self.last_action = self.policy.act(obs).detach().cpu()
    return self.last_action
```

**用途**：
- 降低推理频率（例如：每 5 步推理一次）
- 节省计算资源
- 模拟真实机器人的控制频率（控制 30Hz，推理 6Hz）

### 2. 自动重连（WebsocketClientPolicy）

```python
def act(self, obs: dict) -> th.Tensor:
    try:
        self._ws.send(data)
        response = self._ws.recv()
        return action
    except websockets.exceptions.ConnectionClosedError:
        if self._allow_reconnect:
            # 自动重连
            self._ws, _ = self._wait_for_server()
            # 重试
            return self.act(obs)
        else:
            raise
```

### 3. 健康检查

```python
# 策略服务器提供健康检查端点
GET http://127.0.0.1:8000/healthz
→ 200 OK

# 评估器在连接前会轮询此端点
while True:
    response = requests.get(health_url, timeout=2)
    if response.ok:
        break  # 服务器就绪
    time.sleep(5)
```

---

## 🆚 LocalPolicy vs WebsocketPolicy 对比

| 特性 | LocalPolicy | WebsocketPolicy |
|------|-------------|-----------------|
| **运行位置** | 评估器进程内 | 远程服务器 |
| **GPU 使用** | 共享 GPU（仿真 + 推理） | 分离 GPU |
| **通信开销** | 无 | ~10ms/step |
| **内存需求** | 高（模型 + 仿真） | 低（仅仿真） |
| **模型大小限制** | 受显存限制 | 无限制 |
| **适用场景** | 小模型、快速原型 | 大模型、生产环境 |
| **调试难度** | 简单 | 中等（需要两个进程） |
| **竞赛标准** | ❌ | ✅ |

---

## 💡 实现自定义 Policy

### 方法 1：扩展 LocalPolicy

```python
class MyLocalPolicy(LocalPolicy):
    def __init__(self, model_path: str):
        super().__init__()
        self.policy = MyModel.load(model_path)
        self.policy.eval()
    
    def forward(self, obs: dict) -> th.Tensor:
        # 自定义推理逻辑
        rgb = obs["robot0::eyes::rgb"]
        proprio = obs["robot0::proprio"]
        
        with torch.no_grad():
            action = self.policy(rgb, proprio)
        
        return action
```

### 方法 2：创建 WebSocket 服务器

```python
from omnigibson.eval.utils.network_utils import WebsocketPolicyServer

class MyServerPolicy:
    def __init__(self):
        self.model = load_model()
        self.hidden_state = None
    
    def act(self, obs: dict) -> th.Tensor:
        # 实现你的推理逻辑
        action, self.hidden_state = self.model(obs, self.hidden_state)
        return action
    
    def reset(self):
        self.hidden_state = None

# 启动服务器
policy = MyServerPolicy()
server = WebsocketPolicyServer(policy, host="0.0.0.0", port=8000)
server.serve_forever()
```

---

## 🎓 总结

### Policy 的核心作用

```python
观察 → Policy → 动作

obs = {
    "rgb": [720, 720, 3],
    "proprio": [61],
    ...
}

action = policy.act(obs)  # [23] 维动作

action = [
    base_vel,      # 底座移动
    arm_joints,    # 手臂关节
    gripper,       # 夹爪开合
    ...
]
```

### 两种 Policy 的选择

- **LocalPolicy**：零动作基准、小模型、快速测试
- **WebsocketPolicy**：大模型、GPU 分离、竞赛提交

### 关键设计模式

1. **统一接口**：`act(obs) → action`
2. **状态管理**：`reset()` 在每个 episode 开始时调用
3. **分布式架构**：WebSocket 实现策略与仿真分离
4. **动作缓存**：降低推理频率
5. **健康检查**：确保服务可用再开始评估

---

希望这份详尽的 Policy 解析帮助你理解了 BEHAVIOR-1K 的策略系统！有任何疑问随时问我。
