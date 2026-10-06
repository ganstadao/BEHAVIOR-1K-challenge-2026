# WebSocket Policy Server 详解：以 Pi0.5 为例

本文档详细讲解 WebSocket 在 VLA Policy Server 中的使用，包括参数传递、数据格式、通信协议等，以 OpenPI (Pi0.5) 代码为例进行分析。

## 1. 系统架构对比

### 1.1 三种 Policy Server 对比

| 特性 | GR00T | Pi0.5 (OpenPI) | 共同点 |
|------|-------|----------------|--------|
| **框架** | JAX/PyTorch | JAX/PyTorch | 都支持两种框架 |
| **模型** | Qwen3-VL + DiT | PaliGemma + Diffusion | VLM + Diffusion |
| **参数量** | ~1.3B | ~3B (PaliGemma 2.8B) | 都是十亿级 |
| **WebSocket** | websockets.asyncio | websockets.asyncio | 相同协议 |
| **序列化** | MessagePack | MessagePack | 相同格式 |
| **Health Check** | /healthz | /healthz | 相同端点 |
| **控制模式** | 默认 receding_horizon | receding_horizon / receding_temporal | 都支持 action chunking |

## 2. Pi0.5 执行脚本分析

### 2.1 你的 `run_pi0_5_eval.sh` 脚本

```bash
#!/bin/bash
# SBATCH 配置省略...

# ========== 配置区 ==========
export OPENPI_DIR=~/LINJ0121/openpi
export PATH_TO_BEHAVIOR_1K=~/project/BEHAVIOR-1K
export TASK_NAME=turning_on_radio
export PATH_TO_CKPT=~/LINJ0121/checkpoint/pi05_turn_on_the_radio
export PORT=8000
export REPO_ID=turning_on_radio
export LOG_PATH=./eval_logs/pi05_$TASK_NAME

# Python 环境
export OPENPI_PYTHON=$OPENPI_DIR/.venv/bin/python
export BEHAVIOR_PYTHON=/home/msai/linj0121/.conda/envs/behavior/bin/python
# ===========================

# Step 1: 启动 Pi0.5 Policy Server
cd "$OPENPI_DIR"
CUDA_VISIBLE_DEVICES=0 XLA_PYTHON_CLIENT_MEM_FRACTION=0.85 \
"$OPENPI_PYTHON" scripts/b1k/serve_b1k.py \
    --robot b1k/R1Pro \                    # 机器人配置
    --task b1k/$TASK_NAME \                # 任务配置
    --repo-id $REPO_ID \                   # LeRobot repo ID (norm stats)
    --policy.config pi05_b1k \             # Policy 配置名
    --policy.dir "$PATH_TO_CKPT" \         # Checkpoint 路径
    --control_mode receding_horizon \      # 控制模式
    --action_horizon 16 \                  # Action horizon
    --port "$PORT" \                       # WebSocket 端口
    &
SERVE_PID=$!

# Step 2: 等待服务器就绪
for i in $(seq 1 90); do
    if curl -s "http://127.0.0.1:$PORT/healthz" > /dev/null 2>&1; then
        echo "Policy server is ready"
        break
    fi
    sleep 2
done

# Step 3: 启动 OmniGibson Evaluator
cd "$PATH_TO_BEHAVIOR_1K"
CUDA_VISIBLE_DEVICES=0 "$BEHAVIOR_PYTHON" -m omnigibson.eval.eval \
    --task-name "$TASK_NAME" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --output-dir "$LOG_PATH" \
    --write-video \
    --env-wrapper omnigibson.eval.wrappers.RGBDFullResWrapper

# Step 4: 清理
kill "$SERVE_PID" 2>/dev/null || true
```

### 2.2 关键参数说明

#### Server 启动参数

```python
# scripts/b1k/serve_b1k.py 的参数

@dataclasses.dataclass
class Args:
    # === 必需参数 ===
    robot: str
    # 格式: "bucket/name"
    # 例如: "b1k/R1Pro"
    # 从 ROBOT_REGISTRY 加载配置
    
    task: str
    # 格式: "bucket/name"
    # 例如: "b1k/turning_on_radio"
    # 从 TASK_REGISTRY 加载任务提示词
    
    policy: Checkpoint
    # policy.config: 训练配置名 (e.g., "pi05_b1k")
    # policy.dir: checkpoint 目录路径
    
    # === 可选参数 ===
    repo_id: str | None = None
    # LeRobot repo ID，用于加载归一化统计
    # 如果为 None，使用 task 作为 repo_id
    
    control_mode: str = "receding_horizon"
    # 控制模式:
    #   - "receding_horizon": 每 K 步重新规划
    #   - "receding_temporal": 时间集成平滑
    
    action_horizon: int = 16
    # 多少步后重新规划 (K)
    
    port: int = 8000
    # WebSocket 服务器端口
    
    record: bool = False
    # 是否记录 policy 行为用于调试
```

