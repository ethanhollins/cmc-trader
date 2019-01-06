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
	'FIXED_SL' : 17,
	'FIXED_TP' : 200,
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'maximum_risk' : 1.5,
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
	'set_breakeven' : '15:50',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5,
	'CONFIRMATION' : None,
	'strand_size' : 22,
	'DMI' : None,
	'dmi_t_threshold' : 24,
	'dmi_ct_threshold' : 18,
	'dmi_spread' : 10
}

class SortedList(list):
	def __getitem__(self, row):
		return sorted(list(self), key=lambda x: x.count, reverse = True)[row]

	def getSorted(self):
		return sorted(list(self), key=lambda x: x.count, reverse = True)

current_triggers = SortedList()
re_entry_trigger = None
momentum_trigger = None

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

is_profit_nnt = False
is_nnt = False
is_be = False
is_end_time = False

bank = 0

class Direction(Enum):
	LONG = 1
	SHORT = 2

class State(Enum):
	SWING_ONE = 1
	HIT_PARA = 3
	ENTERED = 4

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
	def __init__(self, direction, start, tradable = False, is_regular = True):
		self.direction = direction
		self.start = start
		self.state = State.SWING_ONE
		self.tradable = tradable
		self.is_regular = is_regular
		self.is_size_validated = False
		self.delete = False

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

	if stop_trading:
		onDownTime()
		return

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
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_regular = False)
					re_entry_trigger.state = State.SWING_ONE

					pos.quickExit()

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: stop and reverse")
					handleStopAndReverse(pos, entry)

			else:

				if no_new_trades:
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
				elif news_trade_block:
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_regular = False)
					re_entry_trigger.state = State.SWING_ONE

					pos.quickExit()

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
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_regular = False)
					re_entry_trigger.state = State.SWING_ONE

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
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_regular = False)
					re_entry_trigger.state = State.SWING_ONE

					pos.quickExit()

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter short: regular")
					handleRegularEntry(entry)

@Backtester.skip_on_recover
def handleStopAndReverse(pos, entry):
	''' 
	Handle stop and reverse entries 
	and check if tradable conditions are met.
	'''

	current_profit = utils.getTotalProfit() + pos.getProfit()
	loss_limit = -VARIABLES['stoprange'] * VARIABLES['maximum_risk']
	
	if current_profit < loss_limit or current_profit > VARIABLES['profit_limit']:
		print("Tradable conditions not met:", str(current_profit))
		pos.quickExit()
		stop_trading = True
	else:
		print("Entered")
		pos.stopAndReverse(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])

	del pending_entries[pending_entries.index(entry)]

@Backtester.skip_on_recover
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

@Backtester.skip_on_recover
def handleStop():
	''' 
	Handle all pending breakevens
	and positions that have exceeded breakeven threshold
	'''

	global stop_state

	for pos in utils.positions:
		
		if pos.getProfit() >= VARIABLES['breakeven_point'] and stop_state.value < StopState.BREAKEVEN.value:
			print("Reached BREAKEVEN point:", str(pos.getProfit()))
			stop_state = StopState.BREAKEVEN
			pos.breakeven()
			if not pos.apply():
				pending_breakevens.append(pos)
		
		elif pos.getProfit() >= VARIABLES['first_stop_pips'] and stop_state.value < StopState.FIRST.value:
			print("Reached FIRST STOP point:", str(pos.getProfit()))
			
			pos.modifySL(VARIABLES['first_stop_points'])
			if pos.apply():
				stop_state = StopState.FIRST

		if pos in pending_breakevens:
			if pos.getProfit() > VARIABLES['breakeven_min_pips']:
				pos.breakeven()
				if pos.apply():
					stop_state = StopState.BREAKEVEN
					del pending_breakevens[pending_breakevens.index(pos)]

@Backtester.skip_on_recover
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

	global current_triggers, re_entry_trigger, cross_strand_long, cross_strand_short, stop_state

	current_triggers = []
	re_entry_trigger = None

	cross_strand_long = None
	cross_strand_short = None

	stop_state = StopState.NONE

def onStopLoss(pos):
	print("onStopLoss")

	global re_entry_trigger

	if stop_state == StopState.BREAKEVEN:
		
		if pos.direction == 'buy':
			re_entry_trigger = Trigger(Direction.LONG, 0, tradable = True, is_regular = False)
			re_entry_trigger.state = State.SWING_ONE
		else:
			re_entry_trigger = Trigger(Direction.SHORT, 0, tradable = True, is_regular = False)
			re_entry_trigger.state = State.SWING_ONE

