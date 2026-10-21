# 不使用 LLM 的 Skeleton 生成方法

> **核心问题**：BDDL 不提供 action 定义，如何在不使用 LLM 的情况下生成 skeleton（subgoal 序列）？
>
> **答案**：利用 OmniGibson 提供的多种预定义资源进行**反向规划**或**规则匹配**。

---

## 目录

1. [OmniGibson 提供的预定义资源](#omnigibson-提供的预定义资源)
2. [方法 1：基于 Object States 的反向搜索](#方法-1基于-object-states-的反向搜索)
3. [方法 2：基于 Transition Rules 的正向匹配](#方法-2基于-transition-rules-的正向匹配)
4. [方法 3：基于 Action Primitives 的模板匹配](#方法-3基于-action-primitives-的模板匹配)
5. [方法 4：混合方法（最实用）](#方法-4混合方法最实用)
6. [完整实现示例](#完整实现示例)
7. [对比总结](#对比总结)

---

## OmniGibson 提供的预定义资源

OmniGibson 虽然没有完整的 PDDL action 定义，但提供了丰富的**隐式知识**：

### 1. Object States（对象状态系统）

**位置**：`OmniGibson/omnigibson/object_states/`

每个 state 都隐式定义了 preconditions 和 effects：

```python
# ==================== 对象状态示例 ====================
from omnigibson.object_states import ToggledOn, OnTop, Inside, Cooked

# 每个 state 都有：
# - get_value(): 查询当前状态
# - set_value(): 设置状态（隐式定义了如何达到该状态）

# ToggledOn 状态
class ToggledOn(AbsoluteObjectState):
    """
    隐式 precondition: 对象必须有 toggleable 能力
    隐式 effect: 对象的开关状态改变
    隐式 action: toggle_on/toggle_off
    """
    
    @staticmethod
    def get_dependencies():
        # 依赖其他 states（隐式 preconditions）
        return AbsoluteObjectState.get_dependencies() + [AABB]
    
    def _set_value(self, new_value):
        # 如何达到这个状态（隐式 action）
        # ...

# OnTop 状态
class OnTop(RelativeObjectState):
    """
    隐式 precondition: obj1 必须可移动，obj2 必须有表面
    隐式 effect: obj1 在 obj2 上方
    隐式 action: place_on_top (如果拿着 obj1)
                 或 grasp + place_on_top (如果没拿)
    """
    
    def _set_value(self, other, new_value):
        # 如何将 obj1 放到 obj2 上（隐式 action sequence）
        # ...
```

**关键洞察**：每个 state 的 `set_value()` 方法隐式定义了达到该状态所需的 action！

### 2. Action Primitives（动作原语）

**位置**：`OmniGibson/omnigibson/action_primitives/`

每个 primitive 都有**隐式的 preconditions 和 effects**：

```python
# ==================== Action Primitives 的隐式定义 ====================
class StarterSemanticActionPrimitives:
    
    def _grasp(self, obj):
        """
        隐式 preconditions:
        - robot 必须在 obj 附近
        - robot 的手必须是空的
        - obj 必须是可抓取的
        
        隐式 effects:
        - robot 持有 obj
        - obj 不再在原位置
        """
        # 代码中有隐式检查
        if not self._get_obj_in_hand() is None:
            raise ActionPrimitiveError("Hand not empty")
        
        # ... 执行抓取
    
    def _place_on_top(self, obj):
        """
        隐式 preconditions:
        - robot 必须持有某个对象
        - robot 必须在 obj 附近
        - obj 必须有可放置的表面
        
        隐式 effects:
        - 被持有的对象现在在 obj 上
        - robot 的手变空
        """
        held_obj = self._get_obj_in_hand()
        if held_obj is None:
            raise ActionPrimitiveError("Not holding any object")
        
        # ... 执行放置
    
    def _toggle_on(self, obj):
        """
        隐式 preconditions:
        - robot 必须在 obj 附近
        - obj 必须有 toggleable 能力
        
        隐式 effects:
        - obj.states[ToggledOn] = True
        """
        # ... 执行开关
```

### 3. Transition Rules（状态转换规则）

**位置**：`OmniGibson/omnigibson/transition_rules.py` + `bddl3/bddl/transition_rules.py`

定义了对象如何通过物理交互改变状态：

```python
# ==================== Transition Rules 示例 ====================
from bddl.knowledge_base import CookingRecipe, MachineRecipe, MixingRecipe

# CookingRecipe: 烹饪规则
recipe = CookingRecipe(
    name="dough_to_cookie",
    input_synsets={"dough.n.01": 1},                    # 输入：面团
    output_synsets={"cookie.n.01": 5},                  # 输出：5 个饼干
    container_synsets={"cookie_sheet.n.01"},            # 需要：烤盘
    heatsource_synsets={"oven.n.01"},                   # 需要：烤箱
    timesteps=100,                                      # 需要：100 步加热
    input_states={
        "dough.n.01": [StateCondition(OnTop, True)]    # 面团必须在烤盘上
    },
    output_states={
        "cookie.n.01": [StateCondition(Cooked, True)]  # 饼干是熟的
    }
)

# MachineRecipe: 机器规则
recipe = MachineRecipe(
    name="ground_coffee_to_coffee",
    input_synsets={"ground_coffee.n.01": 1, "water.n.06": 1},
    output_synsets={"coffee.n.01": 1},
    machine_synsets={"coffee_maker.n.01"}
)

# 从 Recipe 可以推导出 action sequence:
# 1. 把 input 放进 container/machine
# 2. 如果是 CookingRecipe：打开 heatsource
# 3. 如果是 MachineRecipe：toggle_on machine
# 4. 等待 timesteps
# 5. 取出 output
```

**关键洞察**：Transition Rules 定义了**复杂任务的子目标结构**！

### 4. Knowledge Base（知识库）

**位置**：`bddl3/bddl/knowledge_base/`

包含大量预定义的语义信息：

```python
# ==================== Knowledge Base 内容 ====================
from omnigibson.utils.bddl_utils import get_knowledge_base

kb = get_knowledge_base()

# 对象的能力（abilities）
abilities = kb.get_abilities("radio_receiver.n.01")
# {
#     "toggleable": True,        # 可以 toggle
#     "heatSource": False,
#     "coldSource": False,
#     # ...
# }

# 对象的状态（states）
states = kb.get_states("apple.n.01")
# {
#     "sliceable": True,         # 可以切
#     "cookable": True,          # 可以煮
#     "freezable": True,
#     # ...
# }

# 对象的分类（taxonomy）
parent = kb.get_parent_synset("radio_receiver.n.01")
# "receiver.n.01" → 更通用的类别

children = kb.get_children_synsets("appliance.n.01")
# ["radio.n.01", "toaster.n.01", ...] → 具体的子类

# 所有 recipes
recipes = kb.get_all_recipes()
# [CookingRecipe(...), MachineRecipe(...), ...]
```

**关键洞察**：Knowledge Base 告诉我们**对象能做什么**，从而推断**需要什么 actions**！

---

## 方法 1：基于 Object States 的反向搜索

**核心思想**：从目标状态反向推导，找到达到该状态所需的 actions。

### 算法：Backward Chaining

```python
# ==================== 反向链接算法 ====================
from omnigibson.object_states import *
from omnigibson.utils.bddl_utils import get_knowledge_base

class BackwardPlanner:
    """基于 Object States 的反向规划器"""
    
    def __init__(self, env):
        self.env = env
        self.kb = get_knowledge_base()
        
        # 构建 state → actions 映射
        self.state_to_actions = self._build_state_action_map()
    
    def _build_state_action_map(self):
        """构建状态到动作的映射"""
        return {
            # 一元状态 → 需要的 actions
            ToggledOn: ["navigate_to", "toggle_on"],
            Open: ["navigate_to", "open"],
            Cooked: ["navigate_to", "grasp", "place_inside", "toggle_on"],  # 需要烤箱
            Sliced: ["navigate_to", "grasp_knife", "slice"],
            
            # 二元状态 → 需要的 actions
            OnTop: ["navigate_to", "grasp", "navigate_to", "place_on_top"],
            Inside: ["navigate_to", "grasp", "navigate_to", "open", "place_inside"],
            # ... 更多
        }
    
    def plan(self, initial_state, goal_state):
        """从目标反向规划到初始状态"""
        subgoals = []
        current_state = goal_state
        
        while not self._state_matches(current_state, initial_state):
            # 找到一个未满足的目标谓词
            unsatisfied_atom = self._find_unsatisfied(current_state, initial_state)
            
            if unsatisfied_atom is None:
                break  # 所有目标已满足
            
            # 反向推导需要的 actions
            actions = self._get_actions_for_atom(unsatisfied_atom)
            
            # 添加到 subgoals（反向添加）
            subgoals = actions + subgoals
            
            # 更新当前状态（添加 actions 的 preconditions）
            current_state = self._regress(current_state, actions)
        
        return subgoals
    
    def _get_actions_for_atom(self, atom):
        """获取达到某个谓词所需的 actions"""
        predicate_name, entities = atom
        
        # 查找对应的 state class
        state_class = PREDICATE_TO_STATE[predicate_name]
        
        # 查找需要的 actions
        action_template = self.state_to_actions[state_class]
        
        # 实例化 actions
        actions = []
        for action_type in action_template:
            if action_type == "navigate_to":
                actions.append(Subgoal(
                    action_type="navigate_to",
                    target_object=entities[0]
                ))
            elif action_type == "grasp":
                actions.append(Subgoal(
                    action_type="grasp",
                    target_object=entities[0]
                ))
            elif action_type == "toggle_on":
                actions.append(Subgoal(
                    action_type="toggle_on",
                    target_object=entities[0]
                ))
            # ... 更多
        
        return actions
    
    def _regress(self, state, actions):
        """回归：从状态和 actions 推导 preconditions"""
        new_state = state.copy()
        
        # 为每个 action 添加其 preconditions
        for action in reversed(actions):
            if action.action_type == "grasp":
                # grasp 的 precondition: 手是空的，在对象附近
                new_state.add(Atom("hands_empty", ("robot",)))
                new_state.add(Atom("near", ("robot", action.target_object)))
            
            elif action.action_type == "place_on_top":
                # place 的 precondition: 持有对象，在目标附近
                new_state.add(Atom("holding", ("robot", "?obj")))
                new_state.add(Atom("near", ("robot", action.target_object)))
            
            # ... 更多
        
        return new_state

# ==================== 使用示例 ====================
planner = BackwardPlanner(env)

initial_state = {
    Atom("not_toggled_on", ("radio",)),
    Atom("ontop", ("radio", "table")),
    Atom("not_near", ("robot", "radio")),
}

goal_state = {
    Atom("toggled_on", ("radio",))
}

# 反向规划
subgoals = planner.plan(initial_state, goal_state)
# 结果：
# [
#     Subgoal(action_type="navigate_to", target_object="radio"),
#     Subgoal(action_type="toggle_on", target_object="radio")
# ]
```

### 优势和劣势

✅ **优势**：
- 逻辑清晰，易于理解
- 不需要 LLM
- 可以处理简单的单目标任务

❌ **劣势**：
- 状态空间可能很大（搜索效率低）
- 需要手动定义 state → actions 映射
- 难以处理多个子目标的依赖关系
- 需要准确的 precondition 和 effect 定义

---

## 方法 2：基于 Transition Rules 的正向匹配

**核心思想**：如果目标涉及对象转换（如烹饪），直接从 Transition Rules 推导 action sequence。

### 算法：Recipe-based Planning

```python
# ==================== 基于 Recipe 的规划 ====================
from bddl.knowledge_base import CookingRecipe, MachineRecipe

class RecipePlanner:
    """基于 Transition Rules 的规划器"""
    
    def __init__(self, env):
        self.env = env
        self.kb = get_knowledge_base()
        self.recipes = self.kb.get_all_recipes()
    
    def plan(self, initial_state, goal_state):
        """检查目标是否涉及对象转换，使用对应的 recipe"""
        subgoals = []
        
        # 1. 检测目标中是否有 "产物" 对象
        goal_objects = self._extract_objects(goal_state)
        initial_objects = self._extract_objects(initial_state)
        
        # 新出现的对象 = 需要生成的对象
        new_objects = goal_objects - initial_objects
        
        if new_objects:
            # 2. 查找生成这些对象的 recipe
            for new_obj_synset in new_objects:
                recipe = self._find_recipe_for_output(new_obj_synset)
                
                if recipe:
                    # 3. 从 recipe 生成 action sequence
                    subgoals.extend(self._recipe_to_actions(recipe))
        
        # 4. 处理非转换目标（状态改变）
        for atom in goal_state:
            if not self._is_transformation(atom):
                # 使用反向规划处理普通目标
                subgoals.extend(self._plan_for_atom(atom))
        
        return subgoals
    
    def _find_recipe_for_output(self, output_synset):
        """查找生成特定对象的 recipe"""
        for recipe in self.recipes:
            if output_synset in recipe.output_synsets:
                return recipe
        return None
    
    def _recipe_to_actions(self, recipe):
        """将 recipe 转换为 action sequence"""
        subgoals = []
        
        if isinstance(recipe, CookingRecipe):
            # ==================== 烹饪 Recipe ====================
            # 步骤：
            # 1. 获取所有输入材料
            # 2. 获取容器
            # 3. 将材料放入容器
            # 4. 将容器放入热源
            # 5. 打开热源
            # 6. 等待
            # 7. 取出容器
            
            inputs = list(recipe.input_synsets.keys())
            container = list(recipe.container_synsets)[0]
            heatsource = list(recipe.heatsource_synsets)[0]
            
            # 1. 获取每个输入
            for input_synset in inputs:
                # 找到场景中的实例
                input_obj = self._find_object_of_type(input_synset)
                
                subgoals.extend([
                    Subgoal("navigate_to", input_obj),
                    Subgoal("grasp", input_obj),
                ])
            
            # 2. 获取容器
            container_obj = self._find_object_of_type(container)
            subgoals.extend([
                Subgoal("navigate_to", container_obj),
            ])
            
            # 3. 放入材料
            for input_synset in inputs:
                input_obj = self._find_object_of_type(input_synset)
                subgoals.append(
                    Subgoal("place_on_top", target=container_obj, obj=input_obj)
                )
            
            # 4. 将容器放入热源
            heatsource_obj = self._find_object_of_type(heatsource)
            subgoals.extend([
                Subgoal("grasp", container_obj),
                Subgoal("navigate_to", heatsource_obj),
                Subgoal("open", heatsource_obj),  # 打开烤箱门
                Subgoal("place_inside", heatsource_obj, container_obj),
                Subgoal("close", heatsource_obj),
            ])
            
            # 5. 打开热源
            subgoals.append(
                Subgoal("toggle_on", heatsource_obj)
            )
            
            # 6. 等待（隐式，在执行时处理）
            # timesteps = recipe.timesteps
            
            # 7. 取出（如果需要）
            # subgoals.extend([
            #     Subgoal("toggle_off", heatsource_obj),
            #     Subgoal("open", heatsource_obj),
            #     Subgoal("grasp", container_obj),
            #     ...
            # ])
        
        elif isinstance(recipe, MachineRecipe):
            # ==================== 机器 Recipe ====================
            # 步骤：
            # 1. 获取所有输入
            # 2. 将输入放入机器
            # 3. 打开机器
            # 4. 等待
            # 5. 取出输出
            
            inputs = list(recipe.input_synsets.keys())
            machine = list(recipe.machine_synsets)[0]
            machine_obj = self._find_object_of_type(machine)
            
            for input_synset in inputs:
                input_obj = self._find_object_of_type(input_synset)
                subgoals.extend([
                    Subgoal("navigate_to", input_obj),
                    Subgoal("grasp", input_obj),
                    Subgoal("navigate_to", machine_obj),
                    Subgoal("place_inside", machine_obj, input_obj),
                ])
            
            subgoals.append(
                Subgoal("toggle_on", machine_obj)
            )
        
        return subgoals

# ==================== 使用示例 ====================
planner = RecipePlanner(env)

# 任务：做咖啡
initial_state = {
    Atom("exists", ("ground_coffee.n.01_1",)),
    Atom("exists", ("water.n.06_1",)),
    Atom("exists", ("coffee_maker.n.01_1",)),
}

goal_state = {
    Atom("exists", ("coffee.n.01_1",))  # 生成咖啡
}

subgoals = planner.plan(initial_state, goal_state)
# 结果：
# [
#     Subgoal("navigate_to", "ground_coffee.n.01_1"),
#     Subgoal("grasp", "ground_coffee.n.01_1"),
#     Subgoal("navigate_to", "coffee_maker.n.01_1"),
#     Subgoal("place_inside", "coffee_maker.n.01_1"),
#     Subgoal("navigate_to", "water.n.06_1"),
#     Subgoal("grasp", "water.n.06_1"),
#     Subgoal("navigate_to", "coffee_maker.n.01_1"),
#     Subgoal("place_inside", "coffee_maker.n.01_1"),
#     Subgoal("toggle_on", "coffee_maker.n.01_1"),
# ]
```

### 优势和劣势

✅ **优势**：
- 对于涉及转换的任务非常有效
- Recipe 已经定义好了复杂的操作序列
- 不需要搜索
- BEHAVIOR-1K 已有 100+ recipes

❌ **劣势**：
- 只能处理有 recipe 的任务
- 不能处理简单的状态改变任务（如 turn on radio）
- Recipe 可能不完整或有遗漏

---

## 方法 3：基于 Action Primitives 的模板匹配

**核心思想**：为常见的目标模式预定义 action templates，直接匹配。

### 算法：Template Matching

```python
# ==================== 模板匹配算法 ====================
class TemplatePlanner:
    """基于预定义模板的规划器"""
    
    def __init__(self, env):
        self.env = env
        self.templates = self._build_templates()
    
    def _build_templates(self):
        """构建目标模式到 action sequence 的模板"""
        return {
            # 模板 1: Toggle 类任务
            ("toggled_on", 1): [  # (谓词名, 元数)
                {"action": "navigate_to", "target": "$obj"},
                {"action": "toggle_on", "target": "$obj"},
            ],
            
            # 模板 2: Open 类任务
            ("open", 1): [
                {"action": "navigate_to", "target": "$obj"},
                {"action": "open", "target": "$obj"},
            ],
            
            # 模板 3: OnTop 类任务（移动对象）
            ("ontop", 2): [
                {"action": "navigate_to", "target": "$obj1"},
                {"action": "grasp", "target": "$obj1"},
                {"action": "navigate_to", "target": "$obj2"},
                {"action": "place_on_top", "target": "$obj2"},
            ],
            
            # 模板 4: Inside 类任务
            ("inside", 2): [
                {"action": "navigate_to", "target": "$obj1"},
                {"action": "grasp", "target": "$obj1"},
                {"action": "navigate_to", "target": "$obj2"},
                {"action": "open", "target": "$obj2"},  # 可能需要先打开
                {"action": "place_inside", "target": "$obj2"},
            ],
            
            # 模板 5: Cooked 类任务（简化）
            ("cooked", 1): [
                {"action": "navigate_to", "target": "$obj"},
                {"action": "grasp", "target": "$obj"},
                {"action": "navigate_to", "target": "oven.n.01"},
                {"action": "open", "target": "oven.n.01"},
                {"action": "place_inside", "target": "oven.n.01"},
                {"action": "close", "target": "oven.n.01"},
                {"action": "toggle_on", "target": "oven.n.01"},
            ],
            
            # 模板 6: Sliced 类任务
            ("sliced", 1): [
                {"action": "navigate_to", "target": "knife.n.01"},
                {"action": "grasp", "target": "knife.n.01"},
                {"action": "navigate_to", "target": "$obj"},
                {"action": "slice", "target": "$obj"},
            ],
            
            # ... 更多模板
        }
    
    def plan(self, initial_state, goal_state):
        """基于模板匹配生成计划"""
        subgoals = []
        
        for atom in goal_state:
            predicate_name, entities = atom
            arity = len(entities)
            
            # 查找匹配的模板
            template_key = (predicate_name, arity)
            
            if template_key in self.templates:
                template = self.templates[template_key]
                
                # 实例化模板
                instantiated = self._instantiate_template(
                    template, 
                    entities
                )
                
                subgoals.extend(instantiated)
            else:
                # 没有模板，使用默认策略
                print(f"Warning: No template for {predicate_name}")
                # 可以回退到反向搜索
        
        return subgoals
    
    def _instantiate_template(self, template, entities):
        """用实际对象实例化模板"""
        subgoals = []
        
        for step in template:
            action_type = step["action"]
            target_pattern = step["target"]
            
            # 替换变量
            if target_pattern == "$obj":
                target = entities[0]
            elif target_pattern == "$obj1":
                target = entities[0]
            elif target_pattern == "$obj2":
                target = entities[1]
            else:
                # 模板中的固定类型（如 "oven.n.01"）
                target = self._find_object_of_type(target_pattern)
            
            subgoals.append(Subgoal(
                action_type=action_type,
                target_object=target
            ))
        
        return subgoals
    
    def _find_object_of_type(self, synset):
        """在场景中查找特定类型的对象"""
        for obj in self.env.scene.objects:
            if obj.category == synset:
                return obj.name
        return None

# ==================== 使用示例 ====================
planner = TemplatePlanner(env)

# 任务 1: Turn on radio
goal_state = [("toggled_on", ("radio_receiver.n.01_1",))]
subgoals = planner.plan({}, goal_state)
# 结果：
# [
#     Subgoal("navigate_to", "radio_receiver.n.01_1"),
#     Subgoal("toggle_on", "radio_receiver.n.01_1")
# ]

# 任务 2: Place apple on table
goal_state = [("ontop", ("apple.n.01_1", "table.n.02_1"))]
subgoals = planner.plan({}, goal_state)
# 结果：
# [
#     Subgoal("navigate_to", "apple.n.01_1"),
#     Subgoal("grasp", "apple.n.01_1"),
#     Subgoal("navigate_to", "table.n.02_1"),
#     Subgoal("place_on_top", "table.n.02_1")
# ]
```

### 优势和劣势

✅ **优势**：
- **最实用**：简单、快速、有效
- 易于实现和维护
- 覆盖大部分常见任务
- 可以逐步添加新模板

❌ **劣势**：
- 需要手动定义模板
- 对于复杂任务可能不够
- 模板可能不适用于所有场景

---

## 方法 4：混合方法（最实用）

**推荐方案**：结合多种方法的优势。

```python
# ==================== 混合规划器 ====================
class HybridPlanner:
    """混合多种方法的规划器"""
    
    def __init__(self, env):
        self.env = env
        self.template_planner = TemplatePlanner(env)
        self.recipe_planner = RecipePlanner(env)
        self.backward_planner = BackwardPlanner(env)
    
    def plan(self, initial_state, goal_state):
        """智能选择规划方法"""
        subgoals = []
        
        # 策略 1: 检查是否有 recipe 可用
        if self._involves_transformation(goal_state):
            recipe_subgoals = self.recipe_planner.plan(
                initial_state, 
                goal_state
            )
            if recipe_subgoals:
                return recipe_subgoals
        
        # 策略 2: 尝试模板匹配
        template_subgoals = self.template_planner.plan(
            initial_state, 
            goal_state
        )
        if template_subgoals:
            return template_subgoals
        
        # 策略 3: 回退到反向搜索
        backward_subgoals = self.backward_planner.plan(
            initial_state,
            goal_state
        )
        return backward_subgoals
    
    def _involves_transformation(self, goal_state):
        """检查目标是否涉及对象转换"""
        # 检查是否有新对象出现
        # 或者检查特定的转换谓词（如 cooked, sliced）
        transformation_predicates = [
            "cooked", "sliced", "mixed", "melted", "frozen"
        ]
        
        for atom in goal_state:
            predicate_name = atom[0]
            if predicate_name in transformation_predicates:
                return True
        
        return False

# ==================== 使用示例 ====================
planner = HybridPlanner(env)

# 简单任务：使用模板
goal = [("toggled_on", ("radio",))]
subgoals = planner.plan({}, goal)

# 复杂任务：使用 recipe
goal = [("cooked", ("dough",))]
subgoals = planner.plan({}, goal)

# 新任务：回退到反向搜索
goal = [("some_rare_predicate", ("obj",))]
subgoals = planner.plan({}, goal)
```

---

## 完整实现示例

```python
# ==================== 完整的非 LLM 规划器 ====================
from omnigibson.utils.bddl_utils import get_knowledge_base
from omnigibson.object_states import *

class SymbolicPlanner:
    """完整的符号规划器（无需 LLM）"""
    
    def __init__(self, env):
        self.env = env
        self.kb = get_knowledge_base()
        self._init_templates()
        self._init_recipes()
    
    def _init_templates(self):
        """初始化常用模板"""
        self.templates = {
            "toggle_on": [
                ("navigate_to", "target"),
                ("toggle_on", "target"),
            ],
            "place_on_top": [
                ("navigate_to", "obj"),
                ("grasp", "obj"),
                ("navigate_to", "surface"),
                ("place_on_top", "surface"),
            ],
            # ... 更多
        }
    
    def _init_recipes(self):
        """加载所有 recipes"""
        self.recipes = self.kb.get_all_recipes()
    
    def plan(self, bddl_task):
        """主规划接口"""
        initial_state = bddl_task.initial_state
        goal_state = bddl_task.goal_state
        
        # 1. 分析目标类型
        goal_type = self._classify_goal(goal_state)
        
        # 2. 根据类型选择规划方法
        if goal_type == "transformation":
            return self._plan_transformation(initial_state, goal_state)
        elif goal_type == "state_change":
            return self._plan_state_change(initial_state, goal_state)
        elif goal_type == "relocation":
            return self._plan_relocation(initial_state, goal_state)
        else:
            return self._plan_general(initial_state, goal_state)
    
    def _classify_goal(self, goal_state):
        """分类目标类型"""
        predicates = [atom[0] for atom in goal_state]
        
        transformation_preds = ["cooked", "sliced", "mixed", "melted"]
        if any(p in transformation_preds for p in predicates):
            return "transformation"
        
        state_preds = ["toggled_on", "open", "closed", "filled"]
        if any(p in state_preds for p in predicates):
            return "state_change"
        
        relocation_preds = ["ontop", "inside", "nextto"]
        if any(p in relocation_preds for p in predicates):
            return "relocation"
        
        return "general"
    
    def _plan_transformation(self, initial, goal):
        """规划转换任务（使用 recipes）"""
        # 找到相关的 recipe
        for atom in goal:
            pred, entities = atom
            if pred == "cooked":
                obj_synset = self._get_synset(entities[0])
                recipe = self._find_cooking_recipe(obj_synset)
                if recipe:
                    return self._recipe_to_subgoals(recipe)
        
        return []
    
    def _plan_state_change(self, initial, goal):
        """规划状态改变任务（使用模板）"""
        subgoals = []
        
        for atom in goal:
            pred, entities = atom
            
            if pred == "toggled_on":
                obj = entities[0]
                subgoals.extend([
                    Subgoal("navigate_to", obj),
                    Subgoal("toggle_on", obj),
                ])
            
            elif pred == "open":
                obj = entities[0]
                subgoals.extend([
                    Subgoal("navigate_to", obj),
                    Subgoal("open", obj),
                ])
            
            # ... 更多
        
        return subgoals
    
    def _plan_relocation(self, initial, goal):
        """规划重定位任务（使用模板）"""
        subgoals = []
        
        for atom in goal:
            pred, entities = atom
            
            if pred == "ontop":
                obj, surface = entities
                subgoals.extend([
                    Subgoal("navigate_to", obj),
                    Subgoal("grasp", obj),
                    Subgoal("navigate_to", surface),
                    Subgoal("place_on_top", surface),
                ])
            
            elif pred == "inside":
                obj, container = entities
                subgoals.extend([
                    Subgoal("navigate_to", obj),
                    Subgoal("grasp", obj),
                    Subgoal("navigate_to", container),
                    Subgoal("open", container),
                    Subgoal("place_inside", container),
                ])
            
            # ... 更多
        
        return subgoals

# ==================== 使用 ====================
planner = SymbolicPlanner(env)

# 从 BDDL 加载任务
task = env.task  # BehaviorTask

# 生成计划
subgoals = planner.plan(task)

# 执行
executor = PrimitiveExecutor(env, robot)
for subgoal in subgoals:
    success = yield from executor.execute_subgoal(subgoal)
    if not success:
        print(f"Failed: {subgoal}")
        break
```

---

## 对比总结

| 方法 | 实现难度 | 覆盖范围 | 准确性 | 性能 | 推荐度 |
|------|----------|----------|--------|------|--------|
| **反向搜索** | 🔴 高 | ⭐⭐ | ⭐⭐⭐⭐ | 🐌 慢 | ⭐⭐ |
| **Recipe 匹配** | 🟡 中 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⚡ 快 | ⭐⭐⭐⭐ |
| **模板匹配** | 🟢 低 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⚡⚡ 很快 | ⭐⭐⭐⭐⭐ |
| **混合方法** | 🟡 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⚡ 快 | ⭐⭐⭐⭐⭐ |
| **LLM** | 🟢 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 🐌🐌 很慢 | ⭐⭐⭐⭐ |

### 最终推荐

**对于 BEHAVIOR-1K**：

1. **首选：混合方法（模板 + Recipe）**
   - 实现简单
   - 覆盖 80-90% 的任务
   - 速度快、准确率高
   - 易于维护和扩展

2. **次选：LLM**
   - 处理边界情况
   - 处理新任务
   - 作为混合方法的补充

3. **不推荐：纯反向搜索**
   - 除非需要理论保证
   - 或者任务结构非常规则

### 实际工作流

```python
# ==================== 实际推荐的实现 ====================
class PracticalPlanner:
    """实用的混合规划器"""
    
    def __init__(self, env):
        self.template_planner = TemplatePlanner(env)
        self.recipe_planner = RecipePlanner(env)
        self.llm_planner = LLMPlanner(model="gpt-4")  # 备用
    
    def plan(self, task):
        # 尝试 1: 模板匹配（80% 任务）
        subgoals = self.template_planner.plan(task)
        if subgoals:
            return subgoals
        
        # 尝试 2: Recipe 匹配（15% 任务）
        subgoals = self.recipe_planner.plan(task)
        if subgoals:
            return subgoals
        
        # 尝试 3: LLM 兜底（5% 任务）
        subgoals = self.llm_planner.plan(task)
        return subgoals
```

---

## 总结

**核心答案**：
- ✅ OmniGibson 提供了丰富的预定义内容（Object States、Action Primitives、Transition Rules、Knowledge Base）
- ✅ 这些内容可以用来构建 skeleton，无需 LLM
- ✅ **模板匹配 + Recipe 匹配** 是最实用的方案
- ✅ LLM 可以作为补充，处理边界情况

**关键洞察**：
- Action Primitives 的**错误处理**隐式定义了 preconditions
- Object States 的 `set_value()` 隐式定义了达到状态的 actions
- Transition Rules 明确定义了复杂任务的操作序列
- Knowledge Base 提供了对象能力的语义信息

你可以从**模板匹配**开始，逐步添加模板，覆盖大部分任务！
