import csv
import os
from os.path import join

bpth = os.path.dirname(__file__)


def make_datafolders():
    """ Create folder for saving data, if not existing """
    settings = read_settings()
    foldername = settings["datafolder"]

    try:
        os.mkdir(foldername)
        print(f"created {foldername}")
    except FileExistsError:
        pass
    except FileNotFoundError:
        # Put data folder on the Desktop of current user
        foldername = os.path.join(
            os.path.expanduser("~"), "Desktop", "data_controlunit"
        )

        if not os.path.exists(foldername):
            os.mkdir(foldername)
        settings["datafolder"] = foldername
        write_settings(settings)


def read_settings():
    """ Read .settings and get datafoldr path"""
    import os

    pth = None
    sampling_rate = 0.01

    with open(os.path.join(bpth, ".settings"), "r") as f:
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


def write_settings(settings):
    """ Write settings """
    with open(os.path.join(bpth, ".settings"), "w") as f:
        for i in settings:
            f.write(f"{i},{settings[i]}\n")


if __name__ == "__main__":
    # print(read_settings())
    make_datafolders()
