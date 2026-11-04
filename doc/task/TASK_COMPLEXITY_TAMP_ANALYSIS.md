# BEHAVIOR Challenge 任务复杂度与TAMP需求分析

**日期**: 2026-10-11  
**目标**: 从TAMP角度分析BEHAVIOR-1K任务的复杂度和action需求

---

## 一、任务规模概览

### 总体统计
- **总任务数**: 1016个活动定义
- **最长任务**: `cook_seafood_paella` (204行BDDL)
- **复杂任务**: 164行+ BDDL的约20个任务

### 复杂度分类

| 复杂度 | 示例任务 | BDDL行数 | 特点 |
|--------|---------|---------|------|
| ⭐ 简单 | turning_on_radio | ~30 | 单一目标，1-3步 |
| ⭐⭐ 中等 | cleaning_up_plates_and_food | ~60 | 多对象，简单量词 |
| ⭐⭐⭐ 复杂 | making_a_meal | ~80 | 多步骤，需要烹饪 |
| ⭐⭐⭐⭐ 很复杂 | baking_cookies_for_the_PTA_bake_sale | ~90 | 配方，多个future对象 |
| ⭐⭐⭐⭐⭐ 极复杂 | cook_seafood_paella | 204 | 大量对象，复杂量词，多个烹饪步骤 |

---

## 二、最难任务深度分析

### 🏆 Top 5 最复杂任务

#### 1. cook_seafood_paella (204行)

**对象数量**: 42个对象
- 6个大虾 (prawn)
- 6个蛤蜊 (clam)
- 3个大蒜 (clove)
- 2个香肠 (chorizo)
- 多种调料和容器

**操作步骤**（推断）：
```
1. 从冰箱取出食材 (GRASP + NAVIGATE_TO × 多次)
2. 切菜 (需要CUT - 洋葱、大蒜、香肠)
3. 煮米饭 (需要PLACE + 加热)
4. 炒香料 (PLACE_NEAR_HEATING_ELEMENT)
5. 混合所有食材 (需要组合多个primitives)
6. 烹饪到cooked状态 (依赖TransitionRule)
```

**TAMP挑战**：
- ❌ **没有MIX primitive** - 需要组合PLACE动作模拟混合
- ❌ **没有CUT/DICE primitive** - 但有CUT primitive (需验证是否支持dice)
- ⚠️ **大量对象管理** - 需要追踪42个对象的状态
- ⚠️ **复杂的烹饪规则** - 依赖temperature和transition rules
- ⚠️ **顺序依赖** - 必须先煮米饭才能混合

**goal条件**（部分）：
```lisp
(:goal 
    (and 
        (real ?cooked__white_rice.n.01_1)  # 米饭必须煮熟
        (real ?cooked__diced__chorizo.n.01_1)  # 香肠必须切丁并煮熟
        (forall (?prawn.n.01 - prawn.n.01)  # 所有虾必须煮熟
            (cooked ?prawn.n.01)
        )
        (forall (?clam.n.03 - clam.n.03)  # 所有蛤蜊必须煮熟
            (cooked ?clam.n.03)
        )
        # ... 还有更多条件
    )
)
```

#### 2. set_up_a_buffet (164行)

**对象数量**: 22个对象
- 4个盘子 (plate)
- 4个餐巾 (napkin)
- 4个砂锅 (casserole)
- 多种食物和餐具

**操作步骤**：
```
1. 摆放盘子和餐具到餐桌
2. 折叠餐巾 (FOLD - 不在primitives中!)
3. 放置食物容器
4. 配对食物和餐具
```

**TAMP挑战**：
- ❌ **没有FOLD primitive** - 需要新增或组合
- ⚠️ **复杂量词**: forall + exists + forpairs
- ⚠️ **空间布局**: 需要合理摆放多个对象

**goal条件**：
```lisp
(forall (?napkin.n.01 - napkin.n.01)
    (and 
        (folded ?napkin.n.01)  # 需要FOLD action
        (ontop ?napkin.n.01 ?breakfast_table.n.01_1)
    )
)
(exists (?casserole.n.02 - casserole.n.02)
    (contains ?casserole.n.02 ?cooked__diced__broccoli.n.01_1)
)
```

#### 3. baking_cookies_for_the_PTA_bake_sale (120+行)

**对象数量**: 23个对象
- 6个饼干 (future对象!)
- 多种原料 (flour, sugar, eggs, butter)
- 烘焙工具

