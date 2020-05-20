import os
import json
import re
from xml.etree import ElementTree as ET
from xml.dom import minidom
import copy
import types

bench_path = "/scratch/mhuang_lab/ashar36/dla2/sim/debug_10m_rzheng/HeteroSoC/0/0/hetero_prime_power9smt4_TAGE_SC_L_64KB/gobmk/"

# The input mcpat template
mcpat_template = "o3_template.xml"

# Manually set the number of Cores
Manual = True
numInorder = 0#1
numO3 = 1#0#1
gem5_O3_start_index = 1
numCores = numInorder + numO3

# Don't replace cpus_name for
# 1. branch predictor
# 2. caches
# 3. workload
cpus_name = 'switch_cpus'

def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

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
            statValue = statLine.match(line).group(2)
            if statValue == 'nan':
                print "\tWarning (stats): %s is nan. Setting it to 0" % statKind
                statValue = '0'
            stats[statKind] = statValue
    f.close()

def readMcpatTemplate (path):
    global templateMcpat
    templateMcpat = parse(mcpat_template)

def prepareTemplate (path):
    global numCores
    global gem5_O3_start_index

    if not Manual :
        numCores = len(config["system"][cpus_name])
    
    privateL2 = config["system"]["cpu"][0].has_key('l2cache')
    sharedL2 = config["system"].has_key('l2')
    if privateL2:
        numL2 = numCores
    elif sharedL2:
        numL2 = 1
    else:
        numL2 = 0
    elemCounter = 0

    # Count the number of Inorder and O3 cpus seperately
    num_inorder = 0
    num_o3 = 0
    if not Manual:
        for coreCounter in range(numCores):
            if config["system"][cpus_name][coreCounter]["type"] == "MinorCPU":
                num_inorder += 1

            elif config["system"][cpus_name][coreCounter]["type"] == "DerivO3CPU":
                num_o3 += 1

        gem5_O3_start_index = num_inorder
    else:
        num_inorder = numInorder
        num_o3 = numO3

    root = templateMcpat.getroot()
    for child in root[0][0]:
        elemCounter += 1 # to add elements in correct sequence

        if child.attrib.get("name") == "number_of_cores":
            child.attrib['value'] = str(numCores)
        if child.attrib.get("name") == "number_of_L2s":
            child.attrib['value'] = str(numL2)
        if child.attrib.get("name") == "Private_L2":
            child.attrib['value'] = "0" if sharedL2 else "1"
        temp = child.attrib.get('value')

        # remove a core template element and replace it with number of cores template elements
        if child.attrib.get("name") == "Minorcore":
            coreElem = copy.deepcopy(child)
            coreElemCopy = copy.deepcopy(coreElem)
            for coreCounter in range(0, num_inorder):
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
                    if isinstance(childId, basestring) and "Minorcore" in childId:
                        childId = childId.replace("Minorcore", "core" + str(coreCounter))
                    if isinstance(childValue, basestring) and "cpu." in childValue and "stats" in childValue.split('.')[0]:
                        if "cpu.branchPred." in childValue or "cpu.dcache." in childValue or "cpu.icache." in childValue or "cpu.workload." in childValue:
                            childValue = childValue.replace("cpu." , "cpu" + str(coreCounter)+ ".")
                        else:
                            childValue = childValue.replace("cpu." , cpus_name + str(coreCounter)+ ".")
                    if isinstance(childValue, basestring) and "cpu." in childValue and "config" in childValue.split('.')[0]:
                        if "cpu.branchPred." in childValue or "cpu.dcache." in childValue or "cpu.icache." in childValue or "cpu.workload." in childValue:
                            childValue = childValue.replace("cpu." , "cpu."+ str(coreCounter)+ ".")
                        else:
                            childValue = childValue.replace("cpu." , cpus_name + "."+ str(coreCounter)+ ".")
                    if len(list(coreChild)) is not 0:
                        for level2Child in coreChild:
                            level2ChildValue = level2Child.attrib.get("value")
                            if isinstance(level2ChildValue, basestring) and "cpu." in level2ChildValue and "stats" in level2ChildValue.split('.')[0]:
                                if "cpu.branchPred." in level2ChildValue or "cpu.dcache." in level2ChildValue or "cpu.icache." in level2ChildValue or "cpu.workload." in level2ChildValue:
                                    level2ChildValue = level2ChildValue.replace("cpu." , "cpu" + str(coreCounter)+ ".")
                                else:
                                    level2ChildValue = level2ChildValue.replace("cpu." , cpus_name + str(coreCounter)+ ".")
                            if isinstance(level2ChildValue, basestring) and "cpu." in level2ChildValue and "config" in level2ChildValue.split('.')[0]:
                                if "cpu.branchPred." in level2ChildValue or "cpu.dcache." in level2ChildValue or "cpu.icache." in level2ChildValue or "cpu.workload." in level2ChildValue:
                                    level2ChildValue = level2ChildValue.replace("cpu." , "cpu." + str(coreCounter)+ ".")
                                else:
                                    level2ChildValue = level2ChildValue.replace("cpu." , cpus_name + "." + str(coreCounter)+ ".")
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

        elif child.attrib.get("name") == "O3core":
            coreElem = copy.deepcopy(child)
            coreElemCopy = copy.deepcopy(coreElem)
            for coreCounter in range(num_inorder, numCores):
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
                    if isinstance(childId, basestring) and "O3core" in childId:
                        childId = childId.replace("O3core", "core" + str(coreCounter))
                    if isinstance(childValue, basestring) and "cpu." in childValue and "stats" in childValue.split('.')[0]:
                        if "cpu.branchPred." in childValue or "cpu.dcache." in childValue or "cpu.icache." in childValue or "cpu.workload." in childValue:
                            childValue = childValue.replace("cpu." , "cpu" + str(gem5_O3_start_index)+ ".")
                        else:
                            childValue = childValue.replace("cpu." , cpus_name + str(gem5_O3_start_index)+ ".")
                    if isinstance(childValue, basestring) and "cpu." in childValue and "config" in childValue.split('.')[0]:
                        if "cpu.branchPred." in childValue or "cpu.dcache." in childValue or "cpu.icache." in childValue or "cpu.workload." in childValue or "cpu.cpu_clk_domain" in childValue or "cpu.cpu_voltage_domain" in childValue:
                            childValue = childValue.replace("cpu." , "cpu."+ str(gem5_O3_start_index)+ ".")
                        else:
                            childValue = childValue.replace("cpu." , cpus_name + "."+ str(gem5_O3_start_index)+ ".")
                    if len(list(coreChild)) is not 0:
                        for level2Child in coreChild:
                            level2ChildValue = level2Child.attrib.get("value")
                            if isinstance(level2ChildValue, basestring) and "cpu." in level2ChildValue and "stats" in level2ChildValue.split('.')[0]:
                                if "cpu.branchPred." in level2ChildValue or "cpu.dcache." in level2ChildValue or "cpu.icache." in level2ChildValue or "cpu.workload." in level2ChildValue:
                                    level2ChildValue = level2ChildValue.replace("cpu." , "cpu" + str(gem5_O3_start_index)+ ".")
                                else:
                                    level2ChildValue = level2ChildValue.replace("cpu." , cpus_name + str(gem5_O3_start_index)+ ".")
                            if isinstance(level2ChildValue, basestring) and "cpu." in level2ChildValue and "config" in level2ChildValue.split('.')[0]:
                                if "cpu.branchPred." in level2ChildValue or "cpu.dcache." in level2ChildValue or "cpu.icache." in level2ChildValue or "cpu.workload." in level2ChildValue or "cpu.cpu_clk_domain" in level2ChildValue or "cpu.cpu_voltage_domain" in level2ChildValue:
                                    level2ChildValue = level2ChildValue.replace("cpu." , "cpu." + str(gem5_O3_start_index)+ ".")
                                else:
                                    level2ChildValue = level2ChildValue.replace("cpu." , cpus_name + "." + str(gem5_O3_start_index)+ ".")
                            level2Child.attrib["value"] = level2ChildValue
                    
                    if isinstance(childId, basestring):
                        coreChild.attrib["id"] = childId
                    if isinstance(childValue, basestring):
                        coreChild.attrib["value"] = childValue
                
                root[0][0].insert(elemCounter, coreElem)
                coreElem = copy.deepcopy(coreElemCopy)
                elemCounter += 1
                gem5_O3_start_index += 1
            
            root[0][0].remove(child)
            elemCounter -= 1

        # remove a L2 template element and replace it with number of L2 template elements
        elif child.attrib.get("name") == "L2":
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

