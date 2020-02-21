"""
little helper for the notebook plotter
"""

def savitzky_golay(y, window_size, order):
    ''' smoothing 
    https://plot.ly/python/smoothing/
    '''
    import numpy as np
    from math import factorial
    from scipy.signal import savgol_filter
    
    try:
        window_size = np.abs(np.int(window_size))
        order = np.abs(np.int(order))
    except ValueError:
        raise ValueError("window_size and order have to be of type int")
    if window_size % 2 != 1 or window_size < 1:
        window_size += 1
    return savgol_filter(y,window_size,order)


def font_setup(size = 13, weight = 'normal', family = 'serif',color = 'None'):
    ''' Set-up font for Matplotlib plots
    'family':'Times New Roman','weight':'heavy','size': 18
    '''
    import matplotlib.pylab as plt
    
    font = {'family':family,'weight':weight,'size': size}
    plt.rc('font',**font)
    plt.rcParams.update({'mathtext.default':  'regular',
                         'figure.facecolor': color,
                        })
    
    
def ticks_visual(ax,**kwarg):
    '''
    makes auto minor and major ticks for matplotlib figure
    makes minor and major ticks thicker and longer
    '''
    which = kwarg.get('which','both')
    from matplotlib.ticker import AutoMinorLocator
    if which == 'both' or which == 'x':
        ax.xaxis.set_minor_locator(AutoMinorLocator())
    if which == 'both' or which == 'y':
        ax.yaxis.set_minor_locator(AutoMinorLocator())

    l1 = kwarg.get('l1',7)
    l2 = kwarg.get('l2',4)
    w1 = kwarg.get('w1',1.)
    w2 = kwarg.get('w2',.8)
    ax.xaxis.set_tick_params(width= w1,length = l1,which = 'major')
    ax.xaxis.set_tick_params(width= w2,length = l2,which = 'minor')
    ax.yaxis.set_tick_params(width= w1,length = l1,which = 'major')
    ax.yaxis.set_tick_params(width= w2,length = l2,which = 'minor')
    return

def grid_visual(ax, alpha = [.1,.3]):
    '''
    Sets grid on and adjusts the grid style.
    '''
    ax.grid(which = 'minor',linestyle='-', alpha = alpha[0])
    ax.grid(which = 'major',linestyle='-', alpha = alpha[1])
    return