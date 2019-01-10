from CMCTrader import Constants
import copy
import types
import time

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD], # or 'GBPUSD'
	'START_TIME' : '20:00',
	'END_TIME' : '19:00',
	'risk' : 1.0,
	'stoploss' : 17
}

count = 0
nums = []
trig = None

sl = 20

count = 0

class Trigger(dict):
	def __init__(self, txt):
		self.txt1 = txt
		self.txt2 = "text num 2"

	@classmethod
	def fromDict(cls, dic):
		cpy = cls(dic['txt1'])
		for key in dic:
			cpy[key] = dic[key]
		return cpy
	
	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

	def __deepcopy__(self, memo):
		return Trigger.fromDict(dict(self))

# class Trigger(object):
# 	def __init__(self, txt):
# 		self.txt1 = txt
# 		self.txt2 = "text num 2"



def init(utilities):
	print("Hello init World!")
	global utils
	global reg_sar, slow_sar, black_sar, brown_sar, cci, macd, dmi

	utils = utilities
	brown_sar = utils.SAR(1)
	reg_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	black_sar = utils.SAR(4)
	cci = utils.CCI(5, 1)
	macd = utils.MACD(6, 1)
	dmi = utils.DMI(7, 3)

	global pos
	# pos = utils.buy(400)

def onLoop():
	return

def onNewBar():
	print("onNewBar\n")

	global count, pos, newPos
	count += 1
	print("Count:",str(count))
	if count == 2:
		pos = utils.buy(400, sl = 20)
	if count == 4:
		pos.modifySL(30)
		pos.apply()
		pos.close()
		newPos = utils.sell(400, sl = 20)
		newPos.removeSL()
		newPos.apply()


	# 	pos.modifyTP(20)
	# 	pos.modifySL(20)
	# 	pos.apply()
	# elif count == 4:
	# 	newPos = pos.stopAndReverse(500, sl = 30, tp = 25)
	# 	newPos.removeTP()

def onDownTime():
	print("onDownTime")