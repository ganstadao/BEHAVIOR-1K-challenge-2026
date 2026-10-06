#!/usr/bin/env python3
"""
配置生成器 - 快速生成评估配置文件
"""

import argparse
import sys
from pathlib import Path
import yaml


TEMPLATE = {
    'policy': {
        'type': 'pi0.5',
        'openpi_dir': '~/LINJ0121/openpi',
        'checkpoint': '~/LINJ0121/checkpoint/your_checkpoint',
        'repo_id': 'task_name',
        'policy_config': 'pi05_b1k',
        'control_mode': 'receding_horizon',
        'action_horizon': 16,
        'port': 8000,
        'gpu_id': 0,
        'mem_fraction': 0.85,
        'startup_timeout': 300,
    },
    'behavior': {
        'path': '~/project/BEHAVIOR-1K',
        'python_path': '~/.conda/envs/behavior/bin/python',
    },
    'task': {
        'name': 'turning_on_radio',
        'max_steps': 500,
        'write_video': True,
        'env_wrapper': 'omnigibson.eval.wrappers.RGBDFullResWrapper',
    },
    'logging': {
        'detailed_logging': True,
        'record_policy': True,
        'policy_log_level': 'DEBUG',
        'eval_log_level': 'INFO',
    },
    'output': {
        'base_dir': './eval_logs',
        'run_name': 'default',
    }
}


def generate_config(
    policy_type='pi0.5',
    task_name='turning_on_radio',
    checkpoint='~/LINJ0121/checkpoint/your_checkpoint',
    **kwargs
):
    """生成配置"""
    config = TEMPLATE.copy()

    # 设置 policy 类型
    config['policy']['type'] = policy_type
    config['policy']['checkpoint'] = checkpoint
    config['task']['name'] = task_name

    # Pi0.5 特定配置
    if policy_type == 'pi0.5':
        config['policy']['repo_id'] = kwargs.get('repo_id', task_name)
        if 'openpi_dir' in kwargs:
            config['policy']['openpi_dir'] = kwargs['openpi_dir']

    # GR00T 特定配置
    elif policy_type == 'gr00t':
        # 移除 pi0.5 特定字段
        for key in ['openpi_dir', 'repo_id', 'policy_config',
                    'control_mode', 'action_horizon', 'mem_fraction']:
            config['policy'].pop(key, None)

        # 添加 GR00T 特定字段
        config['policy']['groot_dir'] = kwargs.get('groot_dir', '~/LINJ0121/Isaac-GR00T')
        config['policy']['modality_config'] = kwargs.get('modality_config', 'examples/b1k/r1pro.py')
        config['policy']['embodiment_tag'] = kwargs.get('embodiment_tag', 'NEW_EMBODIMENT')
        config['logging']['record_policy'] = False  # GR00T 不支持

    # 应用其他覆盖
    for key, value in kwargs.items():
        if key in ['repo_id', 'openpi_dir', 'groot_dir', 'modality_config', 'embodiment_tag']:
            continue  # 已处理

        # 尝试设置到配置中
        if '.' in key:
            parts = key.split('.')
            d = config
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value
        else:
            # 顶层覆盖
            for section in config:
                if key in config[section]:
                    config[section][key] = value
                    break

    return config


def main():
    parser = argparse.ArgumentParser(
        description='配置文件生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 生成 pi0.5 配置
  python tools/config_gen.py \\
      --type pi0.5 \\
      --task turning_on_radio \\
      --checkpoint ~/checkpoints/my_model \\
      --output configs/my_config.yaml

  # 生成 GR00T 配置
  python tools/config_gen.py \\
      --type gr00t \\
      --task turning_on_lamp \\
      --checkpoint ~/checkpoints/groot_model \\
      --output configs/groot_lamp.yaml

  # 批量生成多个任务的配置
  for task in turning_on_radio turning_on_lamp opening_door; do
      python tools/config_gen.py \\
          --type pi0.5 \\
          --task $task \\
          --checkpoint ~/checkpoints/base_model \\
          --output configs/pi05_$task.yaml
  done
        """
    )

    parser.add_argument('--type', choices=['pi0.5', 'gr00t'], default='pi0.5',
                       help='Policy 类型')
    parser.add_argument('--task', required=True,
                       help='任务名称')
    parser.add_argument('--checkpoint', required=True,
                       help='Checkpoint 路径')
    parser.add_argument('--output', required=True,
                       help='输出配置文件路径')

    # Pi0.5 选项
    parser.add_argument('--openpi-dir',
                       help='OpenPI 目录')
    parser.add_argument('--repo-id',
                       help='Hugging Face repo ID')

    # GR00T 选项
    parser.add_argument('--groot-dir',
                       help='GR00T 目录')
    parser.add_argument('--modality-config',
                       help='Modality 配置文件')
    parser.add_argument('--embodiment-tag',
                       help='Embodiment tag')

    # 通用选项
    parser.add_argument('--port', type=int,
                       help='Server 端口')
    parser.add_argument('--gpu-id', type=int,
                       help='GPU ID')
    parser.add_argument('--max-steps', type=int,
                       help='最大步数')
    parser.add_argument('--no-video', action='store_true',
                       help='不生成视频')
    parser.add_argument('--no-logging', action='store_true',
                       help='禁用详细日志')
    parser.add_argument('--no-record', action='store_true',
                       help='禁用 policy 记录')

    args = parser.parse_args()

    # 收集 kwargs
    kwargs = {}
    if args.openpi_dir:
        kwargs['openpi_dir'] = args.openpi_dir
    if args.repo_id:
        kwargs['repo_id'] = args.repo_id
    if args.groot_dir:
        kwargs['groot_dir'] = args.groot_dir
    if args.modality_config:
        kwargs['modality_config'] = args.modality_config
    if args.embodiment_tag:
        kwargs['embodiment_tag'] = args.embodiment_tag
    if args.port:
        kwargs['port'] = args.port
    if args.gpu_id is not None:
        kwargs['gpu_id'] = args.gpu_id
    if args.max_steps:
        kwargs['max_steps'] = args.max_steps
    if args.no_video:
        kwargs['write_video'] = False
    if args.no_logging:
        kwargs['detailed_logging'] = False
    if args.no_record:
        kwargs['record_policy'] = False

    # 生成配置
    config = generate_config(
        policy_type=args.type,
        task_name=args.task,
        checkpoint=args.checkpoint,
        **kwargs
    )

    # 保存
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Configuration generated: {output_path}")
    print(f"\nTo run evaluation:")
    print(f"  python tools/eval_runner.py --config {output_path} --run-name my_run")


if __name__ == '__main__':
    main()
