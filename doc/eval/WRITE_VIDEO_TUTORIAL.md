# OmniGibson write-video 功能详解与使用教程

本文档详细讲解 `omnigibson.eval.eval` 中 `--write-video` 参数的内部实现原理以及灵活使用方法。

## 1. 功能概览

### 1.1 什么是 write-video？

`--write-video` 是 OmniGibson evaluation 系统的一个功能，用于在执行任务评估时**自动录制机器人的多视角视频**，并保存为 MP4 文件。

**核心特点**:
- **多视角合成**: 自动拼接头部、左手腕、右手腕三个相机视角
- **实时录制**: 在 rollout 执行过程中逐帧写入
- **高效编码**: 使用 PyAV (FFmpeg) 和 H.264 编码
- **自动清理**: 录制失败时自动关闭文件

### 1.2 视频布局

```
+-------------------------+
|  Left    |             |
|  Wrist   |             |
| (224x224)|    Head     |
|----------|  (448x448)  |
|  Right   |             |
|  Wrist   |             |
| (224x224)|             |
+-------------------------+
    最终分辨率: 672x448
```

## 2. 内部实现原理

### 2.1 完整数据流

```
Episode 执行
    ↓
每一步 (step)
    ↓
获取观察 (obs)
    ├─ robot_r1::robot_r1:zed_link:Camera:0::rgb          [H, W, 3]
    ├─ robot_r1::robot_r1:left_realsense_link:Camera:0::rgb
    └─ robot_r1::robot_r1:right_realsense_link:Camera:0::rgb
    ↓
Evaluator._write_video()
    ├─ 提取三个相机图像
    ├─ Resize 到指定尺寸
    │   ├─ left_wrist:  224x224
    │   ├─ right_wrist: 224x224
    │   └─ head:        448x448
    ├─ 拼接成一帧 [448, 672, 3]
    └─ 写入视频文件
    ↓
write_video()
    ├─ 转换为 av.VideoFrame (RGB24)
    ├─ 编码 (H.264)
    └─ 写入容器 (MP4)
```

### 2.2 核心代码解析

#### 2.2.1 Evaluator 中的视频录制

