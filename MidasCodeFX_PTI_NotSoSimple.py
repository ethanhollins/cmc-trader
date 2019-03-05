from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime
import types
import copy

VARIABLES = {
	'START_TIME' : '6:00',
	'END_TIME' : '19:00',
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'maximum_risk' : 2.5,
	'profit_limit' : 51,
	'maximum_bank' : 400,
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
	'min_diff' : 0.2,
	'SAR' : None,
	'sar_count_valid' : 3,
	'sar_count_ret' : 2,
	'sar_count_extend': 1,
	'MACD' : None,
	'macd_threshold' : 2,
	'PTI' : None,
	'num_comp_strands': 4,
	'comp_period': 1
}

class SortedList(list):
	def __getitem__(self, row):
		return sorted(list(self), key=lambda x: x.count, reverse = True)[row]

	def getSorted(self):
		return sorted(list(self), key=lambda x: x.count, reverse = True)

on_down_time = False

current_triggers = []
re_entry_trigger = None
re_entry_direction = None

strands = SortedList()

comp_strands = []

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
	TWO = 2
	ENTERED = 3

class Re_Entry_State(Enum):
	ONE = 1
	TWO = 2
	ENTERED = 3

class TriggerType(Enum):
	REGULAR = 1
	RE_ENTRY = 2
	CROSS_EXIT = 3

class CompType(Enum):
	PRIMARY = 1
	SECONDARY = 2

class TimeState(Enum):
	TRADING = 1
	NNT_PROFIT = 2
	NNT = 3
	CLOSE = 4

class ExitType(Enum):
	NONE = 1
	IMMEDIATE = 2
	CROSS = 3

class PtiDirection(Enum):
	NONE = 1
	LONG = 2
	SHORT = 3

time_state = TimeState.TRADING
pti_direction = PtiDirection.NONE

class Strand(dict):
	def __init__(self, direction, start):
		self.direction = direction
		self.start = start
		self.end = 0
		self.is_completed = False
		self.count = len(strands)
		self.length = 0
		self.is_valid = False

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class CompStrand(dict):
	def __init__(self, direction, half_val, comp_type, strand, is_two_point = False):
		self.direction = direction
		self.half_val = half_val
		self.comp_type = comp_type
		self.strand = strand
		self.is_two_point = is_two_point
		self.has_crossed = False
		self.is_extended = False
		self.comp_length = None

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class Trigger(dict):
	def __init__(self, direction, start, tradable = True, trigger_type = TriggerType.REGULAR):
		self.direction = direction
		self.start = start
		self.trigger_type = trigger_type
		self.state = self._getState()
		self.tradable = tradable
		self.exit_type = ExitType.NONE
		self.is_dir_confirmed = False

	def _getState(self):
		if self.trigger_type == TriggerType.REGULAR:
			return State.ONE
		elif self.trigger_type == TriggerType.RE_ENTRY:
			return Re_Entry_State.ONE
		else:
			return None

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
	global sar, macd, macdz, cci, rsi

	utils = utilities
	sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.2, 0.2)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	cci = utils.CCI(Constants.GBPUSD, Constants.ONE_MINUTE, 5)
	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)

	resetTriggers()

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

	global on_down_time
	on_down_time = False

	print("\nonNewBar")
	checkTime()

	utils.printTime(utils.getAustralianTime())

	runSequence(0)
	handleExits(0)

	report()

def onDownTime():
	''' Function called outside of trading time '''

	global on_down_time
	on_down_time = True

	print("onDownTime")
	ausTime = utils.printTime(utils.getAustralianTime())

	runSequence(0)

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
			profit = pos.getProfit(price_type = 'h')
		else:
			profit = pos.getProfit(price_type = 'l')

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

def onTrade(pos, event):

	global re_entry_direction

	print("onTrade")

	if (pos.direction == 'buy' and re_entry_direction == Direction.LONG) or (pos.direction == 'sell' and re_entry_direction == Direction.SHORT):
		re_entry_direction = None
		return
	
	listened_events = ['Buy Trade', 'Sell Trade']

	if event in listened_events:
		if pos.direction == 'buy':
			configureCompStrandsOnEntry(Direction.SHORT)
		elif pos.direction == 'sell':
			configureCompStrandsOnEntry(Direction.LONG)
	
	resetTriggers()

def onEntry(pos):
	print("onEntry")

	global re_entry_trigger, stop_state

	if pos.direction == 'buy':
		trigger = getDirectionTrigger(Direction.LONG)
		trigger.state = State.ENTERED
	else:
		trigger = getDirectionTrigger(Direction.SHORT)
		trigger.state = State.ENTERED

	re_entry_trigger = None

	stop_state = StopState.NONE

def onStopLoss(pos):
	print("onStopLoss")

	global re_entry_trigger

	if pos.direction == 'buy':
		re_entry_trigger = Trigger(Direction.LONG, 0, tradable = True, trigger_type = TriggerType.RE_ENTRY)
	elif pos.direction == 'sell':
		re_entry_trigger = Trigger(Direction.SHORT, 0, tradable = True, trigger_type = TriggerType.RE_ENTRY)

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
	for trigger in current_triggers:
		checkCompConf(shift, trigger)
	for trigger in current_triggers:
		entrySetup(shift, trigger)

	reEntrySetup(shift, re_entry_trigger)

