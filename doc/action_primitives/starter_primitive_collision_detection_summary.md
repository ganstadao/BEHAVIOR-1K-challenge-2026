# StarterPrimitive 碰撞检测支持对象总结

## 问题回顾

你之前遇到的错误：
```
KeyError: '/World/scene_0/carpet_ctclvd_1/base_link'
File "omnigibson/utils/usd_utils.py", line 636, in get_contact_col_indices
```

**根本原因**: `carpet` 是 CLOTH 类型物体，不会被加入碰撞检测索引 `_PATH_TO_COL_IDX`。

---

## 一、支持的碰撞检测对象类型

### ✅ 支持: RIGID 类型物体 (PrimType.RIGID = 0)

**必须满足的条件**：
1. `obj.prim_type == PrimType.RIGID`
2. Link 是 `RigidDynamicPrim` 或 `RigidKinematicPrim`
3. `link.contact_reporting_enabled == True` (启用了 `PhysxContactReportAPI`)

**实现位置**: `OmniGibson/omnigibson/utils/usd_utils.py:285`
```python
for obj in scene.objects:
    if obj.prim_type == PrimType.RIGID:  # ← 只处理这个类型
        for link in obj.links.values():
            if isinstance(link, (RigidDynamicPrim, RigidKinematicPrim)) and link.contact_reporting_enabled:
                filters[scene_idx].append(link.prim_path)
```

### ❌ 不支持: CLOTH 类型物体 (PrimType.CLOTH = 1)

这些物体**完全不会**被加入碰撞检测系统。

---

## 二、可用于测试的对象列表

### 推荐的 RIGID 物体

#### 1. 小型可抓取物体
- ✅ `apple` - 苹果
- ✅ `orange` - 橙子  
- ✅ `banana` - 香蕉
- ✅ `bowl` - 碗
- ✅ `plate` - 盘子
- ✅ `cup` - 杯子
- ✅ `bottle` - 瓶子
- ✅ `mug` - 马克杯
- ✅ `fork` - 叉子
- ✅ `knife` - 刀
- ✅ `spoon` - 勺子

#### 2. 家具物体
- ✅ `table` - 桌子
- ✅ `chair` - 椅子
- ✅ `cabinet` - 柜子
- ✅ `shelf` - 架子
- ✅ `bookcase` - 书架
- ✅ `desk` - 书桌
- ✅ `countertop` - 台面

#### 3. 电器物体
- ✅ `microwave` - 微波炉
- ✅ `oven` - 烤箱
- ✅ `dishwasher` - 洗碗机
- ✅ `refrigerator` / `fridge` - 冰箱
- ✅ `stove` - 炉灶

#### 4. 门窗物体
- ✅ `door` - 门
- ✅ `window` - 窗户

#### 5. 地面（会被自动过滤）
- ✅ `floor` - 地板（在 `GROUND_CATEGORIES` 中，碰撞检测时自动忽略）

### ❌ 必须避免的 CLOTH 物体

- ❌ `carpet` - 地毯 ← **你遇到的问题**
- ❌ `rug` - 小地毯
- ❌ `curtain` - 窗帘
- ❌ `towel` - 毛巾
- ❌ `cloth` - 布料
- ❌ `blanket` - 毯子
- ❌ `sheet` - 床单
- ❌ `pillow` - 枕头
- ❌ `cushion` - 坐垫
- ❌ `tablecloth` - 桌布

### ⚠️ 可能包含 CLOTH 的复合物体

- ⚠️ `bed` - 床（可能有床单/枕头）
- ⚠️ `sofa` - 沙发（可能有坐垫）
- ⚠️ `chair` - 椅子（某些类型可能有坐垫）

这些物体的主体通常是 RIGID，但可能包含 CLOTH 子部件。

---

## 三、`_PATH_TO_COL_IDX` 工作流程

### 数据结构

```python
# 场景索引 → {prim_path → 列索引}
_PATH_TO_COL_IDX[scene_idx] = {
    '/World/scene_0/table_xyz_0/base_link': 0,
    '/World/scene_0/chair_abc_0/base_link': 1,
    '/World/scene_0/apple_def_0/base_link': 2,
    # ❌ carpet 不在这里！
}
```

### 碰撞矩阵结构

