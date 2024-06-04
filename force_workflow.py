###### execute force dynamically ##########
### requirements: sudo apt-get install xterm
############################################
import subprocess
import time
import glob
from utils.utils import create_folder_structure, execute_cmd
from utils.force_class_utils import force_class

#########################
### define parameters ###
#########################

base_path = '/rvt_mount/'                                               # Base Path where ./process/ folder structure should be created
project_name = "test"                                                   # Project Name defined for data storage
force_dir = "/force:/force"                                             # Mount Point for Force-Datacube
local_dir = "/rvt_mount:/rvt_mount"                                     # Mount Point for local Drive
hold = True                                                             # if True, cmd must be closed manually - recommended for debugging FORCE

aois = glob.glob(f"/rvt_mount/process/data/test/aoi_sbs_test.shp")      # Define multiple or single AOI-Shapefile

###################################################################
### check / create folder structure and create process skeleton ###
###################################################################

#create_folder_structure(base_path)
#force_class(project_name, force_dir, local_dir, base_path, aois, hold)


##############################
### execute parameter file ###
##############################
params_path = "/rvt_mount/process/temp/test/FORCE/aoi_sbs_test.shp/tsa.prm"
execute_cmd(params_path, hold, local_dir, force_dir)





###########################
### MASK Do it yourself ###
###########################

###mask create
# cmd = f'sudo docker run -v {local_dir} -u "$(id -u):$(id -g)" davidfrantz/force ' \
# "force-cube -o /uge_mount/FORCE/new_struc/process/result/aoi_sam/mask " \
# "/uge_mount/FORCE/new_struc/data/aoi_sam/aoi.shp"

###mask mosaic
# cmd = f'sudo docker run -v {local_dir} -u "$(id -u):$(id -g)" davidfrantz/force ' \
# "force-mosaic /uge_mount/FORCE/mask/femophys/process/"


###########################
### Execute Script Do it yourself ###
###########################

#cmd = f'sudo docker run -v {local_dir} -v {force_dir} -u "$(id -u):$(id -g)" davidfrantz/force ' \
 #     "force-higher-level " \
 #     "/rvt_mount/process/temp/test/FORCE/aoi_sbs_test.shp/tsa.prm"

#startzeit = time.time()
#print("Prozess gestartet bei "+str(startzeit))

#subprocess.run(['xterm','-hold','-e', cmd])
#subprocess.run(['xterm','-e', cmd2])

#endzeit = time.time()
#print("Prozess cmd beendet nach "+str((endzeit-startzeit)/60)+" Minuten")