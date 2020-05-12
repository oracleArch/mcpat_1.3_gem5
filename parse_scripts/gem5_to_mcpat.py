import os
import json
import re
from xml.etree import ElementTree as ET
from xml.dom import minidom

bench_path = "/scratch/mhuang_lab/ashar36/dla2/sim/debug_10m_rzheng/MinorCPU/0/0/hetero_power9smt4_TAGE_SC_L_64KB/astar/"

mcpat_template = "../ProcessorDescriptionFiles/Alpha21364.xml"

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

def start (path):
    readgem5Config(path)
    readgem5Stats(path)
    readMcpatTemplate (path)

start(bench_path)