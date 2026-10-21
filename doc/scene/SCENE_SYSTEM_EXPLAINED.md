# OmniGibson Scene 系统详解

本文档详细讲解 OmniGibson 的 Scene 系统架构、实现原理以及使用方法。

## 1. Scene 系统概览

### 1.1 什么是 Scene？

**Scene（场景）** 是 OmniGibson 中的核心概念，代表一个完整的 3D 环境，包括：
- **建筑结构**: 墙壁、地板、天花板
- **物体**: 家具、物品、道具
- **机器人**: 操作机器人
- **系统**: 流体、粒子、布料等物理系统
- **导航信息**: 可通行地图、房间分割

### 1.2 Scene 类层次结构

```
Scene (抽象基类)
    ├── 基础功能: 对象管理、系统管理、注册表
    └── 抽象方法: _load()
        ↓
TraversableScene (可导航场景)
    ├── 继承: Scene
    ├── 新增: TraversableMap (导航地图)
    └── 功能: 路径规划、随机采样点
        ↓
InteractiveTraversableScene (交互式可导航场景)
    ├── 继承: TraversableScene
    ├── 新增: SegmentationMap (房间分割图)
    └── 功能: 房间过滤、对象过滤、任务相关对象
        ↓
StaticTraversableScene (静态可导航场景)
    ├── 继承: TraversableScene
    └── 特点: 简化版本，无房间信息
```

### 1.3 核心组件

```
Scene
├── Object Registry (对象注册表)
│   ├── 唯一键: name, prim_path, uuid
│   └── 分组键: category, states, in_rooms, abilities
├── System Registry (系统注册表)
│   └── 粒子系统: water, dust, steam, etc.
├── TraversableMap (可通行地图)
│   ├── 栅格地图
│   ├── 路径规划
│   └── 随机点采样
└── SegmentationMap (房间分割图)
    ├── 房间类型: kitchen, bedroom, etc.
    └── 房间实例: kitchen_0, kitchen_1, etc.
```

## 2. Scene 基类实现 (scene_base.py)

### 2.1 初始化流程

```python
# omnigibson/scenes/scene_base.py

class Scene(XFormPrim, ABC):
    def __init__(
        self,
        scene_file=None,              # 场景文件路径 (JSON)
        use_floor_plane=True,         # 是否使用地面平面
        include_robots=True,          # 是否包含机器人
    ):
        """
        初始化场景
        
        Args:
            scene_file: 场景配置文件 (JSON)，定义对象和布局
            use_floor_plane: 是否加载平面地板
            include_robots: 是否加载场景中定义的机器人
        """
        # 状态变量
        self._loaded = False          # 是否已加载
        self._initialized = False     # 是否已初始化
        self._idx = None              # 场景索引
        self._scene_prim = None       # 场景 USD prim
        
        # 注册表
        self._registries = {}         # 存储所有注册表
        
        # 系统
        self._available_systems = {}  # 可用系统
        self._init_systems = set()    # 初始化的系统
        
        # 对象
        self._init_objs = {}          # 初始对象
        self._init_state = {}         # 初始状态
        
        # 配置
        self._use_floor_plane = use_floor_plane
        self._include_robots = include_robots
        self.scene_file = scene_file
        
        # 状态追踪
        self._updated_state_objects = set()  # 状态更新的对象
        
        # 解析场景文件
        if scene_file is not None:
            self._parse_scene_file(scene_file)
```

### 2.2 对象注册表 (Object Registry)

```python
@property
def object_registry(self):
    """
    对象注册表：管理场景中的所有对象
    
    支持的查询方式:
        - registry("name", "apple_1") -> 通过名称查找
        - registry("category", "apple") -> 通过类别查找
        - registry("in_rooms", "kitchen_0") -> 通过房间查找
        - registry("states", OnTop) -> 通过状态查找
    """
    return self._registry(key="name", value="object_registry")

@property
def object_registry_unique_keys(self):
    """唯一键: 用于精确查找单个对象"""
    return ["name", "prim_path", "uuid"]

@property
def object_registry_group_keys(self):
    """分组键: 用于查找对象组"""
    return ["prim_type", "states", "category", "fixed_base", "in_rooms", "abilities"]

# 使用示例
# 1. 通过名称查找
apple = scene.object_registry("name", "apple_1")

# 2. 通过类别查找所有苹果
apples = scene.object_registry("category", "apple", [])

# 3. 通过房间查找
kitchen_objects = scene.object_registry("in_rooms", "kitchen_0", [])

# 4. 通过状态查找
toggleable_objects = scene.object_registry("states", ToggledOn, [])
```

