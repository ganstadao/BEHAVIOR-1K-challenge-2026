# TAMP Test 实现 Outline

> **详细的实现计划，按模块分解**

---

## 阶段 0：准备工作

### 0.1 理解 OmniGibson Primitives

**需要了解的内容**：
- StarterSemanticActionPrimitives 的 API
- 如何调用 primitives（apply_ref）
- 连续参数采样（位置、姿态）
- CuRobo 运动规划的使用

**参考文件**：
- `OmniGibson/omnigibson/action_primitives/starter_semantic_action_primitives.py`
- `OmniGibson/omnigibson/examples/action_primitives/`

### 0.2 理解 BDDL Task Loading

**需要了解的内容**：
- 如何从 BDDL 提取 initial state
- 如何从 BDDL 提取 goal state
- 如何访问 object_scope

**参考文件**：
- `doc/bddl3/bddl_dataflow.md`（已创建）
- `OmniGibson/omnigibson/tasks/behavior_task.py`

---

## 阶段 1：PDDL Domain 定义

### 1.1 Types 定义

```lisp
(:types
    robot
    object
    location
)
```

### 1.2 Predicates 定义

基于 `turning_on_radio` 任务需要的谓词：

```lisp
(:predicates
    ; 位置关系
    (at ?r - robot ?l - location)
    (near ?r - robot ?o - object)
    
    ; 对象状态
    (toggled_on ?o - object)
    (toggleable ?o - object)
    
    ; 导航能力
    (reachable ?l - location)
)
```

### 1.3 Actions 定义

**Action 1: navigate_to**

```lisp
(:action navigate_to
    :parameters (?r - robot ?o - object ?l - location)
    :precondition (and
        (at ?o ?l)
        (reachable ?l)
    )
    :effect (and
        (near ?r ?o)
        (at ?r ?l)
    )
)
```

**Action 2: press_button** (简化的 toggle_on)

```lisp
(:action press_button
    :parameters (?r - robot ?o - object)
    :precondition (and
        (near ?r ?o)
        (toggleable ?o)
        (not (toggled_on ?o))
    )
    :effect (toggled_on ?o)
)
```

### 1.4 从 BDDL 生成 Problem

**输入**：`bddl3/bddl/activity_definitions/turning_on_radio/problem0.bddl`

**输出**：`domain/problem.pddl`

```lisp
(define (problem turning_on_radio-0)
    (:domain turning-on-radio)
    
    (:objects
        robot - robot
        radio - object
        living_room - location
    )
    
    (:init
        (at radio living_room)
        (toggleable radio)
        (not (toggled_on radio))
        (reachable living_room)
    )
    
    (:goal
        (toggled_on radio)
    )
)
```

**关键代码**：

```python
def bddl_to_pddl_problem(bddl_task):
    """将 BDDL 任务转换为 PDDL problem"""
    
    # 提取对象
    objects = []
    for synset, instances in bddl_task.parsed_objects.items():
        pddl_type = synset_to_pddl_type(synset)
        for inst in instances:
            objects.append((inst, pddl_type))
    
    # 提取初始状态
    init = []
    for cond in bddl_task.parsed_initial_conditions:
        pddl_pred = bddl_to_pddl_predicate(cond)
        init.append(pddl_pred)
    
    # 提取目标
    goal = []
    for cond in bddl_task.parsed_goal_conditions:
        pddl_pred = bddl_to_pddl_predicate(cond)
        goal.append(pddl_pred)
    
    return PDDLProblem(objects, init, goal)
```

---

## 阶段 2：符号规划器

### 2.1 固定 Skeleton（不搜索）

对于 `turning_on_radio`，skeleton 是固定的：

```python
class FixedSkeletonPlanner:
    """固定 skeleton 的规划器（测试用）"""
    
    def plan(self, task_name, initial_state, goal_state):
        """返回固定的 skeleton"""
        
        if task_name == "turning_on_radio":
            # 从 goal 中提取 radio 对象
            radio_obj = self._extract_target_object(goal_state)
            
            skeleton = [
                Subgoal(
                    action_type="navigate_to",
                    target_object=radio_obj,
                    preconditions=["reachable(living_room)"],
                    effects=["near(robot, radio)", "at(robot, living_room)"]
                ),
                Subgoal(
                    action_type="press_button",
                    target_object=radio_obj,
                    preconditions=["near(robot, radio)", "toggleable(radio)"],
                    effects=["toggled_on(radio)"]
                )
            ]
            
            return skeleton
        else:
            raise NotImplementedError(f"No skeleton for {task_name}")
```

