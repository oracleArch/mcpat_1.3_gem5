import os
import json
import re
from xml.etree import ElementTree as ET
from xml.dom import minidom

bench_path = "/scratch/mhuang_lab/ashar36/dla2/sim/debug_10m_rzheng/MinorCPU/0/0/hetero_power9smt4_TAGE_SC_L_64KB/astar/"

mcpat_template = "template.xml"

# Don't replace cpus_name for
# 1. branch predictor
# 2. caches
cpus_name = 'switch_cpus'

class PIParser(ET.XMLTreeBuilder):
   def __init__(self):
       ET.XMLTreeBuilder.__init__(self)
       # assumes ElementTree 1.2.X
       self._parser.CommentHandler = self.handle_comment
       self._parser.ProcessingInstructionHandler = self.handle_pi
       self._target.start("document", {})

   def close(self):
       self._target.end("document")
       return ET.XMLTreeBuilder.close(self)

   def handle_comment(self, data):
       self._target.start(ET.Comment, {})
       self._target.data(data)
       self._target.end(ET.Comment)

   def handle_pi(self, target, data):
       self._target.start(ET.PI, {})
       self._target.data(target + " " + data)
       self._target.end(ET.PI)

def parse(source):
    return ET.parse(source, PIParser())

def readgem5Config (path):
    global config

    f = open(path + '/m5out/config.json')
    config = json.load(f)
    f.close()

def readgem5Stats (path):
    global stats
    stats = {}

    f = open(path + '/m5out/stats.txt')
    ignores = re.compile(r'^---|^$')
    statLine = re.compile(r'([a-zA-Z0-9_\.:-]+)\s+([-+]?[0-9]+\.[0-9]+|[-+]?[0-9]+|nan|inf)')
    count = 0 
    for line in f:
        #ignore empty lines and lines starting with "---"  
        if not ignores.match(line):
            count += 1
            statKind = statLine.match(line).group(1)
            print statKind
            statValue = statLine.match(line).group(2)
            if statValue == 'nan':
                print "\tWarning (stats): %s is nan. Setting it to 0" % statKind
                statValue = '0'
            stats[statKind] = statValue
    f.close()

def readMcpatTemplate (path):
    global templateMcpat
    templateMcpat = parse(mcpat_template)

def prepareTemplate(outputFile):
    numCores = len(config["system"]["switch_cpus"])
    privateL2 = config["system"]["switch_cpus"][0].has_key('l2cache')
    sharedL2 = config["system"].has_key('l2')
    if privateL2:
        numL2 = numCores
    elif sharedL2:
        numL2 = 1
    else:
        numL2 = 0
    elemCounter = 0
    root = templateMcpat.getroot()
    for child in root[0][0]:
        elemCounter += 1 # to add elements in correct sequence

        if child.attrib.get("name") == "number_of_cores":
            child.attrib['value'] = str(numCores)
        if child.attrib.get("name") == "number_of_L2s":
            child.attrib['value'] = str(numL2)
        if child.attrib.get("name") == "Private_L2":
            if sharedL2:
                Private_L2 = str(0)
            else:
                Private_L2 = str(1)
            child.attrib['value'] = Private_L2
        temp = child.attrib.get('value')

        # to consider all the cpus in total cycle calculation
        if isinstance(temp, basestring) and "cpu." in temp and temp.split('.')[0] == "stats":
            value = "(" + temp.replace("cpu.", "cpu0.") + ")"
            for i in range(1, numCores):
                value = value + " + (" + temp.replace("cpu.", "cpu"+str(i)+".") +")"
            child.attrib['value'] = value

        # remove a core template element and replace it with number of cores template elements
        if child.attrib.get("name") == "core":
            coreElem = copy.deepcopy(child)
            coreElemCopy = copy.deepcopy(coreElem)
            for coreCounter in range(numCores):
                coreElem.attrib["name"] = "core" + str(coreCounter)
                coreElem.attrib["id"] = "system.core" + str(coreCounter)
                for coreChild in coreElem:
                    childId = coreChild.attrib.get("id")
                    childValue = coreChild.attrib.get("value")
                    childName = coreChild.attrib.get("name")
                    if isinstance(childName, basestring) and childName == "x86":
                        if config["system"]["cpu"][coreCounter]["isa"][0]["type"] == "X86ISA":
                            childValue = "1"
                        else:
                            childValue = "0"
                    if isinstance(childId, basestring) and "core" in childId:
                        childId = childId.replace("core", "core" + str(coreCounter))
                    if isinstance(childValue, basestring) and "cpu." in childValue and "stats" in childValue.split('.')[0]:
                        childValue = childValue.replace("cpu." , "cpu" + str(coreCounter)+ ".")
                    if isinstance(childValue, basestring) and "cpu." in childValue and "config" in childValue.split('.')[0]:
                        childValue = childValue.replace("cpu." , "cpu." + str(coreCounter)+ ".")
                    if len(list(coreChild)) is not 0:
                        for level2Child in coreChild:
                            level2ChildValue = level2Child.attrib.get("value")
                            if isinstance(level2ChildValue, basestring) and "cpu." in level2ChildValue and "stats" in level2ChildValue.split('.')[0]:
                                level2ChildValue = level2ChildValue.replace("cpu." , "cpu" + str(coreCounter)+ ".")
                            if isinstance(level2ChildValue, basestring) and "cpu." in level2ChildValue and "config" in level2ChildValue.split('.')[0]:
                                level2ChildValue = level2ChildValue.replace("cpu." , "cpu." + str(coreCounter)+ ".")
                            level2Child.attrib["value"] = level2ChildValue
                    if isinstance(childId, basestring):
                        coreChild.attrib["id"] = childId
                    if isinstance(childValue, basestring):
                        coreChild.attrib["value"] = childValue
                root[0][0].insert(elemCounter, coreElem)
                coreElem = copy.deepcopy(coreElemCopy)
                elemCounter += 1
            root[0][0].remove(child)
            elemCounter -= 1

        # remove a L2 template element and replace it with number of L2 template elements
        if child.attrib.get("name") == "L2":
            if privateL2:
                l2Elem = copy.deepcopy(child)
                l2ElemCopy = copy.deepcopy(l2Elem)
                for l2Counter in range(numL2):
                    l2Elem.attrib["name"] = "L2" + str(l2Counter)
                    l2Elem.attrib["id"] = "system.L2" + str(l2Counter)
                    for l2Child in l2Elem:
                        childValue = l2Child.attrib.get("value")
                        if isinstance(childValue, basestring) and "cpu." in childValue and "stats" in childValue.split('.')[0]:
                            childValue = childValue.replace("cpu." , "cpu" + str(l2Counter)+ ".")
                        if isinstance(childValue, basestring) and "cpu." in childValue and "config" in childValue.split('.')[0]:
                            childValue = childValue.replace("cpu." , "cpu." + str(l2Counter)+ ".")
                        if isinstance(childValue, basestring):
                            l2Child.attrib["value"] = childValue
                    root[0][0].insert(elemCounter, l2Elem)
                    l2Elem = copy.deepcopy(l2ElemCopy)
                    elemCounter += 1
                root[0][0].remove(child)
            else:
                child.attrib["name"] = "L20"
                child.attrib["id"] = "system.L20"
                for l2Child in child:
                    childValue = l2Child.attrib.get("value")
                    if isinstance(childValue, basestring) and "cpu.l2cache." in childValue:
                        childValue = childValue.replace("cpu.l2cache." , "l2.")

    prettify(root)

def start (path):
    readgem5Config(path)
    readgem5Stats(path)
    readMcpatTemplate(path)

start(bench_path)