### 2.3 场景加载流程

```python
def load(self, idx, **kwargs):
    """
    加载场景到仿真器
    
    Args:
        idx: 场景索引 (用于多场景管理)
    
    完整流程:
        1. 预构建 USD
        2. 加载场景 prim
        3. 加载系统
        4. 加载对象
        5. 初始化状态
    """
    assert not self._loaded, "Scene already loaded!"
    
    # Step 1: 保存索引
    self._idx = idx
    
    # Step 2: 预构建并加载场景 prim
    self._load_scene_prim_with_objects(
        last_scene_edge=kwargs.get("last_scene_edge", 0),
        initial_scene_prim_z_offset=kwargs.get("initial_scene_prim_z_offset", 100),
        scene_margin=kwargs.get("scene_margin", 5),
    )
    
    # Step 3: 调用子类特定的加载逻辑
    self._load()
    
    # Step 4: 标记为已加载
    self._loaded = True
    
    return self

def _load_scene_prim_with_objects(self, last_scene_edge, initial_scene_prim_z_offset, scene_margin):
    """
    加载场景 prim 和对象
    
    流程:
        1. 预构建场景 USD (缓存)
        2. 添加到 stage
        3. 加载系统
        4. 加载对象
        5. 定位场景
    """
    # Step 1: 构建场景路径
    scene_relative_path = f"/scene_{self.idx}"
    scene_absolute_path = f"/World{scene_relative_path}"
    
    # Step 2: 检查是否已存在
    scene_prim_obj = og.sim.stage.GetPrimAtPath(scene_absolute_path)
    if not scene_prim_obj:
        # 预构建并添加到 stage
        scene_prim_obj = add_asset_to_stage(
            asset_path=self.prebuild(),
            prim_path=scene_absolute_path
        )
    
    # Step 3: 创建 XFormPrim
    self._scene_prim = XFormPrim(
        relative_prim_path=scene_relative_path,
        name=f"scene_{self.idx}",
    )
    self._scene_prim.load(None)
    
    # Step 4: 加载系统 (water, dust, etc.)
    self._load_systems()
    for system_name in self._init_systems:
        self.get_system(system_name, force_init=True)
    
    # Step 5: 初始位置 (避免碰撞)
    self._scene_prim.set_position_orientation(
        position=th.tensor([0, 0, initial_scene_prim_z_offset if self.idx != 0 else 0])
    )
    
    # Step 6: 批量加载对象
    with og.sim.adding_objects(objs=self._init_objs.values()):
        for obj_name, obj in self._init_objs.items():
            self.add_object(obj, _batched_call=True)
            obj.set_position_orientation(
                position=self._init_state[obj_name]["root_link"]["pos"],
                orientation=self._init_state[obj_name]["root_link"]["ori"],
            )
    
    # Step 7: 定位场景 (相对于上一个场景)
    if self.idx != 0:
        aabb_min, aabb_max = compute_path_world_bounding_box(scene_absolute_path)
        left_edge_to_center = -aabb_min[0]
        right_edge_to_center = aabb_max[0]
        center_to_center = last_scene_edge + scene_margin + left_edge_to_center
        self._scene_prim.set_position_orientation(
            position=th.tensor([center_to_center, 0, 0])
        )
        new_last_scene_edge = center_to_center + right_edge_to_center
    else:
        new_last_scene_edge = 0
    
    return new_last_scene_edge
```

### 2.4 预构建 (Prebuild) 机制

