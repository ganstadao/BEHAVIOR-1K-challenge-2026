# OpenPI-Comet 评估完整流程说明

## 🔍 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    评估系统架构                                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. SLURM 提交脚本                                            │
│     └─> submit_eval_advanced.sh                              │
│                  │                                            │
│                  v                                            │
│  2. 评估运行器                                                │
│     └─> eval_runner.py                                       │
│          ├─> 启动 Policy Server (openpi-comet)               │
│          ├─> 启动 OmniGibson Evaluator                       │
│          └─> 收集和保存结果                                   │
│                                                               │
│  3. Policy Server (端口 8000)                                │
│     └─> openpi-comet/scripts/serve_b1k.py                   │
│          └─> 加载 pt50 checkpoint                            │
│          └─> 提供 WebSocket 接口                             │
│                                                               │
│  4. OmniGibson Evaluator                                     │
│     └─> omnigibson.eval.eval                                 │
│          ├─> 创建仿真环境                                     │
│          ├─> 通过 WebSocket 请求 action                      │
│          ├─> 执行 action 并更新状态                          │
│          └─> 检查任务完成条件                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 📋 详细流程步骤

### 步骤 1: 提交评估作业

```bash
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_test
```

**发生了什么：**
1. SLURM 在 GPU 节点上启动作业
2. 脚本调用：`python tools/eval_runner.py --preset comet_pt50_turning_on_radio --run-name pt50_test`

### 步骤 2: 加载配置

**eval_runner.py 执行：**

```python
# 1. 加载配置文件
config = load_config('configs/comet_pt50_turning_on_radio.yaml')

# 配置内容：
config = {
    'policy': {
        'type': 'pi0.5-comet',  # 类型标识
        'openpi_dir': '~/LINJ0121/openpi-comet',  # comet 项目路径
        'checkpoint': '~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt50-cs32',
        'dataset_root': '/scr/behavior/2025-challenge-demos',
        'task_name': 'turning_on_radio',
        'port': 8000,
    },
    'task': {
        'name': 'turning_on_radio',
        'max_steps': None,  # 不限制
    }
}
```

### 步骤 3: 准备输出目录

```python
# 创建输出目录
output_dir = eval_logs/pi0.5-comet/turning_on_radio/20241006_143022_pt50_test/
    ├── logs/
    ├── json/
    └── videos/
```

### 步骤 4: 启动 Policy Server

**4.1 构建启动命令**

```python
# eval_runner.py 中的 _build_pi05_server_cmd()
cmd = [
    '~/LINJ0121/openpi-comet/.venv/bin/python',
    '~/LINJ0121/openpi-comet/scripts/serve_b1k.py',
    '--policy.config', 'pi05_b1k',
    '--policy.dir', '~/LINJ0121/checkpoint/pi05-comet-pt50/pi05-b1kpt50-cs32',
    '--port', '8000',
    '--dataset_root', '/scr/behavior/2025-challenge-demos',
    '--task_name', 'turning_on_radio',
    '--record',  # 如果启用 logging.record_policy
]
```

**4.2 启动进程**

```bash
# 后台启动 policy server
CUDA_VISIBLE_DEVICES=0 \
XLA_PYTHON_CLIENT_MEM_FRACTION=0.85 \
python serve_b1k.py ... > policy_server.log 2>&1 &
```

**4.3 Policy Server 做什么**

```python
# openpi-comet/scripts/serve_b1k.py
1. 加载 checkpoint: pi05-b1kpt50-cs32/params/
2. 初始化 JAX 模型
3. 从 dataset_root 读取任务的 prompt/示例
4. 启动 WebSocket 服务器在 127.0.0.1:8000
5. 等待接收 observation 并返回 action
```

### 步骤 5: 等待 Policy Server 就绪

```python
# eval_runner.py 中的 _wait_for_server()
for i in range(100):  # 最多等待 300 秒
    try:
        response = curl('http://127.0.0.1:8000/healthz')
        if response.ok:
            break  # Server 就绪
    except:
        time.sleep(3)
```

### 步骤 6: 启动 OmniGibson Evaluator

**6.1 构建评估命令**