**操作步骤**：
```
1. 从容器中取出原料
2. 混合原料 (MIX - 需要electric_mixer)
3. 塑形饼干 (SHAPE - 不存在!)
4. 放入烤箱 (PLACE_INSIDE + TOGGLE_ON)
5. 等待烹饪 (依赖TransitionRule)
```

**TAMP挑战**：
- ❌ **没有MIX primitive** - 虽然有electric_mixer对象
- ❌ **没有SHAPE primitive** - 如何从面团变成饼干形状?
- ⚠️ **future对象** - 初始状态不存在，烹饪后出现
- ⚠️ **复杂的配方规则** - RecipeRule定义了如何混合

**关键发现**：
```lisp
(:init 
    (future sugar_cookie.n.01_1)  # 饼干一开始不存在!
    (future sugar_cookie.n.01_2)
    ...
)

(:goal 
    (and 
        (forall (?sugar_cookie.n.01 - sugar_cookie.n.01)
            (and 
                (real ?sugar_cookie.n.01)  # 必须变成real
                (cooked ?sugar_cookie.n.01)
            )
        )
    )
)
```

#### 4. assembling_furniture (40行，但概念复杂)

**对象数量**: 7个对象
- 1个桌面 (desk_top)
- 1个支架 (desk_bracket)
- 4个桌腿 (desk_leg)

**操作步骤**：
```
1. 拿起支架
2. 附着支架到桌面 (ATTACH - 不在primitives中!)
3. 拿起每个桌腿
4. 附着桌腿到支架 (ATTACH × 4)
```

**TAMP挑战**：
- ❌ **没有ATTACH primitive** - 这是关键操作!
- ⚠️ **需要工具** - 实际需要螺丝刀/扳手（BDDL中未定义）
- ⚠️ **顺序约束** - 必须先附着支架，再附着腿

**goal条件**：
```lisp
(:goal
    (and
        (attached ?desk_bracket.n.01_1 ?desk_top.n.01_1)
        (forall (?desk_leg.n.01 - desk_leg.n.01)
            (attached ?desk_leg.n.01 ?desk_bracket.n.01_1)
        )
    )
)
```

#### 5. making_a_meal (80行)

**对象数量**: 20个对象
- pasta, meatballs, marinara sauce
- 多个容器

**操作步骤**：
```
1. 煮意大利面 (PLACE_INSIDE pot + water + heat)
2. 煮肉丸 (PLACE_NEAR_HEATING_ELEMENT)
3. 加热酱料 (PLACE_NEAR_HEATING_ELEMENT)
4. 混合所有食材
5. 装盘
```

**TAMP挑战**：
- ⚠️ **future对象转换** - cooked__penne从future变real
- ⚠️ **复杂烹饪** - 需要理解多种加热方式
- ⚠️ **容器管理** - 需要使用正确的容器

---

## 三、缺失的Actions/Operators分析

### 3.1 明确缺失的High-Level Actions

基于任务分析，以下actions在primitives中**不存在**：

| Action | 需求任务 | 重要性 | 是否可组合 |
|--------|---------|--------|-----------|
| **FOLD** | set_up_buffet, folding_clothes | ⭐⭐⭐⭐ | ❌ 无法组合 |
| **ATTACH** | assembling_furniture | ⭐⭐⭐⭐⭐ | ❌ 需要新primitive |
| **MIX** | baking, cooking | ⭐⭐⭐⭐ | ⚠️ 可能通过recipe rule |
| **POUR** | pouring drinks, cooking | ⭐⭐⭐ | ✅ PLACE + physics |
| **SHAPE** | baking cookies | ⭐⭐ | ❌ 无法组合 |
| **SCREW/UNSCREW** | assembling_furniture | ⭐⭐⭐ | ❌ 需要新primitive |
| **SPREAD** | spreading butter | ⭐⭐ | ⚠️ 通过WIPE模拟 |
| **SLICE** | 切片面包等 | ⭐⭐⭐ | ✅ CUT primitive存在 |

### 3.2 现有Primitives的Gap

#### CUT vs DICE vs SLICE
```python
# 现有: CUT primitive
# 但BDDL区分:
- sliced (切片)
- diced (切丁) 
- cooked__diced__chorizo (切丁并煮熟)

# 问题: CUT primitive能否区分slice和dice?
```

