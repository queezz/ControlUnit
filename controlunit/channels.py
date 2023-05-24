"""
Constants, such as channel for ADC, GPIO on RasPi, column names for dataframes,
are specified in here. Affects the whole of Contorlunit.
TODO: organize into dictionaries
TODO: add conversion functions for each sensor in a dictionary
"""
MAXTEMP = 1000
# fmt: off
# ADC
CHP1 = 0           # 15, Ionization Gauge (downstream)
CHP2 = 1           # 16, Pfeiffer single gauge (upstream)
CHIP = 2           # 5, Plasma current, Hall effect sensor
CHB1 = 3           # Baratron 1 (upstream)
CHB2 = 4           # Baratron 2 (downstream)
CHNLSADC = [CHP1, CHP2, CHIP, CHB1, CHB2]
# Thermocouple
CHT = 0            # 0 -> CS0, 1 -> CS1 Thermocouple
# GPIOs
CHHEATER = 17      # GPIO channel for turning on heater
CHLED = 27         # GPIO output for LED and sync signal for QMS

# fmt: on
# column names and channels
TCCOLUMNS = ["date", "time", "T", "PresetT"]
ADCSIGNALS = ["P1", "P2", "Ip", "B1", "B2"]
ADCCONVERTED = [i + "_c" for i in ADCSIGNALS]
ADCCOLUMNS = ["date", "time"] + ADCSIGNALS + ["IGmode", "IGscale", "QMS_signal"]

# Conversion of signals is done in worker.py line 405 in update_processed_signals_dataframe
"""
ionization_gauge(p1_v, self.__IGmode, self.__IGrange),
pfeiffer_single_gauge(p2_v),
hall_current_sensor(ip_v),
"""
# When adding ADC channels, must add adc gain in set_adc_channels in worker line 345
