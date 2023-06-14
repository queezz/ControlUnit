import RPi.GPIO as GPIO
import time
import spidev


channel_A   = 0x30
channel_B   = 0x34

DAC_Value_MAX = 65535

DAC_VREF = 5.0


# Pin definition
CS_PIN = 23

# SPI device, bus = 0, device = 0
SPI = spidev.SpiDev(0, 0)


class DAC8532:
    def __init__(self):
        self.cs_pin = CS_PIN
        self.spi = SPI

        self.channel_A = channel_A
        self.channel_B = channel_B

        self.DAC_Value_MAX = DAC_Value_MAX
        self.DAC_VREF = DAC_VREF

        self.module_init()
        
    
    def DAC8532_Write_Data(self, Channel, Data):
        self.digital_write(self.cs_pin, GPIO.LOW)#cs  0
        self.spi_writebyte([Channel, Data >> 8, Data & 0xff])
        self.digital_write(self.cs_pin, GPIO.HIGH)#cs  0
        
    def DAC8532_Out_Voltage(self, Channel, Voltage):
        if((Voltage <= DAC_VREF) and (Voltage >= 0)):
            temp = int(Voltage * DAC_Value_MAX / DAC_VREF)
            self.DAC8532_Write_Data(Channel, temp)



    def digital_write(self, pin, value):
        GPIO.output(pin, value)

    def digital_read(self,pin):
        return GPIO.input(pin)

    def delay_ms(self, delaytime):
        time.sleep(delaytime // 1000.0)

    def spi_writebyte(self, data):
        self.spi.writebytes(data)
        
    def spi_readbytes(self, reg):
        return self.spi.readbytes(reg)
        

    def module_init(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        #GPIO.setup(RST_PIN, GPIO.OUT)
        GPIO.setup(CS_PIN, GPIO.OUT)
        #GPIO.setup(DRDY_PIN, GPIO.IN)
        #GPIO.setup(DRDY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.spi.max_speed_hz = 20000
        self.spi.mode = 0b01
        return 0

