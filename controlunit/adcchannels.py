"""
ADC channel properties class.
"""

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
        self.gainIndex = kws["Gain"]
        self.description = kws["Description"]
        self.conversion_id = kws["Conversion Function"]
        self.full_scale = kws.get("Full Scale", None)
        self.set_conversion_function()
        self.gain = None

    def set_conversion_function(self):
        """
        Select conversion function from a dict by conversion_id
        """
        from conversions import (
            ionization_gauge,
            hall_current_sensor,
            pfeiffer_single_gauge,
            baratron,
            mfc,
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
        if self.conversion_id == "MFC":
            self.conversion = lambda v: mfc(v)

        self.conversion = conversions[self.conversion_id]
