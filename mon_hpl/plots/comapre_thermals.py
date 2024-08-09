"""
Script that generates a plot containing thermal and RAPL data for the paper
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

T1 = Path("../outhap/thermal_data.csv")
T2 = Path("../outiap/thermal_data.csv")
P1 = Path("../outhap/watts_data.csv")
P2 = Path("../outiap/watts_data.csv")

PWR_TICK=40
TEMP_TICK=20
time1 = np.genfromtxt(T1, delimiter=',', names=True, dtype=float)['time']
time2 = np.genfromtxt(T2, delimiter=',', names=True, dtype=float)['time']

t1 = np.genfromtxt(T1, delimiter=',', names=True, dtype=float)['zone9_x86_pkg_temp']
t2 = np.genfromtxt(T2, delimiter=',', names=True, dtype=float)['zone9_x86_pkg_temp']

p1 = np.genfromtxt(P1, delimiter=',', names=True, dtype=float)['intelrapl0']
p2 = np.genfromtxt(P2, delimiter=',', names=True, dtype=float)['intelrapl0']

f, ax = plt.subplots(nrows=2, ncols=1, figsize=(8, 5))


l1 = ax[0].plot(time1, p1, color='b', label='RAPL power')
ax[0].set_title("(a) OpenBLAS HPL", size=18, loc='left')
ax[0].tick_params(axis='both', which='both', labelsize=14)
ax[0].yaxis.set_major_locator(ticker.MultipleLocator(PWR_TICK))
ax[0].set_xlim([0, time1[-1]])
ax[0].set_ylim(bottom=0, top=230)

pax1 = ax[0].twinx()
l2 = pax1.plot(time1, t1, color='r', label='package temp', linestyle='dotted')
pax1.set_ylabel("Temperature ($^\circ$C)", size=16)
pax1.tick_params(axis='both', which='both', labelsize=14)
pax1.yaxis.set_major_locator(ticker.MultipleLocator(TEMP_TICK))
pax1.set_xlim([0, time1[-1]])
pax1.set_ylim(bottom=0)
pax1.legend(l1+l2, [l.get_label() for l in l1+l2], ncol=2, loc='upper center')


l3 = ax[1].plot(time2, p2, color='b', label='RAPL power')
ax[1].set_title("(b) Intel MKL HPL", size=18, loc='left')
ax[1].tick_params(axis='both', which='both', labelsize=14)
ax[1].yaxis.set_major_locator(ticker.MultipleLocator(PWR_TICK))
ax[1].set_xlim([0, time2[-1]])
ax[1].set_ylim(bottom=0, top=230)

pax2 = ax[1].twinx()
l4 = pax2.plot(time2, t2, color='r', label='package temp', linestyle='dotted')
pax2.set_ylabel("Temperature ($^\circ$C)", size=16)
pax2.tick_params(axis='both', which='both', labelsize=14)
pax2.yaxis.set_major_locator(ticker.MultipleLocator(TEMP_TICK))
pax2.set_xlim([0, time2[-1]])
pax2.set_ylim(bottom=0)
pax2.legend(l3+l4, [l.get_label() for l in l3+l4], ncol=2, loc='upper center')

f.supylabel("Power (W)", size=16)
f.supxlabel("Runtime (s)", size=16)
f.tight_layout()

# print some stats
print(f"OpenBLAS HPL: maxp {np.max(p1)} maxt {np.max(t1)}")
print(f"Intels HPL: maxp {np.max(p2)} maxt {np.max(t2)}")

plt.savefig("/home/willow/dev/2024_heterogeneous/paper/figures/power_and_thermals.eps", format="eps")
plt.show()
