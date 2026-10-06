#!/usr/bin/env python3
"""
统一评估接口
支持通过配置文件或命令行参数配置所有选项
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import yaml


class EvalRunner:
    """统一的评估运行器"""

    def __init__(self, config):
        self.config = config
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = self._generate_run_id()
        self.output_dir = self._prepare_output_dir()

    def _generate_run_id(self):
        """生成唯一的运行 ID"""
        policy_type = self.config['policy']['type']
        task_name = self.config['task']['name']
        return f"{policy_type}_{task_name}_{self.timestamp}"

    def _prepare_output_dir(self):
        """准备输出目录结构"""
        base_dir = Path(self.config['output']['base_dir'])

        # 结构: eval_logs/<policy_type>/<task_name>/<timestamp>_<run_name>/
        policy_type = self.config['policy']['type']
        task_name = self.config['task']['name']
        run_name = self.config['output'].get('run_name', 'default')

        output_dir = base_dir / policy_type / task_name / f"{self.timestamp}_{run_name}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (output_dir / "logs").mkdir(exist_ok=True)
        (output_dir / "json").mkdir(exist_ok=True)
        (output_dir / "videos").mkdir(exist_ok=True)

        print(f"✓ Output directory: {output_dir}")
        return output_dir

    def _save_config(self):
        """保存本次运行的配置"""
        config_file = self.output_dir / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
        print(f"✓ Config saved to: {config_file}")

    def _validate_paths(self):
        """验证所有必要的路径"""
        errors = []

        # 检查 policy 相关路径
        policy_config = self.config['policy']

        if policy_config['type'] == 'pi0.5':
            openpi_dir = Path(policy_config['openpi_dir']).expanduser()
            openpi_python = openpi_dir / ".venv" / "bin" / "python"
            checkpoint = Path(policy_config['checkpoint']).expanduser()

            if not openpi_python.exists():
                errors.append(f"OpenPI python not found: {openpi_python}")
            if not checkpoint.exists():
                errors.append(f"Checkpoint not found: {checkpoint}")

        elif policy_config['type'] == 'gr00t':
            groot_dir = Path(policy_config['groot_dir']).expanduser()
            groot_python = groot_dir / ".venv" / "bin" / "python"
            checkpoint = Path(policy_config['checkpoint']).expanduser()

            if not groot_python.exists():
                errors.append(f"GR00T python not found: {groot_python}")
            if not checkpoint.exists():
                errors.append(f"Checkpoint not found: {checkpoint}")

        # 检查 BEHAVIOR-1K 路径
        behavior_dir = Path(self.config['behavior']['path']).expanduser()
        behavior_python = Path(self.config['behavior']['python_path']).expanduser()

        if not behavior_dir.exists():
            errors.append(f"BEHAVIOR-1K not found: {behavior_dir}")
        if not behavior_python.exists():
            errors.append(f"BEHAVIOR python not found: {behavior_python}")

        if errors:
            print("ERROR: Validation failed:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)

        print("✓ All paths validated")

    def run(self):
        """运行完整的评估流程"""
        print("=" * 70)
        print(f"Starting evaluation run: {self.run_id}")
        print("=" * 70)

        # 保存配置
        self._save_config()

        # 验证路径
        self._validate_paths()

        # 启动 policy server
        print("\n[1/3] Starting policy server...")
        server_process = self._start_policy_server()

        try:
            # 等待服务器就绪
            print("\n[2/3] Waiting for policy server...")
            self._wait_for_server()

            # 运行评估
            print("\n[3/3] Running evaluation...")
            eval_exit_code = self._run_evaluation()

            # 创建结果总结
            self._create_summary(eval_exit_code)

            return eval_exit_code

        finally:
            # 清理
            print("\n[Cleanup] Stopping policy server...")
            self._stop_server(server_process)

    def _start_policy_server(self):
        """启动 policy server"""
        policy_config = self.config['policy']
        policy_type = policy_config['type']
        port = policy_config['port']

        # 准备日志文件
        server_log = self.output_dir / "logs" / "policy_server.log"

        # 构建命令
        if policy_type == 'pi0.5':
            cmd = self._build_pi05_server_cmd(policy_config, server_log)
        elif policy_type == 'gr00t':
            cmd = self._build_groot_server_cmd(policy_config, server_log)
        else:
            raise ValueError(f"Unknown policy type: {policy_type}")

        # 启动进程
        print(f"Server command: {' '.join(cmd[:3])} ...")
        print(f"Server log: {server_log}")

        with open(server_log, 'w') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=self._get_server_env(policy_type)
            )

        # 保存 PID
        pid_file = self.output_dir / "server.pid"
        with open(pid_file, 'w') as f:
            f.write(str(process.pid))

        print(f"✓ Policy server started (PID: {process.pid})")
        return process

    def _build_pi05_server_cmd(self, policy_config, server_log):
        """构建 pi0.5 server 命令"""
        openpi_dir = Path(policy_config['openpi_dir']).expanduser()
        python = openpi_dir / ".venv" / "bin" / "python"

        task_name = self.config['task']['name']

        cmd = [
            str(python),
            str(openpi_dir / "scripts" / "b1k" / "serve_b1k.py"),
            "--robot", "b1k/R1Pro",
            "--task", f"b1k/{task_name}",
            "--repo-id", policy_config.get('repo_id', task_name),
            "--policy.config", policy_config.get('policy_config', 'pi05_b1k'),
            "--policy.dir", str(Path(policy_config['checkpoint']).expanduser()),
            "--control_mode", policy_config.get('control_mode', 'receding_horizon'),
            "--action_horizon", str(policy_config.get('action_horizon', 16)),
            "--port", str(policy_config['port']),
        ]

        # 添加 record 参数
        if self.config['logging'].get('record_policy', False):
            cmd.append("--record")

        return cmd

    def _build_groot_server_cmd(self, policy_config, server_log):
        """构建 GR00T server 命令"""
        groot_dir = Path(policy_config['groot_dir']).expanduser()
        python = groot_dir / ".venv" / "bin" / "python"

        cmd = [
            str(python),
            str(groot_dir / "scripts" / "b1k" / "serve_b1k.py"),
            "--model-path", str(Path(policy_config['checkpoint']).expanduser()),
            "--modality-config-path", policy_config.get('modality_config', 'examples/b1k/r1pro.py'),
            "--embodiment-tag", policy_config.get('embodiment_tag', 'NEW_EMBODIMENT'),
            "--host", "127.0.0.1",
            "--port", str(policy_config['port']),
        ]

        return cmd

    def _get_server_env(self, policy_type):
        """获取 server 环境变量"""
        env = os.environ.copy()

        policy_config = self.config['policy']

        # GPU 设置
        env['CUDA_VISIBLE_DEVICES'] = str(policy_config.get('gpu_id', 0))

        # Policy 特定环境变量
        if policy_type == 'pi0.5':
            env['XLA_PYTHON_CLIENT_MEM_FRACTION'] = str(policy_config.get('mem_fraction', 0.85))
            env['OPENPI_LOG_LEVEL'] = self.config['logging'].get('policy_log_level', 'INFO')
        elif policy_type == 'gr00t':
            if 'hf_token' in policy_config:
                env['HF_TOKEN'] = policy_config['hf_token']

        return env

    def _wait_for_server(self):
        """等待 server 就绪"""
        port = self.config['policy']['port']
        timeout = self.config['policy'].get('startup_timeout', 300)
        check_interval = 3
        max_attempts = timeout // check_interval

        for i in range(1, max_attempts + 1):
            # 检查健康端点
            result = subprocess.run(
                ['curl', '-s', f'http://127.0.0.1:{port}/healthz'],
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0:
                print(f"✓ Policy server ready (after ~{i * check_interval}s)")
                return

            # 进度提示
            if i % 10 == 0:
                elapsed = i * check_interval
                print(f"  Still waiting... ({elapsed}s/{timeout}s)")

            time.sleep(check_interval)

        raise RuntimeError(f"Policy server did not become ready within {timeout}s")

    def _run_evaluation(self):
        """运行评估"""
        behavior_config = self.config['behavior']
        task_config = self.config['task']
        policy_config = self.config['policy']
        logging_config = self.config['logging']

        behavior_python = Path(behavior_config['python_path']).expanduser()
        behavior_dir = Path(behavior_config['path']).expanduser()

        # 准备评估日志
        eval_log = self.output_dir / "logs" / "omnigibson_eval.log"

        # 构建评估命令
        if logging_config.get('detailed_logging', False):
            # 使用带详细日志的包装器
            cmd = [
                str(behavior_python),
                str(behavior_dir / "test" / "run_eval_with_logging.py"),
                "--log-file", str(eval_log),
                "--log-level", logging_config.get('eval_log_level', 'INFO'),
            ]
        else:
            # 标准评估
            cmd = [
                str(behavior_python),
                "-m", "omnigibson.eval.eval",
            ]

        # 添加评估参数
        cmd.extend([
            "--task-name", task_config['name'],
            "--host", "127.0.0.1",
            "--port", str(policy_config['port']),
            "--output-dir", str(self.output_dir),
        ])

        # 可选参数
        # max_steps: None 或 0 表示不限制，不传递该参数
        max_steps = task_config.get('max_steps')
        if max_steps is not None and max_steps > 0:
            cmd.extend(["--max-steps", str(max_steps)])

        if task_config.get('write_video', True):
            cmd.append("--write-video")

        if task_config.get('env_wrapper'):
            cmd.extend(["--env-wrapper", task_config['env_wrapper']])

        # 运行评估
        print(f"Evaluation command: {' '.join(cmd[:3])} ...")
        print(f"Evaluation log: {eval_log}")

        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = str(policy_config.get('gpu_id', 0))

        with open(eval_log, 'w') as log_file:
            result = subprocess.run(
                cmd,
                stdout=log_file if logging_config.get('detailed_logging', False) else None,
                stderr=subprocess.STDOUT if logging_config.get('detailed_logging', False) else None,
                env=env,
                cwd=str(behavior_dir)
            )

        print(f"✓ Evaluation completed (exit code: {result.returncode})")
        return result.returncode

    def _stop_server(self, process):
        """停止 policy server"""
        try:
            process.terminate()
            process.wait(timeout=10)
            print("✓ Policy server stopped")
        except subprocess.TimeoutExpired:
            print("! Force killing policy server")
            process.kill()
            process.wait()

    def _create_summary(self, exit_code):
        """创建运行总结"""
        summary = {
            'run_id': self.run_id,
            'timestamp': self.timestamp,
            'config': self.config,
            'exit_code': exit_code,
            'output_dir': str(self.output_dir),
        }

        # 查找评估结果 JSON
        json_files = list((self.output_dir / "json").glob("*.json"))
        if json_files:
            summary['result_files'] = [str(f) for f in json_files]

        # 保存总结
        summary_file = self.output_dir / "summary.yaml"
        with open(summary_file, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False)

        print(f"\n{'=' * 70}")
        print(f"Evaluation completed: {self.run_id}")
        print(f"{'=' * 70}")
        print(f"Exit code: {exit_code}")
        print(f"Output directory: {self.output_dir}")
        print(f"Summary: {summary_file}")
        print(f"\nLogs:")
        print(f"  - Policy server: {self.output_dir / 'logs' / 'policy_server.log'}")
        print(f"  - OmniGibson eval: {self.output_dir / 'logs' / 'omnigibson_eval.log'}")


def load_config(config_file, overrides=None):
    """加载配置文件并应用覆盖"""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # 应用命令行覆盖
    if overrides:
        for key, value in overrides.items():
            keys = key.split('.')
            d = config
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value

    return config


def main():
    parser = argparse.ArgumentParser(
        description='统一评估接口 - 支持 pi0.5 和 GR00T',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            # 使用配置文件运行
            python eval_runner.py --config configs/pi05_turning_on_radio.yaml

            # 覆盖特定参数
            python eval_runner.py --config configs/pi05_turning_on_radio.yaml \\
                --set task.name=turning_on_lamp \\
                --set output.run_name=experiment_1

            # 使用预定义配置
            python eval_runner.py --preset pi05_turning_on_radio --run-name exp1
                    """
    )

    parser.add_argument('--config', type=str, help='配置文件路径')
    parser.add_argument('--preset', type=str, help='预定义配置名称')
    parser.add_argument('--run-name', type=str, help='本次运行的名称')
    parser.add_argument('--set', action='append', dest='overrides',
                       help='覆盖配置项 (格式: key.subkey=value)')

    args = parser.parse_args()

    # 加载配置
    if args.config:
        config_file = args.config
    elif args.preset:
        config_file = f"configs/{args.preset}.yaml"
    else:
        print("ERROR: Must specify --config or --preset")
        sys.exit(1)

    # 解析覆盖项
    overrides = {}
    if args.overrides:
        for override in args.overrides:
            key, value = override.split('=', 1)
            # 尝试解析为 JSON 值
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass  # 保持字符串
            overrides[key] = value

    # 应用 run_name
    if args.run_name:
        overrides['output.run_name'] = args.run_name

    # 加载配置
    config = load_config(config_file, overrides)

    # 运行评估
    runner = EvalRunner(config)
    exit_code = runner.run()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