### 2.2 Skeleton 数据结构

```python
@dataclass
class Subgoal:
    """高层子目标"""
    action_type: str              # "navigate_to", "press_button"
    target_object: str            # BDDL 实例名，如 "radio_receiver.n.01_1"
    preconditions: List[str]      # 符号前置条件
    effects: List[str]            # 符号效果
    status: str = "pending"       # pending/running/success/failed
    error_message: str = ""
```

---

## 阶段 3：低层运动规划

### 3.1 Primitive Wrapper

包装 OmniGibson 的 action primitives：

```python
from omnigibson.action_primitives.starter_semantic_action_primitives import (
    StarterSemanticActionPrimitives,
    StarterSemanticActionPrimitiveSet
)

class PrimitiveWrapper:
    """包装 OmniGibson action primitives"""
    
    def __init__(self, env, robot):
        self.env = env
        self.robot = robot
        
        # 初始化 primitives
        self.primitives = StarterSemanticActionPrimitives(
            env=env,
            robot=robot,
            use_visual_perception=False  # 使用真实对象位置
        )
    
    def execute_navigate_to(self, target_obj):
        """执行 navigate_to action"""
        
        # 调用 primitive
        primitive_enum = StarterSemanticActionPrimitiveSet.NAVIGATE_TO
        
        # 执行（生成器）
        for _ in self.primitives.apply_ref(primitive_enum, target_obj):
            yield
        
        # 验证
        if not self._is_near(target_obj):
            raise ActionPrimitiveError("Navigate failed")
    
    def execute_press_button(self, target_obj):
        """执行 press_button action（映射到 TOGGLE_ON）"""
        
        primitive_enum = StarterSemanticActionPrimitiveSet.TOGGLE_ON
        
        # 执行
        for _ in self.primitives.apply_ref(primitive_enum, target_obj):
            yield
        
        # 验证状态改变
        from omnigibson.object_states import ToggledOn
        if not target_obj.states[ToggledOn].get_value():
            raise ActionPrimitiveError("Press button failed")
    
    def _is_near(self, obj):
        """检查 robot 是否在对象附近"""
        robot_pos = self.robot.get_position()
        obj_pos = obj.get_position()
        distance = np.linalg.norm(robot_pos - obj_pos)
        return distance < 2.0  # 2 米内
```

### 3.2 连续参数采样

对于更复杂的 primitives（如 grasp、place），需要采样连续参数：

```python
class MotionSampler:
    """采样连续参数（位置、姿态）"""
    
    def sample_grasp_pose(self, obj):
        """采样抓取姿态"""
        # 使用 OmniGibson 内置的采样器
        from omnigibson.utils.grasping_planning_helper import (
            get_grasp_poses_for_object_sticky
        )
        
        grasp_poses = get_grasp_poses_for_object_sticky(obj)
        if grasp_poses:
            return grasp_poses[0]  # 返回第一个
        else:
            raise SamplingError("No valid grasp pose")
    
    def sample_placement_pose(self, obj, surface):
        """采样放置位置"""
        # 在 surface 上采样
        surface_aabb = surface.aabb
        
        # 随机采样 x, y
        x = np.random.uniform(
            surface_aabb[0][0], 
            surface_aabb[1][0]
        )
        y = np.random.uniform(
            surface_aabb[0][1], 
            surface_aabb[1][1]
        )
        z = surface_aabb[1][2] + obj.aabb_extent[2] / 2
        
        return np.array([x, y, z])
```

---

## 阶段 4：Skeleton 执行器

### 4.1 执行流程

```python
class SkeletonExecutor:
    """执行 skeleton 中的 subgoals"""
    
    def __init__(self, env, robot):
        self.env = env
        self.robot = robot
        self.primitive_wrapper = PrimitiveWrapper(env, robot)
    
    def execute_skeleton(self, skeleton, object_scope):
        """执行整个 skeleton"""
        
        results = []
        
        for i, subgoal in enumerate(skeleton):
            print(f"\n=== Executing Subgoal {i+1}/{len(skeleton)} ===")
            print(f"Action: {subgoal.action_type}")
            print(f"Target: {subgoal.target_object}")
            
            try:
                # 解析目标对象
                target_obj = object_scope[subgoal.target_object]
                
                # 执行 subgoal
                success = yield from self._execute_subgoal(
                    subgoal, 
                    target_obj
                )
                
                if success:
                    subgoal.status = "success"
                    results.append((subgoal, True, ""))
                else:
                    subgoal.status = "failed"
                    results.append((subgoal, False, "execution_failed"))
                    break  # 停止执行后续 subgoals
                
            except Exception as e:
                subgoal.status = "failed"
                subgoal.error_message = str(e)
                results.append((subgoal, False, str(e)))
                print(f"Error: {e}")
                break
        
        return results
    
    def _execute_subgoal(self, subgoal, target_obj):
        """执行单个 subgoal"""
        
        # 根据 action_type 调用对应的 primitive
        if subgoal.action_type == "navigate_to":
            yield from self.primitive_wrapper.execute_navigate_to(target_obj)
            return True
        
        elif subgoal.action_type == "press_button":
            yield from self.primitive_wrapper.execute_press_button(target_obj)
            return True
        
        else:
            raise ValueError(f"Unknown action: {subgoal.action_type}")
```

