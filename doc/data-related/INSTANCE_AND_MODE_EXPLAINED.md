# 🎯 Instance ID 和 Mode 深度解析

## 📚 核心概念

### BEHAVIOR-1K 的任务组织结构

```
任务名称 (task_name)
    ├── 场景 (scene_model)
    ├── 活动定义 (activity_definition_id)
    └── 任务实例 (instance_id)
        ├── 0   - 训练实例 0
        ├── 1   - 训练实例 1
        ├── ...
        ├── 299 - 训练实例 299
        ├── 301 - 测试实例 0 (public)
        ├── 302 - 测试实例 1 (public)
        ├── ...
        ├── 320 - 测试实例 19 (public)
        ├── 321 - 测试实例 0 (hidden)
        └── ...
```

---

## 🔑 Instance ID - 任务实例

### 什么是 Instance？

**同一个任务的不同初始配置**。想象成"同一个游戏关卡的不同难度版本"。

### 以 `boil_water` (煮水) 为例

```python
任务：boil_water
目标：把水加热到沸腾

# Instance 0
场景：kitchen_1
初始状态：
  - 锅在柜子里（需要先拿出来）
  - 水在冰箱里（需要先取出）
  - 炉子是关闭的
  - 机器人在厨房门口

# Instance 1  
场景：kitchen_2
初始状态：
  - 锅已经在炉子上（省略一步）
  - 水在水槽旁边（更近）
  - 炉子已经打开（又省略一步）
  - 机器人在炉子旁边

# Instance 2
场景：kitchen_3
初始状态：
  - 锅在地上（需要弯腰捡）
  - 水在另一个房间（需要走很远）
  - 炉子坏了（需要用微波炉）
  - 机器人在客厅
```

**每个 instance 测试策略在不同配置下的鲁棒性！**

### Instance ID 的范围

| 范围 | 说明 | 数量 | 用途 |
|------|------|------|------|
| **0-299** | 训练实例 | 300 | 开发和训练策略 |
| **301-320** | 公开测试实例 | 20 | 本地验证 |
| **321-340** | 隐藏测试实例 | 20 | 竞赛排行榜 |

---

## 🎭 Mode - 评估模式

### Mode 决定了使用哪个数据集

```python
mode = "train"         # 使用训练集（0-299）
mode = "public_test"   # 使用公开测试集（301-320）
mode = "hidden_test"   # 使用隐藏测试集（321-340）
```

### Mode 的作用

1. **决定数据文件的查找路径**
2. **映射 instance_indices 到实际的 instance_id**

---

## 🔍 代码逐行解析

### 完整流程

