#!/usr/bin/env python3
import argparse, os, re, subprocess, glob, datetime, sys, shutil
import usb
import serial.tools.list_ports

tmpFiles= "/tmp/arduinotmp"
logFile = "/Users/spyro/Developement/ArduinoLib/ArduinoInstall.log"
arduinoCommand = ['arduino-cli',"compile"]

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
PURPLE = '\033[95m'
CYAN = '\033[96m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'

parser = argparse.ArgumentParser()
parser.add_argument('--test','-t',help="Just a test, display the command without executing it", action='store_true')
parser.add_argument('--board','-b', help='Name of the board or code if it has ":"', default="")
parser.add_argument('--port','-p', help="Com port (if cannot be found)", default = "")
parser.add_argument('--verbose','-v',help="Verbose", action='store_true')
parser.add_argument('--list','-l',help="Lister les boards", action='store_true')
parser.add_argument('--compile','-c',help="Compile (verify) without uploading", action='store_true')
parser.add_argument('sketch',type=str,help="Target sketch (folder or file)")
args = parser.parse_args()

testMode = args.test
comPort = args.port
boardName = args.board
boardTitle = boardName
boardConfig = ""

"""
- boards that have a comPort will just use that
- boards that have "-" as a comPort will not use a comPort
- boards that have a USBName will look for the comPort on USB
- boards that have neither will need you to give a -p comPort

names	: argument for this script --board (and synonyms)
name	: for print (command line feedback and log)
board	: code to use for Arduino's --board
USBName	: name under which the board appears in the USB

To test read USB info, use the usbread.py script
To find board codes, got to this (for adafruit samd boards for exemple)
~/Library/Arduino15/packages/adafruit/hardware/samd/1.0.21/boards.txt

# TODO: ESP32 (ou pas ?)

INSTALL:
sudo python3 -m pip install pyusb
sudo python3 -m pip install pyserial
+ libusb (homebrew on mac)

arduino-cli board list ?
"""

boards = [
	{
		'names':["cpx","circuitm0"],
		'name':"CircuitPlayground Express",
		'board':"adafruit:samd:adafruit_circuitplayground_m0",
		'USBName':"CircuitPlayground Express",
	},
	{
		'names':["featherm0ex","featherm0express"],
		'name':"Feather M0 Express",
		'board':"adafruit:samd:adafruit_feather_m0_express",
		'USBName':"Feather M0 Express",
	},
	{
		'names':["itsym0","itsybitsym0"],
		'name':"ItsyBitsy M0 Express",
		'board':"adafruit:samd:adafruit_itsybitsy_m0",
		'USBName':"ItsyBitsy M0 Express",
	},
	{
		'names':["trinketm0"],
		'name':"Trinket M0",
		'board':"adafruit:samd:adafruit_trinket_m0",
		'USBName':"Trinket M0",
	},
	{
		'names':["gemmam0"],
		'name':"Gemma M0",
		'board':"adafruit:samd:adafruit_gemma_m0",
		'USBName':"Gemma M0",
	},
	{
		'names':["wiced"],
		'name':"Feather WICED",
		'board':"adafruit:wiced:feather:section=usercode",
		'USBName':"WICED Feather Board",
	},
	{
		'names':["huzzah"],
		'name':"Feather Huzzah",
		'board':"esp8266:esp8266:huzzah",
		'USBName':"CP2104 USB to UART Bridge Controller",
	},
	{
		'names':["feather","featherm0"],
		'name':"Feather M0 (any)",
		'board':"adafruit:samd:adafruit_feather_m0",
		'USBName':"Feather M0",
	},
	{
		'names':["feather","featherm0"],
		'name':"Feather M0 (basic)",
		'board':"adafruit:samd:adafruit_feather_m0",
		'USBName':"Feather M0 Basic",
	},
	{
		'names':["micro"],
		'name':"Arduino Micro",
		'board':"arduino:avr:micro",
		'USBName':"Arduino Micro",
	},
	{
		'names':["cp","circuit","circuitplay"],
		'name':"Circuit Playground",
		'board':"adafruit:avr:circuitplay32u4cat",
		'USBName':"Circuit Playground",
	},
	{
		'names':["gemma"],
		'name':"Gemma",
		'board':"adafruit:avr:gemma",
		'noComPort':True,
		#'USBName':"Trinket",
	},
	{
		'names':['trinket','trinket5'],
		'name':"Trinket 5V",
		'board':"adafruit:avr:trinket5",
		'noComPort':True,
		#'USBName':"Trinket",
	},
	{
		'names':['trinket3'],
		'name':"Trinket 3V",
		'board':"adafruit:avr:trinket3",
		'noComPort':True,
		#'USBName':"Trinket",
	},
	{
		'names':['prot','prot5','protrinket','protrinket5'],
		'name':"Pro Trinket 5V",
		'board':"adafruit:avr:protrinket5",
		'noComPort':True,
		#'USBName':"USBTiny",
	},
	{
		'names':['prot3','protrinket3'],
		'name':"Pro Trinket 3V",
		'board':"adafruit:avr:protrinket3",
		'noComPort':True,
		#'USBName':"USBTiny",
	}
]

