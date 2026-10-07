import tempfile
import unittest
from pathlib import Path

from pipeline.config import normalize_config
from utils.force_utils import docker_command


class PipelineContractTest(unittest.TestCase):
    def base_config(self, udf_path):
        return {
            "job": {"project_name": "nbr_germany_2018"},
            "runtime": {
                "process_folder": "/drive_mount/process",
                "force_ard_dir": "/force/C1/L2/ard",
                "force_image": "davidfrantz/force:test",
                "docker_cmd": "docker",
                "mounts": ["/drive_mount:/drive_mount", "/force:/force"],
            },
            "inputs": {"aois": ["/data/germany.shp"]},
            "processing": {
                "mode": "udf",
                "execute": True,
                "mosaic": True,
                "hold": False,
            },
            "parameters": {"FILE_PYTHON": udf_path},
        }

    def test_relative_udf_is_resolved_against_source_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            udf = source_root / "utils" / "templates" / "udf.py"
            udf.parent.mkdir(parents=True)
            udf.write_text("# udf\n", encoding="utf-8")

            config = normalize_config(
                self.base_config("utils/templates/udf.py"), source_root
            )

            self.assertEqual(config["processing"]["mode"], "UDF")
            self.assertEqual(config["parameters"]["FILE_PYTHON"], str(udf))

    def test_interactive_hold_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            udf = source_root / "udf.py"
            udf.write_text("# udf\n", encoding="utf-8")
            config = self.base_config(str(udf))
            config["processing"]["hold"] = True

            with self.assertRaisesRegex(ValueError, "hold must be false"):
                normalize_config(config, source_root)

    def test_docker_command_uses_configured_image_and_mounts(self):
        config = self.base_config("/source/udf.py")

        command = docker_command(config, "force-higher-level", "/work/tsa.prm")

        self.assertEqual(command[:3], ["docker", "run", "--rm"])
        self.assertIn("/drive_mount:/drive_mount", command)
        self.assertIn("/force:/force", command)
        self.assertIn("davidfrantz/force:test", command)
        self.assertEqual(command[-2:], ["force-higher-level", "/work/tsa.prm"])
        self.assertNotIn("sudo", command)


if __name__ == "__main__":
    unittest.main()
