#!/usr/bin/env python3
"""
Usage:
    netlistGen.py (--lef=<file>) [--gates=n] [--name=<name>] [--dist=<file>] [--fanout=<int>] [--suppress-wires]
    netlistGen.py (--help|-h)

Options:
    --lef=<file>            .lef file
    --gates=n               Amount of gate in the netlist
    --name=<name>           Top module name
    --dist=<file>           Std cell distribution file
    --fanout=<int>          Average fanout, integer
    --suppress-wires        Do not write 'wire's in netlist
    -h --help               Print this help

Note: Power pins are ignored in standard cells.
"""

import math
import locale
import os
import datetime
import errno
import random
from docopt import docopt
import logging, logging.config
import numpy as np
import sys
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
        self.inputs = dict() # {pin name : 0|net}, 0 => pin is free
        self.outputs = dict() # {pin name : 0|net}, 0 => pin is free

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

            if macroBlock:
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

            #########
            # MACRO #
            #########
            if 'MACRO' in line:
                stdCell = StdCell(line.split()[1]) # Create an StdCell object. The name of the StdCell is the second word in the line 'MACRO ...'
                stdCells[stdCell.name] = stdCell
                macroBlock = True

            if macroBlock and 'END {}'.format(stdCell.name) in line:
                macroBlock = False

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

def generateNetlist(name, stdCells, distribution, fanout, ngates):
    """
    1. Create *ngates* based on *distribution*.
    2. For each gate, create a net at the output pin.
    3. Once it's done, connect each net to x inputs of other gates.
        x is picked on a gaussian centered around *fanout*.
    4. For each input that has not been connected yet,
        create a top module IO input connecting it.

    Parameters:
    -----------
    name : str
        Name of the top module
    stdCells : dict
        {cell name : StdCell}
    distribution : dict
        {cell name : weight}
    fanout : int
        Average fanout of a net
    ngates : int
        Amount of gates to generate

    return Netlist instance
    """
    ######################
    # Some more parameters
    CPDensity = 30 # Critical Path (CP) Density: Maximum amount of logic gates between two flip-flops (FFs).
    ######################

    # Updated idea: create 'clusters' of logic up to `CPDensity`.
    # Interconnect them using a FF.
    # All other FFs will become registers (shift, ...) by being interconnected toghether.
    # Where should they be connected ?
    # All clusters should not necessarily be daisy-chained. It could be a parameter changing the level of full interconnection.

    netlist = Netlist(name)

    cells = random.choices(list(distribution.keys()), distribution.values(), k=ngates)

    logic = set()
    ff = set()

    #######################
    # Stats on logic and FF
    logicCnt = 0
    ffCnt = 0
    for c in cells:
        cell = stdCells[c]
        logicCnt += 1
        logic.add(c)
        for pin in cell.pins.values():
            if pin.type == "CLOCK":
                ffCnt += 1
                ff.add(c)
                logicCnt -= 1
                logic.remove(c)
                break
    logger.info("Logic: {} ({}%), FF: {} ({}%)".format(logicCnt, 100*logicCnt/(logicCnt+ffCnt), ffCnt, 100*ffCnt/(ffCnt+logicCnt)))


    instAvail = list() # List of instances with at least one input available

    with alive_bar(len(cells)) as bar:
        for i, c in enumerate(cells):
            bar()
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

            # List of all instances having at least on available input:
            instAvail.append(instance)

            netlist.instances.append(instance)

    ###############################
    # Generate clock for Flip-Flops
    clock = Net("clock")
    clock.dir = "input"
    netlist.nets.append(clock)

    clockPin = Pin("clock")
    clockPin.dir = "INPUT"
    clockPin.type = "CLOCK"
    netlist.pins.append(clock)

    for instance in netlist.instances:
        for pinName in instance.inputs.keys():
            pinType = stdCells[instance.cell.name].pins[pinName].type
            if pinType == "CLOCK":
                instance.inputs[pinName] = clock

    #####################
    # Link nets to inputs
    #
    # For each gate, take the output net and assign it to n inputs.
    # n is int(random.gauss(2,1)), where 2 is the average desired fanout and 1 the stdev.
    with alive_bar(len(netlist.instances)) as bar:
        for instance in netlist.instances:
            bar()
            randFanout = int(random.gauss(fanout, 1))
            net = instance.outputs[list(instance.outputs.keys())[0]]

            for i in range(randFanout):
                found = False
                while not found:
                    if len(instAvail) == 0:
                        break
                    candidate = random.choice(instAvail)
                    if 0 in candidate.inputs.values():
                        for pin in candidate.inputs.keys():
                            if candidate.inputs[pin] == 0:
                                candidate.inputs[pin] = net
                                break
                        found = True
                    else:
                        instAvail.remove(candidate)

    ######################################################
    # Create input I/O for unassigned inputs in instances.
    with alive_bar(len(instAvail)) as bar:
        for instance in instAvail:
            bar()
            for pin in instance.inputs.keys():
                if instance.inputs[pin] == 0:
                    netName = instance.name + "_" + pin
                    inIONet = Net(netName)
                    inIONet.dir = "input"
                    instance.inputs[pin] = inIONet
                    netlist.nets.append(inIONet)

                    inIOPin = Pin(netName)
                    inIOPin.dir = "INPUT"
                    inIOPin.type = "SIGNAL"
                    netlist.pins.append(inIOPin)

    return netlist