if args.list:
	print("List of known boards:")
	print("\n".join([x['name']+" : "+" ".join(x['names']) for x in boards]))
	exit(0)
	
# find the trinkets currently in bootloader mode
# (they are not listed as serial ports)
# it's impossible to identify what board they are exactly this way
trinkets = []
try:
	for bus in usb.busses():
		for device in bus.devices:
			dev = device.dev
			if dev.product in ["Trinket","USBTiny"]:
				trinkets += [{
					'name':dev.product,
					'vendor':dev.idVendor,
					'product':dev.idProduct,
				}]
except:
	print(RED+BOLD+"USB ERROR:",sys.exc_info()[0])
if len(trinkets)>0:
	print(CYAN+"Saw a (Pro) Trinket or a Gemma or USBTiny in bootloader mode")

# list the available serial ports, we'll need that
ports = serial.tools.list_ports.comports()
existingPorts = []
for port in ports:
	if port.product == None: continue
	existingPorts += [{'name':port.product, 'port':port.device}]

# if the full board config is specified, just use that
m = re.search("^([^:]+):([^:]+):([^:]+)",boardName)
if m:
	boardConfig = boardName
	boardTitle = m.group(1)+":"+m.group(2)+":"+m.group(3)
	print(YELLOW+"Board config “"+boardConfig+"”")

# try to find the board by name
# - try to get the com port(s) it is connected to
# - if boardConfig given, don't do that (require comport ?)
found = []
if boardName != "" and boardConfig == "":
	boardFound = False
	for bo in boards:
		if boardName.lower() in bo['names']:
			boardFound = True
			if 'name' in bo:
				boardTitle = bo['name']
			if "board" in bo and boardConfig == "":
				boardConfig = bo['board']
			if "noComPort" in bo:
				comPort = "-"
			elif "USBName" in bo and comPort == "":
				for realPort in existingPorts:
					if bo['USBName'] == realPort['name']:
						comPort = realPort['port']
						found += [realPort]
	# if board name not found, die now
	if not boardFound:
		print(RED+"Board “"+boardTitle+"” unknown, what are you talking about ?")
		exit(1)
	elif comPort == "":
		print(RED+"Port not found for the board “"+boardTitle+"”")
		print("Give a port or plug the board with a working cable")
		if not args.compile:
			exit(1)
	else:
		print(YELLOW+"Using the board “"+boardTitle+"”")

# try to find the board and port by looking at the USB register
# - find all potential ports
if comPort == "" and not args.compile:
	for bo in boards:
		if "USBName" in bo:
			for realPort in existingPorts:
				if bo['USBName'] == realPort['name']:
					found += [realPort]
					if "noComPort" in bo:
						comPort = "-"
					else:
						comPort = realPort['port']
					if 'name' in bo:
						boardTitle = bo['name']
					if "board" in bo and boardConfig == "":
						boardConfig = bo['board']
	# not found
	if comPort == "":
		print(RED+"No port found, ever, give a port or plug the board")
		exit(1)
	else:
		print(YELLOW+"Board “"+boardTitle+"” found on serial port")

# if port given but not the board config
# - scan the boards to find which one has the correct USB Name
elif boardConfig == "":
	USBName = ""
	for port in existingPorts:
		if port['port'] == comPort:
			USBName = port['name']
		elif port['port'] == "/dev/"+comPort:
			USBName = port['name']
	if USBName:
		for bo in boards:
			if "USBName" in bo:
				if bo['USBName'] == USBName:
					if 'name' in bo:
						boardTitle = bo['name']
					if "board" in bo and boardConfig == "":
						boardConfig = bo['board']
	if boardConfig != "":
		print(YELLOW+"Board “"+boardTitle+"” found on serial port")

