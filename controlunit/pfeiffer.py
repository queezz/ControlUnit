"""
Pfeiffer Single gauge volts to pressure conversion.
"""
import numpy as np


def maskPfePres(voltages: np.ndarray):
    mask = np.where((voltages[:, 1] > 2.3) & (voltages[:, 1] < 6))
    tmp = voltages[mask]
    tmp[:, 1] = [calcPfePres(i) for i in tmp[:, 1]]
    return tmp


def calcPfePres(voltage):
    """ 
    Calculate pressure for Pfeiffer single gauge

    Parameters
    ----------
    voltage: array
        array of Pfeiffer Single Gauge values, V
    """
    # V → Torr
    exponent = 1.667 * voltage - 11.46
    pres = 10 ** exponent
    return pres


if __name__ == "__main__":
    # a = float(input())
    # print(calcPfePres(a))
    pass