```
接触矩阵维度: (R, C)
- R = Dynamic rigid bodies 的数量（可主动移动）
- C = 所有 rigid bodies 的数量（Dynamic + Kinematic + Static）

           列 (所有 rigid bodies)
           ┌───────────────────────────┐
行 (Dyn)   │  Static  Kinematic  Dyn   │
           │    ✓         ✓        ✓    │
           └───────────────────────────┘

矩阵[i,j] = True 表示第 i 个 dynamic body 与第 j 个 body 接触
```

### 初始化流程

1. **收集过滤器** (`get_body_filters`):
   - 遍历场景中所有 RIGID 类型物体
   - 检查每个 link 是否启用 contact_reporting
   - 构建 prim path 列表

2. **创建接触视图** (`initialize_view`):
   ```python
   self._CONTACT_VIEW[scene_idx] = og.sim.physics_sim_view.create_rigid_contact_view(
       pattern=f"/World/scene_{scene_idx}/*/*",
       filter_patterns=scene_body_filters,
   )
   ```

3. **构建索引字典**:
   ```python
   self._PATH_TO_COL_IDX[scene_idx] = {path: i for i, path in enumerate(col_paths)}
   ```

### 运行时查询流程

```
detect_robot_collision_in_sim(robot)
    ↓
RigidContactAPI.is_in_contact(query_set=[robot], ignore_set=filter_objs)
    ↓
get_contact_col_indices(scene_idx, with_set)
    ↓
# 这里会抛出 KeyError，如果 path 不在字典中
return th.tensor([self._PATH_TO_COL_IDX[scene_idx][path] for path in prim_paths])
```

---

## 四、解决方案工具

### 1. 过滤脚本 - `filter_cloth_objects.py`

**功能**: 从场景配置 JSON 中移除所有 CLOTH 物体

**用法**:
```bash
python scripts/filter_cloth_objects.py \
    datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple.json \
    datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple_filtered.json
```

**输出示例**:
```
📖 读取场景配置: Rs_int_with_apple.json
  ❌ 移除 (state): carpet_ctclvd_0
  ❌ 移除 (state): carpet_ctclvd_1
  ❌ 移除 (state): towel_rack_kqrmrh_0
  ❌ 移除 (state): towel_rack_kqrmrh_1

============================================================
✅ 完成！
============================================================
保留物体数量: 77
移除物体数量: 4
```

### 2. 验证脚本 - `verify_scene_compatibility.py`

**功能**: 检查场景配置是否与 StarterPrimitives 兼容

**用法**:
```bash
python scripts/verify_scene_compatibility.py \
    datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple.json
```

**输出示例**:
```
============================================================
场景兼容性分析: Rs_int_with_apple.json
============================================================

📊 物体统计:
   总物体数: 81
   ✅ RIGID 物体: 75 (92.6%)
   ❌ CLOTH 物体: 4 (4.9%)

❌ 不兼容的 CLOTH 物体 (会导致 KeyError):
   - carpet_ctclvd_0 (category: carpet)
   - carpet_ctclvd_1 (category: carpet)
   - towel_rack_kqrmrh_0 (category: towel)
   - towel_rack_kqrmrh_1 (category: towel)

💡 解决方案:
   1. 使用过滤脚本移除 CLOTH 物体
   2. 使用过滤后的场景
============================================================
```

---

## 五、测试场景推荐

### 方案 1: 使用过滤后的场景配置 ✅ 推荐

```python
cfg = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
        "scene_file": "datasets/behavior-1k-assets/scenes/Rs_int/json/Rs_int_with_apple_filtered.json",
    }
}
```

**优点**:
- 包含完整的房间布局和家具
- 已移除所有 CLOTH 物体
- 可直接用于 StarterPrimitives

### 方案 2: 使用最小场景 + 动态添加物体

```python
cfg = {
    "scene": {
        "type": "InteractiveTraversableScene",
        "scene_model": "Rs_int",
        "scene_file": None,  # 使用默认空场景
    }
}

env = og.Environment(configs=cfg)
env.reset()

# 动态添加测试物体
from omnigibson.objects.dataset_object import DatasetObject

apple = DatasetObject(
    name="apple_0",
    category="apple",
    model="agveuv",
)
scene.add_object(apple)
apple.set_position([1.0, 0.0, 0.5])
```

**优点**:
- 完全可控的测试环境
- 保证所有物体都是 RIGID
- 适合单元测试

### 方案 3: 运行时检查和过滤

