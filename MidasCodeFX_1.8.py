from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime
import types
import copy

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	'START_TIME' : '0:30',
	'END_TIME' : '19:00',
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'maximum_risk' : 4,
	'profit_limit' : 51,
	'maximum_bank' : 1000,
	'PLAN' : None,
	'stoprange' : 17,
	'breakeven_point' : 34,
	'first_stop_pips' : 50,
	'first_stop_points' : -17,
	'full_profit' : 200,
	'rounding' : 100,
	'breakeven_min_pips' : 3,
	'CLOSING SEQUENCE' : None,
	'no_more_trades_in_profit' : '16:00',
	'no_more_trades' : '18:00',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5,
	'CONFIRMATION' : None,
	'strand_size' : 22,
	'MACD' : None,
	'macd_threshold' : 2,
	'CCI' : None,
	'cci_threshold' : 0,
}

class SortedList(list):
	def __getitem__(self, row):
		return sorted(list(self), key=lambda x: x.count, reverse = True)[row]

	def getSorted(self):
		return sorted(list(self), key=lambda x: x.count, reverse = True)

current_trigger = None
re_entry_trigger = None

strands = SortedList()

cross_strand_long = None
cross_strand_short = None

pending_entries = []
pending_breakevens = []
pending_exits = []

current_brown = None

current_news = None
news_trade_block = False

stop_trading = False
no_new_trades = False

bank = 0

class Direction(Enum):
	LONG = 1
	SHORT = 2

class State(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	ENTERED = 4

class TimeState(Enum):
	TRADING = 1
	NNT_PROFIT = 2
	NNT = 3
	CLOSE = 4

time_state = TimeState.TRADING

class Strand(dict):
	def __init__(self, direction, start):
		self.direction = direction
		self.start = start
		self.end = 0
		self.is_completed = False
		self.count = len(strands)
		self.is_hit = False

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class Trigger(dict):
	def __init__(self, direction, tradable = True, is_regular = True):
		self.direction = direction
		self.state = State.ONE
		self.tradable = tradable
		self.is_regular = is_regular
		self.one_cci_conf = False
		self.one_macd_conf = False
		self.final_conf = False

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class HitStrand(dict):
	def __init__(self, shift, hit_val = 0):
		self.num_points = 2

		if hit_val == 0:
			self.to_hit = self.getToHit(shift)
		else:
			self.to_hit = hit_val

		self.is_hit = False
	
	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

	def getToHit(self, shift):
		for i in range(self.num_points):
			current_shift = shift + i
			if (brown_sar.isNewCycle(VARIABLES['TICKETS'][0], current_shift)):

				print("Brown sar:", str(brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]))
				return brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]

		print("Brown sar end:", str(brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]))
		return brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]

class StopState(Enum):
	NONE = 1
	BREAKEVEN = 2
	FIRST = 3

stop_state = StopState.NONE

def init(utilities):
	''' Initialize utilities and indicators '''

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

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	global bank, stop_trading, no_new_trades
	global is_profit_nnt, is_nnt, is_be

	if utils.getBankSize() > VARIABLES['maximum_bank']:
		bank = VARIABLES['maximum_bank']
	else:
		bank = utils.getBankSize()
	print("Starting Bank:", str(bank))

	stop_trading = False
	no_new_trades = False

	is_profit_nnt = False
	is_nnt = False
	is_be = False

def onFinishTrading():
	''' Function called on trade end time '''

	print("onFinishTrading")

	print("Total PIPS gain:", str(utils.getTotalProfit()))

def onNewBar():
	''' Function called on every new bar '''

	print("\nonNewBar")
	checkTime()

	utils.printTime(utils.getAustralianTime())

	runSequence(0)
	handleExits(0)

	report()

def onDownTime():
	''' Function called outside of trading time '''

	print("onDownTime")
	ausTime = utils.printTime(utils.getAustralianTime())

	report()

def onLoop():
	''' Function called on every program iteration '''

	if no_new_trades and len(utils.positions) <= 0:
		global stop_trading
		stop_trading = True

	if stop_trading:
		return

	handleEntries()		# Handle all pending entries
	handleStop()	# Handle all stop modifications

