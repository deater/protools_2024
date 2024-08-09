"""
A script that runs HPL and collects performance data over the course of the run
"""


import argparse
from pathlib import Path
from time import sleep
import os, subprocess, stat, shutil
import glob, re, json, time

THERMALS_ROOT = Path('/sys/class/thermal')
RAPL_ROOT = Path('/sys/class/powercap')
CPUINFO = Path('/proc/cpuinfo')
METADATA = 'metadata.json'
HPLDAT = 'HPL.dat'
THERMAL_CSV = 'thermal_data.csv'
RAPL_CSV = 'rapl_data.csv'
CPU_CSV = 'cpu_data.csv'
PERF_JSON = 'perf.json'

HPL_COMMAND = './xhpl'
PERF_COMMAND = "perf stat -e LLC-stores,LLC-store-misses,LLC-loads,LLC-load-misses,cache-misses,branch-misses,instructions,cpu-cycles -j"

verbose = False

# since we will often run as root, unfortunately we have to change the file permissions frequenly
FILE_PERMS = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
root = False


def process_cores_str(cores_str: str) -> list[int]:
    """
    Takes a cores string, à la taskset, and returns a list of integers
    e.x. '0,2,4,6-10' -> [0, 2, 4, 6, 7, 8, 9, 10]
    """
    cores = []
    entries = re.findall(r'[0-9-]+', cores_str)
    for i, e in enumerate(entries):
        if '-' in e:
            low, high = e.split('-')
            r = list(range(int(low), int(high)+1))
            cores += r
        else:
            cores.append(int(e))
    
    return cores


def set_file_perms(file, perms):
    """
    Sets the permissions and owner of a file to prevent runs as root from being only
    accessible by root
    """
    os.chmod(file, perms)
    if root:
        # change owner of the file to the owner of the cwd
        os.chown(file, os.stat('.').st_uid, os.stat('.').st_gid)


def init_thermal_data(fd) -> list[Path]:
    """
    writes the header for collected thermal data to a file descriptor
    returns a list of thermal zone paths
    """
    header = "time,"
    zones = glob.glob(THERMALS_ROOT.joinpath("thermal_zone*").as_posix())
    for i, z in enumerate(zones):
        header += str(Path(z).parts[-1]).split('_')[-1] + "_" + Path(z, "type").read_text().rstrip() + ","
        zones[i] = Path(zones[i], "temp")

    fd.write(header[:-1]+'\n')
    return zones


def store_thermal_data(fd, zones: list[Path]):
    """
    writes thermal data to the file descriptor
    """
    row = f"{time.time()},"
    for z in zones:
        row += z.read_text().rstrip() + ","
    fd.write(row[:-1]+'\n')


def init_rapl_data(fd) -> list[Path]:
    """
    writes the header for collected energy usage data to the file descriptor
    returns a list of paths to read energy data from
    """
    rapls = [RAPL_ROOT.joinpath(f) for f in glob.glob("intel-rapl*/intel-rapl*", root_dir="/sys/devices/virtual/powercap/")]
    raplnames = [r.name for r in rapls]
    fd.write('time,' + ','.join(raplnames)+'\n')

    # add on the energy_uj path component so we don't do that every time we access the energy usage
    rapls = [r.joinpath('energy_uj') for r in rapls]
    
    return rapls


def store_rapl_data(fd, rapls: list[Path]):
    """
    writes rapl energy data to the file descriptor
    """
    ujs = []
    for r in rapls:
        ujs.append(r.read_text().rstrip())   

    fd.write(f'{time.time()},' + ','.join(ujs)+'\n')
    return ujs


def init_cpu_data(fd):
    """
    writes the header for collected cpu frequency data to the file descriptor
    """
    cpuinfo = CPUINFO.read_text()
    cpus = [c.split(': ')[-1] for c in re.findall(r'processor.*: [0-9]+', cpuinfo)]
    fd.write('time,' + ','.join(cpus) + '\n')


def store_cpu_data(fd):
    """
    writes cpu data to the file descriptor
    """
    cpuinfo = CPUINFO.read_text()
    freqs = [c.split(': ')[1] for c in re.findall(r'cpu.*MHz.*[0-9.]+', cpuinfo)]
    fd.write(f'{time.time()},' + ','.join(freqs) + '\n')


def settle_temps(temps_str: str):
    """
    waits for the thermal zones specified in temps_str to settle to 
    their corresponding temperatures. 
    """
    # parse the temps_str string into a list of tuples [(zone, temp), ...]
    pairs = [(p.split(':')[0], int(p.split(':')[1])) for p in temps_str.split(',')]
    settled = 0

    print(f"Waiting for temperatures to settle:")
    for p in pairs:
        print(f'\t{p[0]} ({THERMALS_ROOT.joinpath(p[0], "type").read_text().rstrip()}): {p[1]}')
    while settled < len(pairs):
        for p in pairs:
            temp = int(THERMALS_ROOT.joinpath(p[0], 'temp').read_text().rstrip())
            if temp > p[1]:
                if verbose:
                    print(f"{p[0]} must fall below {p[1]}mC. current temp: {temp}mC")
            else:
                settled += 1
        
        sleep(1)