#### PLACE vs ATTACH
```python
# PLACE_ON_TOP: 只是物理放置
# ATTACH: 需要固定连接（螺丝、胶水等）

# 在BDDL中:
(attached desk_leg desk_bracket)  # 不只是ontop!
```

#### GRASP vs FOLD
```python
# FOLD需要改变物体形状
# 不是简单的抓取或放置

# 在BDDL中:
(folded napkin)  # 物体状态改变
```

### 3.3 可以通过组合实现的Actions

| 宏操作 | 组合方式 | 可行性 |
|--------|---------|--------|
| **POUR(liquid, source, target)** | GRASP(source) + PLACE(target) + TILT | ✅ 可行 |
| **TRANSFER(obj, container1, container2)** | GRASP(obj) + PLACE_INSIDE(container2) | ✅ 可行 |
| **COOK(obj, method)** | PLACE_NEAR_HEATING_ELEMENT + WAIT | ⚠️ 依赖rules |
| **CLEAN(obj, tool)** | SOAK_UNDER(tool, water) + WIPE(obj, tool) | ✅ 可行 |
| **MIX(ingredients, container)** | 多次PLACE_INSIDE | ⚠️ 需要recipe rule |

---

## 四、Transition Rules的影响

### 4.1 关键Transition Rules

```python
# 1. CookingRule - 温度和时间触发
Temperature > COOKING_TEMP + Time > COOKING_TIME 
→ obj.cooked = True

# 2. SlicingRule - 碰撞触发
Knife.touching(obj) + Knife.slicerActive 
→ create sliced_obj

# 3. RecipeRule - 混合触发
Ingredients_set in Container + Heat 
→ create new_substance

# 4. MeltingRule - 温度触发
Temperature > MELTING_TEMP 
→ obj state change
```

### 4.2 对TAMP的影响

**问题**: Transition rules的效果是**间接的、延迟的**

**示例**：
```python
# 错误的理解:
Action: TOGGLE_ON(stove)
Effect: cooked(meatball)  # ❌ 不是直接效果!

# 正确的理解:
Action: TOGGLE_ON(stove)
Effect: heated(stove)
  → temperature(meatball) increases
  → after X seconds: cooked(meatball)  # 间接效果
```

**对action schema的影响**：
```python
"cook_food": {
    "parameters": ["?obj", "?heat_source"],
    "preconditions": [
        "inside(?obj, container)",
        "ontop(container, ?heat_source)",
        "not cooked(?obj)"
    ],
    "effects": [
        # 不能直接写 cooked(?obj)
        # 需要写成:
        "heated(?obj)",  # 立即效果
    ],
    "delayed_effects": [
        {"condition": "time > cooking_time", 
         "effect": "cooked(?obj)"}  # 延迟效果
    ],
    "requires_rule": "CookingRule"
}
```

---

## 五、是否需要生成新的Actions?

### 5.1 结论：**部分需要**

### 5.2 必须添加的Actions（高优先级）

#### 1. ATTACH (⭐⭐⭐⭐⭐ 必须)
```python
"attach": {
    "parameters": ["?obj1", "?obj2", "?tool"],
    "preconditions": [
        "grasped(?obj1, robot)",
        "near(robot, ?obj2)",
        "grasped(?tool, robot)"  # 需要螺丝刀
    ],
    "effects": [
        "attached(?obj1, ?obj2)",
        "not grasped(?obj1, robot)"
    ],
    "notes": "需要实现新primitive - 物理连接"
}
```

**为什么必须**：
- assembling_furniture等任务**核心操作**
- 无法通过现有primitives组合
- `attached`谓词与`ontop`语义完全不同

#### 2. FOLD (⭐⭐⭐⭐ 强烈建议)
```python
"fold": {
    "parameters": ["?cloth"],
    "preconditions": [
        "grasped(?cloth, robot)",
        "unfolded(?cloth)"
    ],
    "effects": [
        "folded(?cloth)",
        "not unfolded(?cloth)"
    ],
    "notes": "需要实现新primitive - 改变物体形状"
}
```

**为什么建议**：
- folding_clothes, set_up_buffet等任务需要
- 无法通过GRASP+PLACE模拟
- `folded`状态需要特殊操作

### 5.3 可选添加的Actions（中优先级）