#### 环境变量

```bash
# JAX 内存管理
XLA_PYTHON_CLIENT_MEM_FRACTION=0.85
# 限制 JAX 使用 GPU 内存的比例 (85%)
# 避免 OOM，为 OmniGibson 预留内存

# CUDA 设备
CUDA_VISIBLE_DEVICES=0
# 指定使用 GPU 0
# Policy Server 和 OmniGibson 共享同一个 GPU
```

## 3. Policy Server 初始化流程

### 3.1 serve_b1k.py 主流程

```python
# scripts/b1k/serve_b1k.py

def main(args: Args) -> None:
    # === Step 1: 加载任务提示词 ===
    task_bucket, task_name = args.task.split("/")
    task_prompt = TASK_REGISTRY[task_bucket][task_name]
    # 例如: "Turn on the radio"
    
    logging.info(f"Using robot: {args.robot}, prompt: {task_prompt}")
    
    # === Step 2: 加载训练配置 ===
    config = _config.get_config(args.policy.config)
    # 从 openpi/configs/ 加载配置
    # 例如: pi05_b1k -> openpi/configs/pi05_b1k.py
    
    # 覆盖运行时参数
    norm_stats_repo_id = args.repo_id or args.task
    config = dataclasses.replace(
        config,
        data=dataclasses.replace(
            config.data,
            repo_id=norm_stats_repo_id,        # LeRobot repo for norm stats
            robot_config_name=args.robot       # e.g., "b1k/R1Pro"
        )
    )
    
    # === Step 3: 创建 Policy ===
    policy = _policy_config.create_trained_policy(
        config, 
        args.policy.dir,                       # checkpoint 目录
        default_prompt=task_prompt             # 默认提示词
    )
    policy_metadata = policy.metadata
    
    # === Step 4: 可选的记录包装 ===
    if args.record:
        policy = _policy.PolicyRecorder(policy, "policy_records")
    
    # === Step 5: B1K 适配器包装 ===
    policy = B1KPolicyWrapper(
        policy=policy,
        robot=args.robot,                      # "b1k/R1Pro"
        text_prompt=task_prompt,               # "Turn on the radio"
        control_mode=args.control_mode,        # "receding_horizon"
        action_horizon=args.action_horizon,    # 16
        max_len=config.model.action_horizon,   # 模型最大 action horizon
    )
    
    # === Step 6: 启动 WebSocket Server ===
    server = websocket_b1k_server.WebsocketPolicyServer(
        policy=policy,
        host="0.0.0.0",                        # 监听所有接口
        port=args.port,                        # 8000
        metadata=policy_metadata,              # 模型元数据
    )
    server.serve_forever()                     # 阻塞运行
```

### 3.2 B1KPolicyWrapper 详解

**作用**: 适配 OmniGibson 观察格式到 OpenPI 模型输入格式

```python
# src/openpi/shared/eval_b1k_wrapper.py

class B1KPolicyWrapper:
    def __init__(
        self,
        policy: BasePolicy,
        robot: str,                    # "b1k/R1Pro"
        text_prompt: str,              # "Turn on the radio"
        control_mode: str,             # "receding_horizon" | "receding_temporal"
        action_horizon: int,           # 16
        max_len: int,                  # 模型的 max action horizon
        obs_size: tuple = (224, 224),  # 图像尺寸
    ):
        # 1. 加载机器人配置
        self.robot = ROBOT_REGISTRY[robot]
        # ROBOT_REGISTRY["b1k/R1Pro"] = RobotConfig(
        #     name="robot_r1",
        #     observations={...},  # 相机配置
        #     proprio=[...],       # 本体感觉配置
        #     action=[...],        # 动作配置
        # )
        
        self.policy = policy
        self.text_prompt = text_prompt
        self.control_mode = control_mode
        self.action_horizon = action_horizon
        self.obs_size = obs_size
        self.max_len = max_len
        
        # 2. 提取抓手索引 (gripper 需要特殊处理)
        self.gripper_indices = []
        for action_config in self.robot.action:
            if action_config.is_eef and action_config.indices is not None:
                self.gripper_indices.extend(action_config.indices)
        
        # 3. 初始化动作缓冲区 (用于 action chunking)
        self.batch_size = None
        self.action_buffer = None          # [B, max_sequences, max_horizon, action_dim]
        self.sequence_indices = None       # [B, max_sequences]
        self.sequence_lengths = None       # [B, max_sequences]
        self.num_active_sequences = None   # [B]
        self.step_counter = None           # [B]
```

