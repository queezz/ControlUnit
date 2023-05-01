import numpy as np


def maskIonPres(voltages: np.ndarray, **kws):
    """
    apply IGrange if signal is bigger than 0.01
    """
    m = kws.get("IGrange", 1e-3)
    mask = np.where(voltages[:, 1] > 0.01)
    voltages[:, 1] = voltages[:, 1] * m
    tmp = voltages[mask]
    return tmp


def calcIGPres(voltage, mode: int, scale: float):
    """
     convert 0-10 V output into Torr

    Parameters
    ----------
    voltage: array
        array of voltage output from Ionization Gauge controller, 0-10 V.
    mode: int
        0: linear mode, 1: log mode, selected in controller
    scale: float
        multiplier for linear mode, must be entered manually
    """
    if mode == 0:
        return voltage * (10 ** scale)
    elif mode == 1:
        return 10 ** (-5 + voltage / 2)
    else:
        return


if __name__ == "__main__":
    pass
