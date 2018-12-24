from CMCTrader import Constants
import copy
import types
import time

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD], # or 'GBPUSD'
	'START_TIME' : '1:30',
	'END_TIME' : '19:00',
	'risk' : 1.0,
	'stoploss' : 17
}

count = 0
nums = []
trig = None

sl = 20

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
	global reg_sar, slow_sar, black_sar, rsi, cci, macd

	utils = utilities
	reg_sar = utils.SAR(1)
	black_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	brown_sar = utils.SAR(4)
	cci = utils.CCI(5, 1)
	macd = utils.MACD(6, 1)

	global pos
	pos = utils.buy(400)

def onLoop():
	return

def onNewBar():
	print("onNewBar\n")

	global sl

	pos.modifySL(sl)
	pos.apply()

	sl += 1

def onDownTime():
	print("onDownTime")