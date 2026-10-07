#!/usr/bin/env python3
"""Canonical command-line entry point used by the Nextflow orchestrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from force_workflow import run_workflow
from pipeline.config import load_pipeline_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Workflow YAML configuration")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    config = load_pipeline_config(config_path, SOURCE_ROOT)
    run_workflow(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