def writeNetlist(netlist, suppressWires):
    """

    Parameters:
    -----------
    netlist : Netlist

    suppressWires : boolean
        If True, do not write 'wire' statements
    """

    #############################
    # First: top module and pins.
    outStr = "module {} ( {} );\n".format(netlist.topmodule, ",".join([x.name for x in netlist.pins]))
    for pin in netlist.pins:
        outStr += "{} {};\n".format(pin.dir.lower(), pin.name)

    ################
    # Nets and wires
    if not suppressWires:
        for net in netlist.nets:
            if net.dir == "wire":
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
            elif pin.dir == "INPUT":
                if instance.inputs[pin.name] == 0:
                    pinStr += "UNASSIGNED"
                    logger.warning("UNASSIGNED pin '{}' in '{}'".format(pin.name, instance.name))
                else:
                    pinStr += instance.inputs[pin.name].name
            pinStr += ")"
            pinStrList.append(pinStr)
        outStr += ", ".join(pinStrList)
        outStr += ");\n"

    outStr += "\n endmodule"

    ############
    # Write file
    filename = "{}.v".format(netlist.topmodule)
    with open(filename, 'w') as f:
        f.write(outStr)




if __name__ == "__main__":

    random.seed(RANDOM_SEED)

    args = docopt(__doc__)

    topModuleName = "customDesign"
    fanout = 3
    ngates = 10
    suppressWires = False

    if args["--lef"]:
        leffile = args["--lef"]
    if args["--name"]:
        topModuleName = args["--name"]
    if args["--dist"]:
        distfile = args["--dist"]
    if args["--fanout"]:
        fanout = args["--fanout"]
    if args["--gates"]:
        ngates = int(args["--gates"])
    if args["--suppress-wires"]:
        suppressWires = True


    # Create the directory for the output.
    rootDir = os.getcwd()
    output_dir = rootDir + "/" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_" + topModuleName + "_" + "ngates-" + str(ngates) + "_" + "fanout-" + str(fanout) + "_" + leffile.split(os.sep)[-1]

    try:
        os.makedirs(output_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    ###########
    # Logging #
    ###########
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

    ########
    # Algo #
    ########
    stdCells = dict() # {name : StdCell instance}

    stdCells = parseLEF(leffile)

    distribution = distributionFromFile(distfile)

    netlist = generateNetlist(topModuleName, stdCells, distribution, fanout, ngates)
    
    writeNetlist(netlist, suppressWires)

    logger.info("End of all.")

