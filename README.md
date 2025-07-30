# SITS Force Playground

Code for playing around with [FORCE Time Series Framework](https://force-eo.readthedocs.io/en/latest/index.html). The code works with the latest FORCE version 
3.8.01.


## 1. Installing
```
conda create --name SITSclass python==3.9
conda activate SITSclass
sudo apt-get install xterm
```

_**Notes:**_

[How to Install FORCE with Docker](https://force-eo.readthedocs.io/en/latest/setup/docker.html#docker)


## 2. Getting Started

The script is based on the following folder structure :

<img src="img/folderstructure.png" width="650" height="500" />

The script should help to use FORCE-Framwork Path handling.
- *create_folder_structure*: checking / creating the folder structure
- *force_class*: creating mask for given shapefile and already filling out some necessary paths at project specific temp folder
- *execute_cmd*: executes the parameter file given by path

## Versioning
1.0


## Authors

* [**Benjamin Stöckigt**](https://github.com/Bensouh)

## License

This project is licensed under the GNU General Public Licence, Version 3 (GPLv3) - see the [LICENSE.md](LICENSE.md) file for details 

## Acknowledgments

* Time Series Classification by [Marc Rußwurm](https://github.com/MarcCoru)


* FORCE Framework by [David Frantz] (https://force-eo.readthedocs.io/en/latest/index.html).