**关键方法**:

```python
def process_input(self, obs: dict) -> dict:
    """
    将 OmniGibson 观察转换为模型输入格式
    
    输入 (OmniGibson):
    obs = {
        "robot_r1::proprio": [61] or [B, 61],
        "robot_r1::robot_r1:zed_link:Camera:0::rgb": [H, W, 3] or [B, H, W, 3],
        "robot_r1::robot_r1:left_realsense_link:Camera:0::rgb": ...,
        "robot_r1::robot_r1:right_realsense_link:Camera:0::rgb": ...,
    }
    
    输出 (OpenPI):
    [
        {
            "observation/image_0": [224, 224, 3] uint8,
            "observation/image_1": [224, 224, 3] uint8,
            "observation/image_2": [224, 224, 3] uint8,
            "observation/state": [23] float32,  # 从 61 维提取
            "prompt": "Turn on the radio",
        },
        ...  # 批次中的其他样本
    ]
    """
    # 1. 提取本体感觉
    prop_state = obs[f"{self.robot.name}::proprio"]
    if prop_state.ndim == 1:
        prop_state = prop_state[None, :]  # [61] -> [1, 61]
    batch_size = prop_state.shape[0]
    
    # 2. 处理相机图像
    observations = []
    for camera_key in sorted(self.robot.observations.keys()):
        camera_obs = obs[self.robot.observations[camera_key].obs_key][..., :3]
        if camera_obs.ndim == 3:
            camera_obs = camera_obs[None, ...]  # [H,W,C] -> [1,H,W,C]
        # Resize 到 224x224 (保持纵横比，padding)
        observations.append(resize_with_pad(camera_obs, *self.obs_size))
    
    # 3. 如果少于3个相机，用零填充
    while len(observations) < 3:
        observations.append(np.zeros((batch_size, *self.obs_size, 3), dtype=np.uint8))
    
    img_obs = np.stack(observations, axis=1)  # [B, 3, 224, 224, 3]
    
    # 4. 构建批量输入
    processed_input = [
        {
            "observation/image_0": img_obs[i, 0],
            "observation/image_1": img_obs[i, 1],
            "observation/image_2": img_obs[i, 2],
            "observation/state": prop_state[i],  # [61] 会在 b1k_policy.py 中提取到 [23]
            "prompt": self.text_prompt,
        }
        for i in range(batch_size)
    ]
    return processed_input
```

**Receding Horizon 控制**:

```python
def act_receding_horizon(self, input_obs):
    """
    Receding Horizon 控制模式:
    - 预测 16 步动作
    - 执行当前动作
    - 每 16 步重新规划
    """
    batched = input_obs[f"{self.robot.name}::proprio"].ndim != 1
    input_batch = self.process_input(input_obs)
    batch_size = len(input_batch)
    
    # 判断是否需要推理
    if self.sequence_indices is None:
        needs_inference = np.ones(batch_size, dtype=bool)
    else:
        needs_inference = (
            (self.sequence_indices[:, 0] >= self.sequence_lengths[:, 0]) |  # 已执行完所有动作
            ((self.step_counter % self.action_horizon) == 0)                # 达到重新规划时间
        )
    
    # 对需要推理的样本运行 policy
    if needs_inference.any():
        indices_needing_inference = np.where(needs_inference)[0]
        action = []
        for i in indices_needing_inference:
            action.append(self.policy.infer(input_batch[i]))
        target_action = np.array([a["actions"].copy() for a in action])  # [sub_batch, T, action_dim]
        
        # 初始化缓冲区 (第一次推理)
        if self.action_buffer is None:
            action_dim = target_action.shape[2]
            self._ensure_batch_initialized(batch_size, action_dim)
        
        # 存储新的动作序列
        seq_len = min(target_action.shape[1], self.max_len)
        self.action_buffer[indices_needing_inference, 0, :seq_len] = target_action[:, :seq_len]
        self.sequence_lengths[indices_needing_inference, 0] = seq_len
        self.sequence_indices[indices_needing_inference, 0] = 0
    
    # 提取当前时间步的动作
    batch_range = np.arange(batch_size)
    current_indices = self.sequence_indices[batch_range, 0]
    final_actions = self.action_buffer[batch_range, 0, current_indices]
    
    # 递增索引
    self.sequence_indices[:, 0] += 1
    self.step_counter += 1
    
    if not batched:
        final_actions = final_actions[0]
    
    return torch.from_numpy(final_actions)
```

