from CMCTrader import Constants
import copy

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

	global trig
	trig = Trigger("text 1")
	print(str(trig))
	print(str(trig.txt1), str(trig['txt2']))

	trig2 = copy.deepcopy(trig)
	trig.txt1 = "text again"
	print(str(trig2.txt1))
	print(str(trig))

def onLoop():
	return

def onNewBar():
	print("onNewBar")
	
	global count

	count += 1

	print(trig)

	nums.append(count)
	print(nums)

def onRecovery():
	print("onRecovery")
	global pending_entries
	pending_entries = []

def onDownTime():
	print("onDownTime")

class SaveState(object):
	def __init__(self):
		self.saved_vars = {}
		self.saved_names = self.getPicklable()
		self.save()

	def getPicklable(self):
		names = []
		
		for i in globals():	
			try:
				copy.deepcopy(globals()[i])
				names.append(i)
			except:
				continue

		print(names)
		return names

	def save(self):
		self.saved_names = self.getPicklable()

		for name in self.saved_names:
			self.saved_vars[name] = copy.deepcopy(globals()[name])

		print(self.saved_vars)

	def load(self):
		for name in self.saved_names:
			print(str(globals()[name]), ":", str(self.saved_vars[name]))
			globals()[name] = self.saved_vars[name]
	