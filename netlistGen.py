#!/usr/bin/env python3
"""
Usage:
    netlistGen.py (--lef=<file>) [--gates=n] [--name=<name>] [--dist=<file>]
    netlistGen.py (--help|-h)

Options:
    --lef=<file>            .lef file
    --gates=n               Amount of gate in the netlist
    --name=<name>           Top module name
    --dist=<file>           Std cell distribution file
    -h --help               Print this help

Note: Power pins are ignored in standard cells.
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
import logging, logging.config
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
NO_POWER = True # Ignore POWER pins.

logger = logging.getLogger('default')


class StdCell:
    def __init__(self, name):
        self.name = name
        self.pins = dict() # {name : Pin instance}
        self.width = 0
        self.height = 0
        # self.inputs = list() # list of input names
        # self.output = "" # output pin name

    def numberPins(self):
        return len(self.pins)

    def addPin(self, pin):
        '''
        pin: Pin object
        '''
        self.pins[pin.name] = pin

    def setWidth(self, w):
        self.width = w

    def setHeight(self, h):
        self.height = h

class Pin:
    def __init__(self,name):
        self.name = name
        self.dir = "" # INPUT, OUTPUT, INOUT
        self.type = "" # SIGNAL, CLOCK, POWER

class Instance:
    def __init__(self, name, cell=None):
        self.name = name # str : name of the instance
        self.cell = cell # StdCell
        self.inputs = dict() # {pin name : 0|net name}, 0 => pin is free
        self.outputs = dict() # {pin name : 0|net name}, 0 => pin is free

class Net:
    def __init__(self, name):
        self.name = name
        self.dir = "" # input, output, wire

class Netlist:
    def __init__(self, topmodule):
        self.topmodule = topmodule # [str] name of the to module
        self.pins = list() # [Pin] list of input/output pins of the top module
        self.instances = list() # [Instance]
        self.nets = list() # [Net]

        ##       ##     ###     ########   ##      ##          
        ###     ###    ## ##       ##      ###     ##          
        ## ## ## ##   ##   ##      ##      ## ##   ##          
        ##  ###  ##  ##     ##     ##      ##  ##  ##          
        ##       ##  #########     ##      ##   ## ##          
        ##       ##  ##     ##     ##      ##     ###          
####### ##       ##  ##     ##  ########   ##      ##  ####### 



def parseLEF(leffile):
    """

    Parameters:
    -----------
    leffile : str
        Path to file to parse

    Return:
    -------
    stdCells : dict
        {cell name : StdCell}
    """

    stdCells = dict() # Dictionary of Macro objects. Key: macro name.
    pinBlock = False # True if we are in a PIN block.
    macroBlock = False # True if we are in a MACRO block.

    with open(leffile, 'r') as f:
        lines = f.readlines()

    with alive_bar(len(lines)) as bar:
        for line in lines:
            bar()
            line = line.strip()

            #######
            # PIN #
            #######
            if 'PIN' in line:
                pinName = line.split()[1]
                pin = Pin(pinName) # Create a Pin object. The name of the pin is the second word in the line 'PIN ...'

            # Direction of the pin previously created.
            if 'DIRECTION' in line:
                direction = line.split()[1]
                if direction not in ["INPUT", "OUTPUT", "INOUT"]:
                    logger.error("Unknown pin direction: {}\n Aborting.".format(line))
                    sys.exit()
                pin.dir = direction

            # Type of pin.
            if 'USE ' in line:
                use = line.split()[1]
                if use not in ["POWER", "SIGNAL", "CLOCK", "GROUND"]:
                    logger.error("Unknown pin use: {}\n Aborting.".format(line))
                    sys.exit()
                pin.type = use

                if NO_POWER and use in ["POWER", "GROUND"]:
                    continue
                else:
                    stdCell.addPin(pin)
                    # logger.debug("Adding pin {}, dir {}, to cell {}".format(pin.name, pin.dir, stdCell.name))

            #########
            # MACRO #
            #########
            if 'MACRO' in line:
                stdCell = StdCell(line.split()[1]) # Create an StdCell object. The name of the StdCell is the second word in the line 'MACRO ...'
                stdCells[stdCell.name] = stdCell

            if 'SIZE' in line:
                # Sample line: SIZE 0.42 BY 0.24 ;
                # width BY height
                size = line.split()
                stdCell.setWidth(float(size[1]))
                stdCell.setHeight(float(size[3]))
    return stdCells

def distributionFromFile(inFile):
    """
    Input file format:
    <cell name> <quantity>

    Parameters:
    -----------
    inFile : str
        Path to input file.

    Return:
    -------
    distribution : dict
        {cell name : weight}
    """
    with open(inFile, 'r') as f:
        lines = f.readlines()
    distribution = dict()
    for line in lines:
        distribution[line.split()[0]] = float(line.split()[1])

    ###############
    # Normalisation
    total = sum(distribution.values())
    for cell in distribution.keys():
        distribution[cell] = distribution[cell]/total

    return distribution

def generateNetlist(name, stdCells, distribution):
    """

    Parameters:
    -----------
    name : str
        Name of the top module
    stdCells : dict
        {cell name : StdCell}
    distribution : dict
        {cell name : weight}

    return Netlist instance
    """
    netlist = Netlist(name)

    cells = random.choices(list(distribution.keys()), distribution.values(), k=10)

    for i, c in enumerate(cells):
        cell = stdCells[c]
        name = cell.name.lower() + "_" + str(i)
        instance = Instance(name, cell=cell)

        #############################################################
        # Extract and list all pins of the stdcell into the instance.
        outputPinName = ""
        for pin in cell.pins.values():
            if pin.dir == "INPUT":
                instance.inputs[pin.name] = 0
            elif pin.dir == "OUTPUT":
                instance.outputs[pin.name] = 0
                outputPinName = pin.name
            else:
                logger.error("Unexpected pin dir: {} for pin {} in cell {}\n Aborting".format(pin.dir, pin.name, cell.name))
                sys.exit()
        if len(instance.outputs) > 1:
            logger.error("Too many outputs in cell {}".format(cell.name))
            sys.exit()


        #######################################
        # Create a net for each instance output
        net = Net(instance.name + "_net")
        net.dir = "wire" # not connected to an I/O pin yet.
        instance.outputs[outputPinName] = net
        netlist.nets.append(net)


        netlist.instances.append(instance)

    return netlist



def writeNetlist(netlist):
    """

    Parameters:
    -----------
    netlist : Netlist
    """

    #############################
    # First: top module and pins.
    outStr = "module {} ( {} );\n".format(netlist.topmodule, ",".join([x.name for x in netlist.pins]))
    for pin in netlist.pins:
        outStr += "{} {};\n".format(pin.dir, pin.name)

    ################
    # Nets and wires
    for net in netlist.nets:
        outStr += "{} {};\n".format(net.dir, net.name)

    ###########
    # Instances
    for instance in netlist.instances:
        # print(instance.cell.name)
        outStr += "{} {} ( ".format(instance.cell.name, instance.name)
        pinStrList = list()
        for pin in instance.cell.pins.values():
            pinStr = "." + pin.name + "("
            if pin.dir == "OUTPUT":
                pinStr += instance.outputs[pin.name].name
            pinStr += ")"
            pinStrList.append(pinStr)
        outStr += ", ".join(pinStrList)
        outStr += ");\n"

    ############
    # Write file
    filename = "{}.v".format(netlist.topmodule)
    with open(filename, 'w') as f:
        f.write(outStr)




if __name__ == "__main__":

    random.seed(RANDOM_SEED)

    args = docopt(__doc__)

    topModuleName = "customDesign"

    if args["--lef"]:
        leffile = args["--lef"]
    if args["--name"]:
        topModuleName = args["--name"]
    if args["--dist"]:
        distfile = args["--dist"]


    # Create the directory for the output.
    rootDir = os.getcwd()
    output_dir = rootDir + "/" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + topModuleName + "_" + leffile.split(os.sep)[-1]

    try:
        os.makedirs(output_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    # Load base config from conf file.
    logging.config.fileConfig('log.conf')
    # Load logger from config
    logger = logging.getLogger('default')
    # Create new file handler
    fh = logging.FileHandler(os.path.join(output_dir, 'netlistGen_' + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '.log'))
    # Set a format for the file handler
    fh.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
    # Add the handler to the logger
    logger.addHandler(fh)

    logger.debug(args)

    # Change the working directory to the one created above.
    os.chdir(output_dir)

    stdCells = dict() # {name : StdCell instance}

    stdCells = parseLEF(leffile)

    distribution = distributionFromFile(distfile)

    netlist = generateNetlist(topModuleName, stdCells, distribution)
    writeNetlist(netlist)


    logger.info("End of all.")