## 4. WebSocket 通信协议

### 4.1 WebsocketPolicyServer 实现

```python
# src/openpi/serving/websocket_b1k_server.py

class WebsocketPolicyServer:
    def __init__(
        self,
        policy: Any,
        host: str = "0.0.0.0",
        port: int = 8000,
        metadata: dict | None = None,
    ):
        self._policy = policy
        self._host = host
        self._port = port
        self._metadata = metadata or {}
    
    def serve_forever(self) -> None:
        """启动异步事件循环"""
        asyncio.run(self.run())
    
    async def run(self):
        """启动 WebSocket 服务器"""
        logger.info(f"Starting websocket server on {self._host}:{self._port}...")
        async with _server.serve(
            self._handler,
            self._host,
            self._port,
            compression=None,      # 禁用压缩 (MessagePack 已经很高效)
            max_size=None,         # 无消息大小限制
            process_request=_health_check,  # Health check 钩子
        ) as server:
            await server.serve_forever()
```

**连接处理**:

```python
async def _handler(self, websocket):
    """处理单个 WebSocket 连接"""
    logger.info(f"Connection from {websocket.remote_address} opened")
    packer = Packer()  # MessagePack packer
    
    # Step 1: 发送元数据 (handshake)
    await websocket.send(packer.pack(self._metadata))
    # metadata = {
    #     "model_type": "pi05",
    #     "action_dim": 23,
    #     "action_horizon": 16,
    #     ...
    # }
    
    prev_total_time = None
    
    # Step 2: 主循环
    while True:
        try:
            start_time = time.monotonic()
            
            # 2.1 接收观察
            result = unpackb(await websocket.recv(), strict_map_key=False)
            
            # 2.2 处理 reset 请求
            if "reset" in result:
                self._policy.reset()
                continue
            
            # 2.3 复制观察 (避免被 transform 修改)
            obs = deepcopy(result)
            
            # 2.4 Policy 推理
            infer_time = time.monotonic()
            action = self._policy.act(obs)  # B1KPolicyWrapper.act_*()
            infer_time = time.monotonic() - infer_time
            
            # 2.5 构建响应
            action_dict = {
                "action": action.cpu().numpy(),  # [23] float32
            }
            action_dict["server_timing"] = {
                "infer_ms": infer_time * 1000,
            }
            if prev_total_time is not None:
                action_dict["server_timing"]["prev_total_ms"] = prev_total_time * 1000
            
            # 2.6 发送动作
            await websocket.send(packer.pack(action_dict))
            prev_total_time = time.monotonic() - start_time
        
        except websockets.ConnectionClosed:
            logger.info(f"Connection from {websocket.remote_address} closed")
            break
        
        except Exception:
            logger.error(f"Error in connection: {traceback.format_exc()}")
            await websocket.close(code=1011, reason="Internal server error")
            raise
```

### 4.2 Health Check 端点

```python
def _health_check(connection, request) -> Optional[Any]:
    """
    HTTP Health Check 钩子
    
    OmniGibson evaluator 在启动时会轮询这个端点:
    $ curl -s "http://127.0.0.1:8000/healthz"
    OK
    """
    if hasattr(request, "path") and request.path == "/healthz":
        if hasattr(connection, "respond"):
            return connection.respond(http.HTTPStatus.OK, "OK\n")
        else:
            # 旧版 websockets 兼容
            return http.HTTPStatus.OK, {"Content-Type": "text/plain"}, b"OK\n"
    
    # 非 health check 请求，继续正常处理
    return None
```

### 4.3 MessagePack 序列化

**支持类型**:
- NumPy arrays
- PyTorch tensors (自动转换为 NumPy)
- Scalars
- Nested dicts/lists

