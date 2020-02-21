# Data Logger and controller for Raspberry Pi

# 1. Introduction

There are commercially available data loggers and temperature control units, however sometimes it is nice to have all things you need in one place, and with a tailored UI. Also, the price for commercial data loggers could be several times higher then a simple SPC alternative.



In our project, we have an experimental device where we want to measure several signals, plus to implement a feed-back control of a sensor temperature. 



## 1.1 Hardware components:

- [Raspberry Pi 3 Model B](https://www.raspberrypi.org/products/raspberry-pi-3-model-b/)
- ADC (Analog to Digital Convertor), 16 bit 32 channel: [I2C アナログ入力ボード AIO-32/0RA-IRC](https://www.y2c.co.jp/i2c-r/aio-32-0ra-irc/)
- solid-state relay: Celduc [SO842074](https://docs.rs-online.com/4deb/0900766b8050bf44.pdf)
- halogen lamp as a heating element: Panasonic [JCD100V300WCG](https://www2.panasonic.biz/scvb/a2A/opnItemDetail?use_obligation=scva&contents_view_flg=1&catalog_view_flg=1&item_cd=JCD100V300WCG&item_no=JCD100V300WCG&b_cd=101&hinban_kbn=1&s_hinban_key=JCD100V300WCG&s_end_flg=&vcata_flg=1)
- 7'' touch screen as indicator and input device: [EVICIV B07PY5XND3](https://www.amazon.com/Eviciv-Portable-Monitor-Display-1024X600/dp/B07L6WT77H?ref_=ast_sto_dp&th=1&psc=1)



## 1.2 Program summary

The analog signals from vacuum gauges, 0 - 10 V, and the K-type thermocouple, 0 - 15 mV, are red by the DAC in the worker thread. The Raspi GPIO are used to control the solid state relay and turn on the halogen lamp. A Variac is used to power the lamp.  



![UI](images/app_screenshot_1.png)



# 2. Requirements

```
- pyqtgraph
- numpy
- scipy
- matplotlib
- pandas
- python3-smbus
- RPi.GPIO
```

`pyqtgraph` requires either pyqt5 or pyside. To install pyqt5, use `apt-get`:

```py
sudo apt-get update
sudo apt-get install qt5-default pyqt5-dev pyqt5-dev-tools
```

RPi.GPIO:

```
sudo apt-get update
sudo apt-get install rpi.gpio
```

python3-smbus:

```
python3 -m pip install smbus --user
```

or

```
sudo apt-get install python3-smbus
```



# 3. Usage

## 3.1 start Logger

```
$ pyton3 main.py
```

## 3.2 Settings

### Data folder

The data folder name and location is stored in the settings file, .setings - a csv file. By default the data folder is placed relatively to the parent directory in `../data`.



# 4. What is where

In the `Worker` thread, `worker.py` class from `customTypes.py` has method `getCalcValue` for each type of  signal, which calls a method to convert signal into data.



`customTypes.py`:

```python
def getCalcValue(self, data: float):
    if self == self.PLASMA:
        # TODO: calc
        return data
    elif self == self.TEMPERATURE:
        return calcTemp(data)
    elif self == self.PRESSURE1:
        return data
    elif self == self.PRESSURE2:
        return calcPfePres(data)
    else:
        return data
```


## Pressure from Ionization Gauge Vacuumeter

`IGmode` and `IGrange` determine log or normal scale, as well as the multiplier for normal scale. A set method is defined in the `worker.py`. The mode will be sent to `getCalcValue` method, which has to call `calcIGPressure` method with this parameters.