import csv
import os
from os.path import join, expanduser
from controlunit.devices.adc_channels import AdcChannelProps

# not working on RasPi, encoding error.
GOOD = "\U00002705"


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
    local_settings = os.path.join(
        os.path.expanduser("~"), ".controlunit", "settings.yml"
    )

    try:
        local_config = load_settings(local_settings)
        config = load_settings(path_to_file)
        if local_config["Settings Version"] == config["Settings Version"]:
            config = local_config
            if verbose:
                print(f" Configuration file loaded:\n{local_settings}")
            return config
    except FileNotFoundError as ex:
        pass

    script_directory = os.path.dirname(os.path.abspath(__file__))
    absolute_path_to_file = os.path.join(script_directory, path_to_file)
    config = load_settings(absolute_path_to_file)

    if verbose:
        print(f" Configuration file loaded:\n{os.path.abspath(path_to_file)}")

    return config


def init_configuration(settings="settings.yml", verbose=False):
    """
    Read settings.yml file, populate ADC Channels Properties,
    create datafolder if it dosn't exist.
    """
    config = select_settings(settings, verbose=verbose)
    config["Data Folder"] = init_datafolder(config)
    config["Log File Path"] = check_logfile(config)

    adc_channels = {
        name: AdcChannelProps(name, **config["ADC Channels"][name])
        for name in list(config["ADC Channels"])
    }

    config["Adc Channel Properties"] = adc_channels

    config["Ion Gauges"] = ion_gauge_names(config)
    for name in config["Ion Gauges"]:
        for column in (adc_channels[name].mode_column, adc_channels[name].scale_column):
            if column not in config["ADC Additional Columns"]:
                raise ValueError(
                    f"ion gauge {name} records into {column!r}, "
                    "which is not one of the ADC Additional Columns"
                )

    config["ADC Signal Names"] = list(config["ADC Channels"])
    config["ADC Converted Names"] = [i + "_c" for i in config["ADC Signal Names"]]
    config["ADC Column Names"] = (
        config["ADC Additional Columns"]
        + config["ADC Signal Names"]
        + config["ADC Converted Names"]
    )

    a = config["ADC Channels"]
    config["ADC Channel Numbers"] = [a[i]["Channel"] for i in list(a)]

    return config


def ion_gauge_names(config):
    """The ionization gauge channels, in the order the settings list them.

    Works on the raw settings as well as the initialised configuration, so
    the Control dock and the web view can name the gauges without a worker.
    The first one is the gauge the record has always carried as IGmode and
    IGscale.
    """
    return [
        name
        for name, channel in config["ADC Channels"].items()
        if channel["Conversion Function"] == "Ionization Gauge"
    ]


def check_logfile(config):
    folder = config["Data Folder"]
    logname = config["Log File"]
    logfilepath = os.path.join(folder, logname)
    if not os.path.exists(logfilepath):
        open(logfilepath, "a").close()
    return logfilepath


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

    try:
        os.makedirs(foldername)
        print(f" Created new datafolder: {foldername}")
    except FileExistsError:
        print(f" Using existing datafolder: {foldername}")
        pass

    return foldername


if __name__ == "__main__":
    print(load_settings())
