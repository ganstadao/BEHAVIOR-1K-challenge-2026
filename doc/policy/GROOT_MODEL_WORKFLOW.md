# GR00T 模型工作流程详解

本文档详细讲解 NVIDIA GR00T (Generalist Robot 00 Technology) 模型的完整工作流程，对应到 BEHAVIOR-1K 的 WebSocket 通信结构，包括模型架构、数据流转、推理过程以及与 OmniGibson 的集成。

## 1. 系统架构概览

### 1.1 完整数据流图

```
OmniGibson Evaluator (Client)           GR00T Policy Server
    │                                         │
    │  [1] WebSocket Connection               │
    │─────────────────────────────────────────>│
    │                                         │
    │  === 每个时间步的循环 ===                │
    │                                         │
    │  [2] 发送观察 (MessagePack)              │
    │─────────────────────────────────────────>│
    │  {                                      │ [3] 解包观察
    │    "video": {                           │     ↓
    │      "head": [1,1,H,W,3] uint8,         │ Gr00tPolicy._get_action()
    │      "left_wrist": [...],               │     ↓
    │      "right_wrist": [...]               │ [4] 数据预处理
    │    },                                   │     ↓
    │    "state": {                           │ Processor(observation)
    │      "base_qvel": [1,1,3] float32,      │  ├─ 图像预处理 (resize, normalize)
    │      "torso": [1,1,4],                  │  ├─ 状态归一化
    │      "left_arm": [1,1,7],               │  └─ 语言编码
    │      "left_gripper": [1,1,2],           │     ↓
    │      "right_arm": [1,1,7],              │ [5] Collate 成批次
    │      "right_gripper": [1,1,2]           │     ↓
    │    },                                   │ collate_fn([processed])
    │    "language": {                        │     ↓
    │      "task_description": [[            │ [6] 模型推理
    │        "turn on the radio"              │     ↓
    │      ]]                                 │ ┌─────────────────────────┐
    │    }                                    │ │   Gr00tN1d7 Model       │
    │  }                                      │ │                         │
    │                                         │ │ [6.1] Qwen3 Backbone    │
    │                                         │ │   ├─ Vision Encoder     │
    │                                         │ │   └─ Language Encoder   │
    │                                         │ │        ↓                │
    │                                         │ │   VL Features           │
    │                                         │ │   [B, seq_len, 3584]    │
    │                                         │ │        ↓                │
    │                                         │ │ [6.2] Action Head       │
    │                                         │ │   ├─ State Encoder      │
    │                                         │ │   ├─ DiT (Flow Match)   │
    │                                         │ │   └─ Action Decoder     │
    │                                         │ │        ↓                │
    │                                         │ │   Action [B,16,23]      │
    │                                         │ └─────────────────────────┘
    │                                         │     ↓
    │                                         │ [7] 动作解码
    │                                         │     ↓
    │                                         │ Processor.decode_action()
    │                                         │  └─ 反归一化到物理单位
    │  [8] 接收动作 (MessagePack)             │     ↓
    │<─────────────────────────────────────────│
    │  {                                      │
    │    "action": [23] float32,              │
    │    "server_timing": {                   │
    │      "infer_ms": 150.2                  │
    │    }                                    │
    │  }                                      │
    │                                         │
    │  [9] 执行动作                            │
    │     ↓                                   │
    │  env.step(action)                       │
    │     ↓                                   │
    │  [10] 获取新观察                         │
    │     ↓                                   │
    │  obs = env.get_obs()                    │
    │     ↓                                   │
    │  ===== 回到步骤 2 =====                  │
```

## 2. GR00T 模型架构

### 2.1 模型组成

GR00T 采用 **视觉-语言-动作 (VLA)** 架构：