```python
def pack_data(obj):
    """序列化数据"""
    # PyTorch tensor → NumPy
    if isinstance(obj, torch.Tensor):
        data = obj.detach().cpu().numpy()
        return {
            b"__ndarray__": True,
            b"data": data.tobytes(),
            b"dtype": data.dtype.str,
            b"shape": data.shape,
        }
    
    # NumPy array
    if isinstance(obj, np.ndarray):
        if obj.dtype.kind in ("V", "O", "c"):
            raise ValueError(f"Unsupported dtype: {obj.dtype}")
        return {
            b"__ndarray__": True,
            b"data": obj.tobytes(),
            b"dtype": obj.dtype.str,
            b"shape": obj.shape,
        }
    
    # NumPy scalar
    if isinstance(obj, np.generic):
        return {
            b"__npgeneric__": True,
            b"data": obj.item(),
            b"dtype": obj.dtype.str,
        }
    
    return obj

def unpack_data(obj):
    """反序列化数据"""
    if b"__ndarray__" in obj:
        return np.ndarray(
            buffer=obj[b"data"],
            dtype=np.dtype(obj[b"dtype"]),
            shape=obj[b"shape"]
        )
    
    if b"__npgeneric__" in obj:
        return np.dtype(obj[b"dtype"]).type(obj[b"data"])
    
    return obj

# 创建自定义 Packer/Unpacker
Packer = functools.partial(msgpack.Packer, default=pack_data)
Unpacker = functools.partial(msgpack.Unpacker, object_hook=unpack_data)
```

## 5. 数据流详解

### 5.1 完整的一个时间步

```python
# ========== OmniGibson (Client) ==========

# Step 1: 获取观察
obs = env.get_obs()
# obs = {
#     "robot_r1::proprio": np.array([61], dtype=float32),
#     "robot_r1::robot_r1:zed_link:Camera:0::rgb": np.array([H, W, 3], dtype=uint8),
#     "robot_r1::robot_r1:left_realsense_link:Camera:0::rgb": ...,
#     "robot_r1::robot_r1:right_realsense_link:Camera:0::rgb": ...,
# }

# Step 2: 通过 WebSocket 发送
obs_bytes = msgpack.packb(obs, default=pack_array)
await websocket.send(obs_bytes)

# ========== Policy Server ==========

# Step 3: 接收并反序列化
obs = unpackb(await websocket.recv(), strict_map_key=False)

# Step 4: B1KPolicyWrapper 预处理
processed_input = policy.process_input(obs)
# processed_input = [
#     {
#         "observation/image_0": [224, 224, 3] uint8,
#         "observation/image_1": [224, 224, 3] uint8,
#         "observation/image_2": [224, 224, 3] uint8,
#         "observation/state": [23] float32,  # 从 61 维提取
#         "prompt": "Turn on the radio",
#     }
# ]

# Step 5: 根据控制模式执行
if control_mode == "receding_horizon":
    action = policy.act_receding_horizon(obs)
    # - 检查是否需要推理 (每 16 步)
    # - 如果需要: 运行 policy.infer()，缓存 16 步动作
    # - 返回当前时间步的动作

# Step 6: Policy.infer() 内部
# 6.1 数据 transform (B1KInputs)
inputs = self._input_transform(processed_input[0])
# {
#     "image": {
#         "base_0_rgb": [224, 224, 3],
#         "left_wrist_0_rgb": [224, 224, 3],
#         "right_wrist_0_rgb": [224, 224, 3],
#     },
#     "image_mask": {
#         "base_0_rgb": True,
#         "left_wrist_0_rgb": True,
#         "right_wrist_0_rgb": True,
#     },
#     "state": [23] float32,
#     "prompt": "Turn on the radio",
# }

# 6.2 添加 batch 维度并转换为 JAX/PyTorch
if is_jax:
    inputs = jax.tree.map(lambda x: jnp.asarray(x)[None, ...], inputs)
else:
    inputs = jax.tree.map(lambda x: torch.from_numpy(x).to(device)[None, ...], inputs)

# 6.3 模型推理
observation = Observation.from_dict(inputs)
actions = model.sample_actions(rng, observation, **sample_kwargs)
# actions: [1, action_horizon, action_dim] = [1, 16, 23]

# 6.4 移除 batch 维度
if is_jax:
    actions = np.asarray(actions[0, ...])
else:
    actions = actions[0, ...].detach().cpu().numpy()
# actions: [16, 23]

# Step 7: 输出 transform (B1KOutputs)
output = self._output_transform({"actions": actions})
# output = {"actions": actions[:, :23]}  # 截取前 23 维

# Step 8: 返回第一步动作
action = torch.from_numpy(output["actions"][0])  # [23]

# Step 9: 序列化并发送
action_dict = {
    "action": action.cpu().numpy(),
    "server_timing": {"infer_ms": 150.2},
}
action_bytes = msgpack.packb(action_dict, default=pack_data)
await websocket.send(action_bytes)

# ========== OmniGibson (Client) ==========

# Step 10: 接收动作
action_bytes = await websocket.recv()
action_dict = msgpack.unpackb(action_bytes, object_hook=unpack_array)
action = action_dict["action"]  # [23] float32

# Step 11: 执行动作
obs, reward, done, info = env.step(action)
```

