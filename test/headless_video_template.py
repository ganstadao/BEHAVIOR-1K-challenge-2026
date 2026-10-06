"""
无头模式视频录制模板
适用于所有 OmniGibson 环境的视频录制
"""
import os
import cv2
import numpy as np
import omnigibson as og
from omnigibson.macros import gm

# 关键：启用无头模式
gm.HEADLESS = True
gm.ENABLE_OBJECT_STATES = True


def to_image(x):
    """提取图像数组"""
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return to_image(x[0]) if len(x) > 0 else None
    if isinstance(x, dict):
        return to_image(next(iter(x.values()))) if x else None
    arr = np.asarray(x)
    if arr.dtype == object:
        return to_image(arr.flat[0]) if arr.size > 0 else None
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        return arr
    return None


def collect_rgb(obs, sensor_name=""):
    """递归收集所有相机的 RGB 图像"""
    results = []
    if isinstance(obs, dict):
        if "rgb" in obs:
            img = to_image(obs["rgb"])
            if img is not None:
                results.append((sensor_name, img))
        else:
            for k, v in obs.items():
                results.extend(collect_rgb(v, k))
    return results


def process_frame(rgb):
    """处理单帧图像为 OpenCV 格式"""
    rgb = np.asarray(rgb)
    # 归一化到 0-255
    if rgb.dtype != np.uint8:
        rgb = (rgb * 255).astype(np.uint8) if rgb.max() <= 1.0 else rgb.astype(np.uint8)
    # 去掉 alpha 通道
    if rgb.shape[-1] == 4:
        rgb = rgb[..., :3]
    # RGB -> BGR (OpenCV 格式)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


class VideoRecorder:
    """视频录制器"""
    def __init__(self, output_path, fps=30, prefer_camera="eyes"):
        self.output_path = os.path.expanduser(output_path)
        self.fps = fps
        self.prefer_camera = prefer_camera
        self.writer = None
        self.frame_count = 0

    def add_frame(self, obs):
        """添加一帧"""
        cams = collect_rgb(obs)
        if not cams:
            return False

        # 优先选择指定的相机（如头部相机 "eyes"）
        rgb = next((img for name, img in cams if self.prefer_camera in name), cams[0][1])

        frame = process_frame(rgb)
        h, w = frame.shape[:2]

        # 初始化 writer
        if self.writer is None:
            print(f"📹 初始化视频录制器：")
            print(f"   - 分辨率: {w}x{h}")
            print(f"   - 帧率: {self.fps} FPS")
            print(f"   - 找到 {len(cams)} 个相机: {[name for name, _ in cams]}")
            self.writer = cv2.VideoWriter(
                self.output_path,
                cv2.VideoWriter_fourcc(*"mp4v"),
                self.fps,
                (w, h)
            )

        self.writer.write(frame)
        self.frame_count += 1
        return True

    def release(self):
        """保存并关闭"""
        if self.writer is not None:
            self.writer.release()
            duration = self.frame_count / self.fps
            print(f"✅ 视频已保存: {self.output_path}")
            print(f"   - 总帧数: {self.frame_count}")
            print(f"   - 时长: {duration:.2f} 秒")
        else:
            print("⚠️ 没有录制到任何帧")


def run_with_video(env, num_steps=300, video_path="~/output.mp4", fps=30):
    """运行环境并录制视频"""
    recorder = VideoRecorder(video_path, fps=fps)

    print(f"🎬 开始录制 {num_steps} 步...")
    for step in range(num_steps):
        obs, rew, term, trunc, info = env.step(env.action_space.sample())
        recorder.add_frame(obs)

        if step % 50 == 0:
            print(f"   进度: {step}/{num_steps}")

        if term or trunc:
            print(f"   任务在第 {step+1} 步结束")
            break

    recorder.release()


# ============ 使用示例 ============
if __name__ == "__main__":
    # 配置环境
    cfg = {
        "scene": {"type": "Scene", "floor_plane_visible": True},
        "objects": [
            {
                "type": "DatasetObject",
                "name": "apple",
                "category": "apple",
                "model": "agveuv",
                "position": [0, 0, 1.0],
            },
            {
                "type": "PrimitiveObject",
                "name": "box",
                "primitive_type": "Cube",
                "rgba": [1.0, 0, 0, 1.0],
                "scale": [0.3, 0.3, 0.3],
                "position": [0.5, 0, 0.5],
            }
        ],
        "robots": [{
            "type": "Fetch",
            "name": "robot",
            "obs_modalities": ["rgb", "depth"],
        }],
        "task": {
            "type": "DummyTask",
            "termination_config": {},
            "reward_config": {},
        }
    }

    print("🚀 创建环境...")
    env = og.Environment(cfg)

    print("✅ 环境创建成功！")
    run_with_video(
        env,
        num_steps=200,
        video_path="~/project/headless_demo.mp4",
        fps=30
    )

    og.shutdown()
    print("🎉 完成！")