```python
def prebuild(self):
    """
    预构建场景 USD
    
    原理:
        1. 将所有对象预先构建到临时 USD 文件
        2. 缓存结果 (避免重复构建)
        3. 后续加载时直接引用缓存
    
    优势:
        - 加速场景加载 (特别是复杂场景)
        - 避免重复计算
        - 支持多实例共享
    
    Returns:
        str: 预构建的 USD 文件路径
    """
    # Step 1: 计算场景文件哈希
    if isinstance(self.scene_file, str):
        scene_file_path = self.scene_file
    else:
        # 场景文件是字典，序列化后哈希
        scene_file_str = json.dumps(self.scene_file, cls=TorchEncoder, indent=4)
        scene_file_hash = get_uuid(scene_file_str, deterministic=True)
        scene_file_path = os.path.join(og.tempdir, f"scene_file_{scene_file_hash}.json")
        with open(scene_file_path, "w+") as f:
            json.dump(self.scene_file, f, cls=TorchEncoder, indent=4)
    
    # Step 2: 检查缓存
    if scene_file_path not in PREBUILT_USDS:
        log.info(f"Prebuilding scene file {scene_file_path}...")
        
        # Step 3: 创建临时 USD stage
        decrypted_fd, usd_path = tempfile.mkstemp(
            os.path.basename(scene_file_path) + ".usd",
            dir=og.tempdir
        )
        os.close(decrypted_fd)
        stage = create_usd_stage(usd_path)
        
        # Step 4: 创建 World prim
        world_prim = stage.DefinePrim("/World", "Xform")
        stage.SetDefaultPrim(world_prim)
        
        # Step 5: 预构建所有对象
        for obj_name, obj in self._init_objs.items():
            obj.prebuild(stage)
        
        # Step 6: 保存并缓存
        stage.Save()
        del stage
        PREBUILT_USDS[scene_file_path] = usd_path
    
    # Step 7: 复制缓存文件 (每个场景实例独立)
    decrypted_fd, instance_usd_path = tempfile.mkstemp(
        os.path.basename(scene_file_path) + ".usd",
        dir=og.tempdir
    )
    os.close(decrypted_fd)
    shutil.copyfile(PREBUILT_USDS[scene_file_path], instance_usd_path)
    
    return instance_usd_path
```

### 2.5 对象管理

```python
def add_object(self, obj, register=True, _batched_call=False):
    """
    添加对象到场景
    
    Args:
        obj: 要添加的对象
        register: 是否注册到 object_registry
        _batched_call: 是否批量调用 (内部使用)
    """
    # Step 1: 导入对象到仿真器
    if not _batched_call:
        obj.load(self._scene_prim)
    
    # Step 2: 注册到 object_registry
    if register:
        # 唯一键注册
        for key in self.object_registry_unique_keys:
            value = getattr(obj, key)
            self.object_registry.add(obj=obj, key=key, value=value)
        
        # 分组键注册
        for key in self.object_registry_group_keys:
            values = getattr(obj, key)
            if not isinstance(values, list):
                values = [values]
            for value in values:
                self.object_registry.add(obj=obj, key=key, value=value)

def remove_object(self, obj, _batched_call=False):
    """
    从场景移除对象
    
    Args:
        obj: 要移除的对象
        _batched_call: 是否批量调用
    """
    # Step 1: 从注册表移除
    # 唯一键
    for key in self.object_registry_unique_keys:
        value = getattr(obj, key)
        self.object_registry.remove(obj=obj, key=key, value=value)
    
    # 分组键
    for key in self.object_registry_group_keys:
        values = getattr(obj, key)
        if not isinstance(values, list):
            values = [values]
        for value in values:
            self.object_registry.remove(obj=obj, key=key, value=value)
    
    # Step 2: 从仿真器移除
    if not _batched_call:
        obj.remove()

def reset(self, hard=True):
    """
    重置场景
    
    Args:
        hard: 是否硬重置 (完全重新初始化)
    """
    # Step 1: 停止记录
    for obj in self.objects:
        obj.keep_still()
    
    # Step 2: 重置所有对象
    if hard:
        # 硬重置: 恢复到初始状态
        for obj_name, obj in self._init_objs.items():
            obj.set_position_orientation(
                position=self._init_state[obj_name]["root_link"]["pos"],
                orientation=self._init_state[obj_name]["root_link"]["ori"],
            )
    else:
        # 软重置: 保持当前状态
        pass
    
    # Step 3: 清空状态追踪
    self._updated_state_objects.clear()
```

### 2.6 系统管理

