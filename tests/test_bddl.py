"""
BDDL数据流学习测试
==================
本文件用于调试和学习BDDL的数据加载与解析流程

关键配置说明：
1. online_object_sampling=True: 在线采样对象（简单测试，不需要预缓存场景）
2. online_object_sampling=False: 使用预缓存场景（需要scene_instance存在）
   - 如果 scene_file 和 scene_instance 都是 None，会自动查找：
     "{scene_model}_task_{activity_name}_{definition_id}_{instance_id}_template"
   - 例如："house_double_floor_lower_task_turning_on_radio_0_0_template.json"

重要：场景和任务必须匹配！
- turning_on_radio 任务在 house_double_floor_lower 场景中
- 不同任务可能在不同的场景中，需要查看 datasets/2026-challenge-task-instances/scenes/

调试建议：
1. 在函数入口处设置断点（如第88行）
2. 使用F10单步执行，F11进入函数内部
3. 在变量上悬停查看其值
4. 使用调试控制台输入表达式查看变量详情
"""

import omnigibson as og
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


cfg = dict()
cfg["scene"] = {
    "type": "InteractiveTraversableScene",
    "scene_model": "house_double_floor_lower",  # turning_on_radio 任务在这个场景中
    "scene_file": None,  # 将自动查找缓存的任务实例
    "load_room_types": ["living_room"],  # 只加载客厅，减少内存占用
}
cfg["robots"] = [
    {
        "type": "Fetch",
        "obs_modalities": ["rgb", "depth"],
    },
]
# 定义behaviortask domain和activity
cfg["task"] = {
    "type": "BehaviorTask",
    "activity_name": "turning_on_radio",
    "activity_definition_id": 0,
    "activity_instance_id": 0,
    "online_object_sampling": False,  
}

def print_expression_tree(node, indent=0):
    """递归打印表达式树"""
    prefix = "  " * indent
    
    if hasattr(node, "STATE_NAME"):
        # Predicate 节点
        print(f"{prefix}Predicate: {node.STATE_NAME}")
        print(f"{prefix}  Body: {node.body}")
    elif isinstance(node, list):
        # 多个 HEAD 节点
        for i, child in enumerate(node):
            print(f"{prefix}[{i}]")
            print_expression_tree(child, indent + 1)
    elif hasattr(node, "children"):
        # 逻辑节点
        class_name = node.__class__.__name__
        print(f"{prefix}{class_name}")
        for child in node.children:
            print_expression_tree(child, indent + 1)
    else:
        print(f"{prefix}{node}")

# 测试bddl的加载与解析
def test_bddl_load_analyze(config):
    """
    1. BehaviorTask.__init__() 被调用
    2. BehaviorTask._load(env) 被调用
       a. task.update_activity() 加载 BDDL
          - get_knowledge_base().get_task("turning_on_radio-0")
          - 解析 BDDL 文件，得到 parsed_objects, parsed_initial_conditions, parsed_goal_conditions
          - 创建 object_scope 骨架
       b. task.initialize_activity() 初始化对象
          - assign_object_scope_with_cache() 从场景元数据填充 object_scope
          - _compile_with_rooms() 编译任务为表达式树
          - _assign_wildcard_instances() 分配通配符实例
    3. og.sim.play() 启动仿真
    4. task.post_play_load(env) 计算观察维度
    """

    print("=" * 60)
    print("开始创建环境...")
    print("=" * 60)

    test_env = og.Environment(config)

    print("\n环境创建完成！")
    print(f"环境类型: {type(test_env)}")
    print(f"场景: {test_env.scene}")
    print(f"任务: {test_env.task}")
    
    test_task = test_env._task
    '''
    # 查看任务的关键属性
    if hasattr(test_env.task, 'object_scope'):
        print(f"\nobject_scope 类型: {type(test_env.task.object_scope)}")
        print(f"object_scope 内容预览: {list(test_env.task.object_scope.keys()) if hasattr(test_env.task.object_scope, 'keys') else 'N/A'}")

    if hasattr(test_env.task, '_base_conditions'):
        print(f"\n_base_conditions 类型: {type(test_env.task._base_conditions)}")
        print(f"_base_conditions 内容预览: {test_env.task._base_conditions}")

    if hasattr(test_env.task, '_base_inroom_assignments'):
        print(f"\n_base_inroom_assignments 类型: {type(test_env.task._base_inroom_assignments)}")
        print(f"_base_inroom_assignments 内容预览: {test_env.task._base_inroom_assignments}")
        
    if hasattr(test_env.task, 'object_instance_to_category'):
        print(f"\nobject_instance_to_category 类型: {type(test_env.task.object_instance_to_category)}")
        print(f"object_instance_to_category 内容预览: {test_env.task.object_instance_to_category}")
    '''
    
    # 查看表达式树
    print("=== Initial Conditions ===")
    print_expression_tree(test_env.task.activity_initial_conditions)

    print("\n=== Goal Conditions ===")
    print_expression_tree(test_env.task.activity_goal_conditions)
        
    # 1. 检查 object_scope
    print(test_env.task.object_scope)

    # 2. 检查对象是否存在
    obj = test_env.task.object_scope["radio_receiver.n.01_1"]
    print(f"Object exists: {obj is not None}")
    print(f"Object initialized: {obj.initialized if obj else False}")

    # 3. 检查状态类是否可用
    from omnigibson.object_states import ToggledOn
    print(f"State available: {ToggledOn in obj.states}")

    # 4. 手动评估状态
    result = obj.states[ToggledOn].get_value()
    print(f"State value: {result}")

    # 5. 检查表达式树
    print_expression_tree(test_env.task.activity_goal_conditions)

    # 6. 单步评估目标
    done, goal_status = test_env.task.compiled_task.check_goal(
        test_env.task._evaluate_predicate
    )
    print(f"Done: {done}")
    print(f"Goal status: {goal_status}")


    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

    return test_env
    


if __name__ == "__main__":
    # 从这里开始，查看整个执行流程
    print("启动BDDL数据流测试...")
    env = test_bddl_load_analyze(cfg)