# StarterPrimitive 碰撞检测系统详解

## 概述

StarterSemanticActionPrimitives 使用 `RigidContactAPI` 进行碰撞检测，该系统通过接触矩阵追踪所有刚体之间的碰撞。理解这个系统对于调试运动规划问题至关重要。

## 支持的对象类型

### ✅ 支持的对象 (RIGID)

只有 **`PrimType.RIGID`** 类型的物体会被加入碰撞检测索引：

```python
# 从 omnigibson/utils/usd_utils.py:285
for obj in scene.objects:
    if obj.prim_type == PrimType.RIGID:  # ← 只处理 RIGID 类型
        for link in obj.links.values():
            if isinstance(link, (RigidDynamicPrim, RigidKinematicPrim)) and link.contact_reporting_enabled:
                filters[scene_idx].append(link.prim_path)
```

**必要条件**：
1. `obj.prim_type == PrimType.RIGID` (值为 0)
2. Link 是 `RigidDynamicPrim` 或 `RigidKinematicPrim`
3. `link.contact_reporting_enabled == True` (有 `PhysxContactReportAPI`)

**常见 RIGID 物体**：
- 可抓取物体：`apple`, `orange`, `banana`, `bowl`, `plate`, `cup`, `bottle`
- 家具：`table`, `chair`, `cabinet`, `shelf`, `bookcase`
- 电器：`microwave`, `oven`, `dishwasher`, `refrigerator`
- 门窗：`door`, `window`

### ❌ 不支持的对象 (CLOTH)

**`PrimType.CLOTH`** 类型的物体**不会**被加入碰撞检测索引：

**常见 CLOTH 物体**：
- `carpet` (地毯) ← 你遇到的问题
- `rug` (小地毯)
- `curtain` (窗帘)
- `towel` (毛巾)
- `cloth` (布料)
- `blanket` (毯子)
- `pillow` (枕头)
- `tablecloth` (桌布)

## 碰撞检测数据结构

### `_PATH_TO_COL_IDX` 字典

这是核心索引字典，将物体的 prim path 映射到碰撞矩阵的列索引：

```python
# 从 omnigibson/utils/usd_utils.py:375
self._PATH_TO_COL_IDX[scene_idx] = {path: i for i, path in enumerate(col_paths)}

# 示例：
{
    '/World/scene_0/table_xyz_0/base_link': 0,
    '/World/scene_0/chair_abc_0/base_link': 1,
    '/World/scene_0/apple_def_0/base_link': 2,
    # ❌ carpet 不在这里！
}
```

### 接触矩阵 (Contact Matrix)

接触矩阵是一个 2D 布尔矩阵，追踪所有刚体对之间的接触：

```
       列 (所有 rigid bodies)
       ┌─────────────────────────┐
行     │  Static  Kinematic  Dyn │
(Dyn)  │    ✓         ✓        ✓  │
       └─────────────────────────┘
```

**矩阵维度**：
- **行 (Rows)**: 只包含 **Dynamic** rigid bodies (可主动移动的物体)
- **列 (Columns)**: 包含 **所有** rigid bodies (Dynamic + Kinematic + Static)
- **值**: `True` = 有接触，`False` = 无接触

**索引映射**：
```python
self._ROW_IDX_TO_PATH[scene_idx]  # 行索引 → prim path
self._COL_IDX_TO_PATH[scene_idx]  # 列索引 → prim path
self._PATH_TO_ROW_IDX[scene_idx]  # prim path → 行索引
self._PATH_TO_COL_IDX[scene_idx]  # prim path → 列索引 ← KeyError 发生在这里
```

## 碰撞检测流程

### 1. 初始化阶段 (`initialize_view`)

```python
# omnigibson/utils/usd_utils.py:299
def initialize_view(self):
    # 1. 收集所有启用碰撞报告的 RIGID 物体
    body_filters = self.get_body_filters()
    
    # 2. 创建接触视图 (Contact View)
    self._CONTACT_VIEW[scene_idx] = og.sim.physics_sim_view.create_rigid_contact_view(
        pattern=f"/World/scene_{scene_idx}/*/*",
        filter_patterns=scene_body_filters,
    )
    
    # 3. 构建索引字典
    self._PATH_TO_COL_IDX[scene_idx] = {path: i for i, path in enumerate(col_paths)}
    
    # 4. 初始化接触矩阵
    self._CONTACT_MATRIX[scene_idx] = initial_contacts.clone()
```

### 2. 运行时碰撞检测

```python
# 调用链：
detect_robot_collision_in_sim(robot)
    ↓
RigidContactAPI.is_in_contact(query_set=[robot], with_set=None, ignore_set=filter_objs)
    ↓
get_contact_col_indices(scene_idx, with_set)
    ↓
# omnigibson/utils/usd_utils.py:636
return th.tensor([self._PATH_TO_COL_IDX[scene_idx][path] for path in prim_paths])
    ↑
    ❌ KeyError: '/World/scene_0/carpet_ctclvd_1/base_link'
    如果 path 不在字典中，抛出 KeyError
```

### 3. 每个物理步更新

```python
# 每个物理步 (在 simulator.step() 中)
add_contacts_from_physics_step()
    # 收集接触力矩阵和物体变换
    impulses = self._CONTACT_VIEW[scene_idx].get_contact_force_matrix(dt=1.0)
    self._PENDING_IMPULSES[scene_idx].append(impulses)

# 每个非物理步 (在 env.step() 中)  
update_contact_cache()
    # 批量处理挂起的接触数据
    # 更新 _CONTACT_MATRIX 和 _CURRENT_CONTACT_MATRIX
```

