from enum import Enum
import numpy as np
from thermocouple import calcTemp, maskTemp
from ionizationGauge import maskIonPres, calcIGPres
from pfeiffer import maskPfePres, calcPfePres

threadnames = ["Plasma", "Temperature","Pressure1","Pressure2"]

class ThreadType(Enum):
    PLASMA,TEMPERATURE,PRESSURE1,PRESSURE2 = threadnames 

    def getGPIO(self):
        if self == self.PLASMA:
            return 0
        elif self == self.TEMPERATURE:
            return 17
        else:
            return

    def getIndex(self):
        if self == self.PLASMA:
            return 3
        elif self == self.PRESSURE1:
            return 1
        elif self == self.PRESSURE2:
            return 2
        elif self == self.TEMPERATURE:
            return 1
        else:
            return 

    def getCalcArray(self, data: np.ndarray,**kws):
        if self == self.PLASMA:
            # TODO: calc
            return data
        elif self == self.TEMPERATURE:
            return maskTemp(data)
        elif self == self.PRESSURE1:
            return maskIonPres(data,IGrange=m)
        elif self == self.PRESSURE2:
            return maskPfePres(data)
        else:
            return data

    def getCalcValue(self, data: float,**kws):
        if self == self.PLASMA:
            # TODO: calc
            return data
        elif self == self.TEMPERATURE:
            return calcTemp(data)
        elif self == self.PRESSURE1:
            mode = kws.get('IGmode', 0)
            scale = kws.get('IGrange',-3)
            return calcIGPres(data, mode, scale)
        elif self == self.PRESSURE2:
            return calcPfePres(data)
        else:
            return data

class ScaleSize(Enum):
    SMALL = -400
    MEDIUM = -1000
    LARGE = -2500
    FULL = 0

    @classmethod
    def getEnum(cls, index: int):
        if index == 0:
            return cls.SMALL
        elif index == 1:
            return cls.MEDIUM
        elif index == 2:
            return cls.LARGE
        elif index == 3:
            return cls.FULL
        else:
            return

if __name__=="__main__":
    pass