```python
cmd = [
    '~/.conda/envs/behavior/bin/python',
    '-m', 'omnigibson.eval.eval',
    '--task-name', 'turning_on_radio',
    '--host', '127.0.0.1',
    '--port', '8000',
    '--output-dir', 'eval_logs/pi0.5-comet/turning_on_radio/20241006_143022_pt50_test/',
    '--write-video',
    '--env-wrapper', 'omnigibson.eval.wrappers.RGBDFullResWrapper',
]
```

**6.2 OmniGibson Evaluator 做什么**

```python
# omnigibson/eval/eval.py
1. 加载场景和任务定义 (BDDL)
2. 初始化机器人
3. 创建环境
4. 连接到 Policy Server (WebSocket)

# 评估循环
for step in range(max_steps or infinity):
    # 1. 获取观察
    obs = env.get_observation()
    # obs 包含: RGB, depth, robot_state, etc.
    
    # 2. 发送到 Policy Server
    action = policy_client.get_action(obs)
    # 通过 WebSocket 发送 obs, 接收 action
    
    # 3. 执行动作
    obs, reward, done, info = env.step(action)
    # 物理仿真更新，机器人移动
    
    # 4. 检查任务完成
    if task.check_success():
        break
    
    # 5. 记录视频帧
    if write_video:
        video_writer.write_frame(obs['rgb'])

# 保存结果
save_json(result, 'json/turning_on_radio_301_0.json')
save_video('videos/turning_on_radio_301_0.mp4')
```

### 步骤 7: 评估循环详解

```
┌─────────────────────────────────────────────────┐
│           单步评估循环                            │
├─────────────────────────────────────────────────┤
│                                                   │
│  OmniGibson Environment                          │
│  ┌──────────────────┐                           │
│  │ 1. 获取观察      │                           │
│  │    - RGB 图像    │                           │
│  │    - Depth       │                           │
│  │    - Robot state │                           │
│  └────────┬─────────┘                           │
│           │                                      │
│           v                                      │
│  ┌──────────────────┐                           │
│  │ 2. 发送到 Policy │ ─────> WebSocket          │
│  └────────┬─────────┘        (127.0.0.1:8000)  │
│           │                          │           │
│           │    Policy Server         │           │
│           │    ┌──────────────┐     │           │
│           │    │ pt50 Model   │<────┘           │
│           │    │ 推理 Action  │                 │
│           │    └──────┬───────┘                 │
│           │           │                          │
│           v           v                          │
│  ┌──────────────────┐                           │
│  │ 3. 接收 Action   │<────── WebSocket          │
│  └────────┬─────────┘                           │
│           │                                      │
│           v                                      │
│  ┌──────────────────┐                           │
│  │ 4. 执行 Action   │                           │
│  │    - 移动机器人  │                           │
│  │    - 物理模拟    │                           │
│  └────────┬─────────┘                           │
│           │                                      │
│           v                                      │
│  ┌──────────────────┐                           │
│  │ 5. 检查成功条件  │                           │
│  │    - BDDL 验证   │                           │
│  └────────┬─────────┘                           │
│           │                                      │
│           v                                      │
│        done? ─── Yes ──> 保存结果               │
│           │                                      │
│           No                                     │
│           │                                      │
│           └───────> 下一步                       │
│                                                   │
└─────────────────────────────────────────────────┘
```

### 步骤 8: 保存结果

```python
# 生成的文件
output_dir/
├── config.yaml              # 本次运行的配置
├── summary.yaml             # 运行总结
├── logs/
│   ├── policy_server.log    # Policy server 日志
│   └── omnigibson_eval.log  # OmniGibson 日志
├── json/
│   └── turning_on_radio_301_0.json  # 评估结果
│       {
│         "success": true/false,
│         "num_steps": 234,
│         "satisfied_predicates": [...],
│         "unsatisfied_predicates": [...]
│       }
└── videos/
    └── turning_on_radio_301_0.mp4   # 评估视频
```

### 步骤 9: 清理

```python
# eval_runner.py
1. 停止 policy server (kill PID)
2. 关闭 OmniGibson 环境
3. 生成 summary.yaml
4. 退出
```

## 🔧 关键组件详解

### OpenPI-Comet Checkpoint 结构

