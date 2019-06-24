from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime
import types
import copy

VARIABLES = {
	'TIMEZONE' : 'America/New_York',
	'START_TIME' : '19:00',
	'END_TIME' : '14:00',
	'PAIRS': [Constants.GBPUSD],
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'maximum_risk' : 2.8,
	'profit_limit' : 200,
	'maximum_bank' : 500,
	'PLAN' : None,
	'stoprange' : 25,
	'full_profit' : 200,
	'breakeven_min_pips' : 3,
	'CLOSING SEQUENCE' : None,
	'close_exit_only' : '13:30',
	'SAR' : None,
	'sar_min_length' : 3,
	'RSI' : None,
	'rsi_overbought': 70,
	'rsi_oversold': 30,
	'rsi_supply_t': 30,
	'rsi_supply_ct': 60,
	'rsi_demand_t': 70,
	'rsi_demand_ct': 40,
	'rsi_confirmed': 50,
	'MACD' : None,
	'macd_override': 10
}

class Direction(Enum):
	LONG = 1
	SHORT = 2

class EntryState(Enum):
	ONE = 1
	TWO = 2
	COMPLETE = 3

class TrendState(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	COMPLETE = 4

class RetState(Enum):
	ONE = 1
	COMPLETE = 3

class MomState(Enum):
	ONE = 1
	COMPLETE = 3

class TimeState(Enum):
	TRADING = 1
	NNT = 2
	CLOSE = 3

class StopState(Enum):
	NONE = 1
	BREAKEVEN = 2
	FIRST = 3

class SortedList(list):
	def __getitem__(self, row):
		return sorted(list(self), key=lambda x: x.count, reverse = True)[row]

	def getSorted(self):
		return sorted(list(self), key=lambda x: x.count, reverse = True)

	def getUnsorted(self):
		return self

class Trigger(dict):
	static_count = 0

	def __init__(self, direction):
		self.direction = direction
		self.cross_strand = None
		
		self.entry_state = EntryState.ONE

		self.count = Trigger.static_count
		Trigger.static_count += 1

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class Strand(dict):
	static_count = 0

	def __init__(self, direction, start):
		self.direction = direction
		self.start = start
		self.end = 0
		self.length = 1

		self.count = Strand.static_count
		Strand.static_count += 1

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global fast_sar, slow_sar, macd, macdz

	utils = utilities
	fast_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.2, 0.2)
	slow_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.008, 0.2)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)

	setGlobalVars()

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	setGlobalVars()

	firstStrand(0)

	print("Starting Bank:", str(bank))

	
def setGlobalVars():
	global bank, stop_trading, no_new_trades
	global long_trigger, short_trigger, fast_strands, slow_strands
	global current_strand
	global pending_entries, pending_breakevens, pending_exits
	global current_news, news_trade_block
	global time_state, stop_state

	if utils.getBankSize() > VARIABLES['maximum_bank']:
		bank = VARIABLES['maximum_bank']
	else:
		bank = utils.getBankSize()

	stop_trading = False
	no_new_trades = False

	long_trigger = Trigger(Direction.LONG)
	short_trigger = Trigger(Direction.SHORT)
	fast_strands = SortedList()
	slow_strands = SortedList()

	current_strand = None

	pending_entries = []
	pending_breakevens = []
	pending_exits = []

	current_news = None
	news_trade_block = False

	time_state = TimeState.TRADING
	stop_state = StopState.NONE

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
				else:
					print("Attempting position enter long: stop and reverse")
					handleStopAndReverse(pos, entry)

			else:

				if no_new_trades:
					print("Trade blocked! Current position exited.")

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
				else:
					print("Attempting position enter short: stop and reverse")
					handleStopAndReverse(pos, entry)
			else:

				if no_new_trades:
					print("Trade blocked!")
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
			utils.buy(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), pairs = VARIABLES['PAIRS'], sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		else:
			utils.sell(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), pairs = VARIABLES['PAIRS'], sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		
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

	for direction in pending_exits:

		if isFastParaConfirmation(shift, direction, reverse = True):
			print("Attempting exit")
			is_exit = True
			for pos in utils.positions:
				pos.quickExit()

	if is_exit:
		pending_exits = []

def onTrade(pos, event):
	global entry_trigger_l, entry_trigger_s

	# listened_types = ['Take Profit', 'Stop Loss', 'Close Trade']

	# if event in listened_types:
	# 	if pos.direction == 'buy':
	# 	else:

	return