def onNews(title, time):
	''' 
	Block new trades 
	and set current position to breakeven on news.
	'''

	global current_news

	print("NEWS:", str(title))
	be_time = time - datetime.timedelta(minutes = VARIABLES['time_threshold_no_trades'])
	no_trade_time = time - datetime.timedelta(minutes = VARIABLES['time_threshold_no_trades'])
	
	if be_time <= utils.getLondonTime() < time and stop_state.value < StopState.BREAKEVEN.value:
		print(str(title), "done")
		for pos in utils.positions:
			if not pos in pending_breakevens:
				print(str(time), "current pos to breakeven on NEWS")
				pending_breakevens.append(pos)
	
	if no_trade_time <= utils.getLondonTime() < time + datetime.timedelta(minutes = 1):
		print("no trades, 5 mins")
		current_news = time
	
	elif utils.getLondonTime() > time:
		if (current_news == time):
			print("reset current news")
			current_news = None
		if (title.startswith('_')):
			del utils.newsTimes[title]

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

	global is_profit_nnt, is_nnt, is_be, is_end_time, no_new_trades

	london_time = utils.getLondonTime()
	parts = VARIABLES['no_more_trades_in_profit'].split(':')
	profit_nnt_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['no_more_trades'].split(':')
	nnt_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['set_breakeven'].split(':')
	be_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)

	if london_time.hour < utils.endTime.hour and london_time.hour >= 0:
		pass
	else:
		profit_nnt_time += datetime.timedelta(days=1)
		nnt_time += datetime.timedelta(days=1)
		be_time += datetime.timedelta(days=1)

	print(str(london_time), str(utils.endTime))
	if london_time > utils.endTime and not is_end_time:
		is_endTime = True
		print("End time: looking to exit")
		for pos in utils.positions:
			if pos.direction == 'buy':
				pending_exits.append(Trigger(Direction.LONG, 0))
			else:
				pending_exits.append(Trigger(Direction.SHORT, 0))

	elif london_time > nnt_time and not is_nnt and not is_end_time:
		print("No more trades")
		no_new_trades = True
		is_nnt = True
	
	elif london_time > profit_nnt_time and not is_profit_nnt and not is_nnt and not is_end_time:
		print("No more trades in profit")
		print("Total profit:", str(utils.getTotalProfit()))
		if utils.getTotalProfit() >= VARIABLES['breakeven_point']:
			is_profit_nnt = True
			no_new_trades = True


def runSequence(shift):
	''' Main trade plan sequence '''
	onSlowCross(shift)

	onNewCycle(shift)

	if (isCompletedStrand()):
		getTrigger(shift)

	for trigger in current_triggers:
		entrySetup(shift, trigger)

	for trigger in current_triggers.copy():
		if trigger.delete:
			print("DELETED IT IN SEQUENCE")
			del current_triggers[current_triggers.index(trigger)]

	entrySetup(shift, re_entry_trigger, no_conf = True)

	momentumSetup(shift, momentum_trigger)

def getTrigger(shift):
	''' Form trigger in direction of black cross '''

	print("GET TRIGGER")

	if black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		print("NEW TRIGGER")

		if black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			direction = Direction.LONG
			setCurrentTrigger(direction)

		elif black_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]:
			direction = Direction.SHORT
			setCurrentTrigger(direction)

def setCurrentTrigger(direction):

	start = getLastStrandStart(direction)

	trigger = Trigger(direction, start)
	print(trigger)

	current_triggers.append(trigger)

	return trigger

def triggerExists(direction):
	return len([i for i in current_triggers if i.direction == direction]) > 0

def getLastStrandStart(direction):
	for strand in strands.getSorted():
		if strand.direction == direction:
			return strand.start

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''
	
	global cross_strand_long, cross_strand_short, current_brown

	if black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		if black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			direction = Direction.SHORT
		else:
			direction = Direction.LONG
		
		if len(strands) > 0:

			print(strands[0])

			strands[0].is_completed = True
			strands[0].end = black_sar.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]

			if strands[0].direction == Direction.LONG:
				print("this1")
				if cross_strand_long == None or strands[0].end < cross_strand_long:
					print("cross long")
					cross_strand_long = strands[0].end
			else:
				print("this2")
				if cross_strand_short == None or strands[0].end > cross_strand_short:
					print("cross short")
					cross_strand_short = strands[0].end
	
		strand = Strand(direction, black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
		strands.append(strand)

		print("New Strand:", str(strand.direction), str(strand.start))

	if brown_sar.isNewCycle(VARIABLES['TICKETS'][0], shift):

		current_brown = HitStrand(shift + 1)

	for trigger in current_triggers:
		if not trigger.is_size_validated and not trigger.direction == strands[0].direction:
			trigger.is_size_validated = True
			

def onSlowCross(shift):

	global cross_strand_long, cross_strand_short

	if hasSlowCrossed(shift, Direction.LONG):

		for trigger in current_triggers:

			if trigger.direction == Direction.LONG:
				trigger.tradable = True

			elif trigger.direction == Direction.SHORT:
				trigger.delete = True


		trigger = Trigger(Direction.LONG, 0)
		momentum_trigger = trigger

		cross_strand_long = None
		cross_strand_short = None

	if hasSlowCrossed(shift, Direction.SHORT):
		for trigger in current_triggers:

			if trigger.direction == Direction.SHORT:
				trigger.tradable = True

			if trigger.direction == Direction.LONG:
				trigger.delete = True
		
		trigger = Trigger(Direction.SHORT, 0)
		momentum_trigger = trigger

		cross_strand_long = None
		cross_strand_short = None

	for trigger in current_triggers:
		del current_triggers[current_triggers.index(trigger)]

def isCompletedStrand():
	for strand in strands:
		if strand.is_completed:
			return True

	return False

def hasCrossedBelow(shift, item):
	''' Check if black sar has passed the current max strand on falling black '''
	
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if low < item.start:
		print("has crossed below")
		return True

	return False

def hasCrossedAbove(shift, item):
	''' Check if black sar has passed the current min strand on rising black '''

	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]

	if high > item.start:
		print("has crossed above")
		return True

	return False