def resetTriggers(direction = None):
	global current_triggers

	long_t = Trigger(Direction.LONG, 0, tradable = True, trigger_type = TriggerType.REGULAR)
	short_t = Trigger(Direction.SHORT, 0, tradable = True, trigger_type = TriggerType.REGULAR)

	if direction:
		if direction == Direction.LONG:
			current = getDirectionTrigger(Direction.LONG)
			if current:
				del current_triggers[current_triggers.index(current)]
			current_triggers.append(long_t)
		else:
			current = getDirectionTrigger(Direction.SHORT)
			if current:
				del current_triggers[current_triggers.index(current)]
			current_triggers.append(short_t)
	else:
		current_triggers = [long_t, short_t]

def getTrigger(shift, pos):

	directions = [Direction.LONG, Direction.SHORT]

	if pos:
		if pos.direction == 'buy':
			if getDirectionTrigger(Direction.LONG):
				del current_triggers[current_triggers.index(getDirectionTrigger(Direction.LONG))]
			del directions[0]
			print(pos.direction)
		elif pos.direction == 'sell':
			if getDirectionTrigger(Direction.SHORT):
				del current_triggers[current_triggers.index(getDirectionTrigger(Direction.SHORT))]
			del directions[1]
			print(pos.direction)

	for direction in directions:
		if not getDirectionTrigger(direction):
			trigger = Trigger(direction, 0, tradable = True, trigger_type = TriggerType.REGULAR)

			current_triggers.append(trigger)

def configureCompStrandsOnEntry(direction):
	primary_strand = getCompStrand(direction, CompType.PRIMARY)

	if primary_strand:
		secondary_strand = getCompStrand(direction, CompType.SECONDARY)
		del comp_strands[comp_strands.index(secondary_strand)]

		primary_strand.comp_type = CompType.SECONDARY

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''

	if sar.isNewCycle(shift):

		if sar.isRising(shift, 1)[0]:
			direction = Direction.SHORT
			opp_direction = Direction.LONG
		else:
			direction = Direction.LONG
			opp_direction = Direction.SHORT

		strand = Strand(direction, sar.get(shift, 1)[0])
		
		if len(strands) > 0:
			print("new cycle:\n")

			if not strands[0].direction == direction:

				last_strand = getNthDirectionStrand(opp_direction, 1)

				last_strand.is_completed = True
				last_strand.end = sar.get(shift + 1, 1)[0]
				last_strand.length = sar.strandCount(shift + 1)

				getPTI()

		strands.append(strand)
		print("New Strand:", str(strand.direction))

def getDirectionTrigger(direction):
	for trigger in current_triggers:
		if trigger.direction == direction:
			return trigger

	return None

def getNthDirectionStrand(direction, count):

	current_count = 0
	for i in range(len(strands)):
		if strands[i].direction == direction:
			current_count += 1
			if count == current_count:
				print("at: " + str(i))
				print(strands[i])
				return strands[i]

	return None

def getCompStrand(direction, comp_type):
	for strand in comp_strands:
		if strand.direction == direction and strand.comp_type == comp_type:
			return strand

	return None

def getPTI():

	global pti_direction

	long_strands = [i for i in strands.getSorted() if i.direction == Direction.SHORT]
	short_strands = [i for i in strands.getSorted() if i.direction == Direction.LONG]

	temp_direction = None

	if len(long_strands) >= VARIABLES['num_comp_strands'] + VARIABLES['comp_period']-1 and len(short_strands) >= VARIABLES['num_comp_strands'] + VARIABLES['comp_period']-1:
		long_len = 0
		short_len = 0

		temp_direction = PtiDirection.NONE
		for i in range(VARIABLES['comp_period']):

			for strand in long_strands[i:VARIABLES['num_comp_strands'] + i]:
				long_len += strand.length
			
			for strand in short_strands[i:VARIABLES['num_comp_strands'] + i]:
				short_len += strand.length

			if long_len > short_len and (temp_direction == PtiDirection.NONE or temp_direction == PtiDirection.LONG):
				temp_direction = PtiDirection.LONG

			elif short_len > long_len and (temp_direction == PtiDirection.NONE or temp_direction == PtiDirection.SHORT):
				temp_direction = PtiDirection.SHORT

			else:
				temp_direction = None

	if temp_direction:
		pti_direction = temp_direction

def isValidStrandBetween(direction):
	comp_strand = getCompStrand(direction, CompType.PRIMARY)
	if not comp_strand:
		comp_strand = getCompStrand(direction, CompType.SECONDARY)

	print("comp strand:\n", str(comp_strand))

	if comp_strand:
		direction_strands = [i for i in strands.getSorted() if i.direction == direction and i.count > comp_strand.strand.count]
		
		for strand in direction_strands:
			print(str(strand.count)+":")
			print(strand)

			if strand.length >= VARIABLES['sar_count_ret']:
				print("Valid inbetween strand found")
				return True

	return False

