import os
import subprocess

local_dir = "/uge_mount:/uge_mount"
create_params = True




output_path = "/uge_mount/FORCE/new_struc/scripts/skel/SAMPLE.prm"
params = "SMP" # TSA (Time Series Analysis), UDF (User Defined Function), SMP (Sampling)

comments= "-c " # "-c " --> no comments; "" --> commented
hold = True




if create_params == True:
    cmd = f"docker run -v {local_dir} davidfrantz/force " \
          f"force-parameter {comments}{output_path} {params}"

    if hold == True:
        subprocess.run(['xterm','-hold','-e', cmd])
    else:
        subprocess.run(['xterm', '-e', cmd])