#### 3. MIX (⭐⭐⭐ 建议)
```python
"mix": {
    "parameters": ["?container", "?tool"],
    "preconditions": [
        "grasped(?tool, robot)",
        "near(robot, ?container)",
        "contains(?container, ?ingredient1)",
        "contains(?container, ?ingredient2)"
    ],
    "effects": [
        # 触发RecipeRule
        "mixed(?container)"
    ],
    "requires_rule": "RecipeRule",
    "notes": "可能通过recipe rule自动触发"
}
```

**为什么可选**：
- RecipeRule可能自动处理混合
- 但显式MIX action更清晰

#### 4. SCREW/UNSCREW (⭐⭐ 可选)
```python
"screw": {
    "parameters": ["?screw", "?obj", "?screwdriver"],
    "preconditions": [
        "grasped(?screwdriver, robot)",
        "near(robot, ?obj)"
    ],
    "effects": [
        "screwed(?screw)",
        "attached(?screw, ?obj)"
    ]
}
```

### 5.4 不需要添加的Actions

#### POUR, CLEAN, TRANSFER
- ✅ 可以通过现有primitives组合
- 作为**宏操作**在planner层实现

```python
# 宏操作定义
MACRO_ACTIONS = {
    "pour": ["grasp(bottle)", "place_on_top(bottle, target)"],
    "clean": ["soak_under(sponge, water)", "wipe(plate, sponge)"],
    "transfer": ["grasp(obj)", "place_inside(obj, new_container)"]
}
```

---

## 六、Skeleton生成策略

### 6.1 简单任务（turning_on_radio）

**不需要特殊处理**：
```python
skeleton = [
    "navigate_to(radio)",
    "toggle_on(radio)"
]
```

### 6.2 中等任务（cleaning_up_plates）

**需要循环展开**：
```python
# LLM生成的抽象skeleton:
skeleton = [
    "foreach plate in plates:",
    "  grasp(plate)",
    "  place_inside(plate, sink)"
]

# 展开为具体skeleton:
skeleton = [
    "navigate_to(plate1)",
    "grasp(plate1)",
    "navigate_to(sink)",
    "place_inside(plate1, sink)",
    "navigate_to(plate2)",
    "grasp(plate2)",
    "navigate_to(sink)",
    "place_inside(plate2, sink)"
]
```

### 6.3 复杂任务（making_a_meal）

**需要子任务分解**：
```python
# 高层skeleton (子任务):
skeleton = [
    "cook_pasta()",
    "cook_meatballs()",
    "heat_sauce()",
    "combine_meal()"
]

# 每个子任务展开:
"cook_pasta" → [
    "grasp(pasta_box)",
    "open(pasta_box)",
    "grasp(pot)",
    "place_inside(pasta, pot)",
    "fill(pot, water)",
    "place_on_top(pot, stove)",
    "toggle_on(stove)",
    "wait(cooking_time)",
    ...
]
```

### 6.4 极复杂任务（cook_seafood_paella）

**需要分层规划**：

```python
# Level 1: 抽象目标
goals = [
    "prepare_ingredients",
    "cook_rice",
    "cook_seafood",
    "combine_paella"
]

# Level 2: 每个目标的子目标
"prepare_ingredients" → [
    "dice_chorizo",
    "clean_prawns",
    "clean_clams",
    "measure_spices"
]

# Level 3: 每个子目标的具体actions
"dice_chorizo" → [
    "navigate_to(fridge)",
    "open(fridge)",
    "grasp(chorizo)",
    "close(fridge)",
    "navigate_to(cutting_board)",
    "cut(chorizo)",  # 使用CUT primitive
    ...
]
```

---

## 七、对LLM Planner的影响

### 7.1 LLM需要理解的概念

#### 基础概念（已有）
- ✅ 空间关系 (ontop, inside, near)
- ✅ 基本操作 (grasp, place, open)
- ✅ 简单状态 (toggled_on, open, cooked)

#### 高级概念（需要教）
- ⚠️ **Transition rules** - 间接效果
- ⚠️ **Future对象** - 烹饪后出现
- ⚠️ **Recipe rules** - 混合规则
- ⚠️ **时间依赖** - 需要等待

### 7.2 Prompt Engineering策略

