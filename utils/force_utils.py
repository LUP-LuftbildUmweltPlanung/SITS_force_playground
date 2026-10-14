import os
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import geopandas as gpd


def run_command(command, hold=False):
    """Run a command in the current terminal and propagate failures."""
    if hold:
        raise ValueError("Interactive hold mode is not supported by the pipeline")
    subprocess.run(command, check=True)


def docker_command(config, *arguments):
    runtime = config["runtime"]
    command = shlex.split(str(runtime.get("docker_cmd", "docker")))
    if not command:
        raise ValueError("runtime.docker_cmd cannot be empty")
    command.extend(["run", "--rm"])
    for mount in runtime.get("mounts", []):
        command.extend(["-v", str(mount)])
    if "FILL_INTERNAL_MONTH_GAPS" in config.get("parameters", {}):
        fill_gaps = str(
            config["parameters"]["FILL_INTERNAL_MONTH_GAPS"]
        ).upper()
        command.extend(["-e", f"FORCE_NBR_FILL_INTERNAL_GAPS={fill_gaps}"])
    command.extend(
        [
            "-u",
            f"{os.getuid()}:{os.getgid()}",
            str(runtime["force_image"]),
            *[str(item) for item in arguments],
        ]
    )
    return command


def generate_input_feature_line(tif_path, num_layers):
    sequence = " ".join(str(i) for i in range(1, num_layers + 1))
    return f"INPUT_FEATURE = {tif_path} {sequence}"


def replace_parameters(filename, replacements):
    with open(filename, "r", encoding="utf-8") as stream:
        content = stream.read()

    for old_line, new_line in replacements.items():
        tag = old_line.split("=", 1)[0].strip()
        pattern = rf"^{re.escape(tag)}\s*=.*$"
        content, count = re.subn(pattern, new_line, content, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"Parameter {tag!r} was not found exactly once in {filename}")

    with open(filename, "w", encoding="utf-8") as stream:
        stream.write(content)


def extract_coordinates(file_path):
    with open(file_path, "r", encoding="utf-8") as stream:
        lines = stream.readlines()[1:]
    if not lines:
        raise ValueError(f"FORCE did not return any tiles for the AOI: {file_path}")
    x_values = [int(line.split("_")[0][1:]) for line in lines]
    y_values = [int(line.split("_")[1][1:]) for line in lines]
    return f"{min(x_values)} {max(x_values)}", f"{min(y_values)} {max(y_values)}"