```
pi05-b1kpt50-cs32/
├── params/                  # 模型参数（JAX format）
│   ├── chunk_0/
│   ├── chunk_1/
│   └── ...
├── assets/                  # 元数据
└── _CHECKPOINT_METADATA     # Checkpoint 信息
```

### Policy Server 内部

```python
# openpi-comet/scripts/serve_b1k.py
class PolicyServer:
    def __init__(self, checkpoint_dir):
        # 1. 加载 checkpoint
        self.model = load_checkpoint(checkpoint_dir)
        
        # 2. 加载任务 prompt
        self.task_prompt = load_task_prompt(task_name, dataset_root)
        
    def get_action(self, observation):
        # 1. 预处理观察
        obs_tensor = preprocess(observation)
        
        # 2. 模型推理
        action = self.model.predict(obs_tensor, self.task_prompt)
        
        # 3. 后处理
        action = postprocess(action)
        
        return action
```

### WebSocket 通信协议

```python
# Client (OmniGibson) → Server (Policy)
{
    "observation": {
        "rgb": np.array([H, W, 3]),
        "depth": np.array([H, W]),
        "robot_state": {...}
    }
}

# Server (Policy) → Client (OmniGibson)
{
    "action": np.array([action_dim])  # 机器人动作
}
```

## 🐛 常见错误和解决方案

### 错误 1: ValueError: Unknown policy type: pi0.5-comet

**原因**: `eval_runner.py` 不识别 `pi0.5-comet` 类型

**解决**: 已修复！现在支持任何包含 'pi0.5' 的类型

### 错误 2: Policy server 启动失败

**检查**:
```bash
cat eval_logs/pi0.5-comet/turning_on_radio/*/logs/policy_server.log
```

**常见原因**:
- Checkpoint 路径错误
- Python 环境不对
- GPU 内存不足

### 错误 3: dataset_root 路径不存在

**检查**:
```bash
ls /scr/behavior/2025-challenge-demos
```

**解决**: 如果路径不存在，可以省略或修改
```yaml
policy:
  # 注释掉或修改路径
  # dataset_root: /scr/behavior/2025-challenge-demos
```

### 错误 4: 端口被占用

**检查**:
```bash
lsof -i :8000
```

**解决**:
```bash
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio test \
    --set policy.port=8001
```

## 📊 监控运行状态

### 查看作业状态
```bash
squeue -u $USER
```

### 实时查看日志
```bash
# SLURM 输出
tail -f logs/eval_<job_id>.out

# Policy Server 日志
tail -f eval_logs/pi0.5-comet/turning_on_radio/*/logs/policy_server.log

# OmniGibson 日志
tail -f eval_logs/pi0.5-comet/turning_on_radio/*/logs/omnigibson_eval.log
```

### 检查 Policy Server 是否运行
```bash
# 查看进程
ps aux | grep serve_b1k.py

# 检查端口
curl http://127.0.0.1:8000/healthz
```

## 🎯 完整示例

```bash
# 1. 提交作业
sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_test

# 2. 查看作业（假设 job_id=40177）
squeue -j 40177

# 3. 查看日志
tail -f logs/eval_40177.out

# 4. 等待完成（可能需要几小时）

# 5. 分析结果
bash tools/analyze_results.sh latest pi0.5-comet turning_on_radio

# 6. 查看详细结果
cat eval_logs/pi0.5-comet/turning_on_radio/*/json/*.json | jq '.'

# 7. 播放视频
mpv eval_logs/pi0.5-comet/turning_on_radio/*/videos/*.mp4
```

## 💡 优化建议

1. **快速测试**: 先限制步数
   ```bash
   --set task.max_steps=100
   ```

2. **禁用视频**: 加快速度
   ```bash
   --set task.write_video=false
   ```

3. **降低日志级别**: 减少磁盘 I/O
   ```bash
   --set logging.policy_log_level=WARNING
   ```

4. **批量评估**: 一次提交多个任务
   ```bash
   bash tools/submit_batch.sh comet_pt50_turning_on_radio baseline task1 task2
   ```

---

**立即开始**: `sbatch tools/submit_eval_advanced.sh comet_pt50_turning_on_radio pt50_test`
