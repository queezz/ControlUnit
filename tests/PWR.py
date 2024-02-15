import serial
import time


# Open serial port
def port_setup(func):
    def open_do_close_port(*args, **kwargs):
        ser = serial.Serial('/dev/ttyAMA1', 115200, timeout=0.1)
        func(ser, *args, **kwargs)
        
        time.sleep(0.1)
        res = ser.read_all()
        print(res)
        ser.close()
    return open_do_close_port
    

@port_setup
def write_command(ser, command):
    # 初期化コマンド
    ser.write((command + '\n').encode())
    pass
    
    
class PWR401L:
	def __init__(self):
		self.init_pwr401l()
	

	def init_pwr401l(self):
		write_command("SYST:COMM:RLST")
		write_command("VOLT:PROT 50")

	def set_current(self, current):
		command = "CUR " + str(current)
		write_command(command)
		
	def on(self):
		write_command("OUTP ON")
		
	def off(self):
		write_command("OUTP OFF")


if __name__ == '__main__':
	pwr = PWR401L()
	pwr.set_current(22.5)
	pwr.on()
	pwr.off()
    


