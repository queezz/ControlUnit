import math
import numpy as np
import tc

AMBIENT = 20.9

''' thermocouple at membrane '''
def maskTemp(voltages: np.ndarray):
    mask = np.where(voltages[:, 1] < 0.015)
    tmp = voltages[mask]
    tmp[:,1] = [calcTemp(i) for i in tmp[:,1]]
    return tmp

def calcTemp(voltage: float):
    # V -> mV
    v = voltage * (1e3)
    return tc.Thermocouple.mv_to_typek(v) + AMBIENT

def run():
    """ to run from command line, use following:
    python -c 'import thermocouple as tc; tc.run()'
    """
    print("input mv:")
    a = float(input())
    a /= (10**3)
    print(calcTemp(a))
    
if __name__ == "__main__":
    pass
    # run()
