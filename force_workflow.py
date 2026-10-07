import argparse
from pathlib import Path

from utils.utils import create_folder_structure, mosaicing
from utils.force_utils import force_process


def run_workflow(config):
    create_folder_structure(config["runtime"]["process_folder"])
    force_process(config)

    if config["processing"]["mosaic"]:
        mosaicing(config)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    from pipeline.config import load_pipeline_config

    source_root = Path(__file__).resolve().parent
    config = load_pipeline_config(Path(args.config).expanduser().resolve(), source_root)
    run_workflow(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