def onEntry(pos):
	print("onEntry")

	# long_trigger.entry_state = EntryState.ONE
	# long_trigger.cross_strand = None

	# short_trigger.entry_state = EntryState.ONE
	# short_trigger.cross_strand = None

	stop_state = StopState.NONE

def onStopLoss(pos):
	print("onStopLoss")
	return

def onTakeProfit(pos):
	print("onTakeProfit")
	stop_trading = True
	return

def onNews(title, time):
	''' 
	Block new trades 
	and set current position to breakeven on news.
	'''

	# checkCurrentNews()

	return


def checkCurrentNews():
	''' Block new trades if there is news currently in action '''

	return

def checkTime():
	''' 
	Checks current time and initiates 
	closing sequence where necessary.
	'''

	global time_state, no_new_trades

	time = utils.getTime(VARIABLES['TIMEZONE'])
	parts = VARIABLES['close_exit_only'].split(':')
	nnt_time = utils.createNewYorkTime(time.year, time.month, time.day, int(parts[0]), int(parts[1]), 0)

	if not (time < nnt_time and nnt_time + datetime.timedelta(days=1) < utils.endTime):
		nnt_time += datetime.timedelta(days=1)

	if time > utils.endTime and time_state.value < TimeState.CLOSE.value:
		time_state = TimeState.CLOSE

		print("End time: looking to exit")
		for pos in utils.positions:
			if pos.direction == 'buy':
				pending_exits.append(Direction.LONG)
			else:
				pending_exits.append(Direction.SHORT)

	elif time > nnt_time and time_state.value < TimeState.NNT.value:
		print("No more trades")
		time_state = TimeState.NNT
		no_new_trades = True

def firstStrand(shift):
	while not slow_sar.isNewCycle(shift):
		shift += 1

	start = slow_sar.get(shift, 1)[0]

	if slow_sar.isRising(shift, 1)[0]:
		print("first rising slow para")
		last_strand = getLastDirectionSlowStrand(Direction.SHORT)

		slow_strands.append(Strand(Direction.SHORT, start))
	else:
		print("first falling slow para")
		last_strand = getLastDirectionSlowStrand(Direction.LONG)

		slow_strands.append(Strand(Direction.LONG, start))


def runSequence(shift):
	''' Main trade plan sequence '''

	onNewFastStrand(shift)
	onNewSlowStrand(shift)

	setCrossStrand(long_trigger)
	setCrossStrand(short_trigger)

	paraRevSetup(shift, long_trigger)
	paraRevSetup(shift, short_trigger)

def onNewFastStrand(shift):
	global current_strand

	print(fast_sar.isNewCycle(shift))
	if fast_sar.isNewCycle(shift):
		print("new fast")
		start = fast_sar.getCurrent()

		if fast_sar.isRising(shift, 1)[0]:
			last_strand = getLastDirectionFastStrand(Direction.SHORT)

			new_strand = Strand(Direction.SHORT, start)
			fast_strands.append(new_strand)

			current_strand = new_strand
		else:
			last_strand = getLastDirectionFastStrand(Direction.LONG)

			new_strand = Strand(Direction.LONG, start)
			fast_strands.append(new_strand)
			
			current_strand = new_strand
	
		if last_strand:
			last_strand.end = fast_sar.get(shift + 1, 1)[0]
	elif current_strand:
		current_strand.length += 1

def onNewSlowStrand(shift):

	if slow_sar.isNewCycle(shift):
		start = slow_sar.getCurrent()

		if slow_sar.isRising(shift, 1)[0]:
			print("new rising slow para")
			last_strand = getLastDirectionSlowStrand(Direction.SHORT)

			slow_strands.append(Strand(Direction.SHORT, start))
		else:
			print("new falling slow para")
			last_strand = getLastDirectionSlowStrand(Direction.LONG)

			slow_strands.append(Strand(Direction.LONG, start))
	
		if last_strand:
			last_strand.end = slow_sar.get(shift + 1, 1)[0]

