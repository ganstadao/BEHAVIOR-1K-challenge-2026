"""
Main evaluation script for TAMP test.

Usage:
    python eval/run_eval.py --config configs/turning_on_radio.yaml --instance 301
"""

import argparse
import json
import os
import sys
from pathlib import Path
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import omnigibson as og
from omnigibson.macros import gm

from core import ExecutionResult
from planner.symbolic_planner import FixedSkeletonPlanner
from planner.skeleton_executor import SkeletonExecutor
from eval.video_utils import VideoRecorder


def log(msg):
    """Log message to stderr (survives OmniGibson stdout redirection)"""
    print(msg, file=sys.stderr, flush=True)
    # Also try stdout in case it's not redirected yet
    print(msg, flush=True)


class TAMPEvaluator:
    """TAMP evaluator for BEHAVIOR-1K tasks"""

    def __init__(self, config_path):
        """Initialize evaluator

        Args:
            config_path: Path to config YAML file
        """
        self.config = self._load_config(config_path)
        self.env = None
        self.planner = None
        self.executor = None
        self.video_recorder = VideoRecorder()
        self.current_instance_id = None

        # Set OmniGibson to headless mode
        gm.ENABLE_OBJECT_STATES = True

        log(f"[TAMPEvaluator] Loaded config from {config_path}")


    def _load_config(self, config_path):
        """Load configuration from YAML file"""
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config

    def setup(self):
        """Initialize environment and components"""
        log("\n" + "="*60)
        log("[TAMPEvaluator] Setting up environment...")
        log("="*60 + "\n")

        # Enable CuRobo for R1
        from omnigibson.macros import macros as m
        m.robots.CUROBO_ROBOT_CONFIG_MAPPING = {
            "R1": "r1.yml"
        }
        log("[TAMPEvaluator] CuRobo enabled for R1")

        # 1. Build environment config
        env_config = self._build_env_config()

        # 2. Create OmniGibson environment
        log("[TAMPEvaluator] Creating OmniGibson environment...")
        self.env = og.Environment(configs=env_config)
        log(f"[TAMPEvaluator] ✓ Environment created")

        # 3. Create planner
        log("[TAMPEvaluator] Creating planner...")
        self.planner = FixedSkeletonPlanner()
        log(f"[TAMPEvaluator] ✓ Planner created")

        # 4. Create executor
        log("[TAMPEvaluator] Creating executor...")
        robot = self.env.robots[0]
        self.executor = SkeletonExecutor(self.env, robot)
        log(f"[TAMPEvaluator] ✓ Executor created")

        log("\n" + "="*60)
        log("[TAMPEvaluator] Setup complete!")
        log("="*60 + "\n")

    def run_evaluation(self, instance_id):
        """Run evaluation on a single instance

        Args:
            instance_id: Task instance ID

        Returns:
            dict: Evaluation results
        """
        log("\n" + "="*60)
        log(f"[TAMPEvaluator] Evaluating instance {instance_id}")
        log("="*60 + "\n")

        self.current_instance_id = instance_id

        # Setup video recording if enabled
        record_video = self.config.get('evaluation', {}).get('record_video', False)
        if record_video:
            video_dir = self.config.get('output', {}).get('video_dir', 'results/videos')
            os.makedirs(video_dir, exist_ok=True)
            video_path = os.path.join(video_dir, f'instance_{instance_id}.mp4')
            self.video_recorder.start_recording(video_path, rate=30)

        # 1. Reset environment
        log("[TAMPEvaluator] Resetting environment...")
        obs = self.env.reset()
        log("[TAMPEvaluator] ✓ Environment reset")

        # Capture first frame
        if record_video:
            robot_name = self.env.robots[0].name
            self.video_recorder.write_frame(obs, robot_name)

        # Log robot initial state
        robot_pos = self.env.robots[0].get_position()
        robot_ori = self.env.robots[0].get_orientation()
        log(f"[TAMPEvaluator] Robot initial position: {robot_pos}")
        log(f"[TAMPEvaluator] Robot initial orientation: {robot_ori}")

        # 2. Generate skeleton
        log("\n[TAMPEvaluator] Generating skeleton...")
        task_name = self.config['task']['name']
        object_scope = self.env.task.object_scope

        # skeleton 输入 object_scope
        skeleton = self.planner.plan(task_name, object_scope)

        log(f"[TAMPEvaluator] Generated skeleton with {len(skeleton)} subgoals:")
        for i, sg in enumerate(skeleton):
            log(f"  {i+1}. {sg.action_type} -> {sg.target_object}")
            # Log target object position if available
            if sg.target_object in object_scope:
                target_obj = object_scope[sg.target_object]
                target_pos = target_obj.get_position()
                log(f"      Target position: {target_pos}")

        # 3. Execute skeleton
        log("\n[TAMPEvaluator] Executing skeleton...\n")

        result = None
        step_count = 0
        robot_name = self.env.robots[0].name
        try:
            # Execute the generator - it yields during execution and returns the result
            gen = self.executor.execute_skeleton(skeleton, object_scope)
            for _ in gen:
                step_count += 1

                # Capture video frame every N steps
                if record_video and step_count % 2 == 0:
                    obs = self.env.get_obs()
                    self.video_recorder.write_frame(obs, robot_name)

                # Log robot state every 10 steps
                if step_count % 10 == 0:
                    robot_pos = self.env.robots[0].get_position()
                    log(f"[TAMPEvaluator] Step {step_count}, Robot position: {robot_pos}")

        except StopIteration as e:
            # The generator's return value is in the exception
            result = e.value
        finally:
            # Finalize video recording
            if record_video:
                self.video_recorder.stop_recording()

        # Check if we got a result
        if result is None:
            log("[TAMPEvaluator] Warning: No result returned from executor")
            # Create a failure result with required fields
            from core import ExecutionResult
            result = ExecutionResult(
                skeleton=skeleton,
                success=False,
                num_steps=step_count,
                subgoal_results=[],
                goal_status={},
                error_message="No result from executor"
            )

        # 4. Print summary
        self._print_result_summary(result, instance_id)

        # 5. Build result dict
        result_dict = self._build_result_dict(result, instance_id)

        return result_dict

    def _print_result_summary(self, result: ExecutionResult, instance_id: int):
        """Print evaluation result summary"""
        log("\n" + "="*60)
        log(f"[TAMPEvaluator] Evaluation Result (Instance {instance_id})")
        log("="*60)

        if result.success:
            print(f"✓ SUCCESS")
        else:
            print(f"✗ FAILED")
            if result.error_message:
                print(f"  Error: {result.error_message}")

        log(f"\nSubgoals: {sum(1 for r in result.subgoal_results if r['success'])}/{len(result.skeleton)}")
        log(f"Total steps: {result.num_steps}")

        log(f"\nGoal status:")
        log(f"  Satisfied: {result.goal_status.get('satisfied', [])}")
        log(f"  Unsatisfied: {result.goal_status.get('unsatisfied', [])}")

        log("\nSubgoal details:")
        for r in result.subgoal_results:
            status = "✓" if r['success'] else "✗"
            print(f"  {status} {r['subgoal_index']+1}. {r['action']} ({r.get('steps', 0)} steps)")
            if not r['success']:
                print(f"     Error: {r['error']}")

        log("="*60 + "\n")

    def _build_result_dict(self, result: ExecutionResult, instance_id: int) -> dict:
        """Build result dictionary for JSON output"""
        return {
            "instance_id": instance_id,
            "task_name": result.skeleton.task_name,
            "success": result.success,
            "num_steps": result.num_steps,
            "num_subgoals": len(result.skeleton),
            "num_successful_subgoals": sum(
                1 for r in result.subgoal_results if r['success']
            ),
            "subgoal_results": result.subgoal_results,
            "goal_status": result.goal_status,
            "error_message": result.error_message,
        }

    def _build_env_config(self):
        """Build OmniGibson environment configuration"""
        task_config = self.config['task']

        return {
            "scene": {
                "type": "InteractiveTraversableScene",
                "scene_model": task_config.get('scene_model', 'house_double_floor_lower'),
                # 加载所有房间类型，确保收音机所在区域可达
            },
            "robots": [
                {
                    "name": "robot0",
                    "model": "r1pro",
                    "obs_modalities": ["rgb", "depth"],
                    "action_type": "continuous",
                    "action_normalize": False,
                    "controller_config": {
                        "base": {
                            "name": "HolonomicBaseJointController",
                            "motor_type": "velocity",
                            "vel_kp": 150,
                            "command_input_limits": [
                                [-1.0, -1.0, -1.0],
                                [1.0, 1.0, 1.0]
                            ],
                            "command_output_limits": None,
                            "use_impedances": False,
                        },
                        "trunk": {
                            "name": "JointController",
                            "motor_type": "position",
                            "pos_kp": 150,
                            "command_input_limits": None,
                            "command_output_limits": None,
                            "use_delta_commands": False,
                            "use_impedances": False,
                        },
                        "arm_left": {
                            "name": "JointController",
                            "motor_type": "position",
                            "pos_kp": 150,
                            "command_input_limits": None,
                            "command_output_limits": None,
                            "use_delta_commands": False,
                            "use_impedances": False,
                        },
                        "gripper_left": {
                            "name": "JointController",
                            "motor_type": "position",
                            "pos_kp": 150,
                            "command_input_limits": None,
                            "command_output_limits": None,
                            "use_delta_commands": False,
                            "use_impedances": False,
                        },
                        "arm_right": {
                            "name": "JointController",
                            "motor_type": "position",
                            "pos_kp": 150,
                            "command_input_limits": None,
                            "command_output_limits": None,
                            "use_delta_commands": False,
                            "use_impedances": False,
                        },
                        "gripper_right": {
                            "name": "JointController",
                            "motor_type": "position",
                            "pos_kp": 150,
                            "command_input_limits": None,
                            "command_output_limits": None,
                            "use_delta_commands": False,
                            "use_impedances": False,
                        },
                    },
                }
            ],
            "task": {
                "type": "BehaviorTask",
                "activity_name": task_config['name'],
                "activity_definition_id": task_config.get('activity_definition_id', 0),
                "activity_instance_id": task_config.get('activity_instance_id', 0),
                "online_object_sampling": False,
            },
        }

    def cleanup(self):
        """Cleanup resources"""
        log("\n[TAMPEvaluator] Cleaning up...")
        if self.env is not None:
            og.shutdown()
        log("[TAMPEvaluator] ✓ Cleanup complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run TAMP evaluation on BEHAVIOR-1K tasks"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to config YAML file"
    )
    parser.add_argument(
        "--instance",
        type=int,
        default=301,
        help="Task instance ID (default: 301)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results",
        help="Output directory (default: results)"
    )

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(f"{args.output}/logs", exist_ok=True)

    # Initialize evaluator
    evaluator = TAMPEvaluator(args.config)

    try:
        # Setup
        evaluator.setup()

        # Run evaluation
        result = evaluator.run_evaluation(args.instance)

        # Save results
        output_file = f"{args.output}/instance_{args.instance}_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        log(f"\n[Main] Results saved to {output_file}")

        # Print final summary
        log("\n" + "="*60)
        log("EVALUATION COMPLETE")
        log("="*60)
        log(f"Success: {result['success']}")
        log(f"Instance: {args.instance}")
        log(f"Task: {result['task_name']}")
        log(f"Subgoals: {result['num_successful_subgoals']}/{result['num_subgoals']}")
        log(f"Steps: {result['num_steps']}")
        log("="*60 + "\n")

    except Exception as e:
        log(f"\n[Main] Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        evaluator.cleanup()


if __name__ == "__main__":
    main()