## 常见错误和解决方案

### 错误 1: KeyError in `_PATH_TO_COL_IDX`

```
KeyError: '/World/scene_0/carpet_ctclvd_1/base_link'
File "omnigibson/utils/usd_utils.py", line 636, in get_contact_col_indices
```

**原因**：场景中有 CLOTH 类型物体（如 carpet），但它不在碰撞检测索引中。

**解决方案**：

1. **使用过滤脚本移除 CLOTH 物体**：
```bash
python scripts/filter_cloth_objects.py \
    datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple.json \
    datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple_filtered.json
```

2. **使用清理后的场景配置**：
```python
cfg = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
        "scene_file": "datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple_filtered.json",
    }
}
```

3. **手动检查物体类型**：
```python
from omnigibson.utils.constants import PrimType

for obj in scene.objects:
    if obj.prim_type == PrimType.CLOTH:
        print(f"⚠️ CLOTH object (not in collision index): {obj.name}")
    elif obj.prim_type == PrimType.RIGID:
        print(f"✅ RIGID object (in collision index): {obj.name}")
```

### 错误 2: 视图重建期间的数据丢失

当添加或移除物体时，`initialize_view` 会重建接触视图。旧的接触数据会尽可能保留，但如果在物理步期间重建，挂起的数据可能丢失。

**解决方案**：在非物理步期间添加/移除物体。

## 测试用例建议

### 推荐：简单测试场景

```python
# 最小化场景，只包含必需的 RIGID 物体
cfg = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
        "scene_file": None,  # 使用默认场景
    }
}

env = og.Environment(configs=cfg)
env.reset()

# 动态添加测试物体
apple = DatasetObject(
    name="apple_0",
    category="apple",
    model="agveuv",
)
scene.add_object(apple)
apple.set_position([1.0, 0.0, 0.5])
```

### 推荐：已过滤的场景

```python
# 使用过滤后的场景配置（移除了所有 CLOTH 物体）
cfg = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
        "scene_file": "datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple_filtered.json",
    }
}
```

### ❌ 避免：包含 CLOTH 物体的场景

```python
# 这会导致 KeyError，因为 carpet 不在碰撞索引中
cfg = {
    "scene": {
        "scene_file": "datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple.json",  # ← 包含 carpet
    }
}
```

## 调试技巧

### 1. 列出场景中的所有物体类型

```python
from omnigibson.utils.constants import PrimType

print("\n=== Scene Objects by Type ===")
rigid_objs = []
cloth_objs = []

for obj in scene.objects:
    if obj.prim_type == PrimType.RIGID:
        rigid_objs.append(obj.name)
    elif obj.prim_type == PrimType.CLOTH:
        cloth_objs.append(obj.name)

print(f"\n✅ RIGID objects ({len(rigid_objs)}):")
for name in sorted(rigid_objs):
    print(f"  - {name}")

print(f"\n❌ CLOTH objects ({len(cloth_objs)}):")
for name in sorted(cloth_objs):
    print(f"  - {name}")
```

### 2. 验证碰撞检测索引

```python
from omnigibson.utils.usd_utils import RigidContactAPI

scene_idx = robot.scene.idx

# 检查索引是否已初始化
if scene_idx in RigidContactAPI._PATH_TO_COL_IDX:
    col_paths = RigidContactAPI._COL_IDX_TO_PATH[scene_idx]
    print(f"\n碰撞检测索引包含 {len(col_paths)} 个物体:")
    for i, path in enumerate(col_paths[:10]):  # 只显示前 10 个
        print(f"  [{i}] {path}")
else:
    print("❌ 碰撞检测索引未初始化")
```

### 3. 测试特定物体的碰撞

```python
# 检查物体是否在碰撞索引中
def check_object_in_collision_index(obj, scene_idx):
    from omnigibson.utils.usd_utils import RigidContactAPI
    
    for link in obj.links.values():
        path = link.prim_path
        if path in RigidContactAPI._PATH_TO_COL_IDX.get(scene_idx, {}):
            print(f"✅ {obj.name}/{link.name} 在碰撞索引中")
        else:
            print(f"❌ {obj.name}/{link.name} 不在碰撞索引中")
            print(f"   - prim_type: {obj.prim_type}")
            print(f"   - link type: {type(link).__name__}")
            print(f"   - contact_reporting: {link.contact_reporting_enabled}")

# 使用
target_obj = scene.object_registry("name", "carpet_ctclvd_0")
if target_obj:
    check_object_in_collision_index(target_obj[0], robot.scene.idx)
```

## 参考代码位置

- **碰撞检测 API**: `OmniGibson/omnigibson/utils/usd_utils.py:216` (`RigidContactAPIImpl`)
- **过滤器构建**: `OmniGibson/omnigibson/utils/usd_utils.py:274` (`get_body_filters`)
- **索引字典构建**: `OmniGibson/omnigibson/utils/usd_utils.py:375`
- **KeyError 位置**: `OmniGibson/omnigibson/utils/usd_utils.py:636` (`get_contact_col_indices`)
- **运动规划碰撞检测**: `OmniGibson/omnigibson/utils/motion_planning_utils.py:519` (`detect_robot_collision_in_sim`)
- **PrimType 定义**: `OmniGibson/omnigibson/utils/constants.py:78`

## 总结

- ✅ **只有 RIGID 类型物体会被加入碰撞检测索引**
- ❌ **CLOTH 类型物体（如 carpet）不支持碰撞检测**
- 🔧 **使用 `filter_cloth_objects.py` 脚本清理场景配置**
- 🧪 **测试时使用过滤后的场景或手动验证物体类型**