```python
# omnigibson/eval/evaluator.py

class Evaluator:
    def __init__(self, cfg):
        # ...
        self._video_writer = None    # (container, stream) 元组
        self._video_path = None      # 视频文件路径
        self._video_rate = 30        # 帧率 (默认 30 FPS)
    
    def start_recording(self, fpath: str, rate: int = 30) -> None:
        """
        开始录制视频
        
        Args:
            fpath: 视频文件路径 (e.g., "output/video.mp4")
            rate: 帧率 (默认 30 FPS)
        """
        # 1. 关闭之前的录制（如果有）
        self.video_writer = None
        
        # 2. 保存参数（实际的 writer 在第一帧时创建）
        self._video_path = fpath
        self._video_rate = rate
    
    def stop_recording(self) -> None:
        """停止录制并关闭文件"""
        # 设置为 None 会触发 setter，自动关闭文件
        self.video_writer = None
        self._video_path = None
    
    @property
    def video_writer(self) -> Tuple[Container, Stream]:
        """获取 video writer"""
        return self._video_writer
    
    @video_writer.setter
    def video_writer(self, video_writer: Tuple[Container, Stream]) -> None:
        """
        设置 video writer，自动关闭旧的
        
        重要: 这个 setter 实现了自动清理机制
        """
        if self._video_writer is not None:
            # 关闭旧的 writer
            container, stream = self._video_writer
            # 1. Flush 编码器（输出缓冲区中的剩余帧）
            for packet in stream.encode():
                container.mux(packet)
            # 2. 关闭容器（写入文件头、尾）
            container.close()
        
        # 设置新的 writer
        self._video_writer = video_writer
    
    def _write_video(self) -> None:
        """
        每一步调用，写入一帧视频
        
        在 Evaluator.step() 中自动调用
        """
        # Step 0: 检查必要的相机
        required_camera_ids = ("left_wrist", "right_wrist", "head")
        if not all(camera_id in self.robot_camera_names for camera_id in required_camera_ids):
            return  # 缺少必要相机，跳过
        
        if self.robot_camera_names["head"] + "::rgb" not in self.obs:
            return  # 没有 RGB 观察，跳过
        
        # Step 1: 提取并 resize 相机图像
        left_wrist_rgb = cv2.resize(
            self.obs[self.robot_camera_names["left_wrist"] + "::rgb"].numpy(),
            (224, 224),  # 目标尺寸
        )
        right_wrist_rgb = cv2.resize(
            self.obs[self.robot_camera_names["right_wrist"] + "::rgb"].numpy(),
            (224, 224),
        )
        head_rgb = cv2.resize(
            self.obs[self.robot_camera_names["head"] + "::rgb"].numpy(),
            (448, 448),
        )
        
        # Step 2: 拼接图像
        # left_wrist 和 right_wrist 垂直堆叠 [448, 224, 3]
        wrist_stack = np.vstack([left_wrist_rgb, right_wrist_rgb])
        # 与 head 水平拼接 [448, 672, 3]
        composite_frame = np.hstack([wrist_stack, head_rgb])
        
        # Step 3: 添加 batch 维度 [1, 448, 672, 3]
        frame = np.expand_dims(composite_frame, 0)
        
        # Step 4: 创建 video writer（懒加载，第一帧时创建）
        if self._video_writer is None:
            # 根据实际帧尺寸创建 writer
            self.video_writer = create_video_writer(
                self._video_path,
                resolution=frame.shape[1:3],  # (H, W) = (448, 672)
                rate=self._video_rate,        # FPS
            )
        
        # Step 5: 写入这一帧
        write_video(
            frame,                        # [1, H, W, 3]
            video_writer=self.video_writer,
            batch_size=1,
            mode="rgb"
        )
    
    def step(self) -> Tuple[bool, bool]:
        """执行一步并录制视频"""
        # ... 执行动作、获取观察 ...
        
        # 录制视频（如果启用）
        if self._video_path is not None:
            self._write_video()
        
        return terminated, truncated
```

#### 2.2.2 create_video_writer()

```python
# omnigibson/eval/utils/obs_utils.py

def create_video_writer(
    fpath,                          # 视频文件路径
    resolution,                     # (height, width) 分辨率
    codec_name="libx264",           # 编码器
    rate=30,                        # 帧率
    pix_fmt="yuv420p",              # 像素格式
    stream_options=None,            # 流选项
    context_options=None,           # 上下文选项
) -> Tuple[Container, Stream]:
    """
    使用 PyAV 创建视频写入器
    
    Returns:
        (container, stream): PyAV 容器和流对象
    """
    # Step 1: 验证文件扩展名
    assert fpath.endswith(".mp4") or fpath.endswith(".mkv"), \
        f"Video writer fpath must end with .mp4 or .mkv! Got: {fpath}"
    
    # Step 2: 创建容器（文件）
    container = av.open(fpath, mode="w")
    
    # Step 3: 添加视频流
    stream = container.add_stream(codec_name, rate=rate)
    # codec_name="libx264" -> H.264 编码
    # rate=30 -> 30 FPS
    
    # Step 4: 设置流参数
    stream.height = resolution[0]     # 448
    stream.width = resolution[1]      # 672
    stream.pix_fmt = pix_fmt          # "yuv420p" (常用格式)
    
    # Step 5: 可选参数
    if stream_options is not None:
        stream.options = stream_options
    if context_options is not None:
        stream.codec_context.options = context_options
    
    return container, stream
```

**PyAV 架构**:
```
av.Container (文件容器)
    └─ av.Stream (视频流)
        ├─ codec: libx264 (H.264)
        ├─ pix_fmt: yuv420p
        ├─ rate: 30 FPS
        └─ resolution: 448x672
```

#### 2.2.3 write_video()

