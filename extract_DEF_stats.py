#!/usr/bin/env python3
"""
Usage:
    netlistGen.py (--def <file>)
    netlistGen.py (--help|-h)

Options:
    --def <file>        .def file
    -h --help               Print this help
"""

from PIL import Image
import math
import copy
import locale
import os
import shutil
import datetime
import errno
import random
from docopt import docopt
import numpy as np
import sys
import matplotlib.pyplot as plt
import statistics
from alive_progress import alive_bar
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'en_GB.UTF-8')

RANDOM_SEED = 0 # Set to 0 if no seed is used, otherwise set to seed value.

def extractDEF(filename, design):
    """

    Parameters:
    -----------
    filename : str
        Path to DEF file
    """

    stats = dict() # {Standard cell : amount}
    totCells = 0 # Total amount of components, given at "COMPONENTS 52184 ;"
    cellsCount = 0 # Cells counter

    with open(filename, 'r') as f:
        lines = f.readlines()

    inComponents = False

    with alive_bar(len(lines)) as bar:
        for line in lines:
            if "COMPONENTS" in line and not inComponents:
                inComponents = True
                totCells = int(line.split()[1])
                continue
            elif "COMPONENTS" in line and inComponents:
                inComponents = False
                continue
            if inComponents and not ';' in line:
                # If the line starts with '+', skip.
                if line.split()[0] == '+':
                    continue
                stdcell = line.split()[2]
                if stdcell in stats:
                    stats[stdcell] += 1
                else:
                    stats[stdcell] = 1
                cellsCount += 1
            bar()

    # Sanity check
    if cellsCount != totCells:
        print("Discrepency between total: {} and parsed: {}".format(totCells, cellsCount))
        print("Aborting")
        sys.exit()

    # Dump stats
    outStr = ""
    for cell in stats:
        outStr += "{} {}\n".format(cell, stats[cell])
    outFileName = "stats/"+design+"_stats.csv"
    with open(outFileName, 'w') as f:
        f.write(outStr)
    print("Exported to {}".format(outFileName))



if __name__ == "__main__":

    args = docopt(__doc__)

    topModuleName = "customDesign"

    if args["--def"]:
        deffile = args["--def"]

    try:
        os.makedirs("stats")
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    design = deffile.split(os.sep)[-1]
    design = design.replace(".def", '')
    print("Extracting {}".format(deffile))
    extractDEF(deffile, design)