```
Gr00tN1d7 Model (总参数: ~1.3B)
│
├── Qwen3Backbone (~100M 参数)
│   ├── Vision Encoder: Qwen3-VL Vision Model
│   │   └── 功能: 处理多视角图像
│   └── Language Encoder: Qwen3 Language Model
│       └── 功能: 理解任务指令
│       └── 输出: VL Features [B, seq_len, 3584]
│
└── Gr00tN1d7ActionHead (~1.2B 参数)
    │
    ├── State Encoder (CategorySpecificMLP)
    │   └── 输入: State [B, 1, state_dim * history_length]
    │   └── 输出: State Features [B, 1, 512]
    │
    ├── DiT (Diffusion Transformer) (~1.09B 参数)
    │   ├── 类型: AlternateVLDiT (交替注意力)
    │   ├── 功能: Flow Matching Diffusion
    │   └── 输出: Denoised Features [B, action_horizon+1, 512]
    │
    ├── SelfAttentionTransformer (~201M 参数)
    │   └── 功能: 时间序列建模
    │
    ├── Action Encoder (MultiEmbodimentActionEncoder)
    │   └── 功能: 编码带噪声的动作轨迹
    │
    └── Action Decoder (CategorySpecificMLP)
        └── 输入: DiT Output [B, action_horizon, 512]
        └── 输出: Actions [B, action_horizon, action_dim]
```

### 2.2 关键参数配置

从你的日志中看到的模型配置：

```python
# 模型路径
model_path = "/home/msai/linj0121/LINJ0121/checkpoint/turning_on_radio_GR00T-checkpoint-150000"

# 模型大小
DiT parameters: 1,091,722,240
Transformer parameters: 201,433,088
Total: ~1.3B

# 推理配置
action_horizon = 16          # 预测16步未来动作
action_dim = 23              # R1Pro 23维动作空间
state_history_length = 1     # 使用1步历史状态
num_inference_timesteps = 10 # Diffusion去噪步数

# Backbone 配置
model_name = "nvidia/Cosmos-Reason2-2B"  # 或 "Qwen/Qwen3-VL-2B"
backbone_embedding_dim = 3584  # VL特征维度
```

## 3. 详细数据流程

### 3.1 观察数据结构 (OmniGibson → GR00T)

#### 3.1.1 原始观察 (从 OmniGibson)

```python
# env.step() 后的 observation
obs = {
    # 视觉观察 - 来自机器人传感器
    "robot_r1::robot_r1:zed_link:Camera:0::rgb": np.ndarray[uint8, (128, 128, 3)],
    "robot_r1::robot_r1:left_realsense_link:Camera:0::rgb": np.ndarray[uint8, (128, 128, 3)],
    "robot_r1::robot_r1:right_realsense_link:Camera:0::rgb": np.ndarray[uint8, (128, 128, 3)],
    
    # 本体感觉 - 61维向量
    "proprio": np.ndarray[float32, (61,)],
    # 分解：
    # [0:3]    base_qvel      - 基座速度
    # [3:10]   left_arm       - 左臂关节位置 (7)
    # [10:17]  left_arm_qvel  - 左臂关节速度 (7)
    # [17:24]  left_arm_qeffort - 左臂关节力矩 (7)
    # [24:26]  left_gripper   - 左抓手位置 (2)
    # [26:28]  left_gripper_qvel - 左抓手速度 (2)
    # [28:35]  right_arm      - 右臂关节位置 (7)
    # [35:42]  right_arm_qvel - 右臂关节速度 (7)
    # [42:49]  right_arm_qeffort - 右臂关节力矩 (7)
    # [49:51]  right_gripper  - 右抓手位置 (2)
    # [51:53]  right_gripper_qvel - 右抓手速度 (2)
    # [53:57]  torso          - 躯干关节位置 (4)
    # [57:61]  torso_qvel     - 躯干关节速度 (4)
}
```

#### 3.1.2 转换为 GR00T 格式

**WebsocketPolicy 客户端** 转换：

