from CMCTrader import Constants
import time

VARIABLES = {
	'risk' : 1.0,
	'stoploss' : 17
}



def init(utilities):
	print("Hello init World!")
	global utils, boll, count, is_live

	utils = utilities

	boll = utils.BOLL(Constants.GBPUSD, Constants.ONE_MINUTE, 20, 2.0)
	count = 0
	is_live = False

def onLoop():
	global count

	# if utils.backtester.isNotBacktesting():
	# 	count += 1
	# 	if count == 1:
	# 		print("do it")
	# 		# local_storage = utils.getLocalStorage()
	# 		# print(local_storage)
	# 		# pos = utils.buy(400)
	# 		local_storage = utils.getLocalStorage()
			
	# 		for pos in local_storage['POSITIONS']:
	# 			pos['data']['hello'] = 'world'

	# 		print(local_storage)
	# 		utils.updateLocalStorage(local_storage)
	# 		# pos.close()

	return

def onNewBar():
	print("onNewBar\n")
	global count, pos, is_live

	if utils.backtester.isNotBacktesting():
		is_live = True
	

	if is_live:
		count += 1
		if count == 1:
			pos = utils.buy(400)
		elif count == 2:
			pos.breakeven()
			pos.apply()

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