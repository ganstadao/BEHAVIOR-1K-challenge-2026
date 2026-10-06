import os
import cv2
import numpy as np
import omnigibson as og
from omnigibson.macros import gm

gm.HEADLESS = True

cfg = dict()
cfg["scene"] = {"type": "Scene", "floor_plane_visible": True}
cfg["objects"] = [
    {"type": "DatasetObject", "name": "delicious_apple",
     "category": "apple", "model": "agveuv", "position": [0, 0, 1.0]},
    {"type": "PrimitiveObject", "name": "incredible_box",
     "primitive_type": "Cube", "rgba": [0, 1.0, 1.0, 1.0],
     "scale": [0.5, 0.5, 0.1], "fixed_base": True,
     "position": [-1.0, 0, 1.0], "orientation": [0, 0, 0.707, 0.707]},
    {"type": "LightObject", "name": "brilliant_light",
     "light_type": "Sphere", "intensity": 50000, "radius": 0.1,
     "position": [3.0, 3.0, 4.0]},
]
cfg["robots"] = [
    {"model": "fetch", "name": "baby_robot",
     "obs_modalities": ["rgb", "depth"]},
]
cfg["task"] = {"type": "DummyTask",
               "termination_config": dict(), "reward_config": dict()}

env = og.Environment(cfg)


def to_image(x):
    """取出一张 (H,W,3/4) 图像，兼容 数组/列表/字典/object数组"""
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


def collect_rgb(obj, sensor_name=""):
    """递归遍历整棵obs树，返回 [(相机名, 图像)]"""
    results = []
    if isinstance(obj, dict):
        if "rgb" in obj:                              # 这一层就是相机
            img = to_image(obj["rgb"])
            if img is not None:
                results.append((sensor_name, img))
        else:                                         # 继续往下钻
            for k, v in obj.items():
                results.extend(collect_rgb(v, k))
    return results


NUM_FRAMES = 300
FPS = 30
video_path = os.path.expanduser("~/project/myfirst_demo.mp4")
writer = None

for step in range(NUM_FRAMES):
    obs, rew, terminated, truncated, info = env.step(env.action_space.sample())

    # 递归收集所有相机的rgb
    cams = collect_rgb(obs)
    rgb = None
    if cams:
        # 优先头部eyes相机，否则用第一个
        rgb = next((img for name, img in cams if "eyes" in name), cams[0][1])

    if rgb is not None:
        rgb = np.asarray(rgb)
        if rgb.dtype != np.uint8:
            rgb = (rgb * 255).astype(np.uint8) if rgb.max() <= 1.0 else rgb.astype(np.uint8)
        if rgb.shape[-1] == 4:
            rgb = rgb[..., :3]
        h, w = rgb.shape[:2]
        if writer is None:
            print(f"找到 {len(cams)} 个相机，开始录制，分辨率 {w}x{h}")
            writer = cv2.VideoWriter(
                video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h))
        writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    if step % 50 == 0:
        print(f"进度: {step}/{NUM_FRAMES}")

if writer is not None:
    writer.release()
    print(f"✅ 视频已保存: {video_path}")
else:
    print("⚠️ 还是没取到，把上面obs结构发我")

og.shutdown()
