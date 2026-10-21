import omnigibson as og
from omnigibson.robots import Robot
from omnigibson.scenes import InteractiveTraversableScene

import omnigibson as og
from omnigibson.robots import Robot
from omnigibson.scenes import InteractiveTraversableScene

og.launch()

scene = InteractiveTraversableScene(scene_model="Rs_int")

og.sim.import_scene(scene)  # 这会调用 scene.load() 并初始化 _registry

# 4. 创建 Robot
robot = Robot(
    name="robot0",
    model="r1pro",
    
    # 控制配置
    control_freq=30.0,           # 30 Hz 控制频率
    action_normalize=True,        # 归一化动作到 [-1, 1]
    
    # 观察配置
    obs_modalities=["rgb", "depth", "proprio"],
    proprio_obs=[
        "eef_left_pos", "eef_left_quat",
        "eef_right_pos", "eef_right_quat",
        "arm_left_qpos", "arm_right_qpos",
        "gripper_left_qpos", "gripper_right_qpos",
        "base_qpos", "trunk_qpos",
    ],
    
    # 抓取配置
    grasping_mode="assisted",
    finger_static_friction=1.5,
    
    # Reset 配置
    default_reset_mode="untuck",
)

# 5. 添加 Robot 到 Scene
scene.add_object(robot)

print("== finish ==")