```python
# OmniGibson/omnigibson/eval/policies.py: WebsocketPolicy

def get_action(self, obs):
    # 1. 提取和重组观察
    observation = {
        "video": {
            "head": obs["robot_r1::robot_r1:zed_link:Camera:0::rgb"][None, None, ...],  # [1, 1, H, W, 3]
            "left_wrist": obs["robot_r1::robot_r1:left_realsense_link:Camera:0::rgb"][None, None, ...],
            "right_wrist": obs["robot_r1::robot_r1:right_realsense_link:Camera:0::rgb"][None, None, ...],
        },
        "state": {
            # 根据 r1pro.py 配置提取对应索引
            "base_qvel": obs["proprio"][0:3][None, None, :],      # [1, 1, 3]
            "left_arm": obs["proprio"][3:10][None, None, :],      # [1, 1, 7]
            "left_gripper": obs["proprio"][24:26][None, None, :], # [1, 1, 2]
            "right_arm": obs["proprio"][28:35][None, None, :],    # [1, 1, 7]
            "right_gripper": obs["proprio"][49:51][None, None, :], # [1, 1, 2]
            "torso": obs["proprio"][53:57][None, None, :],        # [1, 1, 4]
        },
        "language": {
            "annotation.human.task_description": [["turn on the radio"]],  # [[str]]
        },
    }
    
    # 2. MessagePack 序列化
    obs_bytes = msgpack.packb(observation, default=pack_array)
    
    # 3. 通过 WebSocket 发送
    await websocket.send(obs_bytes)
    
    # 4. 接收动作
    action_bytes = await websocket.recv()
    action_dict = msgpack.unpackb(action_bytes, object_hook=unpack_array)
    
    return action_dict["action"]  # [23] float32
```

### 3.2 模型推理流程

#### 3.2.1 数据预处理

**GR00T Policy Server** 接收到观察后：

```python
# gr00t/policy/websocket_b1k_server.py

async def _handler(self, websocket):
    while True:
        # 1. 接收观察
        obs_bytes = await websocket.recv()
        obs = msgpack.unpackb(obs_bytes, ...)
        
        # 2. Policy 推理
        action = self._policy.act(obs)  # 调用 Gr00tPolicy.act()
        
        # 3. 发送动作
        action_dict = {"action": action.cpu().numpy()}
        await websocket.send(msgpack.packb(action_dict))
```

**Gr00tPolicy.act() 内部**：

```python
# gr00t/policy/gr00t_policy.py: Gr00tPolicy

def act(self, observation):
    # Step 1: 验证观察格式
    self.check_observation(observation)
    
    # Step 2: 调用内部推理方法
    action, info = self._get_action(observation)
    
    return action

def _get_action(self, observation):
    # Step 1: Unbatch 观察 (batch_size=1)
    unbatched_obs = self._unbatch_observation(observation)
    # unbatched_obs[0] = {
    #   "video": {"head": [1,H,W,3], ...},
    #   "state": {"base_qvel": [1,3], ...},
    #   "language": {"annotation.human.task_description": [["text"]]}
    # }
    
    # Step 2: 转换为 VLAStepData
    processed_inputs = []
    states = []
    for obs in unbatched_obs:
        vla_step_data = VLAStepData(
            images=obs["video"],
            states=obs["state"],
            actions={},  # 推理时无 ground truth
            text=obs["language"][self.language_key][0],  # "turn on the radio"
            embodiment=self.embodiment_tag,  # EmbodimentTag.NEW_EMBODIMENT
        )
        states.append(vla_step_data.states)
        
        # Step 3: 使用 Processor 处理
        messages = [{"type": "episode_step", "content": vla_step_data}]
        processed = self.processor(messages)
        processed_inputs.append(processed)
    
    # Step 4: Collate 成批次
    collated = self.collate_fn(processed_inputs)
    collated = _rec_to_dtype(collated, torch.bfloat16)
    
    # collated 结构:
    # {
    #   "vlm_content": {...},  # Qwen3 格式的输入
    #   "state": [B, state_history_length, max_state_dim],
    #   "embodiment_id": [B],
    #   ...
    # }
    
    # Step 5: 模型推理
    with torch.inference_mode():
        model_pred = self.model.get_action(**collated)
    
    # model_pred: {"action_pred": [B, action_horizon, action_dim]}
    normalized_action = model_pred["action_pred"].float()
    
    # Step 6: 动作解码 (反归一化)
    batched_states = {
        k: np.stack([s[k] for s in states], axis=0)
        for k in self.modality_configs["state"].modality_keys
    }
    unnormalized_action = self.processor.decode_action(
        normalized_action.cpu().numpy(),
        self.embodiment_tag,
        batched_states
    )
    
    # unnormalized_action: {
    #   "base": [B, 16, 3],
    #   "torso": [B, 16, 4],
    #   "left_arm": [B, 16, 7],
    #   "left_gripper": [B, 16, 1],
    #   "right_arm": [B, 16, 7],
    #   "right_gripper": [B, 16, 1],
    # }
    
    # Step 7: 提取第一步动作并拼接
    action = np.concatenate([
        unnormalized_action["base"][:, 0, :],       # [B, 3]
        unnormalized_action["torso"][:, 0, :],      # [B, 4]
        unnormalized_action["left_arm"][:, 0, :],   # [B, 7]
        unnormalized_action["left_gripper"][:, 0, :], # [B, 1]
        unnormalized_action["right_arm"][:, 0, :],  # [B, 7]
        unnormalized_action["right_gripper"][:, 0, :], # [B, 1]
    ], axis=-1)  # [B, 23]
    
    return {"action": action[0]}, {}  # 返回第一个样本
```

