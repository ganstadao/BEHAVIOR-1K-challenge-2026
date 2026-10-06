#!/usr/bin/env python3
"""
批量评估工具 - 自动运行多个任务/配置的评估
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
import yaml


def run_evaluation(config_file, run_name, dry_run=False):
    """运行单个评估"""
    cmd = [
        'python', 'tools/eval_runner.py',
        '--config', config_file,
        '--run-name', run_name
    ]

    print(f"Running: {' '.join(cmd)}")

    if dry_run:
        print("  [DRY RUN - not actually running]")
        return 0

    result = subprocess.run(cmd)
    return result.returncode


def batch_eval_tasks(base_config, tasks, run_prefix, delay=0, dry_run=False):
    """批量评估多个任务"""
    print(f"Batch evaluation: {len(tasks)} tasks")
    print(f"Base config: {base_config}")
    print(f"Tasks: {', '.join(tasks)}")
    print("=" * 70)

    results = []

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] Evaluating task: {task}")
        print("-" * 70)

        # 生成临时配置
        with open(base_config, 'r') as f:
            config = yaml.safe_load(f)

        config['task']['name'] = task
        config['output']['run_name'] = f"{run_prefix}_{task}"

        temp_config = f"/tmp/eval_config_{task}.yaml"
        with open(temp_config, 'w') as f:
            yaml.dump(config, f)

        # 运行评估
        exit_code = run_evaluation(
            temp_config,
            f"{run_prefix}_{task}",
            dry_run=dry_run
        )

        results.append({
            'task': task,
            'exit_code': exit_code,
            'success': exit_code == 0
        })

        # 延迟
        if delay > 0 and i < len(tasks):
            print(f"\nWaiting {delay}s before next task...")
            time.sleep(delay)

    # 总结
    print("\n" + "=" * 70)
    print("Batch Evaluation Summary")
    print("=" * 70)

    for result in results:
        status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
        print(f"  {result['task']}: {status} (exit code: {result['exit_code']})")

    success_count = sum(1 for r in results if r['success'])
    print(f"\nTotal: {success_count}/{len(tasks)} succeeded")

    return results


def batch_eval_checkpoints(base_config, task, checkpoints, run_prefix, delay=0, dry_run=False):
    """批量评估多个 checkpoint"""
    print(f"Batch evaluation: {len(checkpoints)} checkpoints")
    print(f"Base config: {base_config}")
    print(f"Task: {task}")
    print("=" * 70)

    results = []

    for i, (ckpt_name, ckpt_path) in enumerate(checkpoints.items(), 1):
        print(f"\n[{i}/{len(checkpoints)}] Evaluating checkpoint: {ckpt_name}")
        print(f"  Path: {ckpt_path}")
        print("-" * 70)

        # 生成临时配置
        with open(base_config, 'r') as f:
            config = yaml.safe_load(f)

        config['policy']['checkpoint'] = ckpt_path
        config['task']['name'] = task
        config['output']['run_name'] = f"{run_prefix}_{ckpt_name}"

        temp_config = f"/tmp/eval_config_{ckpt_name}.yaml"
        with open(temp_config, 'w') as f:
            yaml.dump(config, f)

        # 运行评估
        exit_code = run_evaluation(
            temp_config,
            f"{run_prefix}_{ckpt_name}",
            dry_run=dry_run
        )

        results.append({
            'checkpoint': ckpt_name,
            'path': ckpt_path,
            'exit_code': exit_code,
            'success': exit_code == 0
        })

        # 延迟
        if delay > 0 and i < len(checkpoints):
            print(f"\nWaiting {delay}s before next checkpoint...")
            time.sleep(delay)

    # 总结
    print("\n" + "=" * 70)
    print("Batch Evaluation Summary")
    print("=" * 70)

    for result in results:
        status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
        print(f"  {result['checkpoint']}: {status}")

    success_count = sum(1 for r in results if r['success'])
    print(f"\nTotal: {success_count}/{len(checkpoints)} succeeded")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='批量评估工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 评估多个任务
  python tools/batch_eval.py --mode tasks \\
      --config configs/pi05_turning_on_radio.yaml \\
      --tasks turning_on_radio turning_on_lamp opening_door \\
      --run-prefix baseline_eval

  # 评估多个 checkpoint
  python tools/batch_eval.py --mode checkpoints \\
      --config configs/pi05_turning_on_radio.yaml \\
      --task turning_on_radio \\
      --checkpoints ckpt1=~/ckpts/step_1000 ckpt2=~/ckpts/step_2000 \\
      --run-prefix ckpt_comparison

  # 从文件读取任务列表
  python tools/batch_eval.py --mode tasks \\
      --config configs/pi05_turning_on_radio.yaml \\
      --tasks-file tasks.txt \\
      --run-prefix batch_1
        """
    )

    parser.add_argument('--mode', choices=['tasks', 'checkpoints'], required=True,
                       help='评估模式')
    parser.add_argument('--config', required=True,
                       help='基础配置文件')
    parser.add_argument('--run-prefix', required=True,
                       help='运行名称前缀')

    # Tasks 模式
    parser.add_argument('--tasks', nargs='+',
                       help='任务列表')
    parser.add_argument('--tasks-file',
                       help='任务列表文件 (每行一个任务)')

    # Checkpoints 模式
    parser.add_argument('--task',
                       help='任务名称 (用于 checkpoints 模式)')
    parser.add_argument('--checkpoints', nargs='+',
                       help='Checkpoint 列表 (格式: name=path)')
    parser.add_argument('--checkpoints-file',
                       help='Checkpoint 列表文件 (格式: name=path)')

    # 其他选项
    parser.add_argument('--delay', type=int, default=0,
                       help='评估之间的延迟(秒)')
    parser.add_argument('--dry-run', action='store_true',
                       help='模拟运行，不实际执行')

    args = parser.parse_args()

    # 验证配置文件
    if not Path(args.config).exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    # Tasks 模式
    if args.mode == 'tasks':
        # 获取任务列表
        if args.tasks_file:
            with open(args.tasks_file, 'r') as f:
                tasks = [line.strip() for line in f if line.strip()]
        elif args.tasks:
            tasks = args.tasks
        else:
            print("Error: Must specify --tasks or --tasks-file")
            sys.exit(1)

        # 运行批量评估
        results = batch_eval_tasks(
            args.config,
            tasks,
            args.run_prefix,
            delay=args.delay,
            dry_run=args.dry_run
        )

    # Checkpoints 模式
    elif args.mode == 'checkpoints':
        if not args.task:
            print("Error: Must specify --task for checkpoints mode")
            sys.exit(1)

        # 获取 checkpoint 列表
        checkpoints = {}
        if args.checkpoints_file:
            with open(args.checkpoints_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line:
                        name, path = line.split('=', 1)
                        checkpoints[name.strip()] = path.strip()
        elif args.checkpoints:
            for item in args.checkpoints:
                if '=' not in item:
                    print(f"Error: Invalid checkpoint format: {item}")
                    print("Expected format: name=path")
                    sys.exit(1)
                name, path = item.split('=', 1)
                checkpoints[name] = path
        else:
            print("Error: Must specify --checkpoints or --checkpoints-file")
            sys.exit(1)

        # 运行批量评估
        results = batch_eval_checkpoints(
            args.config,
            args.task,
            checkpoints,
            args.run_prefix,
            delay=args.delay,
            dry_run=args.dry_run
        )

    # 退出代码
    failed = sum(1 for r in results if not r['success'])
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