def checkCompConf(shift, trigger):
	if not trigger == None and trigger.tradable and not trigger.state == State.ENTERED:

		if trigger.state == State.ONE:
			print("stateOne")
			if ptiConf(shift, trigger.direction):

				if trigger.direction == Direction.LONG:
					opp_direction = Direction.SHORT
				else:
					opp_direction = Direction.LONG

				opp_trigger = getDirectionTrigger(opp_direction)
				if opp_trigger:
					opp_trigger.is_dir_confirmed = False

				trigger.is_dir_confirmed = True
				trigger.state = State.TWO
				entrySetup(shift, trigger)

def entrySetup(shift, trigger):
	''' Checks for swing sequence once trigger has been formed '''

	if not trigger == None and trigger.tradable and not trigger.state == State.ENTERED:

		if not trigger.is_dir_confirmed:
			trigger.state = State.ONE

		if trigger.state == State.TWO:

			if directionConf(shift, trigger.direction):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)

def reEntrySetup(shift, trigger):

	if not trigger == None and trigger.tradable and not trigger.state == State.ENTERED:

		if trigger.state == Re_Entry_State.ONE:
			if reEntryConf(shift, trigger.direction):
				trigger.state = Re_Entry_State.ENTERED
				confirmation(shift, trigger)

def ptiConf(shift, direction):
	print("PTI conf")

	if direction == Direction.LONG and pti_direction == PtiDirection.LONG:
		return True
	elif direction == Direction.SHORT and pti_direction == PtiDirection.SHORT:
		return True

	return False

def directionConf(shift, direction):
	print("Direction conf")

	return ( isMacdHistConfirmation(direction) or isMacdZeroConfirmation(direction) ) and isCCIConfirmation(shift, direction) and isParaConfirmation(shift, direction) and isRSIConfirmation(shift, direction)

def reEntryConf(shift, direction):
	print("re entry conf")

	return isMacdEitherConfirmation(direction) and isParaConfirmation(shift, direction)

def isParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.SHORT:
			print("long:", str(sar.isRising(shift, 1)[0]))
			return sar.isRising(shift, 1)[0]
		else:
			print("short:", str(sar.isFalling(shift, 1)[0]))
			return sar.isFalling(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			print("long:", str(sar.isRising(shift, 1)[0]))
			return sar.isRising(shift, 1)[0]
		else:
			print("short:", str(sar.isFalling(shift, 1)[0]))
			return sar.isFalling(shift, 1)[0]

def isMacdHistConfirmation(direction):

	hist = macd.getCurrent()[2]

	if direction == Direction.LONG:
		if hist > 0:
			return True
	else:
		if hist < 0:
			return True

def isMacdZeroConfirmation(direction):

	hist = macd.getCurrent()[2]
	histz = macdz.getCurrent()[2]

	print("MACDZ:", str(histz))

	if direction == Direction.LONG:
		if hist >= 0 and histz > 0:
			return True
	else:
		if hist <= 0 and histz < 0:
			return True

def isMacdEitherConfirmation(direction):

	hist = macd.getCurrent()[2]
	histz = macdz.getCurrent()[2]

	print("MACDZ:", str(histz))

	if direction == Direction.LONG:
		if hist > 0 and histz >= 0:
			return True
		if hist >= 0 and histz > 0:
			return True
	else:
		if hist < 0 and histz <= 0:
			return True
		if hist <= 0 and histz < 0:
			return True

def isCCIConfirmation(shift, direction):
	cur_cci = cci.get(shift, 1)[0][0]
	last_cci = cci.get(shift+1, 1)[0][0]

	print("CCI:", str(cur_cci), str(last_cci))

	if direction == Direction.LONG:
		if cur_cci > last_cci:
			return True
	else:
		if cur_cci < last_cci:
			return True

	return False

def isRSIConfirmation(shift, direction):
	strength = rsi.getCurrent()[0]

	if direction == Direction.LONG:
		if strength > 0:
			return True
	else:
		if strength < 0:
			return True

	return False

def confirmation(shift, trigger):
	''' Checks for overbought, oversold and confirm entry '''

	global re_entry_direction

	print("confirmation")

	if on_down_time:
		resetTriggers(direction = trigger.direction)
		return

	if len(utils.positions) > 0:
		if utils.positions[0].direction == 'buy' and trigger.direction == Direction.LONG:
			resetTriggers(direction = Direction.LONG)
			return
		elif utils.positions[0].direction == 'sell' and trigger.direction == Direction.SHORT:
			resetTriggers(direction = Direction.SHORT)
			return

	if trigger.trigger_type == TriggerType.RE_ENTRY:
		re_entry_direction = trigger.direction

	pending_entries.append(trigger)

	global re_entry_trigger

	re_entry_trigger = None

def report():
	''' Prints report for debugging '''

	print("\n")

	for i in comp_strands:
		print(i)

	print("\n")

	print("PTI Direction:", str(pti_direction))

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