```python
def _load_systems(self):
    """
    加载所有可用系统
    
    系统类型:
        - FluidSystem: 流体 (water, milk, etc.)
        - MacroParticleSystem: 宏粒子 (dust, dirt, etc.)
        - Cloth: 布料
    """
    system_dir = os.path.join(get_dataset_path("behavior-1k-assets"), "systems")
    
    # Step 1: 从元数据创建系统
    available_systems = {}
    if os.path.exists(system_dir):
        for system_name in get_all_system_names():
            available_systems[system_name] = create_system_from_metadata(
                system_name=system_name
            )
    
    # Step 2: 添加特殊系统
    cloth_system = Cloth(name="cloth")
    available_systems["cloth"] = cloth_system
    
    self._available_systems = available_systems

def get_system(self, system_name, force_init=False):
    """
    获取系统实例
    
    Args:
        system_name: 系统名称 (e.g., "water", "dust")
        force_init: 是否强制初始化
    
    Returns:
        BaseSystem: 系统实例
    """
    # Step 1: 检查是否可用
    assert system_name in self._available_systems, \
        f"System {system_name} not available!"
    
    # Step 2: 获取系统
    system = self._available_systems[system_name]
    
    # Step 3: 初始化（如果需要）
    if force_init and system_name not in self._init_systems:
        system.initialize(self)
        self._init_systems.add(system_name)
        # 注册到 system_registry
        self.system_registry.add(obj=system, key="name", value=system_name)
    
    return system
```

## 3. TraversableScene (可导航场景)

### 3.1 TraversableMap

```python
# omnigibson/scenes/traversable_scene.py

class TraversableScene(Scene):
    def __init__(
        self,
        scene_model,
        scene_file=None,
        trav_map_resolution=0.1,      # 地图分辨率 (米)
        default_erosion_radius=0.0,   # 侵蚀半径
        trav_map_with_objects=True,   # 是否考虑对象
        num_waypoints=10,             # 路点数量
        waypoint_resolution=0.2,      # 路点分辨率
        use_floor_plane=True,
        include_robots=True,
    ):
        """
        可导航场景
        
        新增功能:
            - TraversableMap: 可通行地图
            - 路径规划: A* 算法
            - 随机点采样: 在可通行区域
        """
        self.scene_model = scene_model
        
        # 创建 traversable map
        self._trav_map = TraversableMap(
            map_resolution=trav_map_resolution,
            default_erosion_radius=default_erosion_radius,
            trav_map_with_objects=trav_map_with_objects,
            num_waypoints=num_waypoints,
            waypoint_resolution=waypoint_resolution,
        )
        
        super().__init__(
            scene_file=scene_file,
            use_floor_plane=use_floor_plane,
            include_robots=include_robots,
        )
```

**TraversableMap 功能**:

```python
# 1. 加载地图
self._trav_map.load_map(maps_path)

# 2. 获取随机点
random_point = scene.get_random_point(
    floor=0,                   # 楼层
    reference_point=None,      # 参考点 (限制范围)
    robot=robot,               # 机器人 (考虑尺寸)
)

# 3. 路径规划
path = scene.get_shortest_path(
    floor=0,
    source_world=[1.0, 2.0],   # 起点 (世界坐标)
    target_world=[5.0, 6.0],   # 终点
    entire_path=False,         # 是否返回完整路径
    robot=robot,
)
```

## 4. InteractiveTraversableScene (交互式场景)

### 4.1 特性

```python
class InteractiveTraversableScene(TraversableScene):
    """
    交互式可导航场景
    
    用途:
        - BEHAVIOR-1K 任务
        - 完整的房间结构
        - 对象和房间过滤
    
    新增功能:
        - SegmentationMap: 房间分割
        - 对象过滤: 按类别、房间
        - 任务相关对象: 只加载任务需要的
    """
    def __init__(
        self,
        scene_model,                      # 场景名称 (e.g., "Rs_int")
        scene_instance=None,              # 场景实例 (e.g., "0")
        scene_file=None,                  # 或直接指定文件
        load_object_categories=None,      # 只加载这些类别
        not_load_object_categories=None,  # 不加载这些类别
        load_room_types=None,             # 只加载这些房间类型
        load_room_instances=None,         # 只加载这些房间实例
        load_task_relevant_only=False,   # 只加载任务相关对象
        seg_map_resolution=0.1,           # 房间分割地图分辨率
        include_robots=True,
        **kwargs
    ):
        self.scene_model = scene_model
        self.scene_dir = get_scene_path(scene_model, dataset_name="behavior-1k-assets")
        
        # 加载房间分割地图
        self._seg_map = SegmentationMap(
            scene_dir=self.scene_dir,
            map_resolution=seg_map_resolution
        )
        
        # 过滤配置
        self.load_object_categories = load_object_categories
        self.not_load_object_categories = not_load_object_categories
        self.load_room_instances = load_room_instances
        self.load_task_relevant_only = load_task_relevant_only
        
        super().__init__(
            scene_model=scene_model,
            scene_file=scene_file or self.get_scene_loading_info(scene_model, scene_instance),
            use_floor_plane=False,  # 交互式场景使用自带地板
            include_robots=include_robots,
            **kwargs
        )
```