```python
def write_video(
    obs,                # 观察数据 [N, H, W, 3]
    video_writer,       # (container, stream) 元组
    mode="rgb",         # 模式: "rgb", "depth", "seg"
    batch_size=None,    # 批量大小
    **kwargs
) -> None:
    """
    将观察数据写入视频
    
    Args:
        obs: [N, H, W, 3] numpy array
        video_writer: (container, stream) 来自 create_video_writer()
        mode: "rgb" (彩色), "depth" (深度), "seg" (语义分割)
        batch_size: 批量写入大小（减少内存占用）
    """
    container, stream = video_writer
    batch_size = batch_size or obs.shape[0]
    
    if mode == "rgb":
        # RGB 模式（最常用）
        for i in range(0, obs.shape[0], batch_size):
            batch = obs[i : i + batch_size]
            
            for frame in batch:
                # Step 1: 创建 PyAV VideoFrame
                # frame: [H, W, 3] numpy array (RGB)
                av_frame = av.VideoFrame.from_ndarray(
                    frame[..., :3],  # 只取前 3 个通道 (RGB)
                    format="rgb24"   # RGB 24-bit 格式
                )
                
                # Step 2: 编码帧
                # H.264 编码器将 RGB 转换为 YUV420p 并压缩
                for packet in stream.encode(av_frame):
                    # Step 3: 写入容器
                    # packet 是压缩后的数据包
                    container.mux(packet)
    
    elif mode == "depth":
        # 深度模式（用于深度相机）
        use_log = kwargs.get("use_log", True)
        for i in range(0, obs.shape[0], batch_size):
            batch = obs[i : i + batch_size]
            
            # 量化深度到 12-bit
            quantized_depth = quantize_depth(batch, use_log=use_log)
            
            for depth in quantized_depth:
                # 编码为 YUV420p12le 格式
                av_frame = encode_depth_frame(depth)
                for packet in stream.encode(av_frame):
                    container.mux(packet)
    
    # ... 其他模式
```

**编码流程**:
```
NumPy Array [H, W, 3]
    ↓
av.VideoFrame (RGB24)
    ↓
H.264 Encoder
    ├─ RGB → YUV420p
    ├─ 运动补偿
    ├─ DCT 变换
    └─ 熵编码
    ↓
Compressed Packet
    ↓
MP4 Container
```

### 2.3 评估脚本中的调用

```python
# omnigibson/eval/eval.py

def main():
    # ... 解析参数 ...
    
    # Step 1: 创建输出目录
    video_dir = os.path.join(args.output_dir, "videos")
    if args.write_video:
        os.makedirs(video_dir, exist_ok=True)
    
    # Step 2: 创建 Evaluator
    with Evaluator(cfg) as evaluator:
        for instance_id in instance_ids:
            # 加载任务实例
            evaluator.load_task_instance(int(instance_id))
            
            for rollout_id in range(args.num_rollouts):
                # Step 3: 构造视频路径
                video_path = os.path.join(
                    video_dir,
                    f"{args.task_name}_{instance_id}_{rollout_id}.mp4"
                )
                # 例如: "turning_on_radio_301_0.mp4"
                
                try:
                    evaluator.reset()
                    
                    # Step 4: 开始录制
                    if args.write_video:
                        evaluator.start_recording(
                            video_path,
                            rate=args.video_fps  # 默认 30
                        )
                    
                    # Step 5: 执行 rollout
                    terminated = truncated = False
                    steps = 0
                    while not (terminated or truncated):
                        terminated, truncated = evaluator.step()
                        # step() 内部会调用 _write_video()
                        steps += 1
                    
                    # ... 计算 metrics ...
                    
                finally:
                    # Step 6: 停止录制（无论成功或失败）
                    if args.write_video:
                        evaluator.stop_recording()
```

## 3. 使用教程

### 3.1 基础使用

#### 命令行参数

```bash
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --mode public_test \
    --instance-indices 301 \
    --host 127.0.0.1 \
    --port 8000 \
    --output-dir outputs/my_eval \
    --write-video \              # 启用视频录制
    --video-fps 30               # 设置帧率 (可选，默认 30)
```

