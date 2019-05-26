from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime
import types
import copy

VARIABLES = {
	'TIMEZONE' : 'America/New_York',
	'START_TIME' : '18:00',
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
}

class Direction(Enum):
	LONG = 1
	SHORT = 2

class EntryState(Enum):
	ONE = 1
	TWO = 2
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
		self.end = 0
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

		self.count = Strand.static_count
		Strand.static_count += 1

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global fast_sar, slow_sar, rsi, macd, macdz, cci

	utils = utilities
	fast_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.2, 0.2)
	slow_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.015, 0.04)
	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)
	cci = utils.CCI(Constants.GBPUSD, Constants.ONE_MINUTE, 5)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)

	setGlobalVars()

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	setGlobalVars()

	print("Starting Bank:", str(bank))

	
def setGlobalVars():
	global bank, stop_trading, no_new_trades
	global long_trigger, short_trigger, fast_strands, slow_strands
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

	long_strand = getLastDirectionFastStrand(Direction.LONG)
	long_trigger.entry_state = EntryState.ONE

	short_strand = getLastDirectionFastStrand(Direction.SHORT)
	short_trigger.entry_state = EntryState.ONE

	stop_state = StopState.NONE

def onStopLoss(pos):
	print("onStopLoss")
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


def runSequence(shift):
	''' Main trade plan sequence '''

	print(slow_sar.getCurrent())

	onNewFastStrand(shift)
	onNewSlowStrand(shift)

	# updateTrigger(shift, Direction.LONG)
	# updateTrigger(shift, Direction.SHORT)

	entrySetup(shift, long_trigger)
	entrySetup(shift, short_trigger)
		

def onNewFastStrand(shift):

	if fast_sar.isNewCycle(shift):
		start = fast_sar.getCurrent()

		if fast_sar.isRising(shift, 1)[0]:
			print("new rising fast para")
			last_strand = getLastDirectionFastStrand(Direction.SHORT)

			new_strand = Strand(Direction.SHORT, start)
			fast_strands.append(new_strand)

			if short_trigger.cross_strand:
				if new_strand.start < short_trigger.cross_strand.start:
					short_trigger.cross_strand = new_strand
			else:
				short_trigger.cross_strand = new_strand
		else:
			print("new falling fast para")
			last_strand = getLastDirectionFastStrand(Direction.LONG)

			new_strand = Strand(Direction.LONG, start)
			fast_strands.append(new_strand)

			if long_trigger.cross_strand:
				if new_strand.start < long_trigger.cross_strand.start:
					long_trigger.cross_strand = new_strand
			else:
				long_trigger.cross_strand = new_strand
	
		if last_strand:
			last_strand.end = fast_sar.get(shift + 1, 1)[0]

def onNewSlowStrand(shift):

	print("slow")
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


def entrySetup(shift, trigger):

	if trigger and not trigger.entry_state == EntryState.COMPLETE:

		if trigger.entry_state == EntryState.ONE:
			if trigger.cross_strand and isParaCrossedConfirmation(shift, trigger):
				if trigger.direction == Direction.LONG:
					short_trigger.entry_state = EntryState.ONE
				else:
					long_trigger.entry_state = EntryState.ONE

				trigger.entry_state = EntryState.TWO
				return entrySetup(shift, trigger)

		if trigger.entry_state == EntryState.TWO:
			if isEntryConfirmation(shift, trigger):
				trigger.entry_state = EntryState.COMPLETE
				return confirmation(trigger)

def isEntryConfirmation(shift, trigger):
	print("CONFIRMATION:", 
			str(isFastParaConfirmation(shift, trigger.direction)),
			str(isSlowParaConfirmation(shift, trigger.direction)),
			str(isMacdConfirmation(trigger.direction)),
			str(isCciConfirmation(shift, trigger.direction)),
			str(isRsiConfirmation(shift, trigger.direction)),
			str(isParaCrossedConfirmation(shift, trigger))
		)
	return (
			isFastParaConfirmation(shift, trigger.direction) and
			isSlowParaConfirmation(shift, trigger.direction) and
			isMacdConfirmation(trigger.direction) and
			isCciConfirmation(shift, trigger.direction) and
			isRsiConfirmation(shift, trigger.direction) and
			isParaCrossedConfirmation(shift, trigger)
		)

def isParaCrossedConfirmation(shift, trigger):
	sar = slow_sar.getCurrent()

	if trigger.direction == Direction.LONG:
		return sar > trigger.cross_strand.start and slow_sar.isRising(shift, 1)[0]
	else:
		return sar < trigger.cross_strand.start and slow_sar.isFalling(shift, 1)[0]

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
			return (hist < 0 and histz <= 0) or (hist <= 0 and histz < 0)
		else:
			return (hist > 0 and histz >= 0) or (hist >= 0 and histz > 0)

	else:
		if direction == Direction.LONG:
			return (hist > 0 and histz >= 0) or (hist >= 0 and histz > 0)
		else:
			return (hist < 0 and histz <= 0) or (hist <= 0 and histz < 0)

def isCciConfirmation(shift, direction, reverse = False):
	chidx = cci.getCurrent()[0]
	cci_signal = cci.getSignalLine(2, 0, 1)[0]

	if reverse:
		if direction == Direction.LONG:
			return chidx < cci_signal
		else:
			return chidx > cci_signal
	else:
		if direction == Direction.LONG:
			return chidx > cci_signal
		else:
			return chidx < cci_signal

def isRsiConfirmation(shift, direction):
	stridx = rsi.get(shift, 2)

	if direction == Direction.LONG:
		return stridx[0] > stridx[1]
	else:
		return stridx[0] < stridx[1]

def confirmation(trigger):
	''' confirm entry '''

	print("confirmation:", str(trigger.direction), str(trigger.count))

	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	print("FAST STRANDS:", str(len(fast_strands)))
	print("SLOW STRANDS:", str(len(slow_strands))+"\n")

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
