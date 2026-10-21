#!/usr/bin/env python3
"""
快速分析 action 日志，诊断机器人为什么不移动
"""

import json
import sys
from pathlib import Path
import numpy as np

def analyze_actions(log_path):
    """分析 action 日志文件"""

    log_file = Path(log_path) / "actions.jsonl"

    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        return

    print("="*80)
    print("🔍 Action Log Analysis")
    print("="*80)
    print(f"Log file: {log_file}")
    print()

    # 读取所有 action
    actions = []
    with open(log_file) as f:
        for line in f:
            actions.append(json.loads(line))

    if not actions:
        print("❌ No actions found in log!")
        return

    print(f"📊 Total steps: {len(actions)}")
    print()

    # 分析 base 移动
    print("-"*80)
    print("🚶 Base Movement Analysis")
    print("-"*80)

    if 'base' in actions[0]:
        base_moves = [a['base'] for a in actions if 'base' in a]

        # 统计移动步数
        moving_threshold = 0.001
        moving_steps = []
        stationary_steps = []

        for i, base in enumerate(base_moves):
            is_moving = (abs(base['linear_x']) > moving_threshold or
                        abs(base['linear_y']) > moving_threshold or
                        abs(base['angular_z']) > moving_threshold)
            if is_moving:
                moving_steps.append(i)
            else:
                stationary_steps.append(i)

        print(f"Moving steps:      {len(moving_steps):4d} / {len(base_moves)} ({len(moving_steps)/len(base_moves)*100:.1f}%)")
        print(f"Stationary steps:  {len(stationary_steps):4d} / {len(base_moves)} ({len(stationary_steps)/len(base_moves)*100:.1f}%)")
        print()

        # 统计量
        linear_x = [b['linear_x'] for b in base_moves]
        linear_y = [b['linear_y'] for b in base_moves]
        angular_z = [b['angular_z'] for b in base_moves]

        print("Linear X (forward/backward):")
        print(f"  Min:  {min(linear_x):8.5f}")
        print(f"  Max:  {max(linear_x):8.5f}")
        print(f"  Mean: {np.mean(linear_x):8.5f}")
        print(f"  Std:  {np.std(linear_x):8.5f}")
        print()

        print("Linear Y (left/right):")
        print(f"  Min:  {min(linear_y):8.5f}")
        print(f"  Max:  {max(linear_y):8.5f}")
        print(f"  Mean: {np.mean(linear_y):8.5f}")
        print(f"  Std:  {np.std(linear_y):8.5f}")
        print()

        print("Angular Z (rotation):")
        print(f"  Min:  {min(angular_z):8.5f}")
        print(f"  Max:  {max(angular_z):8.5f}")
        print(f"  Mean: {np.mean(angular_z):8.5f}")
        print(f"  Std:  {np.std(angular_z):8.5f}")
        print()

        # 打印前10步
        print("-"*80)
        print("First 10 steps:")
        print("-"*80)
        for i in range(min(10, len(base_moves))):
            b = base_moves[i]
            status = "🚶 MOVE" if i in moving_steps else "🛑 STOP"
            print(f"Step {i:3d}: x={b['linear_x']:7.4f}, y={b['linear_y']:7.4f}, θ={b['angular_z']:7.4f}  {status}")
        print()

        # 诊断
        print("-"*80)
        print("🔬 Diagnosis")
        print("-"*80)

        avg_velocity = np.mean([np.linalg.norm([b['linear_x'], b['linear_y']]) for b in base_moves])

        if len(moving_steps) < len(base_moves) * 0.1:
            print("❌ Problem: Robot is mostly STATIONARY (< 10% moving steps)")
            print()
            print("Possible causes:")
            print("  1. Policy is not outputting valid movement commands")
            print("  2. Policy thinks robot is already at target")
            print("  3. Navigation module failed in training")
            print("  4. Action normalization issue")
            print()
            print("Next steps:")
            print("  - Check policy server log for errors")
            print("  - Compare with training data actions")
            print("  - Verify checkpoint is correct")
        elif avg_velocity < 0.01:
            print("⚠️  Problem: Robot is moving but velocity is very low")
            print(f"   Average velocity: {avg_velocity:.6f} m/s")
            print()
            print("Possible causes:")
            print("  1. Action scaling/normalization issue")
            print("  2. Policy trained with different action space")
            print("  3. Sim-to-sim transfer issue")
        else:
            print("✅ Robot appears to be moving!")
            print(f"   Average velocity: {avg_velocity:.4f} m/s")
            print(f"   Moving {len(moving_steps)/len(base_moves)*100:.1f}% of the time")
            print()
            print("If task still fails, check:")
            print("  - Does robot reach the table?")
            print("  - Is manipulation part working?")
    else:
        print("⚠️  Warning: No 'base' field found in actions")
        print("    Action structure might be different than expected")

    print()
    print("-"*80)
    print("📝 Full Analysis")
    print("-"*80)
    print(f"Action dimension: {actions[0]['action_dim']}")

    all_actions = np.array([a['action'] for a in actions])
    print(f"Overall action range: [{all_actions.min():.4f}, {all_actions.max():.4f}]")
    print(f"Overall action mean:  {all_actions.mean():.4f}")
    print(f"Overall action std:   {all_actions.std():.4f}")
    print()

    # 检查是否全零或近零
    if np.abs(all_actions).max() < 0.001:
        print("🚨 CRITICAL: All actions are near zero!")
        print("   Policy is likely not working correctly.")

    print("="*80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_actions.py <log_directory>")
        print("Example: python analyze_actions.py eval_logs/turning_on_radio_action_debug")
        sys.exit(1)

    log_path = sys.argv[1]
    analyze_actions(log_path)
