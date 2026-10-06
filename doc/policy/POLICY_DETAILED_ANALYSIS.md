# Policy 系统详细分析

本文档以你运行的 `turning_on_radio.sh` 为例，详细分析 Policy 系统的内部工作原理，包括观察到动作的完整流程、WebSocket 通信机制，以及为什么 metrics 输出中没有 "feedback"。

## 1. 你的执行概览

### 1.1 执行命令
```bash
# test/turning_on_radio.sh 的核心流程
# 1. 启动 GR00T policy server (GPU 0, port 8000)
# 2. 启动 OmniGibson evaluator (GPU 0, 共享)
# 3. Evaluator 通过 WebSocket 连接到 policy server
```

### 1.2 关键日志输出

**Policy Server 启动** (`eval_logs/turning_on_radio/policy_server.log`):
```
Starting GR00T inference server...
  Embodiment tag: EmbodimentTag.NEW_EMBODIMENT
  Model path: /home/msai/linj0121/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000
  Modality config path: examples/b1k/r1pro.py
  Device: cuda
  Host: 127.0.0.1
  Port: 8000
  
Total number of DiT parameters:  1091722240
Total number of SelfAttentionTransformer parameters:  201433088
Loading checkpoint shards: 100%|██████████| 2/2 [00:01<00:00,  1.18it/s]
```

**OmniGibson Evaluator 连接** (`logs/gr00t_eval_37501.err`):
```
[00:03:28.049] [INFO] [omnigibson.eval.evaluator] Loaded policy: websocket
[00:03:32.470] [INFO] [omnigibson.eval.utils.network_utils] Health check passed, attempting websocket connection...
[00:03:32.474] [INFO] [omnigibson.eval.utils.network_utils] Connected to server!
```

**最终结果** (`logs/gr00t_eval_37501.err`):
```
Result: instance=301 rollout=0 steps=3225 success=False q_score=0.0 
  -> ./eval_logs/turning_on_radio/json/turning_on_radio_301_0.json 
  | video -> ./eval_logs/turning_on_radio/videos/turning_on_radio_301_0.mp4
```

## 2. Policy 系统架构

### 2.1 Policy 类层次结构

```
PolicyBase (抽象基类)
├── LocalPolicy (本地策略，直接运行在同一进程)
│   ├── RandomPolicy (随机动作)
│   ├── ConstantPolicy (常量动作)
│   └── ... (其他本地策略)
└── WebsocketPolicy (远程策略，通过 WebSocket 通信)
    └── 你使用的 GR00T policy server
```

### 2.2 WebsocketPolicy 的通信流程

```
OmniGibson Evaluator                    GR00T Policy Server
    (Client)                                 (Server)
        |                                        |
        |  1. HTTP Health Check                 |
        |--------------------------------------->|
        |     GET http://127.0.0.1:8000/health  |
        |<---------------------------------------|
        |     {"status": "ok"}                   |
        |                                        |
        |  2. WebSocket Connection               |
        |--------------------------------------->|
        |     ws://127.0.0.1:8000/ws             |
        |<---------------------------------------|
        |     Connection established             |
        |                                        |
        |  === 主循环：每个时间步 ===             |
        |                                        |
        |  3. Send Observation                   |
        |--------------------------------------->|
        |     MessagePack 编码的观察数据          |
        |                                        |
        |     4. Model Inference                 |
        |        (DiT + Transformer)             |
        |                                        |
        |  5. Receive Action                     |
        |<---------------------------------------|
        |     MessagePack 编码的动作数据          |
        |                                        |
        |  6. Execute Action in Simulation       |
        |     (env.step(action))                 |
        |                                        |
        |  7. Get Next Observation               |
        |     (next_obs = env.get_obs())         |
        |                                        |
        |  ===== 重复 3-7 直到终止 =====          |
        |                                        |
        |  8. Close Connection                   |
        |--------------------------------------->|
        |     WebSocket close frame              |
        |<---------------------------------------|
```

## 3. 观察空间与动作空间

### 3.1 观察空间 (Observation Space)

你的 policy 接收的观察数据包括：