```python
def load_task_instance(self, instance_id: int) -> None:
    # ========================================
    # 第 1 步：构建任务实例文件路径
    # ========================================
    
    # 1.1 获取场景名称
    scene_model = self.env.task.scene_name
    # 例如：scene_model = "house_single_floor"
    
    # 1.2 构建任务缓存文件名
    tro_filename = self.env.task.get_cached_activity_scene_filename(
        scene_model=scene_model,
        activity_name=self.env.task.activity_name,      # "boil_water"
        activity_definition_id=self.env.task.activity_definition_id,  # 0
        activity_instance_id=instance_id,                # 301 (例如)
    )
    # 返回类似：
    # "house_single_floor_Beechwood_0_int_boil_water_0_0_0"
    #  └─场景名─┘  └─场景变体─┘ └─任务名─┘ └─定义ID─┘ └─实例ID─┘
    
    # 1.3 获取模式
    mode = self.cfg.get("mode", "public_test")
    # mode = "public_test"（默认）
    
    # 1.4 构建完整文件路径
    tro_file_path = get_task_instance_path(
        scene_model,
        f"{scene_model}_task_{self.env.task.activity_name}_instances/{tro_filename}-tro_state",
        mode=mode,
    )
    # 返回完整路径，例如：
    # "/data/2026-challenge-task-instances/public_test/
    #  house_single_floor_task_boil_water_instances/
    #  house_single_floor_Beechwood_0_int_boil_water_0_0_301-tro_state"
    
    if tro_file_path is None:
        raise FileNotFoundError(
            f"Could not find 2026 {mode} task instance {instance_id} for "
            f"{self.env.task.activity_name} in scene {scene_model}."
        )
    
    # ========================================
    # 第 2 步：加载任务实例的状态
    # ========================================
    
    with open(tro_file_path, "r") as f:
        tro_state = recursively_convert_to_torch(json.load(f))
    # tro_state 包含：
    # {
    #     "robot_poses": { ... },      # 机器人的初始位置
    #     "water.n.06_1": { ... },     # 水的状态
    #     "pot.n.04_1": { ... },       # 锅的状态
    #     "stove.n.01_1": { ... },     # 炉子的状态
    #     ...
    # }
    
    # ========================================
    # 第 3 步：恢复对象和机器人的状态
    # ========================================
    
    for tro_key, tro_state in tro_state.items():
        if tro_key == "robot_poses":
            # 3.1 处理机器人姿态
            presampled_robot_poses = {key.lower(): value for key, value in tro_state.items()}
            # presampled_robot_poses = {
            #     "robot": [...],      # 通用机器人位置
            #     "fetch": [...],      # Fetch 专用位置
            #     "r1pro": [...],      # R1Pro 专用位置
            # }
            
            # 3.2 选择合适的姿态
            if "robot" in presampled_robot_poses:
                # 优先使用通用姿态
                available_poses = presampled_robot_poses["robot"]
            elif self.robot.model in presampled_robot_poses:
                # 否则使用机器人特定姿态
                logger.info("No generic presampled robot pose found, using robot-specific pose.")
                available_poses = presampled_robot_poses[self.robot.model]
            else:
                raise KeyError(f"No generic or model-specific presampled robot pose found for {self.robot.model}!")
            
            # 3.3 设置机器人位置和朝向
            self.robot.set_position_orientation(
                available_poses[0]["position"],     # [x, y, z]
                available_poses[0]["orientation"]   # [x, y, z, w] (四元数)
            )
            
            # 3.4 保存元数据
            self.env.scene.write_task_metadata(key=tro_key, data=tro_state)
        else:
            # 3.5 加载其他对象的状态（水、锅、炉子等）
            self.env.task.object_scope[tro_key].load_state(tro_state, serialized=False)
            # 恢复：
            # - 对象位置
            # - 对象姿态
            # - 物理属性（速度、角速度）
            # - 对象状态（温度、是否被抓取等）
    
    # ========================================
    # 第 4 步：同步灯光（某些任务需要）
    # ========================================
    
    if self.should_sync_lights:
        set_light_control_toggles(self.env.task.object_scope.values(), True)
        # 确保灯光开关状态与任务要求一致
    
    # ========================================
    # 第 5 步：稳定物理场景
    # ========================================
    
    # 在加载状态后，需要让物理引擎运行几步来"稳定"场景
    # 防止对象因为数值误差而抖动或漂移
    
    og.sim.update_handles()  # 更新物理句柄
    
    for _ in range(25):
        og.sim.step_physics()  # 运行物理步
        
        # 同时保持所有任务相关对象静止
        for inst, entity in self.env.task.object_scope.items():
            if not is_system_bddl_inst(inst) and entity is not None:
                entity.keep_still()  # 防止对象移动
    
    # ========================================
    # 第 6 步：保存初始状态并重置
    # ========================================
    
    self.env.scene.update_initial_file()  # 更新初始状态文件
    self.env.scene.reset()                 # 重置场景到初始状态
    self._reset_light_synchronizer()       # 重置灯光同步器
```

---

## 📂 文件系统结构

### 任务实例文件的组织

```
$OMNIGIBSON_DATA_PATH/
└── 2026-challenge-task-instances/
    ├── train/                          # 训练集（mode="train"）
    │   └── house_single_floor_task_boil_water_instances/
    │       ├── ...0-tro_state         # instance_id = 0
    │       ├── ...1-tro_state         # instance_id = 1
    │       └── ...299-tro_state       # instance_id = 299
    │
    ├── public_test/                    # 公开测试（mode="public_test"）
    │   └── house_single_floor_task_boil_water_instances/
    │       ├── ...301-tro_state       # instance_id = 301
    │       ├── ...302-tro_state       # instance_id = 302
    │       └── ...320-tro_state       # instance_id = 320
    │
    └── hidden_test/                    # 隐藏测试（mode="hidden_test"）
        └── house_single_floor_task_boil_water_instances/
            ├── ...321-tro_state       # instance_id = 321
            ├── ...322-tro_state       # instance_id = 322
            └── ...340-tro_state       # instance_id = 340
```

### TRO State 文件内容

```json
{
  "robot_poses": {
    "robot": [
      {
        "position": [2.5, 1.3, 0.0],
        "orientation": [0.0, 0.0, 0.707, 0.707]
      }
    ],
    "r1pro": [
      {
        "position": [2.6, 1.4, 0.0],
        "orientation": [0.0, 0.0, 0.7, 0.714]
      }
    ]
  },
  "water.n.06_1": {
    "root_link": {
      "pos": [3.2, 2.1, 0.8],
      "ori": [0, 0, 0, 1],
      "lin_vel": [0, 0, 0],
      "ang_vel": [0, 0, 0]
    },
    "states": {
      "Heated": {"value": false},
      "OnTop": {"value": ["table.n.02_1"]}
    }
  },
  "pot.n.04_1": {
    "root_link": {
      "pos": [1.5, 0.8, 0.9],
      "ori": [0, 0, 0, 1]
    }
  },
  "stove.n.01_1": {
    "states": {
      "ToggledOn": {"value": false}
    }
  }
}
```

