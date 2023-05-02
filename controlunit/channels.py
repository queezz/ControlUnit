"""
Constants, such as channel for ADC, GPIO on RasPi, column names for dataframes,
are specified in here. Affects the whole of Contorlunit.
TODO: organize into dictionaries
TODO: add conversion functions for each sensor in a dictionary
"""
# fmt: off
# ADC
CHP1 = 0           # 15, Ionization Gauge
CHP2 = 1           # 16, Pfeiffer single gauge
CHIP = 2           # 5, Plasma current, Hall effect sensor
# Thermocouple
CHT = 0            # 0 -> CS0, 1 -> CS1 Thermocouple
# GPIOs
CHHEATER = 17      # GPIO channel for turning on heater
CHLED = 27         # GPIO output for LED and sync signal for QMS

# fmt: on
# column names and channels
TCCOLUMNS = ["date", "time", "T", "PresetT"]
ADCSIGNALS = ["P1", "P2", "Ip"]
ADCCONVERTED = [i + "_c" for i in ADCSIGNALS]
ADCCOLUMNS = ["date", "time"] + ADCSIGNALS + ["IGmode", "IGscale", "QMS_signal"]

# ADCCHANNELS = [CHP1, CHP2, CHIP]