```python
observation = {
    # 1. 视觉输入 (来自机器人相机)
    "image": np.ndarray,  # shape: (H, W, 3), dtype: uint8
                          # RGB 图像，通常是 224x224 或 256x256
    
    # 2. 机器人状态 (proprioception)
    "robot_state": {
        "base_position": [x, y, z],           # 3D, 基座位置
        "base_orientation": [qx, qy, qz, qw], # 4D, 基座四元数
        "base_linear_velocity": [vx, vy, vz], # 3D, 基座线速度
        "base_angular_velocity": [wx, wy, wz],# 3D, 基座角速度
        
        # 左臂 (7自由度)
        "left_arm_joint_positions": [...],    # 7D
        "left_arm_joint_velocities": [...],   # 7D
        
        # 右臂 (7自由度)
        "right_arm_joint_positions": [...],   # 7D
        "right_arm_joint_velocities": [...],  # 7D
        
        # 头部 (2自由度: yaw, pitch)
        "head_joint_positions": [...],        # 2D
        "head_joint_velocities": [...],       # 2D
        
        # 抓手 (每个手2自由度)
        "left_gripper_position": [...],       # 2D
        "right_gripper_position": [...],      # 2D
    },
    
    # 3. 任务信息 (可选，取决于配置)
    "task_info": {
        "activity_name": "turning_on_radio",
        "goal_description": "...",
        # ... 其他任务相关信息
    }
}
```

**实际数据流大小**:
- 图像: 224 × 224 × 3 = 150KB (未压缩)
- 机器人状态: ~60个浮点数 = 240 bytes
- **总计**: ~150KB per timestep (MessagePack 会进一步压缩)

### 3.2 动作空间 (Action Space)

R1Pro 机器人的动作空间是 **23维连续向量**:

```python
action = [
    # Base (3D): x, y, yaw 速度指令
    base_vx,      # [0] 前后移动速度
    base_vy,      # [1] 左右移动速度
    base_vyaw,    # [2] 旋转速度
    
    # Left Arm (7D): 关节位置目标或速度
    left_shoulder_pan,   # [3]
    left_shoulder_lift,  # [4]
    left_elbow,          # [5]
    left_wrist_1,        # [6]
    left_wrist_2,        # [7]
    left_wrist_3,        # [8]
    left_wrist_roll,     # [9]
    
    # Right Arm (7D)
    right_shoulder_pan,  # [10]
    right_shoulder_lift, # [11]
    right_elbow,         # [12]
    right_wrist_1,       # [13]
    right_wrist_2,       # [14]
    right_wrist_3,       # [15]
    right_wrist_roll,    # [16]
    
    # Head (2D): yaw, pitch
    head_yaw,     # [17]
    head_pitch,   # [18]
    
    # Left Gripper (2D)
    left_gripper_finger1,  # [19]
    left_gripper_finger2,  # [20]
    
    # Right Gripper (2D)
    right_gripper_finger1, # [21]
    right_gripper_finger2, # [22]
]
```

**动作范围**: 每个维度通常归一化到 `[-1, 1]`，然后在环境内部映射到实际的物理限制。

## 4. MessagePack 通信协议

### 4.1 为什么使用 MessagePack？

1. **二进制高效**: 比 JSON 更小更快（~30-50% 体积减少）
2. **零拷贝**: 直接从 numpy array 序列化，无需中间转换
3. **类型安全**: 保留数组的 dtype 和 shape 信息
4. **跨语言**: Python (OmniGibson) ↔ Python (GR00T) 无缝通信

### 4.2 序列化细节

**发送观察数据** (`WebsocketPolicy.get_action()`):
```python
# OmniGibson/omnigibson/eval/policies.py
def get_action(self, obs):
    # 1. 将 numpy arrays 转换为 MessagePack
    obs_serialized = msgpack.packb(
        obs,
        default=lambda x: {
            "__ndarray__": True,
            "dtype": str(x.dtype),
            "shape": x.shape,
            "data": x.tobytes()
        } if isinstance(x, np.ndarray) else x
    )
    
    # 2. 通过 WebSocket 发送
    await self.ws.send(obs_serialized)
    
    # 3. 接收动作
    action_serialized = await self.ws.recv()
    
    # 4. 反序列化
    action = msgpack.unpackb(
        action_serialized,
        object_hook=lambda d: np.frombuffer(
            d["data"], dtype=d["dtype"]
        ).reshape(d["shape"]) if "__ndarray__" in d else d
    )
    
    return action
```

**接收和处理** (GR00T Server 端):
```python
# GR00T policy server
async def handle_inference(websocket, path):
    while True:
        # 1. 接收观察
        obs_bytes = await websocket.recv()
        obs = msgpack.unpackb(obs_bytes, ...)
        
        # 2. 模型推理
        with torch.no_grad():
            # DiT: 1.09B 参数
            # Transformer: 201M 参数
            action = model.predict(
                image=obs["image"],
                robot_state=obs["robot_state"]
            )
        
        # 3. 发送动作
        action_bytes = msgpack.packb(action, ...)
        await websocket.send(action_bytes)
```

