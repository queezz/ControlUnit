"""
Constants, such as channel for ADC, GPIO on RasPi, column names for dataframes,
are specified in here. Affects the whole of Contorlunit.
TODO: organize into dictionaries
TODO: add conversion functions for each sensor in a dictionary
"""
from conversions import ionization_gauge, hall_current_sensor, pfeiffer_single_gauge, baratron

MAXTEMP = 1000

# Temperature Worker Settings
# fmt: off
CHT = 0            # 0 -> CS0, 1 -> CS1 Thermocouple
# GPIOs
CHHEATER = 17      # GPIO channel for turning on heater
CHLED = 27         # GPIO output for LED and sync signal for QMS
# fmt: on

# column names and channels
TCCOLUMNS = ["date", "time", "T", "PresetT"]

# ADC Worker Settings
# fmt: off
CHP1 = 0           # 15, Ionization Gauge (downstream)
CHP2 = 1           # 16, Pfeiffer single gauge (upstream)
CHIP = 2           # 5, Plasma current, Hall effect sensor
CHB1 = 3           # Baratron 1 (upstream)
CHB2 = 4           # Baratron 2 (downstream)
CHNLSADC = [CHP1, CHP2, CHIP, CHB1, CHB2]
# fmt: on

# Conversion of signals is done in worker.py line 405 in update_processed_signals_dataframe
class AdcChannelProps:
    """
    ADC channel properties
    """

    def __init__(self, *arg) -> None:
        """
        Arguments
        ----------
        [name,channel, gain, description, conversion]
        """
        self.name = arg[0]
        self.channel = arg[1]
        self.gain = arg[2]
        self.description = arg[3]
        self.conversion = arg[4]


ADC_CHANNELS = [
    AdcChannelProps("Pd", 0, 10, "Ionization Gauge (downstream)", ionization_gauge),
    AdcChannelProps("Pu", 1, 10, "Pfeffer  Single Gauge (upstream)", pfeiffer_single_gauge),
    AdcChannelProps("Ip", 2, 10, "Plasma Current", hall_current_sensor),
    AdcChannelProps("Bu", 3, 1, "Baratron 1 Torr (upstream)", lambda v: baratron(v, 1)),
    AdcChannelProps("Bd", 4, 1, "Baratron 0.1 Torr (downstream)", lambda v: baratron(v, 0.1)),
]

ADC_COLNAMES = ["date", "time"] + [i.name for i in ADC_CHANNELS] + ["IGmode", "IGscale", "QMS_signal"]
ADC_COLNAMES_CONV = [i + "_c" for i in [i.name for i in ADC_CHANNELS]]

# When adding ADC channels, must add adc gain in set_adc_channels in worker line 345

ADCSIGNALS = ["P1", "P2", "Ip", "B1", "B2"]
ADCCONVERTED = [i + "_c" for i in ADCSIGNALS]
ADCCOLUMNS = ["date", "time"] + ADCSIGNALS + ["IGmode", "IGscale", "QMS_signal"]