# if the given board name/port are not enough
if len(found) > 1: # +len(trinkets)
	print(RED+"Too many ports found specify a board name and/or a port")
	for ff in found:
		print("%s : %s" % (ff['name'],ff['port']))
	for ff in trinkets:
		print("%s (%d,%d)" % (ff['name'],ff['vendor'],ff['product']))
	exit(1)

# find the sketch by name of folder or file
# "sketch" or "sketch.ino" finds sketch/sketch.ino
# whether the current directory is "sketch/" or the parent directory
sketch = args.sketch
if sketch[-1] == "/":
	sketch = sketch[0:-1]
if sketch == ".":
	sketch = os.path.abspath(".")
#
if re.match('.*\.ino$',sketch):
	if not os.path.exists(sketch):
		path = os.path.split(sketch)
		tName = os.path.splitext(path[-1])[0]
		lPath = list(path[0:-1])+[tName,tName+".ino"]
		sPath = os.path.normpath(os.path.join(*lPath))
		if os.path.exists(sPath):
			sketch = sPath
else:
	tName = os.path.basename(sketch)
	sPath = os.path.normpath(os.path.join(sketch,tName+".ino"))
	if os.path.exists(sPath):
		sketch = sPath
	else:
		sPath = sketch+".ino"
		if os.path.exists(sPath):
			sketch = sPath

# validate the com port
# if it's "-", just don't specify it
if comPort == "" and not args.compile:
	print(RED+"No COM PORT found or given")
	exit(1)
elif comPort == "-" or args.compile:
	print(YELLOW+"No COM PORT USED")
else:
	if os.path.exists(comPort):
		print(YELLOW+"Com port used <"+comPort+">")
	elif os.path.exists("/dev/"+comPort):
		comPort = "/dev/"+comPort
		print(YELLOW+"Com port used <"+comPort+">")
	else:
		print(RED+"It seems the com port <"+comPort+"> does not exist.")
		print("Is the board correctly plugged in with a data cable ?")
		print("And is it in bootloader mode ? (if necessary)")
		exit(1)
# validate 
if boardConfig == "":
	print(RED+"Board config can not be found (use the -b option)")
	exit(1)
# check that the sketch file exists
if not os.path.exists(sketch):
	print(RED+"Sketch <"+sketch+"> not found or not valid")
	exit(1)
else:
	# check if the sketch is in a folder of the same name
	path = os.path.abspath(sketch)
	if not re.match(r'.*/([^/]+)/\1\.ino$',path):
		print(RED+"Sketch <"+sketch+"> not in a folder by the same name\n(fix it or the Arduino app will complain)")
		exit(1)

# is there a build dir ?
buildDir = os.path.dirname(os.path.abspath(sketch)) + "/build"
hasBuildDir = os.path.exists(buildDir)

# create the command
command = arduinoCommand
# keep temporary files in a normal session
if os.path.exists(os.path.dirname(tmpFiles)):
	if not os.path.exists(tmpFiles):
		os.mkdir(tmpFiles)
	command += [
		#"--preserve-temp-files",
		"--build-cache-path", tmpFiles,
		"--build-path", tmpFiles,
	]
# the options
if args.verbose:
	command += ["-v"]
if comPort != "-":
	command += ["--port",comPort]
command += ["--fqbn",boardConfig]
if args.compile:
	command += ["--verify"]
else:
	command += ["--upload"]
command += [sketch]

# log every compile operation if you want
def logIt(com):
	if not logFile or not os.path.exists(os.path.dirname(logFile)):
		return
	with open(logFile,"a") as fp:
		fp.write("#### ")
		fp.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
		fp.write(" ####")
		fp.write("\n")
		fp.write(os.getcwd())
		fp.write("\n")
		fp.write(" ".join(sys.argv))
		fp.write("\n")
		fp.write(" ".join(com))
		fp.write("\n")

# do the thing
print(PURPLE,end="")
print(" ".join(command),ENDC)
if testMode == False:
	logIt(command)
	subprocess.call(command)

if not hasBuildDir:
	if os.path.exists(buildDir):
		print(CYAN+"Deleting build path: "+buildDir)
		print(RED+"rm -rf "+buildDir)
		shutil.rmtree(buildDir)
else:
	print(RED+"Not"+CYAN+" deleting build path: "+buildDir)

print(CYAN+"FIN !")
