"""Wrapper script to run eval.py with file logging configured.

Usage:
    python test/run_eval_with_logging.py \
        --log-file logs/eval_run.log \
        --task-name turning_on_radio \
        --robot-config omnigibson/eval/r1pro.yaml \
        --mode public_test \
        --instance-indices 0 \
        --max-steps 500 \
        --output-dir eval_logs/turning_on_radio \
        --write-video
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_file_logging(log_file: str, level: int = logging.INFO):
    """Configure root logger to write to both console and file."""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    print(f"Logging configured: file={log_file}, level={logging.getLevelName(level)}", file=sys.stderr)


def main():
    # Parse wrapper-specific args first
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--log-file',
        default=None,
        help='Path to log file. Default: logs/eval_YYYYMMDD_HHMMSS.log'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level. Default: INFO'
    )

    # Parse known args only, let eval.py handle the rest
    args, remaining_args = parser.parse_known_args()

    # Setup logging
    if args.log_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.log_file = f'logs/eval_{timestamp}.log'

    log_level = getattr(logging, args.log_level)
    setup_file_logging(args.log_file, level=log_level)

    # Reconstruct sys.argv for eval.py
    sys.argv = ['omnigibson.eval.eval'] + remaining_args

    # Import and run eval.py's main
    from omnigibson.eval.eval import main as eval_main

    try:
        eval_main()
    except Exception:
        logging.exception("Evaluation failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