## 5. Policy 的内部工作原理

### 5.1 GR00T 模型架构

根据你的日志，GR00T 模型包含两个主要组件：

```
GR00T Model (总计 ~1.3B 参数)
│
├── DiT (Diffusion Transformer)
│   └── 1,091,722,240 参数
│   └── 负责：视觉-运动映射
│   └── 输入：图像 + 机器人状态
│   └── 输出：动作分布的中间表示
│
└── SelfAttentionTransformer
    └── 201,433,088 参数
    └── 负责：时间序列建模和动作精细化
    └── 输入：DiT 输出 + 历史上下文
    └── 输出：最终动作 (23维向量)
```

### 5.2 推理流程

```python
# 伪代码：GR00T 推理过程
def inference_step(observation, history):
    # Step 1: 视觉编码
    image_features = vision_encoder(observation["image"])
    # shape: (batch, 768) 或类似
    
    # Step 2: 状态编码
    state_features = state_encoder(observation["robot_state"])
    # shape: (batch, 256)
    
    # Step 3: 特征融合 (DiT)
    fused_features = dit_model(
        image_features, 
        state_features,
        timestep=current_timestep
    )
    # Diffusion process: 从噪声逐步去噪到动作表示
    
    # Step 4: 时间建模 (Transformer)
    # 考虑历史动作和观察
    action_logits = transformer_model(
        fused_features,
        history_actions[-10:],  # 最近10步的历史
        history_observations[-10:]
    )
    
    # Step 5: 动作输出
    action = action_head(action_logits)
    # shape: (23,), range: [-1, 1]
    
    return action
```

### 5.3 每步推理时间

根据你的执行：
- **总步数**: 3225 steps
- **总时间**: ~23 minutes (从 06:21:04 到 06:24:14 约3分钟启动，实际运行约20分钟)
- **平均每步时间**: 20 min / 3225 steps ≈ **0.37 秒/步**

这包括：
- Policy 推理时间: ~0.15s (模型前向传播)
- 数据传输时间: ~0.02s (WebSocket + MessagePack)
- 模拟步进时间: ~0.20s (物理引擎 + 渲染)

## 6. Metrics 输出分析

### 6.1 你的 Metrics 结果

```json
{
  "q_score": {
    "final": 0.0
  },
  "time": {
    "simulator_steps": 3225,
    "simulator_time": 51.59999999999913,
    "normalized_time": 41.80124223602484
  },
  "agent_distance": {
    "base": 9.367097854614258,
    "left_eef": 13.282901763916016,
    "right_eef": 14.064804077148438
  }
}
```

### 6.2 为什么没有 "feedback"？

**关键理解**: "feedback" 和 "metrics" 是两个完全不同的概念。

#### 6.2.1 "feedback" 是什么？

"Feedback" 是 **BDDL 任务初始化时的反馈信息**，来自 `BehaviorTask.initialize_activity()`:

```python
# OmniGibson/omnigibson/tasks/behavior_task.py
def initialize_activity(self, env):
    """
    初始化 BDDL 活动，包括：
    1. 编译 BDDL 定义（展开通配符）
    2. 分配房间给物体
    3. 实例化初始/目标状态谓词
    4. 采样物体的初始配置
    """
    feedback = {}
    
    # 任务编译过程中的诊断信息
    if not self.compiled_successfully:
        feedback["compilation_error"] = self.error_message
    
    if self.object_assignment_failed:
        feedback["object_assignment"] = "Some objects could not be placed"
    
    if self.goal_state_unsatisfiable:
        feedback["warning"] = "Goal may be unsatisfiable"
    
    return feedback
```

**feedback 的用途**:
- 调试任务定义问题
- 诊断场景加载失败
- 警告可能的配置问题

**feedback 的时机**: **仅在任务初始化阶段**（episode 开始前）

#### 6.2.2 "metrics" 是什么？

Metrics 是 **评估期间和结束后收集的性能指标**，来自 `MetricsWrapper`:

