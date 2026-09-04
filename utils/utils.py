import os
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


def mosaic_rasters(input_files, output_filename, band_descriptions=None):
    vrt_path = output_filename.replace(".tif", "_tmp.vrt")

    # Built VRT
    subprocess.run([
        "gdalbuildvrt",
        "-srcnodata", "-9999",
        "-vrtnodata", "-9999",
        "-overwrite",
        vrt_path,
        *input_files
    ], check=True)

    # Stream VRT to GeoTiff
    subprocess.run([
        "gdal_translate",
        "-of",  "GTiff",
        "-co",  "COMPRESS=LZW",
        "-co",  "TILED=YES",
        "-co",  "BLOCKXSIZE=512",
        "-co",  "BLOCKYSIZE=512",
        "-co",  "BIGTIFF=IF_SAFER",
        "-co", "NUM_THREADS=ALL_CPUS",
        vrt_path,
        output_filename
    ], check=True)

    os.remove(vrt_path)

    # Set band descriptions
    if band_descriptions:
        with rasterio.open(output_filename, "r+") as dst:
            for i, desc in enumerate(band_descriptions, start=1):
                if desc:
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