```python
from omnigibson.utils.constants import PrimType

# 在初始化 StarterPrimitives 之前检查
cloth_objects = [obj for obj in scene.objects if obj.prim_type == PrimType.CLOTH]

if cloth_objects:
    print(f"⚠️ 场景包含 {len(cloth_objects)} 个 CLOTH 物体:")
    for obj in cloth_objects:
        print(f"  - {obj.name} (category: {obj.category})")
    print("建议使用过滤后的场景配置")
```

---

## 六、调试技巧

### 1. 列出所有物体及其类型

```python
from omnigibson.utils.constants import PrimType

print("\n=== 场景物体类型分析 ===")
for obj in scene.objects:
    prim_type_name = "RIGID" if obj.prim_type == PrimType.RIGID else "CLOTH"
    print(f"{prim_type_name:6} | {obj.name:30} | {obj.category}")
```

### 2. 验证碰撞检测索引

```python
from omnigibson.utils.usd_utils import RigidContactAPI

scene_idx = robot.scene.idx

if scene_idx in RigidContactAPI._PATH_TO_COL_IDX:
    col_paths = RigidContactAPI._COL_IDX_TO_PATH[scene_idx]
    print(f"\n碰撞检测索引包含 {len(col_paths)} 个物体")
    
    # 检查特定物体是否在索引中
    carpet = scene.object_registry("category", "carpet", [])
    if carpet:
        carpet_obj = list(carpet)[0]
        for link in carpet_obj.links.values():
            in_index = link.prim_path in RigidContactAPI._PATH_TO_COL_IDX[scene_idx]
            print(f"  {'✅' if in_index else '❌'} {link.prim_path}")
```

### 3. 测试特定物体的碰撞检测

```python
def test_collision_detection(obj, robot):
    """测试物体是否可用于碰撞检测"""
    from omnigibson.utils.usd_utils import RigidContactAPI
    
    scene_idx = robot.scene.idx
    
    print(f"\n测试物体: {obj.name}")
    print(f"  prim_type: {obj.prim_type} ({'RIGID' if obj.prim_type == 0 else 'CLOTH'})")
    
    for link_name, link in obj.links.items():
        path = link.prim_path
        in_index = path in RigidContactAPI._PATH_TO_COL_IDX.get(scene_idx, {})
        contact_enabled = link.contact_reporting_enabled
        
        print(f"  Link: {link_name}")
        print(f"    Path: {path}")
        print(f"    在索引中: {'✅' if in_index else '❌'}")
        print(f"    Contact reporting: {'✅' if contact_enabled else '❌'}")

# 使用
apple = scene.object_registry("category", "apple", [])[0]
test_collision_detection(apple, robot)
```

---

## 七、代码参考位置

| 功能 | 文件路径 | 行号 |
|------|---------|------|
| 碰撞检测 API | `OmniGibson/omnigibson/utils/usd_utils.py` | 216 |
| 过滤器构建 | `OmniGibson/omnigibson/utils/usd_utils.py` | 274 |
| 索引字典构建 | `OmniGibson/omnigibson/utils/usd_utils.py` | 375 |
| KeyError 位置 | `OmniGibson/omnigibson/utils/usd_utils.py` | 636 |
| 运动规划碰撞检测 | `OmniGibson/omnigibson/utils/motion_planning_utils.py` | 519 |
| PrimType 定义 | `OmniGibson/omnigibson/utils/constants.py` | 78 |
| contact_reporting 属性 | `OmniGibson/omnigibson/prims/rigid_prim.py` | 429 |

---

## 八、快速参考

### 检查场景是否兼容

```bash
python scripts/verify_scene_compatibility.py <scene.json>
```

### 过滤场景配置

```bash
python scripts/filter_cloth_objects.py <input.json> <output.json>
```

### 更新测试代码使用过滤后的场景

```python
cfg = {
    "scene": {
        "scene_file": "path/to/scene_filtered.json",  # ← 使用 _filtered 版本
    }
}
```

### 运行测试

```bash
cd tests
bash test_primitives_grasp.sh
```

---

## 总结

1. **只有 RIGID 类型物体支持碰撞检测**
2. **CLOTH 物体（如 carpet）会导致 KeyError**
3. **使用提供的工具过滤场景配置**
4. **测试前验证场景兼容性**
5. **优先使用已知的 RIGID 物体进行测试**

**更新后的场景文件**:
- ✅ `Rs_int_with_apple_filtered.json` - 已移除 4 个 CLOTH 物体（2 个 carpet，2 个 towel_rack）
- ✅ 保留 77 个 RIGID 物体，可安全用于 StarterPrimitives 测试