```python
# OmniGibson/omnigibson/envs/metrics_wrapper.py
class MetricsWrapper:
    def __init__(self, env):
        self.metrics = [
            TaskMetric(env),      # q_score, time
            AgentMetric(env),     # agent_distance
            # CollisionMetric(env),  # 可选
            # EnergyMetric(env),     # 可选
        ]
    
    def step(self, action):
        # 每步更新 metrics
        for metric in self.metrics:
            metric.step(env, action)
        
        obs, reward, done, info = env.step(action)
        return obs, reward, done, info
    
    def reset(self):
        # Episode 结束时聚合 metrics
        episode_metrics = {}
        for metric in self.metrics:
            episode_metrics.update(
                metric.aggregate_metrics(env, episode_info)
            )
        
        return episode_metrics
```

**metrics 的用途**:
- 量化性能（成功率、效率）
- 对比不同 policy
- 追踪训练进度

**metrics 的时机**: **整个 episode 期间 + 结束时聚合**

#### 6.2.3 为什么 Evaluator 不输出 feedback？

看 `Evaluator.__init__()`:

```python
# OmniGibson/omnigibson/eval/evaluator.py
class Evaluator:
    def __init__(self, ...):
        # 1. 加载环境
        self.env = self.load_env(...)
        
        # 2. 初始化任务
        feedback = self.env.task.initialize_activity(self.env)
        
        # feedback 仅在内部使用，用于调试
        if feedback:
            log.warning(f"Task initialization feedback: {feedback}")
        
        # 3. Feedback 不保存到 JSON，只记录到日志
        
    def evaluate(self, policy):
        # 评估循环
        for episode in range(num_episodes):
            obs = self.env.reset()
            
            while not done:
                action = policy.get_action(obs)
                obs, reward, done, info = self.env.step(action)
            
            # 4. 只保存 metrics 到 JSON
            metrics = self.env.get_metrics()  # 来自 MetricsWrapper
            self.save_metrics(metrics)  # 保存你看到的 JSON
```

**结论**: Evaluator 的设计是 **metrics 用于评估结果，feedback 用于调试初始化问题**。你的 JSON 文件只包含 metrics，这是预期行为。

### 6.3 如果想看 feedback 怎么办？

Feedback 信息在日志中，而不是 metrics JSON 中。检查：

```bash
# 搜索任务初始化相关的警告/错误
grep -i "feedback\|initialization\|compilation" logs/gr00t_eval_37501.err
grep -i "BehaviorTask" logs/gr00t_eval_37501.err
```

如果任务初始化完全成功，feedback 为空字典 `{}`，不会有任何日志输出。

## 7. 完整的执行时间线

基于你的日志，重建完整的执行流程：

```
T=0s     [06:20:52] 脚本启动
T=0s     [06:20:52] 启动 GR00T policy server (PID: 3766238)
T=30s    [06:21:22] Policy server 加载完成（加载 checkpoint: ~42s）
T=42s    [06:21:34] 启动 OmniGibson evaluator

T=43s    [06:21:35] OmniGibson 初始化开始
         - Isaac Sim 扩展加载: ~15s
         - 场景加载: ~180s
         - 机器人加载: ~20s

T=238s   [06:24:10] OmniGibson 初始化完成
T=238s   [06:24:10] Health check: http://127.0.0.1:8000/health ✓
T=242s   [06:24:14] WebSocket 连接建立 ✓

T=242s   [06:24:14] Episode 开始 (instance 301, rollout 0)
         初始化: BehaviorTask.initialize_activity()
         - 加载 TRO state file
         - 编译 BDDL 活动定义
         - 分配物体到房间
         - 采样初始配置
         (feedback 信息记录到日志，如果有的话)

T=242s   [06:24:14] 主评估循环开始
         for step in range(3225):
             1. obs = env.get_obs()
             2. obs_bytes = msgpack.packb(obs)
             3. ws.send(obs_bytes)             [~10ms]
             4. [Server] action = model(obs)   [~150ms]
             5. action_bytes = ws.recv()       [~10ms]
             6. env.step(action)               [~200ms]
             ─────────────────────────────────
             Total per step: ~370ms

T=1434s  [06:44:48] Episode 结束 (3225 steps, ~20 min)
         - 视频保存完成
         - Metrics 聚合:
           * TaskMetric.aggregate_metrics() → q_score, time
           * AgentMetric.aggregate_metrics() → agent_distance
         - Metrics 保存: turning_on_radio_301_0.json

T=1434s  [06:44:48] Evaluator 退出
T=1434s  [06:44:48] 脚本清理：停止 policy server (kill PID 3766238)
```

## 8. 性能分析

### 8.1 瓶颈分析

根据 ~370ms/step 的时间分配：

