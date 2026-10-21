"""
测试场景加载和视频录制
使用官方 eval 中的视频写入方式，不依赖 task
"""

import numpy as np
import torch as th
import omnigibson as og
import sys
from omnigibson.eval.utils.obs_utils import create_video_writer, write_video

def log(msg):
    """Log message to stderr (survives OmniGibson stdout redirection)"""
    print(msg, file=sys.stderr, flush=True)
    # Also try stdout in case it's not redirected yet
    print(msg, flush=True)

# 配置
cfg = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
    },
    "robots": [
        {
            "name": "robot0",
            "model": "r1pro",
            "action_normalize": True,
            "obs_modalities": ["rgb", "depth"],  # 确保有 RGB 观察
        }
    ],
}

# 创建环境
env = og.Environment(configs=cfg)
scene = env.scene
robot = env.robots[0]

# Reset 环境
env.reset()

log(f"Scene loaded: {scene.loaded}")
log(f"Scene initialized: {scene._initialized}")
log(f"Robot name: {robot.name}")
log(f"Robot sensors: {list(robot.sensors.keys())}")

# 视频配置
VIDEO_PATH = "outputs/simulation_test.mp4"
VIDEO_FPS = 30
NUM_STEPS = 300  # 录制 10 秒 (300 steps @ 30 FPS)

# 创建视频写入器（懒加载，第一帧时创建）
video_writer = None

log(f"\n开始录制 {NUM_STEPS} 步...")

for step in range(NUM_STEPS):
    # 生成随机动作（机器人随机移动）
    action = th.rand(robot.action_dim) * 2 - 1  # [-1, 1] 范围 r1pro的best.yaml配置的应该是21维度

    # 执行动作
    obs, reward, terminated, truncated, info = env.step(action)
    
    # === 视频录制逻辑（参照官方 eval） ===
    # 提取 RGB 观察
    # obs 结构: {'robot0:sensor_link:Camera:0': {'rgb': tensor, 'depth': tensor}}
    rgb_frame = None
    camera_name = None

    for key, value in obs.items():

        # 提取 RGB tensor [H, W, 4] (RGBA) 这里是 (128,128,4)
        left_rgb_tensor = value["robot0:left_realsense_link:Camera:0"]["rgb"]
        right_rgb_tensor = value["robot0:right_realsense_link:Camera:0"]["rgb"]
        zed_rgb_tensor = value["robot0:zed_link:Camera:0"]["rgb"]
        
        # 只取前 3 个通道 (RGB)，去掉 Alpha 通道
        rgb_frame = zed_rgb_tensor[..., :3].cpu().numpy()  # [H, W, 3]
        break

    if rgb_frame is not None:
        # rgb_frame 已经是 [H, W, 3]
        # 添加 batch 维度 [1, H, W, 3]
        frame = np.expand_dims(rgb_frame, 0)

        # 第一帧：创建 video writer
        if video_writer is None:
            log(f"创建视频写入器: {VIDEO_PATH}")
            log(f"  分辨率: {frame.shape[1:3]} (H, W)")
            log(f"  帧率: {VIDEO_FPS} FPS")

            video_writer = create_video_writer(
                fpath=VIDEO_PATH,
                resolution=frame.shape[1:3],  # (H, W)
                rate=VIDEO_FPS,
            )

        # 写入这一帧
        write_video(
            frame,
            video_writer=video_writer,
            batch_size=1,
            mode="rgb"
        )

    # 进度显示
    if (step + 1) % 30 == 0:
        log(f"  已录制 {step + 1}/{NUM_STEPS} 帧 ({(step+1)/VIDEO_FPS:.1f}s)")

    # 如果环境终止，提前结束
    if terminated or truncated:
        log(f"环境在第 {step} 步终止")
        break

# 关闭视频文件（非常重要！）
if video_writer is not None:
    container, stream = video_writer

    # Flush 编码器
    for packet in stream.encode():
        container.mux(packet)

    # 关闭容器
    container.close()

    log(f"\n✅ 视频已保存到: {VIDEO_PATH}")
else:
    log("\n❌ 未能创建视频（没有找到 RGB 观察）")

log("== 测试完成 ==")
