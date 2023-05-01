"""
Conversion functions for various senseors.
"""


def pfeiffer_single_gauge(voltage):
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


def ionization_gauge(voltage, mode: int, scale: float):
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


def hall_current_sensor(v, type=5):
    """
    Convert voltage from the Hall effect current sensor into current.
    There are several sensors, with ranges 5A, 10 A, and 30 A
    TODO: update formula for other ranges when needed

    Parameters
    ----------
    v: array
        array of signal values
    type: int
        max range of the sensor
    """
    return 5 / 1 * (v - 2.52)