### 4.2 对象过滤

```python
def _should_load_object(self, obj_info, task_metadata):
    """
    决定是否加载对象
    
    过滤规则:
        1. 黑名单: not_load_object_categories
        2. 白名单: load_object_categories
        3. 任务相关: load_task_relevant_only
        4. 房间过滤: load_room_instances
        5. 建筑结构: 始终加载
    
    Returns:
        bool: 是否应该加载
    """
    name = obj_info["args"]["name"]
    category = obj_info["args"].get("category", "object")
    in_rooms = obj_info["args"].get("in_rooms", [])
    
    # 规则 1: 黑名单
    not_blacklisted = (
        self.not_load_object_categories is None 
        or category not in self.not_load_object_categories
    )
    
    # 规则 2 & 3: 白名单或任务相关
    task_relevant_names = set(task_metadata.get("inst_to_name", {}).values())
    is_task_relevant = name in task_relevant_names or category in STRUCTURE_CATEGORIES
    
    whitelisted = (
        # 没有过滤
        (self.load_object_categories is None and not self.load_task_relevant_only)
        or
        # 在白名单中
        (self.load_object_categories is not None and category in self.load_object_categories)
        or
        # 任务相关
        (self.load_task_relevant_only and is_task_relevant)
    )
    
    # 规则 4: 房间过滤
    valid_room = (
        self.load_room_instances is None 
        or len(set(self.load_room_instances) & set(in_rooms)) > 0
    )
    
    # 规则 5: 建筑结构始终加载
    is_building_structure = category in (STRUCTURE_CATEGORIES - GROUND_CATEGORIES)
    
    return (not_blacklisted and whitelisted and valid_room) or is_building_structure
```

### 4.3 SegmentationMap

```python
# 房间分割地图提供:

# 1. 房间类型到实例的映射
seg_map.room_sem_name_to_ins_name
# {
#   "kitchen": ["kitchen_0"],
#   "bedroom": ["bedroom_0", "bedroom_1"],
#   "bathroom": ["bathroom_0"],
# }

# 2. 房间实例到ID的映射
seg_map.room_ins_name_to_ins_id
# {
#   "kitchen_0": 0,
#   "bedroom_0": 1,
#   "bedroom_1": 2,
# }

# 3. 栅格地图
seg_map.map  # [H, W] 每个像素的房间ID
```

## 5. 使用示例

### 5.1 创建简单场景

```python
import omnigibson as og
from omnigibson.scenes import Scene

# 初始化仿真器
og.sim.launch()

# 创建空场景
scene = Scene(
    scene_file=None,        # 无额外对象
    use_floor_plane=True,   # 使用平面地板
)

# 加载场景
scene.load(idx=0)

# 添加对象
from omnigibson.objects import DatasetObject
apple = DatasetObject(
    name="apple",
    category="apple",
    model="agveuv",
)
scene.add_object(apple)
apple.set_position([0, 0, 1])

# 查询对象
print("All objects:", scene.objects)
print("Find apple:", scene.object_registry("name", "apple"))
```

### 5.2 使用可导航场景

```python
from omnigibson.scenes import TraversableScene

scene = TraversableScene(
    scene_model="Rs_int",
    scene_file="path/to/scene.json",
    trav_map_resolution=0.1,
)
scene.load(idx=0)

# 获取随机导航点
random_point = scene.get_random_point(floor=0)
print("Random navigable point:", random_point)

# 路径规划
start = [1.0, 2.0]
goal = [5.0, 6.0]
path = scene.get_shortest_path(
    floor=0,
    source_world=start,
    target_world=goal,
    entire_path=True,
)
print("Path length:", len(path))
```

### 5.3 使用交互式场景 (BEHAVIOR-1K)