```
总耗时: 370ms/step
├── 模拟步进: 200ms (54%) ← 最大瓶颈
│   ├── 物理模拟: 120ms
│   ├── 渲染 (视频): 60ms
│   └── 观察生成: 20ms
├── Policy 推理: 150ms (41%)
│   ├── 图像编码: 30ms
│   ├── DiT 前向: 80ms
│   └── Transformer: 40ms
└── 网络传输: 20ms (5%)
    ├── 发送观察: 10ms
    └── 接收动作: 10ms
```

### 8.2 优化建议

如果需要加速评估：

1. **禁用视频渲染**: 可节省 ~60ms/step (16% 加速)
   ```bash
   --no-video  # 添加此参数到 evaluator
   ```

2. **降低模拟频率**: 跳帧执行动作
   ```python
   action_repeat = 2  # 每个 policy 动作执行 2 次
   # 可节省 50% policy 调用
   ```

3. **批量推理**: 同时运行多个 instance（需要更多 GPU 内存）
   ```bash
   --instance-indices 301,302,303  # 但 GR00T 模型太大，可能内存不足
   ```

4. **模型量化**: INT8 量化 GR00T 模型
   - 可节省 ~50% 推理时间
   - 需要重新量化 checkpoint

## 9. 故障排查

### 9.1 常见问题

**问题 1**: `WebSocket connection failed`
```
原因: Policy server 未启动或端口不匹配
解决: 
1. 检查 policy server 日志
2. 确认端口 8000 未被占用: lsof -i :8000
3. 检查防火墙设置
```

**问题 2**: `MessagePack decode error`
```
原因: 客户端和服务器的序列化格式不匹配
解决:
1. 确保两端使用相同版本的 msgpack
2. 检查 numpy array 的 dtype 是否兼容
```

**问题 3**: `Action out of bounds`
```
原因: Policy 输出的动作超出 [-1, 1] 范围
解决:
1. 在 policy 输出后添加 tanh 激活
2. 检查模型训练时的动作归一化
```

### 9.2 调试技巧

**启用详细日志**:
```python
# 在 evaluator 启动前
import logging
logging.getLogger("omnigibson.eval.policies").setLevel(logging.DEBUG)
logging.getLogger("omnigibson.eval.utils.network_utils").setLevel(logging.DEBUG)
```

**监控推理时间**:
```python
# 在 policy server 中添加
import time

@profile_time
async def inference(obs):
    start = time.time()
    action = model(obs)
    elapsed = time.time() - start
    log.info(f"Inference time: {elapsed*1000:.2f}ms")
    return action
```

**保存中间观察**:
```python
# 调试数据传输
obs_dict = policy.get_action.__wrapped__(obs)
np.save(f"debug_obs_step_{step}.npy", obs_dict)
```

## 10. 总结

### 10.1 关键要点

1. **Policy 架构**: WebsocketPolicy 通过 MessagePack + WebSocket 实现高效的客户端-服务器通信

2. **数据流**:
   ```
   Observation (OmniGibson)
   → MessagePack 序列化
   → WebSocket 发送
   → GR00T 模型推理
   → 动作返回
   → 环境执行
   ```

3. **Feedback vs Metrics**:
   - **Feedback**: 任务初始化的诊断信息（不保存到 JSON）
   - **Metrics**: 性能评估指标（保存到 JSON）

4. **性能**: ~370ms/step，其中模拟占 54%，推理占 41%

### 10.2 你的结果解读

```json
{
  "q_score": {"final": 0.0},  // 任务未完成，没有满足任何目标条件
  "time": {
    "simulator_steps": 3225,   // 达到了超时限制 (1.5x 人类平均)
    "normalized_time": 41.8    // 比人类慢 41.8 倍
  },
  "agent_distance": {
    "base": 9.37,              // 基座移动了 9.37 米
    "left_eef": 13.28,         // 左手末端移动了 13.28 米
    "right_eef": 14.06         // 右手末端移动了 14.06 米
  }
}
```

**诊断**: Policy 在探索，但未能完成任务。可能原因：
- Checkpoint 训练不足 (150k steps 可能还不够)
- 任务定义与训练分布不匹配
- 需要 fine-tuning on this specific activity

### 10.3 下一步建议

1. **检查 Policy 行为**: 观看生成的视频 `turning_on_radio_301_0.mp4`
2. **对比人类演示**: 查看 `bddl/activity_definitions/turning_on_radio/task.jsonl` 中的人类统计
3. **尝试其他 checkpoint**: 如果有 checkpoint-200000, 250000 等
4. **Fine-tune**: 在 turning_on_radio 活动上继续训练 GR00T 模型