#### 3.2.2 模型内部推理

**Gr00tN1d7Model.get_action()**：

```python
# gr00t/model/gr00t_n1d7/gr00t_n1d7.py: Gr00tN1d7

def get_action(self, inputs, options=None):
    # Step 1: 准备输入
    backbone_inputs, action_inputs = self.prepare_input(inputs)
    
    # backbone_inputs: {
    #   "input_ids": [B, seq_len],  # Token IDs
    #   "attention_mask": [B, seq_len],
    #   "pixel_values": [B, n_images, C, H, W],
    #   "image_grid_thw": [B, n_images, 3],
    #   ...
    # }
    
    # action_inputs: {
    #   "state": [B, state_history_length, max_state_dim],
    #   "embodiment_id": [B],
    # }
    
    # Step 2: Backbone 前向 (Qwen3-VL)
    backbone_outputs = self.backbone(backbone_inputs)
    
    # backbone_outputs: {
    #   "backbone_features": [B, seq_len, 3584],
    #   "backbone_attention_mask": [B, seq_len],
    #   "image_mask": [B, seq_len],
    # }
    
    # Step 3: Action Head 推理
    action_outputs = self.action_head.get_action(
        backbone_outputs, 
        action_inputs, 
        options
    )
    
    return action_outputs
```

**Action Head 推理** (`Gr00tN1d7ActionHead.get_action()`):

```python
# gr00t/model/gr00t_n1d7/gr00t_n1d7.py: Gr00tN1d7ActionHead

def get_action(self, backbone_output, action_input, options=None):
    # Step 1: 编码特征
    features = self._encode_features(backbone_output, action_input)
    # {
    #   "backbone_features": [B, seq_len, 3584],
    #   "state_features": [B, 1, 512],
    # }
    
    # Step 2: Flow Matching 生成动作
    return self.get_action_with_features(
        backbone_features=features.backbone_features,
        state_features=features.state_features,
        embodiment_id=action_input.embodiment_id,
        backbone_output=backbone_output,
        action_input=action_input,
        options=options,
    )

def get_action_with_features(self, backbone_features, state_features, embodiment_id, ...):
    """
    Flow Matching Diffusion 生成动作轨迹
    """
    batch_size = backbone_features.shape[0]
    device = backbone_features.device
    
    # Step 1: 初始化为随机噪声
    actions = torch.randn(
        size=(batch_size, self.action_horizon, self.action_dim),
        dtype=backbone_features.dtype,
        device=device,
    )  # [B, 16, 23]
    
    # Step 2: 去噪循环 (10步)
    dt = 1.0 / self.num_inference_timesteps  # 0.1
    
    for t in range(self.num_inference_timesteps):  # t = 0, 1, ..., 9
        # 2.1 当前时间步
        t_cont = t / float(self.num_inference_timesteps)  # 0.0, 0.1, ..., 0.9
        t_discretized = int(t_cont * self.num_timestep_buckets)
        
        # 2.2 编码带噪声的动作
        timesteps_tensor = torch.full(
            size=(batch_size,), 
            fill_value=t_discretized, 
            device=device
        )
        action_features = self.action_encoder(actions, timesteps_tensor, embodiment_id)
        # [B, action_horizon, 512]
        
        # 2.3 添加位置编码
        if self.config.add_pos_embed:
            pos_ids = torch.arange(action_features.shape[1], dtype=torch.long, device=device)
            pos_embs = self.position_embedding(pos_ids).unsqueeze(0)
            action_features = action_features + pos_embs
        
        # 2.4 拼接状态和动作特征
        sa_embs = torch.cat((state_features, action_features), dim=1)
        # [B, 1 + action_horizon, 512]
        
        # 2.5 DiT 前向传播
        if self.config.use_alternate_vl_dit:
            model_output = self.model(
                hidden_states=sa_embs,
                encoder_hidden_states=backbone_features,  # VL features
                timestep=timesteps_tensor,
                image_mask=backbone_output.image_mask,
                backbone_attention_mask=backbone_output.backbone_attention_mask,
            )
        else:
            model_output = self.model(
                hidden_states=sa_embs,
                encoder_hidden_states=backbone_features,
                timestep=timesteps_tensor,
            )
        # model_output: [B, 1 + action_horizon, 512]
        
        # 2.6 解码预测的速度场
        pred = self.action_decoder(model_output, embodiment_id)
        pred_velocity = pred[:, -self.action_horizon:]  # [B, 16, 23]
        
        # 2.7 欧拉积分更新动作
        actions = actions + dt * pred_velocity
        # actions 从纯噪声逐步去噪到真实动作
    
    # Step 3: 返回最终去噪后的动作
    return {
        "action_pred": actions,  # [B, 16, 23]
        "backbone_features": backbone_features,
        "state_features": state_features,
    }
```

