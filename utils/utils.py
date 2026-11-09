import os
import shutil
import subprocess
import glob
from collections import defaultdict
import rasterio
import yaml


def load_config(config_path):
    with open(config_path, "r") as file:
        config = yaml.safe_load(file)
    return config


def create_folder_structure(base_path):
    # Define the folder structure
    folder_structure = [
        'process',
        'process/data',
        'process/results',
        'process/temp',
        'process/temp/_mask'
    ]

    # Create each folder if it does not exist
    for folder in folder_structure:
        path = os.path.join(base_path, folder)
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Created folder: {path}")
        else:
            print(f"Folder already exists: {path}")


def mosaic_rasters(input_files, output_filename):
    tmp_dir = output_filename.replace(".tif", "_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # Date (band description) → list of (file, band index)
    date_bands = defaultdict(list)
    for f in input_files:
        with rasterio.open(f) as src:
            for idx, desc in enumerate(src.descriptions, start=1):
                if not desc:
                    raise ValueError(f"Band {idx} in {f} hat keine Beschreibung")
                date_bands[desc].append((f, idx))

    dates = sorted(date_bands)  # chronological, when format equals YYYYMMDD

    # for every date: singleband-VRTs -> mosaic-VRT
    date_vrts = []
    for desc in dates:
        single_vrts = []
        for n, (f, idx) in enumerate(date_bands[desc]):
            v = f"{tmp_dir}/{desc}_{n}.vrt"
            subprocess.run(["gdal_translate", "-of", "VRT", "-b", str(idx), f, v], check=True)
            single_vrts.append(v)
        date_vrt = f"{tmp_dir}/{desc}.vrt"
        subprocess.run([
            "gdalbuildvrt",
            "-srcnodata", "-9999",
            "-vrtnodata", "-9999",
            "-overwrite",
            date_vrt,
            *single_vrts
        ], check=True)
        date_vrts.append(date_vrt)

    # stack all date-mosaics as bands (extent = union, fill gaps with nodata)
    stack_vrt = f"{tmp_dir}/stack.vrt"
    subprocess.run([
        "gdalbuildvrt",
        "-separate",
        "-srcnodata", "-9999",
        "-vrtnodata", "-9999",
        "-overwrite",
        stack_vrt,
        *date_vrts
    ], check=True)

    # write GeoTiff
    subprocess.run([
        "gdal_translate",
        "-of", "GTiff",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-co", "BLOCKXSIZE=512",
        "-co", "BLOCKYSIZE=512",
        "-co", "BIGTIFF=IF_SAFER",
        "-co", "NUM_THREADS=ALL_CPUS",
        stack_vrt,
        output_filename
    ], check=True)

    shutil.rmtree(tmp_dir)

    # set band description
    with rasterio.open(output_filename, "r+") as dst:
        for i, desc in enumerate(dates, start=1):
            dst.set_band_description(i, desc)


def mosaicing(config):
    base_path = config['project']['base_path']
    project_name = config['project']['name']
    aois = config['aoi']['files']
    temp_folder = base_path + "/process/temp"
    proc_folder = base_path + "/process/results/" + project_name
    os.makedirs(proc_folder, exist_ok=True)
    if config['processing']['mode'].upper() == "UDF":
        tif_folder = "PYP"
    else:
        tif_folder = "TSS"

    for aoi in aois:
        aoi_name = os.path.basename(aoi)
        # colect all tif files
        file_lst = glob.glob(f"{temp_folder}/{project_name}/FORCE/{aoi_name}/tiles_tss/X*/{tif_folder}/*.tif")
        print(file_lst)
        mosaics = defaultdict(list)
        for f in file_lst:
            tif_name = os.path.basename(f)
            mosaics[tif_name].append(f)
        # iterate over lists
        for mosaic_files in mosaics.values():
            output_folder = f"{proc_folder}/{aoi_name}"
            os.makedirs(output_folder, exist_ok=True)
            base = os.path.basename(mosaic_files[0])
            output_filename = f"{output_folder}/{base}"
            mosaic_rasters(mosaic_files, output_filename)