**生成的文件**:
```
outputs/my_eval/
├── videos/
│   └── turning_on_radio_301_0.mp4    # 视频文件
└── json/
    └── turning_on_radio_301_0.json   # 评估结果
```

#### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--write-video` | flag | False | 启用视频录制 |
| `--video-fps` | int | 30 | 视频帧率 |
| `--output-dir` | str | 必需 | 输出目录 |

### 3.2 批量录制

#### 多个实例

```bash
# 录制多个实例
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 301 302 303 \
    --write-video \
    --output-dir outputs/batch_eval

# 生成:
# outputs/batch_eval/videos/
#   ├── turning_on_radio_301_0.mp4
#   ├── turning_on_radio_302_0.mp4
#   └── turning_on_radio_303_0.mp4
```

#### 多次 Rollout

```bash
# 每个实例录制 3 次
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 301 \
    --num-rollouts 3 \
    --write-video \
    --output-dir outputs/multi_rollout

# 生成:
# outputs/multi_rollout/videos/
#   ├── turning_on_radio_301_0.mp4
#   ├── turning_on_radio_301_1.mp4
#   └── turning_on_radio_301_2.mp4
```

### 3.3 自定义帧率

```bash
# 高帧率录制（更流畅）
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 301 \
    --write-video \
    --video-fps 60 \
    --output-dir outputs/high_fps

# 低帧率录制（节省空间）
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 301 \
    --write-video \
    --video-fps 15 \
    --output-dir outputs/low_fps
```

**帧率建议**:
- **15 FPS**: 快速预览，文件小
- **30 FPS**: 标准流畅度（推荐）
- **60 FPS**: 高流畅度，适合演示
- **>60 FPS**: 通常不必要，文件大

### 3.4 在 SLURM 上使用

```bash
#!/bin/bash
#SBATCH --job-name=eval_video
#SBATCH --partition=MGPU-TC2
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --output=logs/eval_video_%j.out

# 启动 policy server
python -m gr00t.eval.run_gr00t_server \
    --model-path /path/to/checkpoint \
    --port 8000 &
SERVER_PID=$!

# 等待服务器就绪
sleep 30

# 评估并录制视频
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 301 302 303 \
    --host 127.0.0.1 \
    --port 8000 \
    --write-video \
    --video-fps 30 \
    --output-dir outputs/eval_$(date +%Y%m%d_%H%M%S)

# 清理
kill $SERVER_PID
```

## 4. 高级用法

### 4.1 自定义视频布局

如果你想自定义视频布局（例如不同的相机组合或尺寸），可以修改 `Evaluator._write_video()`：

```python
# 创建自定义 Evaluator
class MyEvaluator(Evaluator):
    def _write_video(self) -> None:
        """自定义视频布局"""
        # 例如：只录制头部相机，大尺寸
        head_rgb = cv2.resize(
            self.obs[self.robot_camera_names["head"] + "::rgb"].numpy(),
            (1280, 720),  # 720p
        )
        
        frame = np.expand_dims(head_rgb, 0)
        
        if self._video_writer is None:
            self.video_writer = create_video_writer(
                self._video_path,
                resolution=frame.shape[1:3],
                rate=self._video_rate,
            )
        
        write_video(frame, video_writer=self.video_writer, batch_size=1, mode="rgb")
```

### 4.2 录制深度视频

```python
class DepthVideoEvaluator(Evaluator):
    def _write_depth_video(self) -> None:
        """录制深度视频"""
        # 提取深度图像
        head_depth = self.obs[self.robot_camera_names["head"] + "::depth"]
        
        # Resize
        head_depth_resized = cv2.resize(
            head_depth.numpy(),
            (640, 480),
            interpolation=cv2.INTER_NEAREST  # 深度图用最近邻插值
        )
        
        frame = np.expand_dims(head_depth_resized, 0)
        
        if self._depth_video_writer is None:
            # 深度视频需要特殊的像素格式
            self._depth_video_writer = create_video_writer(
                self._depth_video_path,
                resolution=frame.shape[1:3],
                rate=self._video_rate,
                pix_fmt="yuv420p12le",  # 12-bit 用于深度
            )
        
        write_video(
            frame,
            video_writer=self._depth_video_writer,
            batch_size=1,
            mode="depth"
        )
```