def hasSlowCrossed(shift, direction):

	print(str(cross_strand_long), str(cross_strand_short))

	slow_val = slow_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if direction == Direction.LONG and not cross_strand_long == None:
		print("long")
		if slow_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]:
			print("1")
			if slow_val > cross_strand_long:
				print("2")
				return True

	elif direction == Direction.SHORT and not cross_strand_short == None:
		print("short")
		if slow_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]:
			print("1")
			if slow_val < cross_strand_short:
				print("2")
				return True

	return False

def entrySetup(shift, trigger, no_conf = False):
	''' Checks for swing sequence once trigger has been formed '''

	if not trigger == None and trigger.tradable:

		if not isStrandSizeConfirmation(shift, trigger.direction):
			print("DELETED IT")
			trigger.delete = True
			return

		if trigger.state == State.SWING_ONE:
			if swingOne(shift, trigger.direction):
				trigger.state = State.HIT_PARA

		elif trigger.state == State.HIT_PARA:
			if regularParaHit(shift, trigger.direction, no_conf):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)

def momentumSetup(shift, trigger):
	''' Checks for swing sequence once trigger has been formed '''

	if not trigger == None:

		if trigger.state == State.SWING_ONE:
			if isDmiConfirmation(shift, trigger.direction):
				trigger.state = State.HIT_PARA

		elif trigger.state == State.HIT_PARA:
			if momentumParaHit(shift, trigger.direction):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)

def swingOne(shift, direction):

	print("swingOne")

	if isBrownParaConfirmation(shift, direction, reverse = True):
		return True

	return False

def regularParaHit(shift, direction, no_conf):

	brownHit(shift, direction)

	if no_conf:
		return True
	elif current_brown.is_hit and isRegParaConfirmation(shift, direction) and isSlowParaConfirmation(shift, direction) and isBrownParaConfirmation(shift, direction):
		if isMacdConfirmation(shift, direction) and isCciBiasConfirmation(shift, direction) and isBlackPointHitConfirmation(shift, direction):
			return True

	return False

def momentumParaHit(shift, direction):

	brownHit(shift, direction)

	if current_brown.is_hit and isRegParaConfirmation(shift, direction) and isSlowParaConfirmation(shift, direction) and isBrownParaConfirmation(shift, direction):
		if isCciBiasConfirmation(shift, direction):
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

def isMacdConfirmation(shift, direction):

	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		return hist > 0
	else:
		return hist < 0

def isCciBiasConfirmation(shift, direction):
	
	last_chidx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	chidx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		if chidx > last_chidx:
			return True
	else:
		if chidx < last_chidx:
			return True

	return False

def isStrandSizeConfirmation(shift):

	if black_sar.strandCount(VARIABLES['TICKETS'][0], shift) <= VARIABLES['strand_size']:
		return True
	else:
		return False

def isBlackPointHitConfirmation(shift, direction):
	
	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if strands[0].direction == Direction.LONG:
		if strands[0].is_hit or high > strands[0].start:
			strands[0].is_hit = True
			return True
	else:
		if strands[0].is_hit or low < strands[0].start:
			strands[0].is_hit = True
			return True
	
	return False

def isDmiConfirmation(shift, direction):
	plus, minus, adx = dmi.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if direction == Direction.LONG:
		if plus > VARIABLES['dmi_t_threshold'] and minus < VARIABLES['dmi_ct_threshold']:
			if adx >= VARIABLES['dmi_spread']:
				return True
	else:
		if minus > VARIABLES['dmi_t_threshold'] and plus < VARIABLES['dmi_ct_threshold']:
			if adx >= VARIABLES['dmi_spread']:
				return True


def confirmation(shift, trigger):
	''' Checks for overbought, oversold and confirm entry '''

	global current_triggers, cross_strand_long, cross_strand_short

	print("confirmation")

	pending_entries.append(trigger)

	if trigger.is_regular:
		del current_triggers[current_triggers.index(trigger)]

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
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit())

	print("ORDERS:")
	count = 0
	for order in utils.orders:
		count += 1
		print(str(count) + ":", str(order.direction), str(order.entryprice))

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit())

	print("--|\n")

def onMissedEntry(*args, **kwargs):

	global pending_entries, re_entry_trigger

	if args[1] == 'buy':
		direction = Direction.LONG
	else:
		direction = Direction.SHORT

	re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_regular = False)
	re_entry_trigger.state = State.SWING_ONE

	pending_entries = []

def onBacktestFinish():
	global pending_entries

	if len(pending_entries) > 0:
		entry = pending_entries[-1]

		re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_regular = False)
		re_entry_trigger.state = State.SWING_ONE

		pending_entries = []