```python
from omnigibson.scenes import InteractiveTraversableScene

# 完整场景
scene = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_instance="0",  # 实例 ID
)

# 只加载厨房
scene = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_instance="0",
    load_room_types=["kitchen"],  # 只加载厨房
)

# 只加载特定类别
scene = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_instance="0",
    load_object_categories=["apple", "table"],  # 只加载苹果和桌子
)

# 只加载任务相关对象
scene = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_instance="0",
    load_task_relevant_only=True,  # 配合 task_metadata
)

# 查询房间
print("All rooms:", scene.seg_map.room_ins_name_to_ins_id.keys())
print("Kitchen objects:", scene.object_registry("in_rooms", "kitchen_0", []))
```

### 5.4 场景重置

```python
# 硬重置: 恢复到初始状态
scene.reset(hard=True)

# 软重置: 保持当前状态
scene.reset(hard=False)
```

### 5.5 对象过滤示例

```python
# 场景 JSON 文件示例
{
    "objects": [
        {
            "type": "DatasetObject",
            "args": {
                "name": "apple_1",
                "category": "apple",
                "model": "agveuv",
                "in_rooms": ["kitchen_0"],
                "fixed_base": false
            }
        },
        {
            "type": "DatasetObject",
            "args": {
                "name": "table_1",
                "category": "breakfast_table",
                "model": "rjgmmy",
                "in_rooms": ["kitchen_0"],
                "fixed_base": true
            }
        }
    ]
}

# 过滤示例
scene = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_file="path/to/scene.json",
    
    # 只加载可移动对象
    not_load_object_categories=["wall", "floor", "ceiling"],
    
    # 只加载厨房
    load_room_types=["kitchen"],
)
```

## 6. 高级特性

### 6.1 多场景管理

```python
# OmniGibson 支持同时加载多个场景

# 场景 0
scene_0 = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_instance="0",
)
scene_0.load(idx=0)

# 场景 1（自动偏移以避免重叠）
scene_1 = InteractiveTraversableScene(
    scene_model="Beechwood_1_int",
    scene_instance="0",
)
scene_1.load(
    idx=1,
    last_scene_edge=scene_0.get_last_scene_edge(),  # 上一个场景的右边缘
    scene_margin=5.0,  # 场景间距 (米)
)
```

### 6.2 系统使用

```python
# 获取水系统
water_system = scene.get_system("water", force_init=True)

# 生成水粒子
water_system.generate_particles(
    positions=[[0, 0, 1], [0, 0, 1.5]],
)

# 检查粒子数量
print("Water particles:", water_system.n_particles)
```

### 6.3 状态追踪

```python
# 获取状态更新的对象
updated_objects = scene.updated_state_objects
for obj in updated_objects:
    print(f"Object {obj.name} state changed")

# 清空追踪
scene.clear_updated_objects()
```

## 7. 性能优化

### 7.1 部分场景加载

```python
# 只加载必要的房间和对象
scene = InteractiveTraversableScene(
    scene_model="Rs_int",
    scene_instance="0",
    load_room_types=["kitchen"],          # 大幅减少加载时间
    load_task_relevant_only=True,         # 只加载任务对象
)
```

### 7.2 预构建缓存

```python
# 首次加载会预构建并缓存
scene.load(idx=0)  # 慢 (预构建)

# 后续加载相同场景会使用缓存
scene2.load(idx=1)  # 快 (使用缓存)
```

### 7.3 批量对象操作

```python
# 批量添加对象
objects = [obj1, obj2, obj3]
with og.sim.adding_objects(objs=objects):
    for obj in objects:
        scene.add_object(obj, _batched_call=True)
```

## 8. 总结

### 8.1 关键要点

1. **层次结构**: Scene → TraversableScene → InteractiveTraversableScene
2. **对象注册表**: 支持多种查询方式 (name, category, room, state)
3. **系统管理**: 粒子系统 (water, dust) 和布料
4. **导航支持**: TraversableMap 提供路径规划
5. **房间信息**: SegmentationMap 提供房间分割
6. **过滤机制**: 按类别、房间、任务相关性过滤对象

### 8.2 最佳实践

✅ 使用 `InteractiveTraversableScene` 进行 BEHAVIOR-1K 任务  
✅ 利用对象过滤减少加载时间  
✅ 使用 `load_task_relevant_only` 只加载必要对象  
✅ 通过 object_registry 高效查询对象  
✅ 利用预构建缓存加速重复加载  

Scene 系统是 OmniGibson 的核心，提供了灵活而强大的场景管理能力！
