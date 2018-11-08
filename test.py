from CMCTrader import Constants

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD], # or 'GBPUSD'
	# 'START_TIME' : '1:00',
	# 'END_TIME' : '7:55',
	'risk' : 1.0,
	'stoploss' : 17
}
utils = None

sar1 = None
sar2 = None
sar3 = None
cci = None
macd = None
rsi = None
pos = None

def init(utilities):
	print("Hello init World!")
	global utils
	utils = utilities
	
	global sar1
	sar1 = utils.SAR(1)
	
	global sar2
	sar2 = utils.SAR(2)

	global sar3
	sar3 = utils.SAR(3)
	
	global cci
	cci = utils.CCI(4, 2)

	global sma3
	sma3 = utils.CCI(5, 1)
	
	global macd
	macd = utils.MACD(6, 1)

	global rsi
	rsi = utils.RSI(7, 1)


	print(utils.getPositionAmount("GBPUSD"))
	global pos
	pos = utils.buy(400)

def onNewBar():
	print("onNewBar")
	pos.breakeven()
	pos.quickExit()
	# pos = utils.buy(1000, ordertype = 'stopentry', entry = 1.4, sl = 300, tp = 100)
	# pos.close()
	# print(sar1.get(Constants.GBPUSD, 0, 10))
	# print(sar1.isRising(Constants.GBPUSD, 0, 10))
	# pos = pos.stopAndReverse(3000)
	# print(pos.entryprice)
	# pos.modifyPositionSize(2000)
	# pos.modifyTP(30)
	# pos.modifySL(60)
	# pos.removeTP()
	# pos.apply()
	# pos.close()
	# print(pos.closeprice)

def onDownTime():
	print("onDownTime")

def failsafe(timestamps):
	print(timestamps)

	