### 3.3 核心模块详解

#### 3.3.1 Qwen3Backbone

```python
# 基于 Qwen3-VL 或 Cosmos-Reason2
class Qwen3Backbone(nn.Module):
    def __init__(self, model_name="nvidia/Cosmos-Reason2-2B", ...):
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(model_name)
        
        # 只使用前 select_layer 层 (例如 -1 表示倒数第1层)
        while len(self.model.language_model.layers) > select_layer:
            self.model.language_model.layers.pop(-1)
    
    def forward(self, inputs):
        # inputs: {
        #   "input_ids": [B, seq_len],
        #   "pixel_values": [B, n_images, C, H, W],
        #   ...
        # }
        
        outputs = self.model.language_model(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            pixel_values=inputs["pixel_values"],
            image_grid_thw=inputs["image_grid_thw"],
            ...
        )
        
        # 提取最后一层隐藏状态
        hidden_states = outputs.hidden_states[-1]  # [B, seq_len, 3584]
        
        return {
            "backbone_features": hidden_states,
            "backbone_attention_mask": inputs["attention_mask"],
            "image_mask": ...,
        }
```

**输入处理**:
- **图像**: 3个视角 (head, left_wrist, right_wrist)，每个 [H, W, 3]
  - Resize 到 Qwen3-VL 要求的尺寸
  - 归一化: `(pixel - mean) / std`
  - 转换为 grid 格式: `[n_images, C, H, W]`

- **语言**: "turn on the radio"
  - Tokenize: `[BOS, token1, token2, ..., EOS]`
  - 转换为 `input_ids`

- **视觉-语言融合**: Qwen3-VL 内部将图像和文本 token 交错排列
  ```
  [BOS, IMG1_START, img1_tokens..., IMG1_END, 
   IMG2_START, img2_tokens..., IMG2_END,
   IMG3_START, img3_tokens..., IMG3_END,
   text_token1, text_token2, ..., EOS]
  ```

**输出**: VL Features `[B, seq_len, 3584]`
- `seq_len` ≈ 图像 tokens + 文本 tokens ≈ 500-1000
- 每个 token 包含视觉或语言的语义信息

#### 3.3.2 DiT (Diffusion Transformer)

```python
# AlternateVLDiT: 交替自注意力和交叉注意力
class AlternateVLDiT(nn.Module):
    def __init__(
        self,
        num_layers=24,
        hidden_size=512,
        num_attention_heads=16,
        cross_attention_dim=3584,
        ...
    ):
        self.transformer_blocks = nn.ModuleList([
            BasicTransformerBlock(
                dim=hidden_size,
                num_attention_heads=num_attention_heads,
                cross_attention_dim=cross_attention_dim,
                attention_bias=False,
            )
            for _ in range(num_layers)
        ])
    
    def forward(
        self, 
        hidden_states,           # [B, 1+action_horizon, 512] 状态+动作
        encoder_hidden_states,   # [B, seq_len, 3584] VL features
        timestep,                # [B] 当前去噪步数
        ...
    ):
        # Embed timestep
        temb = self.time_encoder(timestep)  # [B, 512]
        
        # 逐层传播
        for block in self.transformer_blocks:
            # Self-attention: 动作序列内部注意力
            hidden_states = block.attn1(
                hidden_states, 
                temb=temb
            )
            
            # Cross-attention: 动作 attend to VL features
            hidden_states = block.attn2(
                hidden_states,
                encoder_hidden_states=encoder_hidden_states,
                temb=temb
            )
            
            # Feed-forward
            hidden_states = block.ff(hidden_states)
        
        return hidden_states  # [B, 1+action_horizon, 512]
```

