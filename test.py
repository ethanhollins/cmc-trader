from CMCTrader import Constants
import time

VARIABLES = {
	'PAIRS': [Constants.GBPUSD],
	'risk' : 1.0,
	'stoploss' : 17
}



def init(utilities):
	print("Hello init World!")
	global utils
	global sma, inner_mae, outer_mae, limit_mae, short_boll, long_boll, macd, rsi, atr, chart
	
	utils = utilities

	sma = utils.SMA(Constants.GBPUSD, Constants.FOUR_HOURS, 10)
	inner_mae = utils.MAE(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 0.035)
	outer_mae = utils.MAE(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 0.09)
	limit_mae = utils.MAE(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 0.2)
	short_boll = utils.BOLL(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 2.2)
	long_boll = utils.BOLL(Constants.GBPUSD, Constants.FOUR_HOURS, 20, 1.9)
	rsi = utils.RSI(Constants.GBPUSD, Constants.FOUR_HOURS, 10)
	macd = utils.MACD(Constants.GBPUSD, Constants.FOUR_HOURS, 4, 40, 3)
	atr = utils.ATR(Constants.GBPUSD, Constants.FOUR_HOURS, 20)
	chart = utils.getChart(Constants.GBPUSD, Constants.FOUR_HOURS)

	utils.setPositionNetting(False)

	global count
	count = 0

def onLoop():
	global count

	if count == 0 and utils.backtester.isNotBacktesting():

		utils.buy(
			utils.getLotsize(20000, 3.0, 130), 
			pairs = VARIABLES['PAIRS'], 
			sl = 130,
			risk = 3.0
		)

		count += 1

	return

def onNewBar():
	print("onNewBar\n")
	global count, pos, is_live

	# if utils.backtester.isNotBacktesting():
	# 	is_live = True
	

	# if is_live:
	# 	count += 1
	# 	if count == 1:
	# 		pos = utils.buy(400)
	# 	elif count == 2:
	# 		pos.breakeven()
	# 		pos.apply()

		# elif count == 3:
		# 	pos.apply()
		# elif count == 4:
		# 	pos.close()
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