---

## 🎮 实际使用示例

### 场景 1：训练模式

```bash
python -m omnigibson.eval.eval \
    --task-name boil_water \
    --mode train \
    --instance-indices 0 1 2  # 直接使用 instance_id
```

**执行流程**：
```python
mode = "train"
instance_indices = [0, 1, 2]

# 直接使用 instance_id
for instance_id in [0, 1, 2]:
    evaluator.load_task_instance(instance_id)
    # 加载文件：train/...0-tro_state
    # 加载文件：train/...1-tro_state
    # 加载文件：train/...2-tro_state
```

### 场景 2：公开测试模式

```bash
python -m omnigibson.eval.eval \
    --task-name boil_water \
    --mode public_test \
    --instance-indices 0 1 2  # 索引，不是实际 ID！
```

**执行流程**：
```python
mode = "public_test"
instance_indices = [0, 1, 2]

# resolve_instance_ids 映射索引到实际 ID
TEST_INSTANCE_IDS = [301, 302, ..., 320]  # 公开测试集的实际 ID
actual_ids = [TEST_INSTANCE_IDS[i] for i in instance_indices]
# actual_ids = [301, 302, 303]

for instance_id in [301, 302, 303]:
    evaluator.load_task_instance(instance_id)
    # 加载文件：public_test/...301-tro_state
    # 加载文件：public_test/...302-tro_state
    # 加载文件：public_test/...303-tro_state
```

### 场景 3：隐藏测试模式

```bash
python -m omnigibson.eval.eval \
    --task-name boil_water \
    --mode hidden_test \
    --instance-indices 0 1 2
```

**执行流程**：
```python
mode = "hidden_test"
instance_indices = [0, 1, 2]

# 映射到隐藏测试集的实际 ID
TEST_INSTANCE_IDS = [301, 302, ..., 340]
hidden_test_ids = TEST_INSTANCE_IDS[20:]  # [321, 322, ..., 340]
actual_ids = [hidden_test_ids[i] for i in instance_indices]
# actual_ids = [321, 322, 323]

for instance_id in [321, 322, 323]:
    evaluator.load_task_instance(instance_id)
    # 加载文件：hidden_test/...321-tro_state
    # 加载文件：hidden_test/...322-tro_state
    # 加载文件：hidden_test/...323-tro_state
```

---

## 🧩 为什么需要这种设计？

### 1. **标准化评估**

所有研究者在**完全相同的初始配置**下测试策略：
- ✅ 结果可比较
- ✅ 排除随机性影响
- ✅ 公平竞争

### 2. **测试泛化能力**

同一任务的多个实例测试策略的**鲁棒性**：
- Instance 0：简单配置
- Instance 10：中等难度
- Instance 19：复杂配置

策略需要在**所有配置下都表现良好**。

### 3. **防止过拟合**

- **训练集（300 个）**：开发时可以看到
- **公开测试集（20 个）**：本地验证，可以看到
- **隐藏测试集（20 个）**：竞赛排行榜，不能看到

防止参赛者"记住"测试集的配置。

### 4. **增量难度**

```python
# 简单 → 困难
instance_id = 0    # 所有物品都在最优位置
instance_id = 10   # 有些物品需要移动
instance_id = 19   # 物品分散在不同房间
```

---

## 📊 总结对比表

| 概念 | 说明 | 示例 | 作用 |
|------|------|------|------|
| **task_name** | 任务名称 | `"boil_water"` | 决定目标 |
| **instance_id** | 任务实例的实际 ID | `301` | 唯一标识一个初始配置 |
| **instance_indices** | 索引（相对值） | `[0, 1, 2]` | 用户友好的引用方式 |
| **mode** | 评估模式 | `"public_test"` | 决定查找路径和映射规则 |
| **scene_model** | 场景模型 | `"house_single_floor"` | 决定物理环境 |

### Instance ID vs Instance Indices

```python
# Train mode：indices == ids
--mode train --instance-indices 0 1 2
→ 实际加载：instance_id = 0, 1, 2

# Public test mode：indices 映射到 301-320
--mode public_test --instance-indices 0 1 2
→ 实际加载：instance_id = 301, 302, 303

# Hidden test mode：indices 映射到 321-340
--mode hidden_test --instance-indices 0 1 2
→ 实际加载：instance_id = 321, 322, 323
```

---

## 🎓 关键要点

1. **Instance ID** = 任务的具体初始配置（对象位置、机器人位置等）
2. **Mode** = 使用哪个数据集（train/public_test/hidden_test）
3. **TRO State 文件** = 保存实例的完整初始状态
4. **load_task_instance** = 从文件恢复场景到特定初始配置
5. **物理稳定步骤** = 确保加载后场景稳定，没有抖动

---

希望这个详细的解释帮助你理解了 instance_id 和 mode 的含义！