### 4.3 添加覆盖信息

使用 OpenCV 在视频帧上添加文本信息：

```python
class AnnotatedVideoEvaluator(Evaluator):
    def _write_video(self) -> None:
        # 获取原始合成帧
        left_wrist_rgb = cv2.resize(
            self.obs[self.robot_camera_names["left_wrist"] + "::rgb"].numpy(),
            (224, 224),
        )
        right_wrist_rgb = cv2.resize(
            self.obs[self.robot_camera_names["right_wrist"] + "::rgb"].numpy(),
            (224, 224),
        )
        head_rgb = cv2.resize(
            self.obs[self.robot_camera_names["head"] + "::rgb"].numpy(),
            (448, 448),
        )
        
        composite_frame = np.hstack([
            np.vstack([left_wrist_rgb, right_wrist_rgb]),
            head_rgb
        ])
        
        # 添加文本覆盖
        # 当前步数
        cv2.putText(
            composite_frame,
            f"Step: {self._current_step}",
            (10, 30),                          # 位置
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,                               # 字体大小
            (255, 255, 255),                   # 白色
            2,                                 # 线宽
            cv2.LINE_AA
        )
        
        # 任务名称
        cv2.putText(
            composite_frame,
            f"Task: {self.cfg.task.name}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )
        
        # q_score (如果有)
        if hasattr(self, '_current_q_score'):
            cv2.putText(
                composite_frame,
                f"Q-Score: {self._current_q_score:.3f}",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),  # 绿色
                2,
                cv2.LINE_AA
            )
        
        frame = np.expand_dims(composite_frame, 0)
        
        # 写入视频
        if self._video_writer is None:
            self.video_writer = create_video_writer(
                self._video_path,
                resolution=frame.shape[1:3],
                rate=self._video_rate,
            )
        
        write_video(frame, video_writer=self.video_writer, batch_size=1, mode="rgb")
```

### 4.4 独立使用 video_utils

你也可以在自己的代码中直接使用 `create_video_writer()` 和 `write_video()`：

```python
import numpy as np
from omnigibson.eval.utils.obs_utils import create_video_writer, write_video

# 创建 video writer
container, stream = create_video_writer(
    fpath="my_video.mp4",
    resolution=(480, 640),  # (H, W)
    rate=30,
)

# 生成一些随机帧
frames = []
for i in range(100):
    # 随机 RGB 图像
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # 添加文本
    import cv2
    cv2.putText(frame, f"Frame {i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    frames.append(frame)

# 批量写入
frames_array = np.array(frames)  # [100, 480, 640, 3]
write_video(frames_array, video_writer=(container, stream), mode="rgb")

# 关闭文件
for packet in stream.encode():
    container.mux(packet)
container.close()

print("Video saved to my_video.mp4")
```

## 5. 常见问题与调试

### 5.1 视频文件损坏

**问题**: 录制过程中程序崩溃，视频文件无法播放

**原因**: 视频文件没有正确关闭（缺少文件尾）

**解决**:
```python
# 使用 try-finally 确保关闭
try:
    evaluator.start_recording("video.mp4")
    # ... 执行 rollout ...
finally:
    evaluator.stop_recording()  # 总是执行
```

### 5.2 视频文件过大

**问题**: 长 episode 生成的视频文件太大

**优化**:
```bash
# 1. 降低帧率
--video-fps 15  # 从 30 降到 15

# 2. 降低分辨率（修改代码）
head_rgb = cv2.resize(obs, (320, 240))  # 从 448x448 降到 320x240

# 3. 使用更高的压缩率
# 在 create_video_writer() 中添加:
context_options = {"crf": "28"}  # CRF 越高，压缩率越高（默认 23）
```

### 5.3 缺少相机观察

**问题**: `_write_video()` 没有输出任何视频

**原因**: 机器人配置中没有必需的相机

