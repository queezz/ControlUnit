import csv
import os
from os.path import join, expanduser
import adcchannels


def load_settings(path_to_file):
    """
    UPDATE: change sattings from a csv file to 
    fully defined settings in a yaml file.
    """
    import yaml

    with open(path_to_file, "r") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)


def select_settings(path_to_file="settings.yml", verbose=False):
    """
    Check if there is local settings file and 
    if its version is same as current, load local one.
    """
    local_settings = os.path.join(os.path.expanduser("~"), ".controlunit", "settings.yml")

    try:
        local_config = load_settings(local_settings)
        config = load_settings(path_to_file)
        if local_config["Settings Version"] == config["Settings Version"]:
            config = local_config
            if verbose:
                print(f"configuration file loaded:\n{local_settings}")
            return config
    except Exception as ex:
        if verbose:
            print(ex)

    config = load_settings(path_to_file)
    if verbose:
        print(f"configuration file loaded:\n{os.path.abspath(path_to_file)}")

    return config


# TODO: make the main method
def init_configuration(settings="settings.yml"):
    # TODO: add option to load ~/.controlunit/settings.yml if exists
    config = select_settings(settings)
    # make_data_folders_updated_function()

    adc_channels = {
        name: adcchannels.AdcChannelProps(name, **config["ADC Channels"][name])
        for name in list(config["ADC Channels"])
    }

    config["Adc Channel Properties"] = adc_channels
    config["Data Folder"] = init_datafolder(config)

    config["ADC Signal Names"] = list(config["ADC Channels"])
    config["ADC Converted Names"] = [i + "_c" for i in config["ADC Signal Names"]]
    config["ADC Column Names"] = (
        config["ADC Additional Columns"] + config["ADC Signal Names"] + config["ADC Converted Names"]
    )

    a = config["ADC Channels"]
    config["ADC Channel Numbers"] = [a[i]["Channel"] for i in list(a)]

    print("controlunit configuration loaded successfully.")
    return config


def init_datafolder(config):
    """
    Create folder for saving data, if not existing
    if datafolder starts with '~' - put the folder in home directory
    """
    foldername = config["Data Folder"]

    if foldername.startswith("~"):
        home = expanduser("~")
        foldername = home + foldername[1:]

    foldername = os.path.abspath(foldername)
    print(f"I'll try to create datafolder: {foldername}")

    try:
        os.makedirs(foldername)
        print(f"created {foldername}")
    except FileExistsError:
        print("Already exists.")
        pass

    return foldername


# TODO: Remove


def make_datafolders():
    """
    Create folder for saving data, if not existing
    if datafolder starts with '~' - put the folder in home directory
    """
    settings = read_settings()
    foldername = settings["datafolder"]

    if foldername.startswith("~"):
        home = expanduser("~")
        foldername = home + foldername[1:]

    print(f"I'll try to create datafolder: {foldername}")

    try:
        os.makedirs(foldername)
        print(f"created {foldername}")
    except FileExistsError:
        pass

    return foldername


def read_settings():
    """ Read .settings and get datafoldr path"""
    pth = None
    sampling_rate = 0.01
    with open(".settings", "r") as f:
        s = csv.reader(f, delimiter=",")
        for r in s:
            if r[0] == "datafolder":
                pth = r[1].strip()
            if r[0] == "pathislocal":
                local = r[1].strip()
            if r[0] == "sampling_rate":
                sampling_rate = r[1].strip()
    if local == "True":
        local = True
    sampling_rate = float(sampling_rate)
    settings = {
        "datafolder": pth,
        "pathislocal": local,
        "samplingtime": sampling_rate,
    }

    return settings


if __name__ == "__main__":
    # print(read_settings())
    make_datafolders()