---

## 阶段 5：评估脚本

### 5.1 主评估流程

```python
import omnigibson as og
from omnigibson.utils.config_utils import parse_config

class TAMPEvaluator:
    """TAMP 评估器"""
    
    def __init__(self, config_path):
        self.config = self._load_config(config_path)
        self.env = None
        self.planner = None
        self.executor = None
    
    def setup(self):
        """初始化环境和组件"""
        
        # 1. 创建 OmniGibson 环境
        env_config = self._build_env_config()
        self.env = og.Environment(configs=env_config)
        
        # 2. 创建规划器
        self.planner = FixedSkeletonPlanner()
        
        # 3. 创建执行器
        robot = self.env.robots[0]
        self.executor = SkeletonExecutor(self.env, robot)
    
    def run_evaluation(self, instance_id):
        """运行单个实例的评估"""
        
        print(f"\n{'='*60}")
        print(f"Evaluating instance {instance_id}")
        print(f"{'='*60}\n")
        
        # 1. 加载任务实例
        self._load_task_instance(instance_id)
        
        # 2. 重置环境
        obs = self.env.reset()
        
        # 3. 生成 skeleton
        skeleton = self.planner.plan(
            task_name="turning_on_radio",
            initial_state=self.env.task.compiled_task.initial_conditions,
            goal_state=self.env.task.compiled_task.goal_conditions
        )
        
        print(f"Generated skeleton with {len(skeleton)} subgoals:")
        for i, sg in enumerate(skeleton):
            print(f"  {i+1}. {sg.action_type} -> {sg.target_object}")
        
        # 4. 执行 skeleton
        execution_results = yield from self.executor.execute_skeleton(
            skeleton, 
            self.env.task.object_scope
        )
        
        # 5. 检查任务完成
        goal_satisfied, goal_status = self.env.task.compiled_task.check_goal(
            self.env.task._evaluate_predicate
        )
        
        # 6. 收集结果
        result = {
            "instance_id": instance_id,
            "success": goal_satisfied,
            "num_subgoals": len(skeleton),
            "num_successful": sum(1 for _, success, _ in execution_results if success),
            "execution_results": [
                {
                    "action": sg.action_type,
                    "target": sg.target_object,
                    "success": success,
                    "error": error
                }
                for sg, success, error in execution_results
            ],
            "goal_status": goal_status
        }
        
        return result
    
    def _load_task_instance(self, instance_id):
        """加载任务实例（TRO state）"""
        # 类似 Evaluator.load_task_instance()
        # 参考：OmniGibson/omnigibson/eval/evaluator.py
        pass
    
    def _build_env_config(self):
        """构建环境配置"""
        return {
            "scene": {
                "type": "TraversableScene",
                "scene_model": "Rs_int",
            },
            "robots": [
                {
                    "type": "Fetch",
                    "obs_modalities": ["rgb", "depth"],
                }
            ],
            "task": {
                "type": "BehaviorTask",
                "activity_name": "turning_on_radio",
                "activity_definition_id": 0,
                "activity_instance_id": 0,
                "online_object_sampling": False,
            },
        }
```

### 5.2 主入口

```python
def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Config file")
    parser.add_argument("--instance", type=int, default=301, help="Instance ID")
    parser.add_argument("--video", action="store_true", help="Record video")
    args = parser.parse_args()
    
    # 初始化评估器
    evaluator = TAMPEvaluator(args.config)
    evaluator.setup()
    
    # 运行评估
    result = None
    for _ in evaluator.run_evaluation(args.instance):
        pass  # 执行生成器
    
    # 保存结果
    print(f"\n{'='*60}")
    print(f"Evaluation Result:")
    print(f"  Success: {result['success']}")
    print(f"  Subgoals: {result['num_successful']}/{result['num_subgoals']}")
    print(f"{'='*60}\n")
    
    # 保存到文件
    import json
    output_path = "results/metrics.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Results saved to {output_path}")
    
    # 关闭环境
    og.shutdown()

if __name__ == "__main__":
    main()
```