**检查**:
```python
# 查看机器人有哪些相机
print("Robot cameras:", robot.sensors.keys())

# 查看观察中有哪些相机
print("Observation keys:", [k for k in obs.keys() if "Camera" in k])

# 必需的相机:
# - head (zed_link:Camera)
# - left_wrist (left_realsense_link:Camera)
# - right_wrist (right_realsense_link:Camera)
```

### 5.4 视频播放卡顿

**问题**: 生成的视频在某些播放器中卡顿

**原因**: 关键帧间隔太大

**解决**:
```python
# 创建 writer 时设置关键帧间隔
stream_options = {
    "g": "30",  # 每 30 帧一个关键帧 (1秒 @ 30 FPS)
}

container, stream = create_video_writer(
    fpath="video.mp4",
    resolution=(448, 672),
    rate=30,
    stream_options=stream_options,
)
```

### 5.5 内存占用过高

**问题**: 录制长视频时内存占用很高

**原因**: 帧数据在内存中累积

**解决**: 使用 batch_size 参数分批写入（已默认实现）

```python
# write_video() 已经支持批量写入
write_video(
    frames,                # [N, H, W, 3]
    video_writer=writer,
    batch_size=10,         # 每次处理 10 帧
    mode="rgb"
)
```

## 6. 性能优化

### 6.1 编码性能

**硬件加速** (如果 GPU 支持):
```python
# 使用 NVENC (NVIDIA GPU 硬件编码)
container, stream = create_video_writer(
    fpath="video.mp4",
    resolution=(448, 672),
    codec_name="h264_nvenc",  # 从 libx264 改为 h264_nvenc
    rate=30,
    context_options={
        "preset": "fast",      # 编码速度
        "rc": "vbr_hq",        # 码率控制
    }
)
```

### 6.2 磁盘 I/O 优化

**使用 SSD**:
```bash
# 写入到 SSD 临时目录
--output-dir /tmp/eval_videos

# 评估完成后移动到最终位置
mv /tmp/eval_videos outputs/
```

### 6.3 并行评估

如果录制多个实例，可以并行执行：

```bash
# 使用 GNU parallel
parallel -j 4 \
    python -m omnigibson.eval.eval \
        --task-name turning_on_radio \
        --instance-indices {} \
        --write-video \
        --output-dir outputs/instance_{} \
    ::: 301 302 303 304

# 合并结果
mkdir -p outputs/all_videos
cp outputs/instance_*/videos/*.mp4 outputs/all_videos/
```

## 7. 总结

### 7.1 关键要点

1. **自动化**: `--write-video` 自动录制多视角视频
2. **高效编码**: 使用 H.264 编码，文件大小合理
3. **鲁棒性**: 自动清理和错误处理
4. **可扩展**: 易于自定义布局和覆盖信息

### 7.2 最佳实践

- ✅ 使用 `try-finally` 确保视频文件正确关闭
- ✅ 根据需求选择合适的帧率 (15-60 FPS)
- ✅ 批量评估时使用有意义的文件名
- ✅ 在 SLURM 上运行时指定明确的输出目录
- ✅ 定期检查磁盘空间（视频文件会快速增长）

### 7.3 典型工作流

```bash
# 1. 启动 policy server
python -m gr00t.eval.run_gr00t_server --model-path /path/to/ckpt --port 8000 &

# 2. 评估并录制视频
python -m omnigibson.eval.eval \
    --task-name turning_on_radio \
    --instance-indices 301 302 303 \
    --write-video \
    --video-fps 30 \
    --output-dir outputs/eval_20250120

# 3. 查看结果
ls outputs/eval_20250120/videos/
# turning_on_radio_301_0.mp4
# turning_on_radio_302_0.mp4
# turning_on_radio_303_0.mp4

# 4. 播放视频
vlc outputs/eval_20250120/videos/turning_on_radio_301_0.mp4

# 5. 分析 metrics
python scripts/analyze_results.py outputs/eval_20250120/json/
```

现在你已经掌握了 OmniGibson `write-video` 功能的完整使用方法！
