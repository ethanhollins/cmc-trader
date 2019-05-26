from CMCTrader import Constants
import time

VARIABLES = {
	'START_TIME' : '20:00',
	'END_TIME' : '00:00',
	'risk' : 1.0,
	'stoploss' : 17
}



def init(utilities):
	print("Hello init World!")
	global utils

	utils = utilities

	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)

def onLoop():
	return

def onNewBar():
	print("onNewBar\n")

	# utils.buy(400)
	# pos_one = utils.sell(400)
	# print(utils.positions)
	# pos_two = utils.buy(400)
	# print(utils.positions)

	# pos_two.close()
	# print(utils.positions)

	# pos_one.modifyTP(100)

	# pos_one.apply()
	# 	pos.modifyTP(20)
	# 	pos.modifySL(20)
	# 	pos.apply()
	# elif count == 4:
	# 	newPos = pos.stopAndReverse(500, sl = 30, tp = 25)
	# 	newPos.removeTP()

def onDownTime():
	print("onDownTime")