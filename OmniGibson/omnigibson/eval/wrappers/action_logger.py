"""
Action Logging Wrapper for debugging policy outputs.
Records all actions to log files without modifying source code.
"""

import json
import os
from typing import Any, Dict, Tuple
import torch as th
import numpy as np

from omnigibson.envs.env_wrapper import EnvironmentWrapper


class ActionLoggingWrapper(EnvironmentWrapper):
    """
    Wrapper that logs actions to files for debugging.

    Usage:
        python -m omnigibson.eval.eval \
            --env-wrapper omnigibson.eval.wrappers.ActionLoggingWrapper \
            ...
    """

    def __init__(self, env, log_dir: str = None):
        super().__init__(env)

        # 设置日志目录
        if log_dir is None:
            log_dir = os.path.expanduser("~/project/BEHAVIOR-1K/eval_logs/action_debug")
        os.makedirs(log_dir, exist_ok=True)

        # 创建日志文件
        self.action_log_path = os.path.join(log_dir, "actions.jsonl")
        self.action_txt_path = os.path.join(log_dir, "actions_readable.txt")
        self.step_count = 0

        # 打开日志文件
        self.action_log_file = open(self.action_log_path, 'w')
        self.action_txt_file = open(self.action_txt_path, 'w')

        print("="*80)
        print("✅ Action Logging Wrapper Enabled!")
        print("="*80)
        print(f"JSONL log:    {self.action_log_path}")
        print(f"Readable log: {self.action_txt_path}")
        print("="*80)

    def step(self, action: th.Tensor, n_render_iterations: int = 1) -> Tuple[Dict, float, bool, bool, Dict[str, Any]]:
        """
        Override step to log actions before executing them.
        """
        # 记录 action
        self._log_action(action)

        # 调用父类的 step（执行 action）
        obs, reward, terminated, truncated, info = super().step(action, n_render_iterations)

        self.step_count += 1
        return obs, reward, terminated, truncated, info

    def _log_action(self, action: th.Tensor):
        """Log action in both JSON and human-readable format."""
        action_np = action.detach().cpu().numpy()

        # JSON 格式 (用于后续分析)
        log_entry = {
            "step": self.step_count,
            "action": action_np.tolist(),
            "action_dim": len(action_np),
            "stats": {
                "min": float(action_np.min()),
                "max": float(action_np.max()),
                "mean": float(action_np.mean()),
                "std": float(action_np.std()),
            }
        }

        # 如果有足够的维度，解析 base 和 arm 部分
        if len(action_np) >= 3:
            log_entry["base"] = {
                "linear_x": float(action_np[0]),
                "linear_y": float(action_np[1]),
                "angular_z": float(action_np[2]),
            }

        self.action_log_file.write(json.dumps(log_entry) + '\n')
        self.action_log_file.flush()

        # 可读格式 - 每10步打印一次详细信息，每步打印简要信息
        if self.step_count % 10 == 0 or self.step_count < 5:
            self.action_txt_file.write(f"\n{'='*80}\n")
            self.action_txt_file.write(f"Step {self.step_count}\n")
            self.action_txt_file.write(f"{'-'*80}\n")

            # 解析 base 部分
            if len(action_np) >= 3:
                self.action_txt_file.write(f"Base Movement Command:\n")
                self.action_txt_file.write(f"  Linear  X: {action_np[0]:8.5f}\n")
                self.action_txt_file.write(f"  Linear  Y: {action_np[1]:8.5f}\n")
                self.action_txt_file.write(f"  Angular Z: {action_np[2]:8.5f}\n")

                # 判断是否在移动
                base_moving = abs(action_np[0]) > 0.001 or abs(action_np[1]) > 0.001 or abs(action_np[2]) > 0.001
                status = "🚶 MOVING" if base_moving else "🛑 STATIONARY"
                self.action_txt_file.write(f"  Status: {status}\n")

            # 全局统计
            self.action_txt_file.write(f"\nAction Statistics:\n")
            self.action_txt_file.write(f"  Dimension: {len(action_np)}\n")
            self.action_txt_file.write(f"  Min:  {action_np.min():8.5f}\n")
            self.action_txt_file.write(f"  Max:  {action_np.max():8.5f}\n")
            self.action_txt_file.write(f"  Mean: {action_np.mean():8.5f}\n")
            self.action_txt_file.write(f"  Std:  {action_np.std():8.5f}\n")
        else:
            # 简要打印
            if len(action_np) >= 3:
                base_status = "MOVE" if (abs(action_np[0]) > 0.001 or abs(action_np[1]) > 0.001) else "STOP"
                self.action_txt_file.write(
                    f"Step {self.step_count:4d}: Base[{action_np[0]:7.4f}, {action_np[1]:7.4f}, {action_np[2]:7.4f}] - {base_status}\n"
                )

        self.action_txt_file.flush()

        # 打印到控制台（每10步一次）
        if self.step_count % 10 == 0:
            if len(action_np) >= 3:
                base_norm = np.linalg.norm(action_np[:2])
                print(f"[Action Log] Step {self.step_count}: Base velocity norm={base_norm:.4f}, "
                      f"x={action_np[0]:.4f}, y={action_np[1]:.4f}, θ={action_np[2]:.4f}")

    def reset(self, *args, **kwargs):
        """Reset the environment and step counter."""
        if self.step_count > 0:
            # 记录一个 episode 结束
            self.action_txt_file.write(f"\n{'#'*80}\n")
            self.action_txt_file.write(f"# EPISODE END - Total steps: {self.step_count}\n")
            self.action_txt_file.write(f"{'#'*80}\n\n")

        self.step_count = 0

        self.action_txt_file.write(f"{'#'*80}\n")
        self.action_txt_file.write(f"# ENVIRONMENT RESET\n")
        self.action_txt_file.write(f"{'#'*80}\n\n")
        self.action_txt_file.flush()

        return super().reset(*args, **kwargs)

    def __del__(self):
        """Clean up log files."""
        if hasattr(self, 'action_log_file'):
            self.action_log_file.close()
        if hasattr(self, 'action_txt_file'):
            self.action_txt_file.close()
