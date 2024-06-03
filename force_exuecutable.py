###### execute force dynamically ##########
### requirements: sudo apt-get install xterm
############################################
import subprocess
import time

###mask create
cmd = "docker run -v /uge_mount:/uge_mount davidfrantz/force " \
      "force-cube -o /uge_mount/FORCE/new_struc/process/result/aoi_sam/mask " \
      "/uge_mount/FORCE/new_struc/data/aoi_sam/aoi.shp"

###mask mosaic
cmd2 = "docker run -v /uge_mount:/uge_mount davidfrantz/force " \
      "force-mosaic /uge_mount/FORCE/mask/femophys/process/"

###force-higher-level

cmd3 = "docker run -it -v /uge_mount:/uge_mount -v /force:/force davidfrantz/force " \
      "force-higher-level " \
      "/uge_mount/FORCE/new_struc/process/temp/FEMO_SAM/TSA_NoCom.prm"

###############
####RUN 1 #####
###############
startzeit = time.time()
print("Prozess gestartet bei "+str(startzeit))

subprocess.run(['xterm','-e', cmd])
subprocess.run(['xterm','-e', cmd2])
subprocess.run(['xterm','-e', cmd3])
subprocess.run(['xterm','-hold','-e', cmd2])

endzeit = time.time()
print("Prozess cmd beendet nach "+str((endzeit-startzeit)/60)+" Minuten")

####################
####RUN 2 hold #####
####################
startzeit = time.time()
print("Prozess gestartet bei "+str(startzeit))

subprocess.run(['xterm','-hold','-e', cmd])
subprocess.run(['xterm','-hold','-e', cmd2])
subprocess.run(['xterm','-hold','-e', cmd3])

endzeit = time.time()
print("Prozess cmd beendet nach "+str((endzeit-startzeit)/60)+" Minuten")

