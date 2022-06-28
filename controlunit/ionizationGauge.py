import numpy as np

''' permeation pressure gauge '''
def maskIonPres(voltages: np.ndarray,**kws):
    m = kws.get('IGrange',1e-3)
    mask = np.where(voltages[:, 1] > 0.01)
    voltages[:, 1] = voltages[:,1]*m
    tmp = voltages[mask]
    return tmp

def calcIGPres(voltage, mode: int, scale: float):
    """ convert 0-10 V output into Torr """
    if mode == 0:
        return voltage * (10**scale)
    elif mode == 1:
        return 10**(-5+voltage/2)
    else:
        return 

if __name__ == "__main__":
    pass
