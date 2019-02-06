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
	'maximum_bank' : 500,
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
	'SAR' : None,
	'sar_count_min' : 3,
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

current_triggers = []
re_entry_trigger = None

strands = SortedList()

cross_strand_long = None
cross_strand_short = None

entry_pivot = None

pending_entries = []
pending_breakevens = []
pending_exits = []

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
	ENTERED = 2

class Re_Entry_State(Enum):
	ONE = 1
	TWO = 2
	ENTERED = 3

class Entry_Pivot_State(Enum):
	TO_ENTER = 1
	TO_EXIT = 2

class TriggerType(Enum):
	REGULAR = 1
	RE_ENTRY = 2
	CROSS_EXIT = 3
	PIVOT_EXIT = 4

class TimeState(Enum):
	TRADING = 1
	NNT_PROFIT = 2
	NNT = 3
	CLOSE = 4

class ExitType(Enum):
	NONE = 1
	IMMEDIATE = 2
	CROSS = 3

time_state = TimeState.TRADING

class Strand(dict):
	def __init__(self, direction, start):
		self.direction = direction
		self.start = start
		self.end = 0
		self.is_completed = False
		self.count = len(strands)
		self.is_crossed = False
		self.is_valid = False

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class Trigger(dict):
	def __init__(self, direction, start = 0, tradable = True, trigger_type = TriggerType.REGULAR):
		self.direction = direction
		self.start = start
		self.state = State.ONE
		self.tradable = tradable
		self.ret_count = 0
		self.trigger_type = trigger_type
		self.exit_type = ExitType.NONE

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class StopState(Enum):
	NONE = 1
	BREAKEVEN = 2
	FIRST = 3

stop_state = StopState.NONE

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global reg_sar, slow_sar, black_sar, sar, cci, macd, dmi

	utils = utilities
	sar = utils.SAR(1)
	reg_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	black_sar = utils.SAR(4)
	cci = utils.CCI(5, 1)
	macd = utils.MACD(6, 1)
	dmi = utils.DMI(7, 3)	


	# global sar, cci, macd

	# utils = utilities
	# sar = utils.SAR(1)
	# cci = utils.CCI(2, 1)
	# macd = utils.MACD(3, 1)

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
					re_entry_trigger = Trigger(entry.direction, tradable = False, trigger_type = TriggerType.RE_ENTRY)
					re_entry_trigger.state = Re_Entry_State.ONE

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
					re_entry_trigger = Trigger(entry.direction, tradable = False, trigger_type = TriggerType.RE_ENTRY)
					re_entry_trigger.state = Re_Entry_State.ONE

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
					re_entry_trigger = Trigger(entry.direction, tradable = False, trigger_type = TriggerType.RE_ENTRY)
					re_entry_trigger.state = Re_Entry_State.ONE

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
					re_entry_trigger = Trigger(entry.direction, tradable = False, trigger_type = TriggerType.RE_ENTRY)
					re_entry_trigger.state = Re_Entry_State.ONE

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
			pos.breakeven()
			if pos.apply():
				stop_state = StopState.BREAKEVEN
			else:
				pending_breakevens.append(pos)
		
		elif profit >= VARIABLES['first_stop_pips'] and stop_state.value < StopState.FIRST.value:
			print("Reached FIRST STOP point:", str(profit))
			
			pos.modifySL(VARIABLES['first_stop_points'])
			if pos.apply():
				stop_state = StopState.FIRST

		if pos in pending_breakevens:
			if profit > VARIABLES['breakeven_min_pips']:
				if stop_state.value < StopState.BREAKEVEN.value:
					pos.breakeven()
					if pos.apply():
						stop_state = StopState.BREAKEVEN
						del pending_breakevens[pending_breakevens.index(pos)]
				else:
					del pending_breakevens[pending_breakevens.index(pos)]

def handleExits(shift):

	global pending_exits

	is_exit = False

	for exit in pending_exits:

		if exit.exit_type == ExitType.CROSS:
			if isParaConfirmation(shift, exit.direction, reverse = True):
				print("Attempting exit")
				is_exit = True
				for pos in utils.positions:
					pos.quickExit()

		elif exit.exit_type == ExitType.IMMEDIATE:
			for pos in utils.positions:
				pos.quickExit()

	if is_exit:
		pending_exits = []

def onEntry(pos):
	print("onEntry")

	global current_triggers, re_entry_trigger, stop_state
	current_triggers = []
	re_entry_trigger = None

	stop_state = StopState.NONE