def handleEntries():
	''' Handle all pending entries '''

	global no_new_trades

	for entry in pending_entries:
		
		if entry.direction == Direction.LONG:
			
			if len(utils.positions) > 0:
				for pos in utils.positions:
					if pos.direction == 'buy':
						del pending_entries[pending_entries.index(entry)]
						return
				
				if no_new_trades:
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
				elif news_trade_block:
					print("Trade blocked on NEWS! Re-entry trigger activated.")
					re_entry_trigger = Trigger(entry.direction, tradable = False, is_regular = False)

					pos.quickExit()

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: stop and reverse")
					handleStopAndReverse(pos, entry)

			else:

				if no_new_trades:
					print("Trade blocked! Current position exited.")

					del pending_entries[pending_entries.index(entry)]
				elif news_trade_block:
					print("Trade blocked on NEWS! Re-entry trigger activated.")
					re_entry_trigger = Trigger(entry.direction, tradable = False, is_regular = False)

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: regular")
					handleRegularEntry(entry)

		else:

			if len(utils.positions) > 0:
				for pos in utils.positions:
					if (pos.direction == 'sell'):
						del pending_entries[pending_entries.index(entry)]
						return
				
				if no_new_trades:
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
				elif news_trade_block:
					print("Trade blocked on NEWS! Re-entry trigger activated.")
					re_entry_trigger = Trigger(entry.direction, tradable = False, is_regular = False)

					pos.quickExit()

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter short: stop and reverse")
					handleStopAndReverse(pos, entry)
			else:

				if no_new_trades:
					print("Trade blocked!")
					del pending_entries[pending_entries.index(entry)]
				elif news_trade_block:
					print("Trade blocked on NEWS! Re-entry trigger activated.")
					re_entry_trigger = Trigger(entry.direction, tradable = False, is_regular = False)

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter short: regular")
					handleRegularEntry(entry)

def handleStopAndReverse(pos, entry):
	''' 
	Handle stop and reverse entries 
	and check if tradable conditions are met.
	'''
	if pos.direction == 'buy':
		current_profit = utils.getTotalProfit() + pos.getProfit(price_type = 'h')
	else:
		current_profit = utils.getTotalProfit() + pos.getProfit(price_type = 'l')

	loss_limit = -VARIABLES['stoprange'] * VARIABLES['maximum_risk']
	
	if current_profit < loss_limit or current_profit > VARIABLES['profit_limit']:
		print("Tradable conditions not met:", str(current_profit))
		pos.quickExit()
		stop_trading = True
	else:
		print("Entered")
		pos.stopAndReverse(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])

	del pending_entries[pending_entries.index(entry)]

