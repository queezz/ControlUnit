"""
Constants, such as channel for ADC, GPIO on RasPi, column names for dataframes,
are specified in here. Affects the whole of Contorlunit.
TODO: move all definitions into readsetting.py, read everything from settings.yml
Here: Leave only the definition of the ADC channel properties class.
"""

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

    def __init__(self, *arg, **kws) -> None:
        """
        Arguments
        ----------
        [name,channel, gain, description, conversion]
        """
        self.name = arg[0]
        self.channel = kws["Channel"]
        self.gain = kws["Gain"]
        self.description = kws["Description"]
        self.conversion_id = kws["Conversion Function"]
        self.full_scale = kws.get("Full Scale", None)
        self.set_conversion_function()

    def set_conversion_function(self):
        """
        Select conversion function from a dict by conversion_id
        """
        from controlunit.conversions import (
            ionization_gauge,
            hall_current_sensor,
            pfeiffer_single_gauge,
            baratron,
        )

        conversions = {
            "Ionization Gauge": ionization_gauge,
            "Pfeiffer Single Gauge": pfeiffer_single_gauge,
            "Hall Sensor": hall_current_sensor,
            "No Conversion": lambda v: v,
        }

        if self.conversion_id == "Baratron":
            self.conversion = lambda v: baratron(v, self.full_scale)
            return

        self.conversion = conversions[self.conversion_id]


def get_adc_channel(name, channels):
    """
    Look for a channel in ADC_CHANNELS by name
    """
    names = [i.name for i in channels]
    if name in names:
        ind = names.index(name)
        print("channel found:", channels[ind])
        return channels[ind]
    else:
        print("channel not found")
        return None


# When adding ADC channels, must add adc gain in set_adc_channels in worker line 345

ADCSIGNALS = ["P1", "P2", "Ip", "B1", "B2"]
ADCCONVERTED = [i + "_c" for i in ADCSIGNALS]
ADCCOLUMNS = ["date", "time"] + ADCSIGNALS + ["IGmode", "IGscale", "QMS_signal"]