### 5.2 状态提取 (61 → 23 维)

```python
# src/openpi/policies/b1k_policy.py: extract_state_from_proprio()

def extract_state_from_proprio(proprio_data, robot_config: RobotConfig) -> np.ndarray:
    """
    从 61 维 proprio 提取 23 维 state
    
    根据 robot_config.proprio 配置提取相应的索引
    """
    state = []
    for proprio in robot_config.proprio:
        if proprio.is_eef:
            # 对于抓手 (end-effector)，求和两个手指的位置
            # 例如: left_gripper [24, 25] -> sum -> [1]
            state.append(proprio_data[..., proprio.indices].sum(axis=-1, keepdims=True))
        else:
            # 直接提取
            state.append(proprio_data[..., proprio.indices])
    
    return np.concatenate(state, axis=-1)

# R1Pro 的 proprio 配置 (示例):
# proprio = [
#     ProprioConfig(name="base_qvel", indices=[0, 1, 2], is_eef=False),
#     ProprioConfig(name="left_arm", indices=[3, 4, 5, 6, 7, 8, 9], is_eef=False),
#     ProprioConfig(name="left_gripper", indices=[24, 25], is_eef=True),  # sum -> 1
#     ProprioConfig(name="right_arm", indices=[28, 29, 30, 31, 32, 33, 34], is_eef=False),
#     ProprioConfig(name="right_gripper", indices=[49, 50], is_eef=True),  # sum -> 1
#     ProprioConfig(name="torso", indices=[53, 54, 55, 56], is_eef=False),
# ]
#
# 输出: [3 + 7 + 1 + 7 + 1 + 4] = 23 维
```

## 6. 控制模式对比

### 6.1 Receding Horizon

```
时间线: 0   1   2   ... 15  16  17  18  ... 31  32  ...
        │                   │               │
        ├─── Plan 1 ────────┤               │
        │   (16 steps)      │               │
        │                   │               │
        └─ execute step 0   ├─── Plan 2 ────┤
            ...             │   (16 steps)  │
            execute step 15 │               │
                            └─ execute step 0
                                ...

特点:
- 每 action_horizon (16) 步重新规划
- 每次推理生成 16 步动作，执行完再推理
- 计算开销: 1 次推理 / 16 步 = 0.0625 推理/步
```

### 6.2 Receding Temporal

```
时间线: 0   1   2   ... 15  16  17  18  ... 31  32  ...
        │                   │               │
        ├─── Plan 1 ────────┤               │
        │                   │               │
        │               ├─── Plan 2 ────────┤
        │               │                   │
        │           ├─── Plan 3 ────────────┤
        │           │                       │
        ├───────────┼───────────┼───────────┼───>
        0          15          31          47
        
每步动作: Weighted Average of [Plan 1, Plan 2, Plan 3]

特点:
- 每 action_horizon (16) 步推理一次新计划
- 维护最近 5 个计划的缓冲区
- 当前动作 = 所有活跃计划的加权平均
- 抓手动作取最大值 (确保抓取)
- 更平滑，但计算开销相同
```

**实现**:

