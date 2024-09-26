"""
Dummy classes to test the code not on RasPi
smbus
RPi
"""


class smbus:
    def __init__(self):
        pass

    class SMBus:
        def __init__(self, bus):
            pass

        def write_byte_data(self, i2c_addr, register, value):
            pass

        def read_byte_data(self, i2c_addr, register):
            pass
            return 0x80

        def write_word_data(self, i2c_addr, register, value):
            pass

        def read_word_data(self, i2c_addr, register):
            return 0x1234


class GPIO:
    BCM = None
    OUT = None
    LOW = 0
    HIGH = 1

    def __init__(self):
        pass

    def setup(CS_PIN, OUT):
        return

    def setmode(BCM):
        return

    def setwarnings(val):
        return

    def output(pin, value):
        return

    def input(pin):
        return


class SpiDev:
    max_speed_hz = 0
    mode = 0b01

    def __init__(self, a, b):
        pass

    def writebytes(self, data):
        return

    def readbytes(self):
        return


class spidev:
    SpiDev = SpiDev

    def __init__(self):
        pass


class pi:
    connected = True

    def stop(self):
        return

    def write(self, pinNum, val):
        return

    def i2c_open(self, val, address):
        return

    def i2c_write_device(self, device, reg_data):
        return

    def set_mode(self, pinNum, OUTPUT):
        return


class pigpio:
    """pigpio dummy"""

    pi = pi
    OUTPUT = None