**关键机制**:
1. **Self-Attention**: 动作序列中不同时间步之间的依赖关系
2. **Cross-Attention**: 动作序列 attend to 视觉-语言特征
3. **Timestep Conditioning**: 时间步编码影响去噪过程

#### 3.3.3 Flow Matching

传统 Diffusion (DDPM) vs. Flow Matching:

```python
# DDPM: 需要学习噪声
# x_t = sqrt(alpha_t) * x_0 + sqrt(1 - alpha_t) * epsilon
# 预测: epsilon_pred = model(x_t, t)

# Flow Matching: 学习速度场
# x_t = (1 - t) * noise + t * x_0
# 预测: v_pred = model(x_t, t)
# 更新: x_{t+dt} = x_t + dt * v_pred

# 优势:
# - 更简单的训练目标
# - 更好的样本质量
# - 更快的采样速度
```

**训练时**:
```python
# 采样时间步 t ~ Beta(alpha, beta)
t = self.beta_dist.sample([batch_size])  # [B]

# 插值: noise → action
noisy_action = (1 - t) * noise + t * action_gt

# 计算真实速度场
velocity_gt = action_gt - noise

# 模型预测速度场
velocity_pred = model(noisy_action, t, vl_features)

# Loss
loss = MSE(velocity_pred, velocity_gt)
```

**推理时**:
```python
# 从纯噪声开始
action = randn(B, action_horizon, action_dim)

# 逐步去噪
for t in range(num_inference_timesteps):
    velocity_pred = model(action, t, vl_features)
    action = action + dt * velocity_pred

# 最终 action 收敛到真实动作分布
```

## 4. 动作空间映射

### 4.1 R1Pro 动作配置

```python
# examples/b1k/r1pro.py

# State 分组 (从 61 维 proprio)
state_groups = {
    "base_qvel": [0:3],      # 基座速度
    "left_arm": [3:10],      # 左臂关节位置 (7)
    "left_gripper": [24:26], # 左抓手 (2)
    "right_arm": [28:35],    # 右臂关节位置 (7)
    "right_gripper": [49:51], # 右抓手 (2)
    "torso": [53:57],        # 躯干 (4)
}

# Action 分组 (输出 23 维)
action_groups = {
    "base": [0:3],           # 基座速度指令 (absolute)
    "torso": [3:7],          # 躯干目标 (relative to state.torso)
    "left_arm": [7:14],      # 左臂目标 (relative to state.left_arm)
    "left_gripper": [14:15], # 左抓手指令 (absolute)
    "right_arm": [15:22],    # 右臂目标 (relative to state.right_arm)
    "right_gripper": [22:23], # 右抓手指令 (absolute)
}

# Action Representation
action_configs = [
    ActionConfig(rep=ABSOLUTE, type=NON_EEF),  # base
    ActionConfig(rep=RELATIVE, type=NON_EEF, state_key="torso"),  # torso
    ActionConfig(rep=RELATIVE, type=NON_EEF, state_key="left_arm"),  # left_arm
    ActionConfig(rep=ABSOLUTE, type=NON_EEF, is_gripper=True),  # left_gripper
    ActionConfig(rep=RELATIVE, type=NON_EEF, state_key="right_arm"),  # right_arm
    ActionConfig(rep=ABSOLUTE, type=NON_EEF, is_gripper=True),  # right_gripper
]
```

### 4.2 Relative Action 转换