def onStopLoss(pos):
	print("onStopLoss")

	global re_entry_trigger

	if stop_state.value <= StopState.BREAKEVEN.value:
		if pos.direction == 'buy':
			re_entry_trigger = Trigger(Direction.LONG, tradable = True, trigger_type = TriggerType.RE_ENTRY)
		elif pos.direction == 'sell':
			re_entry_trigger = Trigger(Direction.SHORT, tradable = True, trigger_type = TriggerType.RE_ENTRY)

		re_entry_trigger.state = Re_Entry_State.ONE

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
				t_exit = Trigger(Direction.LONG, trigger_type = TriggerType.CROSS_EXIT)
				t_exit.exit_type = ExitType.CROSS
				pending_exits.append(t_exit)
			else:
				t_exit = Trigger(Direction.SHORT, trigger_type = TriggerType.CROSS_EXIT)
				t_exit.exit_type = ExitType.CROSS
				pending_exits.append(t_exit)

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

	onTrigger(shift)

	for trigger in current_triggers:
		entrySetup(shift, trigger)

	reEntrySetup(shift, re_entry_trigger)

	entryPivot(shift, entry_pivot)

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''

	if sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		if sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			direction = Direction.SHORT
		else:
			direction = Direction.LONG
		
		if len(strands) > 0:
			strands[0].is_completed = True
			strands[0].end = sar.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
	
		strand = Strand(direction, sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
		strands.append(strand)

		print("New Strand:", str(strand.direction))

def onTrigger(shift):

	if isNumStrands(1):
		isStrandValid(shift)

		long_triggers = [trigger for trigger in current_triggers if trigger.direction == Direction.LONG and trigger.trigger_type == TriggerType.REGULAR]
		short_triggers = [trigger for trigger in current_triggers if trigger.direction == Direction.SHORT and trigger.trigger_type == TriggerType.REGULAR]

		pos_direction = None
		
		if len(utils.positions) > 0:
			pos_direction = utils.positions[0].direction


		if pos_direction == None:
			if isNumValidStrands(2, Direction.LONG):
				if len(long_triggers) <= 0:
					t = Trigger(Direction.LONG, tradable = True)
					current_triggers.append(t)

				getCrossStrand(Direction.LONG)

			if isNumValidStrands(2, Direction.SHORT):
				if len(short_triggers) <= 0:
					t = Trigger(Direction.SHORT, tradable = True)
					current_triggers.append(t)

				getCrossStrand(Direction.SHORT)

		elif pos_direction == 'buy':
			if isNumValidStrands(2, Direction.SHORT):
				if len(short_triggers) <= 0:
					t = Trigger(Direction.SHORT, tradable = True)
					current_triggers.append(t)

				getCrossStrand(Direction.SHORT)

		else:
			if isNumValidStrands(2, Direction.LONG):
				if len(long_triggers) <= 0:
					t = Trigger(Direction.LONG, tradable = True)
					current_triggers.append(t)

				getCrossStrand(Direction.LONG)

	print("Cross strand long:", str(cross_strand_long))
	print("Cross strand short:", str(cross_strand_short))

def getLongTrigger():
	for trigger in current_triggers:
		if trigger.direction == Direction.LONG:
			return trigger

def getShortTrigger():
	for trigger in current_triggers:
		if trigger.direction == Direction.SHORT:
			return trigger

def isNumStrands(count):
	return len(strands) >= count

def isNumValidStrands(count, direction):
	return len([i for i in strands if i.is_valid and i.direction == direction]) >= count

def isStrandValid(shift):
	if not strands[0].is_valid and sar.strandCount(VARIABLES['TICKETS'][0], shift) >= VARIABLES['sar_count_min']:
		strands[0].is_valid = True

def getCrossStrand(direction):

	global cross_strand_long, cross_strand_short

	direction_strands = [strand for strand in strands.getSorted() if strand.direction == direction and strand.is_valid][:2]

	if len(direction_strands) >= 2:
		if direction == Direction.LONG:
			if direction_strands[0].start >= direction_strands[1].start:
				
				if isTriggerRetValid(Direction.LONG, direction_strands[0]):
					cross_strand_long = direction_strands[0]
			
			else:

				if isTriggerRetValid(Direction.LONG, direction_strands[1]):
					cross_strand_long = direction_strands[1]

		else:
			if direction_strands[0].start <= direction_strands[1].start:

				if isTriggerRetValid(Direction.SHORT, direction_strands[0]):
					cross_strand_short = direction_strands[0]

			else:
				
				if isTriggerRetValid(Direction.SHORT, direction_strands[1]):
					cross_strand_short = direction_strands[1]

	elif len(direction_strands) >= 1:
		if direction == Direction.LONG:
			cross_strand_long = direction_strands[0]
		else:
			cross_strand_short = direction_strands[0]

def isTriggerRetValid(direction, strand):

	if direction == Direction.LONG:
		if cross_strand_long and not strand == cross_strand_long:
			if cross_strand_long.start < strand.start:
				if getLongTrigger().ret_count >= 1:
					print("ret not valid")
					return False
				else:
					getLongTrigger().ret_count += 1
			else:
				getLongTrigger().ret_count = 0
				return True
	else:
		if cross_strand_short and not strand == cross_strand_short:
			if cross_strand_short.start > strand.start:
				if getShortTrigger().ret_count >= 1:
					print("ret not valid")
					return False
				else:
					getShortTrigger().ret_count += 1

			else:
				getShortTrigger().ret_count = 0
				return True

	return True

def entrySetup(shift, trigger):
	''' Checks for swing sequence once trigger has been formed '''

	if not trigger == None and trigger.tradable:

		if trigger.state == State.ONE:
			if triggerConf(shift, trigger.direction):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)

