"""
Conversion functions for various senseors.
"""


def pfeiffer_single_gauge(voltage):
    r"""
    Calculate pressure for Pfeiffer single gauge.
    $Pressure = 10^{1.667 * voltage -11.46}\; Torr$

    Parameters
    ----------
    voltage: array
        array of Pfeiffer Single Gauge values, V
    """
    # V → Torr
    exponent = 1.6801381 * voltage - 11.35925447
    pres = 10**exponent
    return pres


def ionization_gauge(voltage, mode: int, scale: float):
    r"""
     convert 0-10 V output into Torr

    Parameters
    ----------
    voltage: array
        array of voltage output from Ionization Gauge controller, 0-10 V.
    mode: int
        0: linear mode $Pressure = voltage \\times 10 ^{scale}\;Torr$
        1: log mode, selected in controller $Pressure = 10^{-5 + voltage/2}\; Pa$
    scale: float
        multiplier for linear mode, must be entered manually
    """
    if mode == 0:
        return voltage * (10**scale)
    elif mode == 1:
        return 10 ** (-5 + voltage / 2)
    else:
        return


def hall_current_sensor(v, type=5):
    r"""
    Convert voltage from the Hall effect current sensor into current.
    There are several sensors, with ranges 5A, 10 A, and 30 A
    $Current = 5 / 1 \cdot (v - 2.52) \; A$
    TODO: update formula for other ranges when needed

    Parameters
    ----------
    v: array
        array of signal values
    type: int
        max range of the sensor
    """
    return 5 / 1 * (v - 2.52)


def baratron(v, fullscale):
    r"""
    Convert Baratron signal to pressure in Torr
    Full scale corresponds to 10 V.
    $Pressure = v/10 \cdot fullscale\; Torr$
    """
    return v / 10 * fullscale


def mfc(v):
    return v


def cathode_current(voltage):
    return voltage


def cathode_volt(voltage):
    return voltage / 10 * 42