```python
# Processor.decode_action() 将归一化的 relative action 转换为 absolute

# 例如，left_arm 的转换:
normalized_left_arm = model_output["left_arm"]  # [B, 16, 7], 范围 [-1, 1]

# 1. 反归一化到物理单位 (弧度)
delta_left_arm = unnormalize(normalized_left_arm, 
                              min=-0.5, max=0.5)  # [B, 16, 7]

# 2. 加上当前状态
current_left_arm = state["left_arm"][:, 0, :]  # [B, 7]
absolute_left_arm = current_left_arm[:, None, :] + delta_left_arm  # [B, 16, 7]

# 3. OmniGibson 执行第一步
action_to_execute = absolute_left_arm[:, 0, :]  # [B, 7]
```

**为什么使用 Relative Action?**
- **更容易学习**: 大部分情况下机器人只需要小幅调整
- **更安全**: 避免突然的大幅跳跃
- **更鲁棒**: 对初始状态的小扰动不敏感

## 5. 与 BEHAVIOR-1K 的集成

### 5.1 WebSocket Server 启动

你的 `turning_on_radio.sh` 脚本：

```bash
#!/bin/bash

# 1. 启动 GR00T policy server
python -m gr00t.eval.run_gr00t_server \
  --model-path /path/to/checkpoint \
  --embodiment-tag new_embodiment \
  --modality-config-path examples/b1k/r1pro.py \
  --device cuda \
  --host 127.0.0.1 \
  --port 8000 &

# 2. 等待 server 启动
sleep 30

# 3. 启动 OmniGibson evaluator
python -m omnigibson.eval.eval \
  --activity turning_on_radio \
  --mode public_test \
  --instance-indices 301 \
  --policy websocket \
  --policy-config '{"host": "127.0.0.1", "port": 8000}' \
  --video
```

**Server 初始化**:
```python
# gr00t/eval/run_gr00t_server.py

# 1. 创建 Policy
policy = Gr00tPolicy(
    embodiment_tag=EmbodimentTag.NEW_EMBODIMENT,
    model_path=model_path,
    device="cuda",
)

# 2. 包装为 WebSocket Server
server = WebsocketPolicyServer(
    policy=policy,
    host="127.0.0.1",
    port=8000,
)

# 3. 启动异步服务
server.serve_forever()
```

### 5.2 完整执行循环

```python
# OmniGibson Evaluator 主循环

for episode in range(num_episodes):
    obs = env.reset()  # 重置环境
    done = False
    step = 0
    
    while not done and step < max_steps:
        # 1. 获取动作 (通过 WebSocket)
        action = policy.get_action(obs)
        # WebSocket 内部:
        #   - 打包观察 → MessagePack
        #   - 发送到 GR00T server
        #   - 等待动作返回
        #   - 解包动作
        
        # 2. 执行动作
        obs, reward, done, info = env.step(action)
        
        # 3. 记录 video (如果启用)
        if video_writer:
            frame = env.render()
            video_writer.write(frame)
        
        step += 1
    
    # 4. 保存 metrics
    metrics = env.get_metrics()
    save_json(metrics, f"turning_on_radio_301_0.json")
```

## 6. 性能分析

### 6.1 时间分解 (你的执行日志)

```
总执行时间: ~20 minutes
总步数: 3225 steps
平均每步: ~0.37 seconds

分解:
├── WebSocket 通信: ~20ms (5%)
│   ├── 序列化观察: ~5ms
│   ├── 网络传输: ~5ms
│   └── 反序列化动作: ~5ms
│
├── GR00T 推理: ~150ms (41%)
│   ├── 数据预处理: ~10ms
│   ├── Qwen3 Backbone: ~50ms
│   │   ├── Vision Encoding: ~30ms
│   │   └── Language Encoding: ~20ms
│   ├── DiT Forward (10 steps): ~80ms
│   │   └── 每步: ~8ms
│   └── Action Decoding: ~10ms
│
└── OmniGibson 模拟: ~200ms (54%)
    ├── 物理步进: ~120ms
    ├── 渲染 (video): ~60ms
    └── 观察生成: ~20ms
```

### 6.2 瓶颈与优化

**当前瓶颈**: OmniGibson 模拟 (54%)

**优化方向**:

1. **Policy 推理优化** (150ms → ~75ms):
   ```python
   # TensorRT 优化
   # - DiT: 80ms → 40ms (50% 加速)
   # - Backbone: 50ms → 25ms (50% 加速)
   
   # 总加速: 150ms → 75ms
   ```