def mon_hpl(hpl_dir: Path, out_dir: Path, args, env: os.environ=None) -> dict:
    """
    runs hpl and monitors thermal, energy, and cpu stats throughout.
    returns the run's metadata
    """
    n = 0

    # open the run data files, and make sure they are not root-only
    therm_csv = open(out_dir.joinpath(THERMAL_CSV), 'a')
    set_file_perms(out_dir.joinpath(THERMAL_CSV), FILE_PERMS)
    rapl_csv = open(out_dir.joinpath(RAPL_CSV), 'a')
    set_file_perms(out_dir.joinpath(RAPL_CSV), FILE_PERMS)
    cpu_csv = open(out_dir.joinpath(CPU_CSV), 'a')
    set_file_perms(out_dir.joinpath(CPU_CSV), FILE_PERMS)

    # initialize data collection
    thermal_zones = init_thermal_data(therm_csv)
    rapls = init_rapl_data(rapl_csv)
    init_cpu_data(cpu_csv)

    # run hpl
    command = PERF_COMMAND.split(' ') + ['-o', Path(os.getcwd(), out_dir, PERF_JSON).as_posix()] + ['taskset', '-a', '-c', args.cores, HPL_COMMAND]
    print(command)
    hpl = subprocess.Popen(command, cwd=hpl_dir, stdout=subprocess.PIPE, text=True, env=env)

    # measure stats until process finishes
    while True:
        try:
            stdout, stderr = hpl.communicate(timeout=args.t_samp)
            break
        except subprocess.TimeoutExpired:
            store_thermal_data(therm_csv, thermal_zones)
            if root:
                store_rapl_data(rapl_csv, rapls)
            store_cpu_data(cpu_csv)

            # debug print the number of threads and what cores they are on
            # print(os.system(f"ps -T -p {hpl.pid}"))

            n += 1
            continue

    # verify that HPL passed
    if 'PASSED' not in stdout:
        print(stdout)
        raise Exception(f"HPL failed!\n\n{stdout}\n\n{stderr}")
    
    # extract some results. Haven't found a better way to do this yet
    # this messy regex and line split gets the row containing the values for 
    #   'T/V      N       NB        P        Q        Time           Gflops'
    # and extracts just the python parseable float values
    # '-18' magic number is the target row indexed from the end, in case misc
    # things were printed during the hpl run
    values = re.findall(r'\b[0-9]+\.?[0-9]*e?\+?[0-9]*\b', stdout.split('\n')[-18])
    runtime = float(values[-2])
    gflops = float(values[-1])

    # finally, save relevant metadata about the run
    meta = {
        'n_samples': n,
        'runtime': runtime,
        'gflops': gflops,
        'processed': False,
    }
    out_dir.joinpath(METADATA).write_text(json.dumps(meta, indent=4))
    set_file_perms(out_dir.joinpath(METADATA), FILE_PERMS)

    # clean up
    therm_csv.close()
    rapl_csv.close()
    cpu_csv.close()

    return meta


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('hpl_dir', type=Path, help='HPL install directory (ex: ~/hpl/bin/linux)')
    parser.add_argument('out_dir', type=Path, help='output directory')
    parser.add_argument('-c', '--cores', type=str, default='0-64', help='comma separated list of cores to run HPL on, passed directly to taskset. e.x: -c 0,2,4,6,8,10,12,14,16-24')
    parser.add_argument('-p', '--t_samp', type=float, default=1.0, help='delay in seconds between measurements during the run')
    parser.add_argument('-n', '--n_runs', default=1, type=int, help='the number times to repeat the HPL run')
    parser.add_argument('-t', '--settled_temps', type=str, help="comma separated list of pairs of thermal_zone:temperature. When specified, the program will wait for each thermal zone to fall below its requisite temperature (in mC) before proceeding to run HPL. e.x: thermal_zone8:35000,thermal_zone0:33000")
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help='whether to run with verbose output enabled')
    args = parser.parse_args()

    # set up the env for HPL. HPL_HOST_CORE is necessary for Intel's distribution of HPL
    # unfortunately it does not affect the normal distribution of HPL
    # therefore taskset must also be used
    env = os.environ.copy() 
    env["HPL_HOST_CORE"] = args.cores 

    # make the program globally aware of its verbosity
    verbose = args.verbose

    # check if we are root
    root = os.geteuid() == 0

    # set up the output directory
    if args.out_dir.exists():
        shutil.rmtree(args.out_dir)
    os.mkdir(args.out_dir)
    set_file_perms(args.out_dir, FILE_PERMS | stat.S_IXUSR)

    print(f"Beginning HPL run.\n\tcores:\t{args.cores}\n\tpolling rate:\t{1/args.t_samp}Hz")
    if not root:
        print(f"WARNING: In order to collect rapl data, run the script as root")

    assert args.n_runs > 0, "--n_args must be greater than zero"

    # save a copy of HPL.dat
    args.out_dir.joinpath(HPLDAT).write_text(Path(args.hpl_dir, HPLDAT).read_text())
    set_file_perms(args.out_dir.joinpath(HPLDAT), FILE_PERMS)

    # run HPL --average times and collect in individual subdirectories
    for i in range(args.n_runs):
        d = args.out_dir.joinpath(f'run_{i}_raw')
        os.mkdir(d)
        set_file_perms(d, FILE_PERMS | stat.S_IXUSR)

        if args.settled_temps:
            settle_temps(args.settled_temps)

        if verbose:
            print(f"Beginning HPL run #{i}")

        mon_hpl(args.hpl_dir, d, args, env=env)

    # write the meta metadata file
    Path(args.out_dir.joinpath(METADATA)).write_text(json.dumps({
        'n_runs': args.n_runs,
        't_samp': args.t_samp,
        'cores': args.cores,
        'settled_temps': args.settled_temps,
    }, indent=4))
    set_file_perms(args.out_dir.joinpath(METADATA), FILE_PERMS)

    if verbose:
        print("Done!")