---

## 阶段 6：视频生成

### 6.1 录制视频

使用 OmniGibson 的视频录制功能：

```python
from omnigibson.utils.vision_utils import VideoWriter

class VideoGenerator:
    """视频生成器"""
    
    def __init__(self, output_path, fps=30):
        self.output_path = output_path
        self.fps = fps
        self.writer = None
    
    def start_recording(self, env):
        """开始录制"""
        # 获取相机观察
        obs = env.get_obs()
        
        # 选择相机视角
        camera_obs = obs[env.robots[0].name]["robot0:eyes:Camera:0"]["rgb"]
        
        # 初始化 writer
        h, w = camera_obs.shape[:2]
        self.writer = VideoWriter(
            output_path=self.output_path,
            fps=self.fps,
            resolution=(w, h)
        )
    
    def add_frame(self, obs):
        """添加一帧"""
        camera_obs = obs[self.env.robots[0].name]["robot0:eyes:Camera:0"]["rgb"]
        self.writer.add_frame(camera_obs)
    
    def stop_recording(self):
        """停止录制"""
        if self.writer:
            self.writer.close()
```

---

## 阶段 7：配置文件

### 7.1 任务配置

```yaml
# configs/turning_on_radio.yaml

task:
  name: turning_on_radio
  activity_definition_id: 0
  scene_model: Rs_int

evaluation:
  instances: [301, 302, 303]  # 测试实例
  max_steps: 500
  record_video: true
  video_fps: 30

planner:
  type: fixed_skeleton
  skeleton:
    - action: navigate_to
      target: radio_receiver.n.01_1
    - action: press_button
      target: radio_receiver.n.01_1

primitives:
  use_curobo: true
  visual_perception: false

output:
  results_dir: results
  video_dir: results/videos
  logs_dir: results/logs
```

---

## 实现顺序

### Week 1: 核心框架
1. ✅ 创建目录结构
2. ✅ 实现 Subgoal 数据结构
3. ✅ 实现 FixedSkeletonPlanner
4. ✅ 实现 PrimitiveWrapper（基本版本）
5. ✅ 实现 SkeletonExecutor

### Week 2: 集成测试
6. ✅ 实现 TAMPEvaluator
7. ✅ 测试 navigate_to primitive
8. ✅ 测试 press_button primitive
9. ✅ 完整的 turning_on_radio 测试
10. ✅ 调试和修复问题

### Week 3: 增强功能
11. ✅ 添加视频录制
12. ✅ 添加详细日志
13. ✅ 添加失败分析
14. ✅ 生成评估报告

---

## 预期输出

### 成功案例

```
=== Executing Subgoal 1/2 ===
Action: navigate_to
Target: radio_receiver.n.01_1
  ✓ Navigation successful (reached in 45 steps)

=== Executing Subgoal 2/2 ===
Action: press_button
Target: radio_receiver.n.01_1
  ✓ Button pressed successfully
  ✓ Radio state changed: toggled_on = True

============================================================
Evaluation Result:
  Success: True
  Subgoals: 2/2
  Goal Status: {'satisfied': [0], 'unsatisfied': []}
============================================================

Results saved to results/metrics.json
Video saved to results/videos/turning_on_radio_301.mp4
```

### 失败案例

```
=== Executing Subgoal 1/2 ===
Action: navigate_to
Target: radio_receiver.n.01_1
  ✗ Navigation failed: motion planning failed, path not found

============================================================
Evaluation Result:
  Success: False
  Subgoals: 0/2
  Error: motion planning failed at subgoal 1
============================================================
```

---

## 与 VLA Baseline 的对比

完成后，我们可以对比：

| 指标 | VLA (GR00T) | TAMP (本测试) |
|------|-------------|---------------|
| 成功率 | ~30% | ? |
| 平均步数 | ~3225 | ? |
| 推理时间 | ~150ms/step | ? |
| 可解释性 | 低 | 高 |
| 失败原因 | 不明 | 明确（哪个 subgoal）|

---

## 下一步扩展

1. 添加更多任务（place apple on table, open drawer）
2. 实现自动 skeleton 生成（模板匹配）
3. 添加 replanning（执行失败时）
4. 与 LLM planner 集成
5. 完整的 BEHAVIOR-1K 评估
