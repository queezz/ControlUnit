import csv
import os
from os.path import join, expanduser


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
