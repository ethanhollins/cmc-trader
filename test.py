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
	rsi = utils.RSI(5, 1)
	cci = utils.CCI(6, 1)
	macd = utils.MACD(7, 1)

	pos = utils.buy(400, ordertype = 'se', entry = 1.3)
	pos.modifyEntryPrice(1.459)
	pos.apply()
	# pos.apply()
	# pos.modifyTrailing(40)
	# pos.modifyTrailing(60)
	# pos.trailingReg(50)
	# time.sleep(3)
	# pos.trailingReg()
	# pos.modifyTrailingSL(10)

def onLoop():
	return

def onNewBar():
	print("onNewBar\n")

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit())

	print("ORDERS:")
	count = 0
	for order in utils.orders:
		count += 1
		print(str(count) + ":", str(order.direction), str(order.entryprice))

def onRecovery():
	print("onRecovery")
	global pending_entries
	pending_entries = []

def onDownTime():
	print("onDownTime")

class SaveState(object):
	def __init__(self, utils):
		self.utils = utils
		self.save_state = self.save()
		# print("SAVED:", str(self.save_state))

	def save(self):
		voided_types = [type(i) for sub in self.utils.indicators.values() for i in sub]
		voided_types.append(type(self.utils))
		return [
				copy.deepcopy(attr) for attr in globals().items() 
				if not attr[0].startswith("__") 
				and not callable(attr[1]) 
				and not isinstance(attr[1], types.ModuleType) 
				and not type(attr[1]) in voided_types 
				and not attr[0] == 'VARIABLES'
			]

	def load(self):
		print("\nLOADING...")
		print("GLOB:", str([globals()[attr[0]] for i in globals() for attr in self.save_state if i is attr[0]]) + "\n")
		print("SAVE:", str([attr[1] for attr in self.save_state]) + "\n")
		for attr in self.save_state:
			globals()[attr[0]] = attr[1]

		print("NEW\nGLOB:", str([globals()[attr[0]] for i in globals() for attr in self.save_state if i is attr[0]]) + "\n")
	