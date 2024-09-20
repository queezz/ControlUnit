import time
try:
    import pigpio
except ImportError:
    from sensors.dummy import pigpio
 
class MCP4725(object):
    DEFAULT_ADDRESS  = 0x60
    CONSTANT = 5.0/(2**12)
 
    def __init__(self, pi):
        self.pi = pi
        self._device = pi.i2c_open(3, self.DEFAULT_ADDRESS)
 
    def set_voltage(self, voltage):
        value = int(voltage / self.CONSTANT)
        # Clamp value to an unsigned 12-bit value.
        if value > 4095:
            value = 4095
        if value < 0:
            value = 0
        print ('Setting value to {0:04}'.format(value))
        reg_data = [0x40, (value >> 4) & 0xFF, (value << 4) & 0xFF]
         
        self.pi.i2c_write_device(self._device, reg_data)
 
    def cancel(self):
        if self._device is not None:
            self.pi.i2c_close(self._device)
            self._device = None
 
             
if __name__ == "__main__":
    pi = pigpio.pi()
    if not pi.connected:
       exit(0)
              
    dac = MCP4725(pi)
    
    i=0
    while i < 50:
        dac.set_voltage(i/10)
        time.sleep(2.0)
        i += 1
         
    dac.cancel()
    pi.stop()