def handleRegularEntry(entry):
	''' 
	Handle regular entries 
	and check if tradable conditions are met.
	'''
	current_profit = utils.getTotalProfit()

	loss_limit = -VARIABLES['stoprange'] * VARIABLES['maximum_risk']

	if current_profit < loss_limit or current_profit > VARIABLES['profit_limit']:
		print("Tradable conditions not met:", str(current_profit))
		stop_trading = True
	else:
		print("Entered")
		if entry.direction == Direction.LONG:
			utils.buy(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		else:
			utils.sell(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		
	del pending_entries[pending_entries.index(entry)]

def handleStop():
	''' 
	Handle all pending breakevens
	and positions that have exceeded breakeven threshold
	'''

	global stop_state

	for pos in utils.positions:
		
		if pos.direction == 'buy':
			profit = utils.getTotalProfit() + pos.getProfit(price_type = 'h')
		else:
			profit = utils.getTotalProfit() + pos.getProfit(price_type = 'l')

		if profit >= VARIABLES['breakeven_point'] and stop_state.value < StopState.BREAKEVEN.value:
			print("Reached BREAKEVEN point:", str(profit))
			stop_state = StopState.BREAKEVEN
			pos.breakeven()
			if not pos.apply():
				pending_breakevens.append(pos)
		
		elif profit >= VARIABLES['first_stop_pips'] and stop_state.value < StopState.FIRST.value:
			print("Reached FIRST STOP point:", str(profit))
			
			pos.modifySL(VARIABLES['first_stop_points'])
			if pos.apply():
				stop_state = StopState.FIRST

		if pos in pending_breakevens:
			if profit > VARIABLES['breakeven_min_pips']:
				pos.breakeven()
				if pos.apply():
					stop_state = StopState.BREAKEVEN
					del pending_breakevens[pending_breakevens.index(pos)]

def handleExits(shift):

	global pending_exits

	is_exit = False

	for exit in pending_exits:

		if exit.direction == Direction.LONG:
			if isBrownParaConfirmation(shift, Direction.LONG, reverse = True):
				print("Attempting exit")
				is_exit = True
				for pos in utils.positions:
					pos.quickExit()

		else:
			if isBrownParaConfirmation(shift, Direction.SHORT, reverse = True):
				print("Attempting exit")
				
				is_exit = True
				for pos in utils.positions:
					pos.quickExit()

	if is_exit:
		pending_exits = []

def onEntry(pos):
	print("onEntry")

	global current_trigger, re_entry_trigger, stop_state

	current_trigger = None
	re_entry_trigger = None

	stop_state = StopState.NONE

def onStopLoss(pos):
	print("onStopLoss")

	global re_entry_trigger

	if stop_state == StopState.BREAKEVEN:
		if pos.direction == 'buy' and strands[0].direction == Direction.SHORT:
			re_entry_trigger = Trigger(Direction.LONG, tradable = True, is_regular = False)
		elif pos.direction == 'sell' and strands[0].direction == Direction.LONG:
			re_entry_trigger = Trigger(Direction.SHORT, tradable = True, is_regular = False)
	
	else:
		if pos.direction == 'buy' and strands[0].direction == Direction.SHORT:
			re_entry_trigger = Trigger(Direction.LONG, tradable = True, is_regular = False)
		elif pos.direction == 'sell' and strands[0].direction == Direction.LONG:
			re_entry_trigger = Trigger(Direction.SHORT, tradable = True, is_regular = False)

		re_entry_trigger.state = State.TWO

def onNews(title, time):
	''' 
	Block new trades 
	and set current position to breakeven on news.
	'''

	global current_news

	print("NEWS:", str(title))
	start_no_trade_time = time - datetime.timedelta(minutes = VARIABLES['time_threshold_no_trades'])
	end_no_trade_time = start_no_trade_time + datetime.timedelta(minutes = 1)
	be_time = time - datetime.timedelta(minutes = VARIABLES['time_threshold_breakeven'])
	
	if be_time <= utils.getLondonTime() < time and stop_state.value < StopState.BREAKEVEN.value:
		print(str(title), "done")
		for pos in utils.positions:
			if not pos in pending_breakevens:
				print(str(time), "current pos to breakeven on NEWS")
				pending_breakevens.append(pos)
	
	if no_trade_time <= utils.getLondonTime() <= end_no_trade_time:
		print("no trades, 5 mins")
		current_news = time
	
	elif utils.getLondonTime() > end_no_trade_time:
		if (current_news == time):
			print("reset current news")
			current_news = None
		if (title.startswith('_')):
			del utils.newsTimes[title]

	checkCurrentNews()

def checkCurrentNews():
	''' Block new trades if there is news currently in action '''

	global news_trade_block

	if not current_news == None:
		news_trade_block = True
	else:
		news_trade_block = False
		if not re_entry_trigger == None and not re_entry_trigger.tradable:
			re_entry_trigger.tradable = True

def checkTime():
	''' 
	Checks current time and initiates 
	closing sequence where necessary.
	'''

	global time_state, no_new_trades

	london_time = utils.getLondonTime()
	parts = VARIABLES['no_more_trades_in_profit'].split(':')
	profit_nnt_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['no_more_trades'].split(':')
	nnt_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)

	if not (london_time.hour < utils.endTime.hour and london_time.hour >= 0):
		profit_nnt_time += datetime.timedelta(days=1)
		nnt_time += datetime.timedelta(days=1)

	print(str(london_time), str(utils.endTime))

	if london_time > utils.endTime and time_state.value < TimeState.CLOSE.value:
		time_state = TimeState.CLOSE

		print("End time: looking to exit")
		for pos in utils.positions:
			if pos.direction == 'buy':
				pending_exits.append(Trigger(Direction.LONG, 0))
			else:
				pending_exits.append(Trigger(Direction.SHORT, 0))

	elif london_time > nnt_time and time_state.value < TimeState.NNT.value:
		print("No more trades")
		time_state = TimeState.NNT
		no_new_trades = True
	
	elif london_time > profit_nnt_time and time_state.value < TimeState.NNT_PROFIT.value:
		print("No more trades in profit")
		print("Total profit:", str(utils.getTotalProfit()))
		if utils.getTotalProfit() >= VARIABLES['breakeven_point']:
			time_state = TimeState.NNT_PROFIT
			no_new_trades = True


def runSequence(shift):
	''' Main trade plan sequence '''
	onNewCycle(shift)

	if (isCompletedStrand()):
		onTrigger(shift)

	entrySetup(shift, current_trigger)
	reEntrySetup(shift, re_entry_trigger)

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''
	
	global current_brown

	if black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		if black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			direction = Direction.SHORT
		else:
			direction = Direction.LONG
		
		if len(strands) > 0:
			strands[0].is_completed = True
			strands[0].end = black_sar.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
	
		strand = Strand(direction, black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
		strands.append(strand)

		print("New Strand:", str(strand.direction))

	if brown_sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		current_brown = HitStrand(shift + 1)

def onTrigger(shift):

	global current_trigger, re_entry_trigger

	if black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		if black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			current_trigger = Trigger(Direction.LONG, is_regular = True)

			if not re_entry_trigger == None and re_entry_trigger.direction == Direction.SHORT:
				re_entry_trigger = None

		else:
			current_trigger = Trigger(Direction.SHORT, is_regular = True)

			if not re_entry_trigger == None and re_entry_trigger.direction == Direction.LONG:
				re_entry_trigger = None

def isCompletedStrand():
	for strand in strands:
		if strand.is_completed:
			return True

	return False

def entrySetup(shift, trigger):
	''' Checks for swing sequence once trigger has been formed '''

	if not trigger == None and trigger.tradable:

		if trigger.state == State.ONE:
			if stateOneConf(shift, trigger.direction):
				trigger.state = State.TWO
				entrySetup(shift, trigger)

		if trigger.state == State.TWO:
			if stateTwoConf(shift, trigger):
				trigger.state = State.THREE
				entrySetup(shift, trigger)

		elif trigger.state == State.THREE:
			if finalConf(shift, trigger):
				trigger.state = State.ENTERED
				confirmation(trigger)

def reEntrySetup(shift, trigger):

	if not trigger == None and trigger.tradable and not trigger.state == State.ENTERED:
		if isBrownParaConfirmation(shift, trigger.direction):
			trigger.state = State.ENTERED
			confirmation(trigger)

def stateOneConf(shift, direction):
	if isBrownParaConfirmation(shift, direction, reverse = True):
		return True

	return False

def stateTwoConf(shift, trigger):

	brownHit(shift, trigger.direction)

	if isBrownParaConfirmation(shift, trigger.direction, reverse = True):

		if trigger.direction == Direction.LONG:
			if isCciBiasConfirmation(shift, Direction.SHORT) and isCciCtCrossConfirmation(shift, Direction.SHORT):
				trigger.one_cci_conf = True
		else:
			if isCciBiasConfirmation(shift, Direction.LONG) and isCciCtCrossConfirmation(shift, Direction.LONG):
				trigger.one_cci_conf = True

		if isMacdRetConfirmation(shift, trigger.direction):
			trigger.one_macd_conf = True

		if trigger.one_cci_conf and trigger.one_macd_conf and current_brown.is_hit:
			current_brown.is_hit = False
			return True

	else:
		trigger.one_cci_conf = False
		trigger.one_macd_conf = False

	return False

def finalConf(shift, trigger):

	brownHit(shift, trigger.direction)

	if isRegParaConfirmation(shift, trigger.direction) and isSlowParaConfirmation(shift, trigger.direction) and isBrownParaConfirmation(shift, trigger.direction):
		if current_brown.is_hit and isMacdConfirmation(shift, trigger.direction) and isDmiConfirmation(shift, trigger.direction):
			trigger.final_conf = True
	else:
		trigger.final_conf = False

	if trigger.final_conf:
		if isCciBiasConfirmation(shift, trigger.direction):
			return True

	return False

def brownHit(shift, direction):

	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if (direction == Direction.LONG):
		if (high > current_brown.to_hit):
			current_brown.is_hit = True

	else:
		if (low < current_brown.to_hit):
			current_brown.is_hit = True

def isBrownParaConfirmation(shift, direction, reverse = False):
	if reverse:
		if direction == Direction.SHORT:
			return brown_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
		else:
			return brown_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return brown_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
		else:
			return brown_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def isSlowParaConfirmation(shift, direction):

	if direction == Direction.LONG:
		return slow_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
	else:
		return slow_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def isRegParaConfirmation(shift, direction):

	if direction == Direction.LONG:
		return reg_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
	else:
		return reg_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def isMacdRetConfirmation(shift, direction):

	last_hist = macd.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0][0]
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		return hist < last_hist
	else:
		return hist > last_hist

def isMacdConfirmation(shift, direction):

	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		return hist >= VARIABLES['macd_threshold'] * 0.00001
	else:
		return hist <= -VARIABLES['macd_threshold'] * 0.00001

def isCciBiasConfirmation(shift, direction):
	
	last_chidx = cci.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0][0]
	chidx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		if chidx > last_chidx:
			return True
	else:
		if chidx < last_chidx:
			return True

	return False

def isCciCtCrossConfirmation(shift, direction):
	chidx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		if chidx > VARIABLES['cci_threshold']:
			return True
	else:
		if chidx < -VARIABLES['cci_threshold']:
			return True

	return False

def isDmiConfirmation(shift, direction):
	plus, minus, adx = dmi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if direction == Direction.LONG:
		return plus > minus
	else:
		return minus > plus

def confirmation(trigger):
	''' Checks for overbought, oversold and confirm entry '''

	print("confirmation")

	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	print("CURRENT TRIGGER:\n ", str(current_trigger))

	if not re_entry_trigger == None:
		print("RE-ENTRY TRIGGER:\n ", str(re_entry_trigger))

	print("CLOSED POSITIONS:")
	count = 0
	for pos in utils.closedPositions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit(price_type = 'c'))

	print("ORDERS:")
	count = 0
	for order in utils.orders:
		count += 1
		print(str(count) + ":", str(order.direction), str(order.entryprice))

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit(price_type = 'c'))

	print("--|\n")