```python
def act_receding_temporal(self, input_obs):
    """时间集成平滑"""
    # Step 1: 每 action_horizon 步推理一次
    if (self.step_counter % self.action_horizon) == 0:
        # 运行推理
        action = self.policy.infer(input_batch[i])
        
        # 将新计划添加到缓冲区
        # action_buffer: [B, max_sequences, max_horizon, action_dim]
        # 新计划插入到 slot 0，旧计划后移
        self.action_buffer[:, 1:] = self.action_buffer[:, :-1].copy()
        self.action_buffer[:, 0, :seq_len] = target_action[:, :seq_len]
        
        # 更新 num_active_sequences (最多 5 个)
        self.num_active_sequences = np.minimum(
            self.num_active_sequences + 1,
            self.temporal_ensemble_max
        )
    
    # Step 2: 计算加权平均
    # 提取所有活跃序列在当前时间步的动作
    batch_range = np.arange(batch_size)
    seq_range = np.arange(self.temporal_ensemble_max)
    active_mask = seq_range[None, :] < self.num_active_sequences[:, None]
    current_indices = self.sequence_indices
    
    # [B, max_sequences, action_dim]
    all_actions = self._get_current_actions(
        batch_range=batch_range,
        seq_range=seq_range,
        active_mask=active_mask,
        current_indices=current_indices,
        sequence_lengths=self.sequence_lengths,
    )
    
    # 归一化权重 (活跃序列权重均匀分布)
    weights = active_mask.astype(np.float32)  # [B, max_sequences]
    weights = weights / np.maximum(weights.sum(axis=1, keepdims=True), 1.0)
    
    # 加权平均
    weighted_actions = (all_actions * weights[:, :, None]).sum(axis=1)
    # [B, action_dim]
    
    # Step 3: 抓手特殊处理 (取最大值，确保抓取)
    if self.gripper_indices:
        gripper_actions = all_actions[:, :, self.gripper_indices]  # [B, seq, gripper_dim]
        gripper_mask = active_mask[:, :, None]  # [B, seq, 1]
        masked_gripper = np.where(gripper_mask, gripper_actions, -np.inf)
        max_gripper = masked_gripper.max(axis=1)  # [B, gripper_dim]
        weighted_actions[:, self.gripper_indices] = max_gripper
    
    # Step 4: 递增所有活跃序列的索引
    self.sequence_indices += active_mask.astype(np.int32)
    self.step_counter += 1
    
    return torch.from_numpy(weighted_actions)
```

## 7. Pi0.5 与 GR00T 对比

### 7.1 参数传递对比

| 参数 | GR00T | Pi0.5 | 说明 |
|------|-------|-------|------|
| **模型路径** | `--model-path <path>` | `--policy.dir <path>` | GR00T 直接传路径，Pi0.5 用嵌套参数 |
| **配置名** | N/A (从模型推断) | `--policy.config <name>` | Pi0.5 需要显式指定配置 |
| **机器人** | N/A (从 modality config) | `--robot b1k/R1Pro` | Pi0.5 用 registry 查找 |
| **任务** | N/A (从命令行参数) | `--task b1k/turning_on_radio` | Pi0.5 从 registry 加载提示词 |
| **归一化** | 内置在 processor | `--repo-id <name>` | Pi0.5 从 LeRobot hub 加载 |
| **控制模式** | 默认 receding_horizon | `--control_mode receding_horizon` | Pi0.5 可选 temporal |
| **Action Horizon** | 固定 16 | `--action_horizon 16` | 可配置 |

### 7.2 代码结构对比

```
GR00T:
gr00t/
├── eval/
│   └── run_gr00t_server.py         # 服务器入口
├── policy/
│   ├── gr00t_policy.py             # Policy 实现
│   └── websocket_b1k_server.py     # WebSocket server
└── model/
    └── gr00t_n1d7/
        └── gr00t_n1d7.py           # 模型实现

特点:
- 所有逻辑集成在 gr00t_policy.py
- 没有额外的 wrapper 层
- 直接处理 OmniGibson 格式

---

Pi0.5 (OpenPI):
openpi/
├── scripts/
│   └── b1k/
│       └── serve_b1k.py            # 服务器入口
├── policies/
│   ├── policy.py                   # 通用 Policy 基类
│   └── b1k_policy.py               # B1K 数据 transforms
├── serving/
│   └── websocket_b1k_server.py     # WebSocket server
├── shared/
│   └── eval_b1k_wrapper.py         # B1K 适配器 (重要!)
└── configs/
    └── robots/                     # 机器人配置 registry

特点:
- 模块化设计
- B1KPolicyWrapper 作为适配层
- transform 分离 (B1KInputs, B1KOutputs)
- 支持多种机器人 (Aloha, Droid, Libero, B1K)
```

### 7.3 优缺点对比

