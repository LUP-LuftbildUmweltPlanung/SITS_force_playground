from utils.utils import load_config, create_folder_structure, mosaicing
from utils.force_utils import force_process


config = load_config("config.yaml")

create_folder_structure(config["project"]["base_path"])

force_process(config)

if config["processing"]["mosaic"]:
    mosaicing(config)