def setCrossStrand(trigger):
	# if trigger.cross_strand:
	# 	for i in range(len(fast_strands)):
	# 		strand = fast_strands[i]
	# 		if strand.direction == trigger.direction:
	# 			if strand.count <= trigger.cross_strand.count:
	# 				return
			
	# 			elif strand.length >= VARIABLES['sar_min_length']:
	# 				if trigger.direction == Direction.LONG:
	# 					if strand.start < trigger.cross_strand.start:
	# 						trigger.cross_strand = strand
	# 						return
	# 				else:
	# 					if strand.start > trigger.cross_strand.start:
	# 						trigger.cross_strand = strand
	# 						return

	# else:
	for i in range(len(slow_strands)):
		strand = slow_strands[i]
		if strand.direction == trigger.direction:
			trigger.cross_strand = strand
			return

def getLastDirectionFastStrand(direction):
	for i in range(len(fast_strands)):
		if fast_strands[i].direction == direction:
			return fast_strands[i]

	return None

def getLastDirectionSlowStrand(direction):
	for i in range(len(slow_strands)):
		if slow_strands[i].direction == direction:
			return slow_strands[i]

	return None			

def paraRevSetup(shift, trigger):

	if trigger and trigger.cross_strand and not trigger.entry_state == EntryState.COMPLETE:

		if trigger.entry_state == EntryState.ONE:
			if isSlowParaConfirmation(shift, trigger.direction):
				trigger.entry_state = EntryState.TWO
				return paraRevSetup(shift, trigger)

		if trigger.entry_state == EntryState.TWO:
			if isPriceExceeded(shift, direction):
				trigger.entry_state = EntryState.ONE
				return

			if isSlowParaConfirmation(shift, trigger.direction, reverse=True):
				trigger.entry_state = EntryState.THREE
				return paraRevSetup(shift, trigger)

		if trigger.entry_state == EntryState.THREE:
			if isParaRevConfirmation(shift, trigger):
				trigger.entry_state = EntryState.COMPLETE
				return confirmation(trigger)

def isParaRevConfirmation(shift, trigger):
	print("Para Conf ("+str(trigger.direction)+"):", 
			str(isFastParaConfirmation(shift, trigger.direction)),
			str(isSlowParaConfirmation(shift, trigger.direction)),
			str(isMacdConfirmation(trigger.direction))
		)
	return (
			isFastParaConfirmation(shift, trigger.direction) and
			isSlowParaConfirmation(shift, trigger.direction) and
			isMacdConfirmation(trigger.direction)
		)

def isPriceExceeded(shift, direction):
	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

	if direction == Direction.LONG:
		cross_sar = short_trigger.cross_strand.start
		low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

		return low < cross_sar

	else:
		cross_sar = long_trigger.cross_strand.start
		high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

		return cross_sar > high


def isFastParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.LONG:
			return fast_sar.isFalling(shift, 1)[0]
		else:
			return fast_sar.isRising(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return fast_sar.isRising(shift, 1)[0]
		else:
			return fast_sar.isFalling(shift, 1)[0]

def isSlowParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.LONG:
			return slow_sar.isFalling(shift, 1)[0]
		else:
			return slow_sar.isRising(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return slow_sar.isRising(shift, 1)[0]
		else:
			return slow_sar.isFalling(shift, 1)[0]

def isMacdConfirmation(direction, reverse = False):
	hist = macd.getCurrent()[2]
	histz = macdz.getCurrent()[2]
	print("hist:", str(hist), "histz:", str(histz))

	if reverse:
		if direction == Direction.LONG:
			return hist < 0 and histz < 0
		else:
			return hist > 0 and histz > 0

	else:
		if direction == Direction.LONG:
			return hist > 0 and histz > 0
		else:
			return hist < 0 and histz < 0

def confirmation(trigger, is_opp = False):
	''' confirm entry '''

	print("confirmation:", str(trigger.direction), str(trigger.count))

	entry_trigger = None
	if is_opp:
		if trigger.direction == Direction.LONG:
			entry_trigger = Trigger(Direction.SHORT)
		else:
			entry_trigger = Trigger(Direction.LONG)
	else:
		entry_trigger = trigger

	pending_entries.append(entry_trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	print("FAST STRANDS:", str(len(fast_strands)))
	print("SLOW STRANDS:", str(len(slow_strands)))
	if current_strand:
		print("Current strand:", str(current_strand.direction), str(current_strand.length)+"\n")

	print("LONG T:", str(long_trigger.cross_strand), str(long_trigger.entry_state))
	print("SHORT T:", str(short_trigger.cross_strand), str(short_trigger.entry_state)+"\n")

	print("CLOSED POSITIONS:")
	count = 0
	for pos in utils.closedPositions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit(price_type = 'c'))

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit(price_type = 'c'))

	print("--|\n")