def getConfigValue (confStr):
    spltConf = re.split('\.', confStr)
    currConf = config
    currHierarchy = ""
    for x in spltConf:
        currHierarchy += x
        if x.isdigit():
            currConf = currConf[int(x)]
        elif x in currConf:
            currConf = currConf[x]
        currHierarchy += "."
    return currConf

def dumpMcpatTemplate (path):
    rootElem = templateMcpat.getroot()
    configMatch = re.compile(r'config\.([][a-zA-Z0-9_:\.]+)')
    
    #replace params with values from the GEM5 config file 
    for param in rootElem.iter('param'):
        name = param.attrib['name']
        value = param.attrib['value']
        if 'config' in value:
            allConfs = configMatch.findall(value)
            for conf in allConfs:
                confValue = getConfigValue(conf)
                value = re.sub("config."+ conf, str(confValue), value)
            if "," in value:
                exprs = re.split(',', value)
                for i in range(len(exprs)):
                    exprs[i] = str(eval(exprs[i]))
                param.attrib['value'] = ','.join(exprs)
            else:
                param.attrib['value'] = str(eval(str(value)))
    
    #replace stats with values from the GEM5 stats file 
    statRe = re.compile(r'stats\.([a-zA-Z0-9_:\.]+)')
    for stat in rootElem.iter('stat'):
        name = stat.attrib['name']
        value = stat.attrib['value']
        if 'stats' in value:
            allStats = statRe.findall(value)
            expr = value
            for i in range(len(allStats)):
                if allStats[i] in stats:
                    expr = re.sub('stats.%s' % allStats[i], stats[allStats[i]], expr)
                else:
                    expr = re.sub('stats.%s' % allStats[i], str(0), expr)
                    print "***WARNING: %s does not exist in stats***" % allStats[i]
                    print "\t Please use the right stats in your McPAT template file"

            if 'config' not in expr and 'stats' not in expr:
                stat.attrib['value'] = str(eval(expr))

    output_template = path + '/m5out/mcpat.xml'
    templateMcpat.write(output_template)

def start (path):
    readgem5Config(path)
    readgem5Stats(path)
    readMcpatTemplate(path)
    prepareTemplate(path)
    dumpMcpatTemplate(path)

start(bench_path)