2. **降低视频分辨率** (60ms → 30ms):
   ```python
   sensor_config = {
       "VisionSensor": {
           "image_height": 128,  # 从 256 降到 128
           "image_width": 128,
       }
   }
   ```

3. **Action Repeat** (减少 policy 调用):
   ```python
   action_repeat = 2  # 每个 action 执行 2 步
   # 理论加速: 2x
   ```

## 7. 常见问题

### 7.1 为什么 metrics 输出没有 "feedback"？

**答案**: "feedback" 是 **BDDL 任务初始化的诊断信息**，不是性能指标。

```python
# Feedback 来源: BehaviorTask.initialize_activity()
feedback = env.task.initialize_activity(env)
# {
#   "compilation_error": ...,
#   "object_assignment": ...,
#   "warning": ...,
# }

# Feedback 只记录到日志，不保存到 metrics JSON
if feedback:
    log.warning(f"Task initialization feedback: {feedback}")

# Metrics 来源: MetricsWrapper
metrics = {
    "q_score": {...},
    "time": {...},
    "agent_distance": {...},
}
# Metrics 保存到 JSON 文件
```

**区别**:
- **Feedback**: 任务初始化阶段，调试用
- **Metrics**: 整个 episode，评估用

### 7.2 模型输出16步动作，为什么只用第1步？

**Action Chunking + Receding Horizon**:

```python
# 模型输出: [B, 16, 23]
# 执行: action[0]  # 只用第1步

# 优势:
# 1. 更流畅: 考虑未来16步的规划
# 2. 更鲁棒: 每步重新规划，响应环境变化
# 3. 更稳定: 避免短视的贪心策略
```

**可选: Receding Horizon with Overlap (RTC)**:
```python
# 第 t 步: 预测 action[t:t+16]
# 第 t+1 步: 预测 action[t+1:t+17]
# 重叠部分: action[t+1:t+16] 作为 warm start
```

### 7.3 如何提高 q_score?

你的结果: `q_score = 0.0` (任务未完成)

**诊断步骤**:

1. **观看视频**:
   ```bash
   vlc eval_logs/turning_on_radio/videos/turning_on_radio_301_0.mp4
   ```
   - 机器人是否移动到收音机附近？
   - 是否尝试抓取或操作？

2. **检查 checkpoint 质量**:
   ```python
   # 你的 checkpoint: 150k steps
   # 可能需要更多训练 (200k-300k steps)
   ```

3. **Fine-tune on this activity**:
   ```bash
   # 在 turning_on_radio 数据上继续训练
   python launch_finetune.py \
     --model-path checkpoint-150000 \
     --dataset turning_on_radio \
     --num-steps 50000
   ```

4. **调整超参数**:
   ```python
   # 增加 num_inference_timesteps
   num_inference_timesteps = 20  # 从 10 增加到 20
   # 可能提高动作质量，但推理变慢
   ```

## 8. 总结

### 8.1 GR00T 核心创新

1. **统一 VLA 架构**: 视觉、语言、动作一体化
2. **Flow Matching**: 比 DDPM 更高效的 diffusion
3. **Multi-Embodiment**: 单一模型支持多种机器人
4. **Action Chunking**: 预测16步提高流畅性

### 8.2 数据流总结

```
图像 (3视角) ─┐
             ├─→ Qwen3 Backbone ─→ VL Features ─┐
语言指令 ─────┘                                │
                                               ├─→ DiT ─→ Action Trajectory
状态 (61维) ───→ State Encoder ─→ State Features ┘       (16步, 23维)
                                                              │
                                                              ↓
                                                         第1步动作 (23维)
                                                              ↓
                                                       OmniGibson 执行
```

### 8.3 与你的系统对应

- **OmniGibson**: 提供物理仿真和观察
- **WebSocket**: 实现客户端-服务器通信
- **GR00T Policy**: VLA模型推理
- **MessagePack**: 高效二进制序列化
- **R1Pro Config**: 定义状态/动作映射

这个完整的流程让你的系统能够：
1. 从仿真中获取多模态观察
2. 通过网络发送到 GPU 服务器
3. GR00T 模型理解任务并生成动作
4. 返回动作并在仿真中执行
5. 循环直到任务完成或超时