| 方面 | GR00T | Pi0.5 |
|------|-------|-------|
| **易用性** | ⭐⭐⭐⭐ 参数少，开箱即用 | ⭐⭐⭐ 需要理解配置系统 |
| **灵活性** | ⭐⭐⭐ 固定流程 | ⭐⭐⭐⭐⭐ 高度模块化 |
| **可扩展性** | ⭐⭐⭐ 添加新机器人需修改代码 | ⭐⭐⭐⭐⭐ 通过 registry 添加 |
| **控制模式** | ⭐⭐⭐ 仅 receding_horizon | ⭐⭐⭐⭐ horizon + temporal |
| **代码复杂度** | ⭐⭐⭐⭐ 简洁 | ⭐⭐ 多层抽象 |

## 8. 调试技巧

### 8.1 启用详细日志

```bash
# 在启动脚本中添加
export OPENPI_LOG_LEVEL=DEBUG

# 或者在 serve_b1k.py 中
logging.basicConfig(level=logging.DEBUG, force=True)
```

### 8.2 记录 Policy 行为

```bash
python scripts/b1k/serve_b1k.py \
    --robot b1k/R1Pro \
    --task b1k/turning_on_radio \
    --policy.config pi05_b1k \
    --policy.dir <path> \
    --record \              # 启用记录
    --port 8000
```

生成 `policy_records/` 目录，包含:
- 观察数据
- 动作输出
- 时间戳

### 8.3 测试 WebSocket 连接

```python
# 手动测试客户端
import asyncio
import msgpack
import websockets
import numpy as np

async def test_connection():
    uri = "ws://127.0.0.1:8000/ws"
    async with websockets.connect(uri) as websocket:
        # 接收元数据
        metadata = msgpack.unpackb(await websocket.recv())
        print(f"Metadata: {metadata}")
        
        # 发送虚拟观察
        obs = {
            "robot_r1::proprio": np.random.rand(61).astype(np.float32),
            "robot_r1::robot_r1:zed_link:Camera:0::rgb": 
                np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8),
            # ... 其他相机
        }
        await websocket.send(msgpack.packb(obs))
        
        # 接收动作
        action_dict = msgpack.unpackb(await websocket.recv())
        print(f"Action: {action_dict['action']}")
        print(f"Timing: {action_dict['server_timing']}")

asyncio.run(test_connection())
```

### 8.4 监控推理时间

```bash
# 查看日志中的 server_timing
grep "server_timing" eval_logs/pi05_turning_on_radio/omnigibson_eval.log

# 或者在代码中添加
logger.info(f"Inference time: {action_dict['server_timing']['infer_ms']:.2f}ms")
```

## 9. 总结

### 9.1 关键要点

1. **WebSocket 是标准**: GR00T 和 Pi0.5 都使用相同的 WebSocket + MessagePack 协议

2. **适配层很重要**: B1KPolicyWrapper 负责格式转换和控制逻辑

3. **Action Chunking**: 预测多步动作提高流畅性，receding horizon 是标准做法

4. **模块化设计**: Pi0.5 的 registry 系统使添加新机器人/任务变得简单

5. **Health Check**: `/healthz` 端点用于服务器就绪检测

### 9.2 参数传递总结

```bash
# Pi0.5 完整命令
python scripts/b1k/serve_b1k.py \
    --robot b1k/R1Pro \              # 从 ROBOT_REGISTRY 加载
    --task b1k/turning_on_radio \    # 从 TASK_REGISTRY 加载提示词
    --repo-id turning_on_radio \     # LeRobot repo (norm stats)
    --policy.config pi05_b1k \       # 训练配置名
    --policy.dir <checkpoint_path> \ # Checkpoint 目录
    --control_mode receding_horizon \# 控制模式
    --action_horizon 16 \            # 重新规划频率
    --port 8000 \                    # WebSocket 端口
    --record                         # 可选: 记录行为
```

### 9.3 数据流总结

```
OmniGibson 观察 [61D proprio + 3 cameras]
    ↓
B1KPolicyWrapper.process_input()
    ↓
Policy 输入 [23D state + 3 images + text]
    ↓
B1KInputs transform
    ↓
Model.sample_actions() [预测 16 步]
    ↓
B1KOutputs transform
    ↓
Action chunking (receding horizon)
    ↓
返回第 1 步动作 [23D]
    ↓
OmniGibson 执行
```

这个完整的流程让 Pi0.5 能够与 BEHAVIOR-1K 无缝集成！