def reEntrySetup(shift, trigger):

	if not trigger == None and trigger.tradable and not trigger.state == State.ENTERED:
		if trigger.state == Re_Entry_State.ONE:
			if reEntryInitConf(shift, trigger.direction):
				trigger.state = Re_Entry_State.TWO
				reEntrySetup(shift, trigger)

		if trigger.state == Re_Entry_State.TWO:
			if triggerConf(shift, trigger.direction, is_re_entry = True):
				trigger.state = Re_Entry_State.ENTERED
				confirmation(shift, trigger)

def entryPivot(shift, trigger):

	global entry_pivot

	print("Entry Pivot:\n ", str(trigger))

	if not trigger == None and trigger.tradable and not trigger.state == State.ENTERED:

		if not isEntryPivotValid(shift, trigger):
			entry_pivot = None
			return

		if trigger.state == Entry_Pivot_State.TO_ENTER:
			if entryPivotEnter(shift, trigger):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)

		elif trigger.state == Entry_Pivot_State.TO_EXIT:
			if entryPivotExit(shift, trigger):
				trigger.state = State.ENTERED
				trigger.exit_type = ExitType.IMMEDIATE
				pending_exits.append(trigger)


def triggerConf(shift, direction, is_re_entry = False):
	print("---Direction:", str(direction))

	if isStrandCrossed(shift, direction) or is_re_entry:
		print("Strand is crossed.")
		print("Conf:", str(isParaConfirmation(shift, direction)), str(isMacdConfirmation(shift, direction)), str(isCciBiasConfirmation(shift, direction)))
		if isParaConfirmation(shift, direction) and isMacdConfirmation(shift, direction) and isCciBiasConfirmation(shift, direction):
			print("Trigger is confirmed")
			return True

	return False

def reEntryInitConf(shift, direction):
	if isParaConfirmation(shift, direction, reverse = True):
		return True

	return False

def entryPivotEnter(shift, trigger):

	sar_val = sar.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if trigger.direction == Direction.LONG:
		if sar_val > trigger.start and sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			return True

	else: 
		if sar_val < trigger.start and sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]:
			return True

def entryPivotExit(shift, trigger):

	sar_val = sar.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if trigger.direction == Direction.LONG:
		if sar_val < trigger.start and sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]:
			return True

	else: 
		if sar_val > trigger.start and sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			return True

	return False

def isEntryPivotValid(shift, trigger):

	if trigger.direction == Direction.LONG:
		if strands[0].start < trigger.start and strands[0].direction == Direction.LONG:
			return False

	else:
		if strands[0].start > trigger.start and strands[0].direction == Direction.SHORT:
			return False
			
	return True

def isStrandCrossed(shift, direction):

	sar_val = sar.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	print("sar val:", str(sar_val))

	if direction == Direction.LONG and cross_strand_long:
		if sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			if sar_val > cross_strand_long.start:
				return True

	elif direction == Direction.SHORT and cross_strand_short:
		if sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]:
			if sar_val < cross_strand_short.start:
				return True

	return False

def isParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.SHORT:
			return sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
		else:
			return sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			print("long:", str(sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]))
			return sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
		else:
			print("short:", str(sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]))
			return sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def isMacdConfirmation(shift, direction):

	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	print("hist:", str(hist))

	if direction == Direction.LONG:
		return hist >= VARIABLES['macd_threshold'] * 0.00001
	else:
		return hist <= -VARIABLES['macd_threshold'] * 0.00001

def isCciBiasConfirmation(shift, direction):
	
	last_chidx = cci.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0][0]
	chidx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	print(str(last_chidx), str(chidx))

	if direction == Direction.LONG:
		if chidx > last_chidx:
			return True
	else:
		if chidx < last_chidx:
			return True

	return False

def confirmation(shift, trigger):
	''' Checks for overbought, oversold and confirm entry '''

	print("confirmation")
	
	global entry_pivot
	
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	if not trigger.trigger_type == TriggerType.PIVOT_EXIT:
		entry_pivot = Trigger(trigger.direction, start = close, trigger_type = TriggerType.PIVOT_EXIT)

	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	for trigger in current_triggers:
		print("CURRENT TRIGGER:\n ", str(trigger))

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
