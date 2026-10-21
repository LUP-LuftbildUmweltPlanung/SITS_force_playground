import os
import subprocess
import time
import shutil
import geopandas as gpd

def run_command(cmd, hold):
    if hold:
        subprocess.run(['xterm', '-hold', '-e', cmd])
    else:
        subprocess.run(['xterm', '-e', cmd])


def generate_input_feature_line(tif_path, num_layers):
    sequence = ' '.join(str(i) for i in range(1, num_layers + 1))
    return f"INPUT_FEATURE = {tif_path} {sequence}"


def replace_parameters(filename, replacements):
    with open(filename, 'r') as f:
        content = f.read()
        for key, value in replacements.items():
            content = content.replace(key, value)
    with open(filename, 'w') as f:
        f.write(content)

def extract_coordinates(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    #Skip the first line
    lines = lines[1:]
    #Extract X and Y values
    x_values = [int(line.split('_')[0][1:]) for line in lines]
    y_values = [int(line.split('_')[1][1:]) for line in lines]
    #Extract the desired values
    x_str = f"{min(x_values)} {max(x_values)}"
    y_str = f"{min(y_values)} {max(y_values)}"

    return x_str, y_str

def check_and_reproject_shapefile(shapefile_path, target_epsg=3035):
    # Load the shapefile
    gdf = gpd.read_file(shapefile_path)
    # Check the current CRS of the shapefile
    if gdf.crs.to_epsg() != target_epsg:
        print("Reprojecting shapefile to EPSG: 3035")
        # Reproject the shapefile
        gdf = gdf.to_crs(epsg=target_epsg)
        # Define the new file path
        new_shapefile_path = shapefile_path.replace(".shp", "_3035.shp")
        # Save the reprojected shapefile
        gdf.to_file(new_shapefile_path, driver='ESRI Shapefile')
        print(f"Shapefile reprojected and saved to {new_shapefile_path}")
        return new_shapefile_path
    else:
        print("Shapefile is already in EPSG: 3035")
        return shapefile_path


def execute_force(params_path, hold, local_dir, force_dir):
    cmd = f'sudo docker run -v {local_dir} -v {force_dir} -u "$(id -u):$(id -g)" davidfrantz/force ' \
          "force-higher-level " \
          f"{params_path}"

    run_command(cmd, hold)


def force_process(config):
    # define parameters
    base_path = config["project"]["base_path"]
    project_name = config["project"]["name"]
    force_dir = config["force"]["force_dir"]
    local_dir = config["force"]["local_dir"]
    force_version = config["force"]["image"]
    aois = config["aoi"]["files"]
    mode = config["processing"]["mode"].upper()
    hold = config["processing"]["hold"]
    execute = config["processing"]["execute"]

    base_path_script = os.getcwd()
    #base_path_script = os.path.dirname(os.path.abspath(__file__))
    startzeit = time.time()

    for aoi in aois:
        print(f"FORCE PROCESSING FOR {aoi}")

        basename = os.path.basename(aoi)
        aoi = check_and_reproject_shapefile(aoi)

        if mode == "UDF":
            print(mode)
            tsa_param = f"{base_path}/process/temp/{project_name}/FORCE/{basename}/tsa_UDF.prm"
            force_mode = "UDF"
        else:
            tsa_param = f"{base_path}/process/temp/{project_name}/FORCE/{basename}/tsa.prm"
            force_mode = "TSA"

        if os.path.isfile(tsa_param):
            print(f"Existing parameter file found: {tsa_param}")
            if execute:
                execute_force(tsa_param, hold, local_dir, force_dir)
            continue

        ### get force extend
        os.makedirs(f'{base_path}/process/temp/{project_name}/FORCE/{basename}', exist_ok=True)

        shutil.copy(f"{base_path_script}/utils/skel/force_cube_sceleton/datacube-definition.prj",f"{base_path}/process/temp/{project_name}/FORCE/{basename}/datacube-definition.prj")

        cmd = f'sudo docker run -v {local_dir} -v {force_dir} -u "$(id -u):$(id -g)" {force_version} ' \
               f'force-tile-extent {aoi} -d {base_path_script}/utils/skel/force_cube_sceleton -a {base_path}/process/temp/{project_name}/FORCE/{basename}/tile_extent.txt'

        run_command(cmd, hold)

        ### mask
        os.makedirs(f"{base_path}/process/temp/_mask/{project_name}/{basename}", exist_ok=True)

        shutil.copy(f"{base_path_script}/utils/skel/force_cube_sceleton/datacube-definition.prj",f"{base_path}/process/temp/_mask/{project_name}/{basename}/datacube-definition.prj")
        cmd = f'sudo docker run -v {local_dir} -u "$(id -u):$(id -g)" {force_version} ' \
              f"force-cube -o {base_path}/process/temp/_mask/{project_name}/{basename} " \
              f"{aoi}"

        run_command(cmd, hold)

        ###mask mosaic
        cmd = f'sudo docker run -v {local_dir} -u "$(id -u):$(id -g)" {force_version} ' \
              f"force-mosaic {base_path}/process/temp/_mask/{project_name}/{basename}"

        run_command(cmd, hold)

        ###force parameters

        os.makedirs(f"{base_path}/process/temp/{project_name}/FORCE/{basename}/provenance", exist_ok=True)
        os.makedirs(f"{base_path}/process/temp/{project_name}/FORCE/{basename}/tiles_tss", exist_ok=True)

        shutil.copy(f"{base_path_script}/utils/skel/force_cube_sceleton/datacube-definition.prj",f"{base_path}/process/temp/{project_name}/FORCE/{basename}/datacube-definition.prj")
        shutil.copy(f"{base_path_script}/utils/skel/force_cube_sceleton/datacube-definition.prj",f"{base_path}/process/temp/{project_name}/FORCE/{basename}/tiles_tss/datacube-definition.prj")

        if mode == "UDF":
            shutil.copy(f"{base_path_script}/utils/skel/udf_pixel.py",f"{base_path}/process/temp/{project_name}/FORCE/{basename}/UDF_pixel.py")

        param_cmd = (
            f'sudo docker run -v {local_dir} -v {force_dir} -u "$(id -u):$(id -g)" '
            f'{force_version} force-parameter {tsa_param} {force_mode}'
        )
        subprocess.run(['bash', '-lc', param_cmd], check=True)

        X_TILE_RANGE, Y_TILE_RANGE = extract_coordinates(f"{base_path}/process/temp/{project_name}/FORCE/{basename}/tile_extent.txt")

        # Define common replacements
        replacements = {
            # INPUT/OUTPUT DIRECTORIES
            f'DIR_LOWER = NULL':f'DIR_LOWER = {force_dir.split(":")[0]}/C1/L2/ard',
            f'DIR_HIGHER = NULL':f'DIR_HIGHER = {base_path}/process/temp/{project_name}/FORCE/{basename}/tiles_tss',
            f'DIR_PROVENANCE = NULL':f'DIR_PROVENANCE = {base_path}/process/temp/{project_name}/FORCE/{basename}/provenance',
            # MASKING
            f'DIR_MASK = NULL':f'DIR_MASK = {base_path}/process/temp/_mask/{project_name}/{basename}',
            f'BASE_MASK = NULL':f'BASE_MASK = {os.path.basename(aoi).replace(".shp",".tif")}',
            # PROCESSING EXTENT AND RESOLUTION
            f'X_TILE_RANGE = 0 0': f'X_TILE_RANGE = {X_TILE_RANGE}',
            f'Y_TILE_RANGE = 0 0': f'Y_TILE_RANGE = {Y_TILE_RANGE}',
            # COMPUTATIONAL PARAMETERS
            f"STREAMING = TRUE" : f"STREAMING = {str(config['parameters']['STREAMING']).upper()}",
            f"OUTPUT_SUBFOLDERS = FALSE": f"OUTPUT_SUBFOLDERS = {str(config['parameters']['OUTPUT_SUBFOLDERS']).upper()}",
            f"CHUNK_SIZE = 0 0": f"CHUNK_SIZE = {config['parameters']['CHUNK_SIZE']}",
            f"ABOVE_NOISE = 0": f"ABOVE_NOISE = {config['parameters']['ABOVE_NOISE']}",
            f"BELOW_NOISE = 0": f"BELOW_NOISE = {config['parameters']['BELOW_NOISE']}",
            f"NTHREAD_READ = 0": f"NTHREAD_READ = {config['parameters']['NTHREAD_READ']}",
            f"NTHREAD_COMPUTE = 0": f"NTHREAD_COMPUTE = {config['parameters']['NTHREAD_COMPUTE']}",
            f"NTHREAD_WRITE = 0": f"NTHREAD_WRITE = {config['parameters']['NTHREAD_WRITE']}",
            # USER SPECIFIC
            f"DATE_RANGE = 2010-01-01 2019-12-31": f"DATE_RANGE = {config['parameters']['DATE_RANGE']}",
            f"DOY_RANGE = 1 365": f"DOY_RANGE = {config['parameters']['DOY_RANGE']}",
            f"SENSORS = LND08 LND09 SEN2A SEN2B SEN2C": f"SENSORS = {config['parameters']['SENSORS']}",
            f"TARGET_SENSOR = LNDLG": f"TARGET_SENSOR = {config['parameters']['TARGET_SENSOR']}",
            f"SPECTRAL_ADJUST = FALSE": f"SPECTRAL_ADJUST = {str(config['parameters']['SPECTRAL_ADJUST']).upper()}",
            f"RESOLUTION = 10": f"RESOLUTION = {config['parameters']['RESOLUTION']}",
            f"INDEX = NDVI EVI NBR RED NIR": f"INDEX = {config['parameters']['INDEX']}",
        }

        # Define UDF specific replacements
        if mode == "UDF":
            replacements.update({
                f"FILE_PYTHON = NULL": f"FILE_PYTHON = {config['parameters']['FILE_PYTHON']}",
                f"OUTPUT_PYP = FALSE": f"OUTPUT_PYP = TRUE",
            })
        else:
            replacements.update({
                f"OUTPUT_TSS = FALSE": f"OUTPUT_TSS = TRUE",
            })

        # Replace parameters in the parameter file
        replace_parameters(tsa_param, replacements)

        if execute:
            execute_force(tsa_param, hold, local_dir, force_dir)

    endzeit = time.time()
    print("FORCE-Processing beendet nach "+str((endzeit-startzeit)/60)+" Minuten")