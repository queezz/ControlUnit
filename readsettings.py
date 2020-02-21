import csv
import customTypes
import os
from os.path import join

def make_datafolders():
    names = customTypes.threadnames 
    foldername, local, sampling_rate = get_datafolderpth()
    bpth = os.path.abspath(__file__)

    if local:
        datapth = foldername
    else:
        datapth = join(bpth,foldername)
    
    dirs = [join(datapth,name) for name in names]
    try:
        os.mkdir(datapth)
        print(f'created {datapth}')
    except FileExistsError:
        pass 

    for d in dirs:
        try:
            os.mkdir(d)
            print(f'created {d}')
        except FileExistsError:
            pass

def get_datafolderpth():
    """ Read .settings and get datafoldr path"""
    pth = None
    sampling_rate = 0.01
    with open('.settings', 'r') as f:
        s = csv.reader(f, delimiter=',')
        for r in s:
            if r[0] == 'datafolder':
                pth = r[1].strip()
            if r[0] == 'pathislocal':
                local = r[1].strip()
            if r[0] == 'sampling_rate':
                sampling_rate = r[1].strip() 
    if local == 'True': local = True
    sampling_rate = float(sampling_rate)

    return pth, local, sampling_rate

if __name__ == '__main__':
    #print(get_datafolderpth())
    make_datafolders()
