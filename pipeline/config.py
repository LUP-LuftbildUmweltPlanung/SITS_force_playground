"""Load and validate the canonical FORCE playground configuration."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml


PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def normalize_config(config: dict, source_root: Path) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Configuration root must be a mapping")

    normalized = copy.deepcopy(config)
    try:
        project_name = normalized["job"]["project_name"]
        runtime = normalized["runtime"]
        process_folder = Path(runtime["process_folder"]).expanduser()
        force_ard_dir = runtime["force_ard_dir"]
        force_image = runtime["force_image"]
        aois = normalized["inputs"]["aois"]
        processing = normalized["processing"]
        parameters = normalized["parameters"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "Configuration must define job.project_name, runtime.process_folder, "
            "runtime.force_ard_dir, runtime.force_image, inputs.aois, processing, "
            "and parameters"
        ) from exc

    if not isinstance(project_name, str) or not PROJECT_NAME_PATTERN.fullmatch(project_name):
        raise ValueError(
            "job.project_name must contain only letters, numbers, dots, underscores, or dashes"
        )
    if not process_folder.is_absolute():
        raise ValueError("runtime.process_folder must be an absolute path")
    if not isinstance(force_ard_dir, str) or not force_ard_dir.startswith("/"):
        raise ValueError("runtime.force_ard_dir must be an absolute container path")
    if not isinstance(force_image, str) or not force_image:
        raise ValueError("runtime.force_image must be a non-empty string")
    if not isinstance(aois, list) or not aois or not all(isinstance(item, str) for item in aois):
        raise ValueError("inputs.aois must be a non-empty list of paths")
    if processing.get("hold", False):
        raise ValueError("processing.hold must be false for unattended execution")

    mode = str(processing.get("mode", "")).upper()
    if mode not in {"TSA", "UDF"}:
        raise ValueError("processing.mode must be TSA or UDF")
    processing["mode"] = mode

    if mode == "UDF":
        udf_setting = parameters.get("FILE_PYTHON")
        if not isinstance(udf_setting, str) or not udf_setting:
            raise ValueError("parameters.FILE_PYTHON is required in UDF mode")
        udf_path = Path(udf_setting).expanduser()
        if not udf_path.is_absolute():
            udf_path = source_root / udf_path
        udf_path = udf_path.resolve()
        if not udf_path.is_file():
            raise ValueError(f"UDF Python file does not exist: {udf_path}")
        parameters["FILE_PYTHON"] = str(udf_path)

        fill_internal_gaps = parameters.get("FILL_INTERNAL_MONTH_GAPS", False)
        if not isinstance(fill_internal_gaps, bool):
            raise ValueError("parameters.FILL_INTERNAL_MONTH_GAPS must be true or false")

    return normalized


def load_pipeline_config(config_path: Path, source_root: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    return normalize_config(config, source_root.resolve())
