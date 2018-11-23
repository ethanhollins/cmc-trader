from CMCTrader import Constants

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD], # or 'GBPUSD'
	# 'START_TIME' : '1:00',
	# 'END_TIME' : '7:55',
	'risk' : 1.0,
	'stoploss' : 17
}
utils = None

reg_sar = None
slow_sar = None
black_sar = None
rsi = None
cci = None
macd = None

pending_entries = []
entered = []
is_init = True

bought = False
sold = False

def init(utilities):
	print("Hello init World!")
	global utils
	global reg_sar, slow_sar, black_sar, rsi, cci, macd

	utils = utilities
	reg_sar = utils.SAR(1)
	black_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	rsi = utils.RSI(4, 1)
	cci = utils.CCI(5, 1)
	macd = utils.MACD(6, 1)

	pending_entries.append('buy')
	entered.append('buy')

def onLoop():
	global bought, sold

	for entry in pending_entries:
		if entry == 'buy' and not bought:
			pos = utils.buy(400, sl = 100)
			pos.quickExit()
			bought = True
		elif not sold:
			pos = utils.sell(400, sl = 200)
			sold = True

def onNewBar():
	print("onNewBar")
	global is_init

	if (is_init):
		pending_entries.append('sell')
		entered.append('sell')
		is_init = False

	print(pending_entries)
	print(entered)
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

def onRecovery():
	print("onRecovery")
	global pending_entries
	pending_entries = []

def onDownTime():
	print("onDownTime")

def failsafe(timestamps):
	print(timestamps)

	