"""
ADC channel properties class.
"""


# Conversion of signals is done in devices/adc.py in update_processed_signals_dataframe
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
        self.supply_channel = kws.get("Supply Channel")
        self.nominal_supply = float(kws.get("Nominal Supply", 5.0))
        self.zero_ratio = float(kws.get("Zero Ratio", 0.5))
        self.amperes_per_volt = float(kws.get("Amperes Per Volt", 5.0))
        self.zero_voltage = float(kws.get("Zero Voltage", 2.52))
        self.supply_minimum = float(kws.get("Supply Minimum", 4.0))
        self.supply_maximum = float(kws.get("Supply Maximum", 6.0))
        # An ionization gauge's own record columns for the mode and the
        # exponent its controller was set to; None for every other kind.
        self.mode_column = kws.get("Mode Column", None)
        self.scale_column = kws.get("Scale Column", None)
        # Where an ionization gauge sits, e.g. "upstream"; None when the
        # settings give it none.
        self.place = kws.get("Place", None)
        self.set_conversion_function()
        self.gain = None

    def convert_hall(self, voltages):
        """Use this scan's supply; an invalid reference never becomes current."""
        import math

        voltage = voltages[self.name]
        if not self.supply_channel:
            return self.amperes_per_volt * (voltage - self.zero_voltage)
        supply = voltages.get(self.supply_channel, float("nan"))
        if not (math.isfinite(voltage) and math.isfinite(supply)
                and self.supply_minimum <= supply <= self.supply_maximum):
            return float("nan")
        return self.amperes_per_volt * self.nominal_supply * (
            voltage / supply - self.zero_ratio
        )

    def set_conversion_function(self):
        """
        Select conversion function from a dict by conversion_id
        """
        from controlunit.devices.conversions import (
            ionization_gauge,
            hall_current_sensor,
            pfeiffer_single_gauge,
            pfeiffer_ikr251,
            baratron,
            mfc,
            cathode_current,
            cathode_volt,
        )

        conversions = {
            "Ionization Gauge": ionization_gauge,
            "Pfeiffer Single Gauge": pfeiffer_single_gauge,
            "Pfeiffer IKR251": pfeiffer_ikr251,
            "Hall Sensor": hall_current_sensor,
            "No Conversion": lambda v: v,
            "cathode current": cathode_current,
            "cathode volt": cathode_volt,
        }

        if self.conversion_id == "Baratron":
            self.conversion = lambda v: baratron(v, self.full_scale)
            return
        if self.conversion_id == "MFC":
            self.conversion = lambda v: mfc(v)

        self.conversion = conversions[self.conversion_id]
