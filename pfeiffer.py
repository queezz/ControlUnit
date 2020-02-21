import numpy as np

''' pressure gauge in plasma chamber '''
def maskPfePres(voltages: np.ndarray):
    mask = np.where((voltages[:, 1] > 2.3) & (voltages[:, 1] < 6))
    tmp = voltages[mask]
    tmp[:, 1] = [calcPfePres(i) for i in tmp[:, 1]]
    return tmp

def calcPfePres(voltage: float):
    """ update to accept numpy.ndarray
    in that case operatio would be much faster
    """
    # V → Torr
    exponent = 1.667 * voltage - 11.46
    pres = 10**exponent
    return pres

if __name__ == "__main__":
    # a = float(input())
    # print(calcPfePres(a))
    pass