```python
# 在LLM prompt中添加:

## 高级Action说明
"""
某些复杂操作需要组合多个primitives:

1. COOK food:
   - place_inside(food, pot)
   - fill(pot, water)  # 如果需要
   - place_on_top(pot, stove)
   - toggle_on(stove)
   - [wait for transition rule to trigger]

2. CLEAN dish:
   - grasp(sponge)
   - soak_under(sponge, water)
   - wipe(dish, sponge)

3. ASSEMBLE furniture:
   ❌ NOT SUPPORTED - requires ATTACH primitive
   
4. FOLD cloth:
   ❌ NOT SUPPORTED - requires FOLD primitive
"""

## Transition Rules说明
"""
某些状态变化不是立即的:
- cooked: 需要时间和温度
- sliced: 需要切割动作完成
- mixed: 需要recipe rule触发
"""
```

### 7.3 任务筛选策略

**Phase 1: 支持的任务类型**
```python
SUPPORTED_TASKS = {
    "manipulation": ["navigate", "grasp", "place"],
    "simple_state_change": ["toggle_on", "open", "close"],
    "basic_cleaning": ["wipe", "soak"],
    "simple_cooking": ["heat without complex recipes"]
}
```

**Phase 2: 暂不支持的任务**
```python
UNSUPPORTED_TASKS = {
    "assembly": ["assembling_furniture"],  # 需要ATTACH
    "folding": ["folding_clothes"],  # 需要FOLD
    "complex_cooking": ["cook_seafood_paella"],  # 太复杂
    "baking": ["baking_cookies"],  # future对象+recipe
}
```

---

## 八、实施建议

### 8.1 优先级1：最小可行（1周）

**支持任务类型**：
- 简单manipulation（30%任务）
- 简单state change（20%任务）

**所需actions**：
- 现有14个primitives ✅
- 无需新增

**测试任务**：
```
turning_on_radio
opening_doors
turning_on_lamp
cleaning_pavement (简单版)
```

### 8.2 优先级2：扩展支持（2-3周）

**支持任务类型**：
- 中等complexity（+30%任务）
- 简单烹饪（+10%任务）

**所需actions**：
- 添加宏操作（CLEAN, POUR, TRANSFER）
- 理解transition rules

**测试任务**：
```
cleaning_up_plates_and_food
loading_the_dishwasher
making_a_simple_meal
```

### 8.3 优先级3：高级功能（1-2月）

**支持任务类型**：
- 组装任务（+5%任务）
- 折叠任务（+5%任务）

**所需actions**：
- ✅ 实现ATTACH primitive
- ✅ 实现FOLD primitive

**测试任务**：
```
assembling_furniture
folding_clothes
set_up_a_buffet
```

### 8.4 优先级4：复杂烹饪（长期）

**支持任务类型**：
- 复杂烹饪（+10%任务）

**所需actions**：
- MIX primitive或宏操作
- 完整理解recipe rules
- 处理future对象

**测试任务**：
```
making_a_meal
baking_cookies
cook_seafood_paella
```

---

## 九、结论

### 核心发现

1. **Primitives覆盖率**: 75-80%够用
   - 基础任务完全支持
   - 中等任务基本支持
   - 复杂任务需要扩展

2. **必须添加的Actions**: 2个
   - **ATTACH** (assembling任务必须)
   - **FOLD** (folding任务强烈建议)

3. **可以组合的宏操作**: 5+个
   - CLEAN, POUR, TRANSFER, COOK等
   - 在planner层实现

4. **最大挑战**: Transition Rules
   - 间接效果
   - 时间依赖
   - Recipe rules

### 实施路径

```
Week 1-2: 
  - ✅ 使用现有14个primitives
  - ✅ 测试30%简单任务
  - ✅ 验证LLM-TAMP框架

Week 3-4:
  - ✅ 添加宏操作
  - ✅ 理解transition rules
  - ✅ 测试50%+任务

Month 2:
  - ⚠️ 实现ATTACH和FOLD primitives
  - ⚠️ 支持70%+任务

Month 3+:
  - ⚠️ 处理复杂烹饪
  - ⚠️ 目标: 80-85%任务覆盖
```

### 最终建议

**不要试图支持所有1016个任务！**

**现实目标**：
- Phase 1: 300个简单任务 (30%)
- Phase 2: 500个中等任务 (50%)
- Phase 3: 700个任务 (70%)
- 80%+覆盖率已经是研究成果

**关键是**：
- ✅ 从简单开始
- ✅ 逐步扩展
- ✅ 优先验证LLM-TAMP方法可行性
- ✅ 不要被复杂任务阻塞