def check_and_reproject_shapefile(shapefile_path, output_directory, target_epsg=3035):
    """Return an EPSG:3035 AOI without modifying the source dataset."""
    shapefile_path = Path(shapefile_path).expanduser().resolve()
    gdf = gpd.read_file(shapefile_path)
    if gdf.crs is None:
        raise ValueError(f"AOI has no coordinate reference system: {shapefile_path}")
    if gdf.crs.to_epsg() == target_epsg:
        print(f"Shapefile is already in EPSG:{target_epsg}")
        return str(shapefile_path)

    output_directory = Path(output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    destination = output_directory / f"{shapefile_path.stem}_{target_epsg}.shp"
    print(f"Reprojecting shapefile to EPSG:{target_epsg}: {destination}")
    gdf.to_crs(epsg=target_epsg).to_file(destination, driver="ESRI Shapefile")
    return str(destination)


def execute_force(params_path, config):
    run_command(docker_command(config, "force-higher-level", params_path))


def force_process(config):
    process_folder = Path(config["runtime"]["process_folder"]).resolve()
    project_name = config["job"]["project_name"]
    force_ard_dir = config["runtime"]["force_ard_dir"]
    aois = config["inputs"]["aois"]
    mode = config["processing"]["mode"].upper()
    hold = bool(config["processing"].get("hold", False))
    execute = bool(config["processing"]["execute"])

    source_root = Path(__file__).resolve().parents[1]
    skeleton = source_root / "utils" / "skel"
    cube_skeleton = skeleton / "force_cube_sceleton"
    definition = cube_skeleton / "datacube-definition.prj"
    project_temp = process_folder / "temp" / project_name
    started = time.time()

    for aoi_setting in aois:
        source_aoi = Path(aoi_setting).expanduser().resolve()
        aoi_name = source_aoi.stem
        print(f"FORCE PROCESSING FOR {source_aoi}")

        aoi = check_and_reproject_shapefile(
            source_aoi,
            project_temp / "inputs" / aoi_name,
        )
        aoi_path = Path(aoi)
        force_folder = project_temp / "FORCE" / aoi_name
        mask_folder = process_folder / "temp" / "_mask" / project_name / aoi_name
        tiles_folder = force_folder / "tiles_tss"
        provenance_folder = force_folder / "provenance"
        for folder in (force_folder, mask_folder, tiles_folder, provenance_folder):
            folder.mkdir(parents=True, exist_ok=True)
        for folder in (force_folder, mask_folder, tiles_folder):
            shutil.copy(definition, folder / definition.name)

        tile_extent = force_folder / "tile_extent.txt"
        run_command(
            docker_command(
                config,
                "force-tile-extent",
                aoi_path,
                "-d",
                cube_skeleton,
                "-a",
                tile_extent,
            ),
            hold,
        )

        run_command(
            docker_command(config, "force-cube", "-o", mask_folder, aoi_path),
            hold,
        )
        run_command(docker_command(config, "force-mosaic", mask_folder), hold)

        if mode == "UDF":
            tsa_param = force_folder / "tsa_UDF.prm"
            force_mode = "UDF"
            shutil.copy(skeleton / "udf_pixel.py", force_folder / "UDF_pixel.py")
        else:
            tsa_param = force_folder / "tsa.prm"
            force_mode = "TSA"

        run_command(
            docker_command(config, "force-parameter", tsa_param, force_mode),
            hold,
        )

        x_tile_range, y_tile_range = extract_coordinates(tile_extent)
        parameters = config["parameters"]
        replacements = {
            "DIR_LOWER = NULL": f"DIR_LOWER = {force_ard_dir}",
            "DIR_HIGHER = NULL": f"DIR_HIGHER = {tiles_folder}",
            "DIR_PROVENANCE = NULL": f"DIR_PROVENANCE = {provenance_folder}",
            "DIR_MASK = NULL": f"DIR_MASK = {mask_folder}",
            "BASE_MASK = NULL": f"BASE_MASK = {aoi_path.stem}.tif",
            "X_TILE_RANGE = 0 0": f"X_TILE_RANGE = {x_tile_range}",
            "Y_TILE_RANGE = 0 0": f"Y_TILE_RANGE = {y_tile_range}",
            "STREAMING = TRUE": f"STREAMING = {str(parameters['STREAMING']).upper()}",
            "OUTPUT_SUBFOLDERS = FALSE": (
                f"OUTPUT_SUBFOLDERS = {str(parameters['OUTPUT_SUBFOLDERS']).upper()}"
            ),
            "CHUNK_SIZE = 0 0": f"CHUNK_SIZE = {parameters['CHUNK_SIZE']}",
            "ABOVE_NOISE = 0": f"ABOVE_NOISE = {parameters['ABOVE_NOISE']}",
            "BELOW_NOISE = 0": f"BELOW_NOISE = {parameters['BELOW_NOISE']}",
            "NTHREAD_READ = 0": f"NTHREAD_READ = {parameters['NTHREAD_READ']}",
            "NTHREAD_COMPUTE = 0": f"NTHREAD_COMPUTE = {parameters['NTHREAD_COMPUTE']}",
            "NTHREAD_WRITE = 0": f"NTHREAD_WRITE = {parameters['NTHREAD_WRITE']}",
            "DATE_RANGE = 2010-01-01 2019-12-31": f"DATE_RANGE = {parameters['DATE_RANGE']}",
            "DOY_RANGE = 1 365": f"DOY_RANGE = {parameters['DOY_RANGE']}",
            "SENSORS = LND08 LND09 SEN2A SEN2B SEN2C": f"SENSORS = {parameters['SENSORS']}",
            "TARGET_SENSOR = LNDLG": f"TARGET_SENSOR = {parameters['TARGET_SENSOR']}",
            "SPECTRAL_ADJUST = FALSE": (
                f"SPECTRAL_ADJUST = {str(parameters['SPECTRAL_ADJUST']).upper()}"
            ),
            "RESOLUTION = 10": f"RESOLUTION = {parameters['RESOLUTION']}",
        }

        if mode == "UDF":
            replacements.update(
                {
                    "FILE_PYTHON = NULL": f"FILE_PYTHON = {parameters['FILE_PYTHON']}",
                    "PYTHON_TYPE = PIXEL": (
                        f"PYTHON_TYPE = {parameters.get('PYTHON_TYPE', 'CHUNK').upper()}"
                    ),
                    "OUTPUT_PYP = FALSE": "OUTPUT_PYP = TRUE",
                }
            )
        else:
            replacements.update(
                {
                    "INDEX = NDVI EVI NBR RED NIR": f"INDEX = {parameters['INDEX']}",
                    "OUTPUT_TSS = FALSE": "OUTPUT_TSS = TRUE",
                }
            )

        replace_parameters(tsa_param, replacements)
        if execute:
            execute_force(tsa_param, config)

    elapsed_minutes = (time.time() - started) / 60
    print(f"FORCE processing completed after {elapsed_minutes} minutes")
