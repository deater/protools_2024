"""
Script that generates a plot containing core frequency data for the paper
"""

import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

CORES_TO_PLOT = [0,2,4,6,8,10,12,14,16,17,18,19,20,21,22,23]
PCORES = ['0','2','4','6','8','10','12','14']
ECORES = ['16','17','18','19','20','21','22','23']

idir = Path("../outiap")
hdir = Path("../outhap")

if __name__ == "__main__":
    f, ax = plt.subplots(nrows=2, ncols=1, figsize=(8, 7))

    # create a plot of the processed core frequencies (assume allcores)
    dcpu = np.genfromtxt(hdir.joinpath('cpu_data.csv'), delimiter=',', names=True, dtype=float)
    processors = dcpu.dtype.names
    for p in processors:
        if p == 'time':
            continue
        if int(p) in CORES_TO_PLOT: 
            ax[0].plot(dcpu['time'], dcpu[p] / 1000, label=f'core {p}')

    # place the labels
    midrange = int(len(dcpu['0']) * .3)
    maxp = max([np.max(dcpu[p][midrange:-midrange]) for p in PCORES])
    mine = min([np.min(dcpu[p][midrange:-midrange]) for p in ECORES])

    print(maxp, mine)

    ax[0].text(ax[0].get_xlim()[1] / 2, maxp / 1000, "p-cores", horizontalalignment="center", verticalalignment="bottom", fontsize=14)
    ax[0].text(ax[0].get_xlim()[1] / 2, mine / 1000, "e-cores", horizontalalignment="center", verticalalignment="top", fontsize=14)
    ax[0].tick_params(axis='both', which='both', labelsize=14)
    ax[0].set_title("(a) OpenBLAS HPL", size=16, loc='left')
    ax[0].set_xlim([0, dcpu['time'][-1]])
    ax[0].set_ylim(bottom=0)

    # create a plot of the processed core frequencies (assume allcores)
    dcpu2 = np.genfromtxt(idir.joinpath('cpu_data.csv'), delimiter=',', names=True, dtype=float)
    processors = dcpu.dtype.names
    for p in processors:
        if p == 'time':
            continue
        if int(p) in CORES_TO_PLOT: 
            ax[1].plot(dcpu2['time'], dcpu2[p] / 1000, label=f'core {p}')

    # place the labels
    midrange = int(len(dcpu2['0']) * .3)
    maxp = max([np.max(dcpu2[p][midrange:-midrange]) for p in PCORES])
    mine = min([np.min(dcpu2[p][midrange:-midrange]) for p in ECORES])

    ax[1].text(ax[1].get_xlim()[1] / 2, maxp / 1000, "p-cores", horizontalalignment="center", verticalalignment="bottom", fontsize=14)
    ax[1].text(ax[1].get_xlim()[1] / 2, mine / 1000, "e-cores", horizontalalignment="center", verticalalignment="top", fontsize=14)
    ax[1].tick_params(axis='both', which='both', labelsize=14)
    ax[1].set_title("(b) Intel MKL HPL", size=16, loc='left')
    ax[1].set_xlim([0, dcpu2['time'][-1]])
    ax[1].set_ylim(bottom=0)

    f.supylabel("CPU core frequency (GHz)", size=16)
    f.supxlabel("Runtime (s)", size=16)
    f.tight_layout()

    # lets get the median core frequencies for e and p
    avgp = np.zeros_like(dcpu['0'])
    avge = np.zeros_like(dcpu['0'])
    for c in PCORES:
        avgp += dcpu[c]
    avgp = avgp / len(PCORES)

    for c in ECORES:
        avge += dcpu[c]
    avge = avge / len(ECORES)

    print("HPL2.3")
    print(f"\tmedian p cores {np.median(avgp)}\n\tmedian e cores {np.median(avge)}")

    avgp = np.zeros_like(dcpu2['0'])
    avge = np.zeros_like(dcpu2['0'])
    for c in PCORES:
        avgp += dcpu2[c]
    avgp = avgp / len(PCORES)

    for c in ECORES:
        avge += dcpu2[c]
    avge = avge / len(ECORES)

    print("INTELS HPL")
    print(f"\tmedian p cores {np.median(avgp)}\n\tmedian e cores {np.median(avge)}")
    
    plt.savefig("/home/willow/dev/2024_heterogeneous/paper/figures/core_frequencies.eps", format="eps") 
    plt.show()
