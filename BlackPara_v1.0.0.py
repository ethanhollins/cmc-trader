from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime
import types
import copy

VARIABLES = {
	'TIMEZONE': 'America/New_York',
	'START_TIME': '19:00',
	'END_TIME': '14:00',
	'PAIRS': [Constants.GBPUSD],
	'INDIVIDUAL': None,
	'risk': 1.0,
	'profit_risk': 50,
	'maximum_risk': 63,
	'maximum_bank': 400,
	'PLAN': None,
	'stoprange': 25,
	'full_profit': 200,
	'breakeven_min_pips': 3,
	'CLOSING SEQUENCE': None,
	'close_exit_only': '13:30',
	'MACD': None,
	'macd_threshold': 2,
	'SAR': None,
	'sar_min_diff': 0.5
}

class Direction(Enum):
	LONG = 1
	SHORT = 2

class EntryState(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	COMPLETE = 4

class EntryThreeState(Enum):
	ONE = 1
	TWO = 2
	COMPLETE = 4

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
		
		self.entry_state = EntryState.ONE
		self.entry_three_state = EntryThreeState.ONE 

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
	global orange_sar, purple_sar, black_sar, yellow_sar, macd, macdz, rsi, cci

	utils = utilities
	orange_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.2, 0.2)
	purple_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.08, 0.2)
	yellow_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.05, 0.2)
	black_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.017, 0.04)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)
	cci = utils.CCI(Constants.GBPUSD, Constants.ONE_MINUTE, 5)

	setGlobalVars()

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	setGlobalVars()

	# firstStrand(0)

	print("Starting Bank:", str(bank))

	
def setGlobalVars():
	global bank, stop_trading, no_new_trades
	global long_trigger, short_trigger
	global orange_strands, purple_strands, black_strands, yellow_strands
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
	orange_strands = SortedList()
	purple_strands = SortedList()
	yellow_strands = SortedList()
	black_strands = SortedList()

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
	
	if current_profit <= -VARIABLES['maximum_risk'] or current_profit >= VARIABLES['profit_risk']:
		print("Trading stopped:", str(current_profit))
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

	if current_profit <= -VARIABLES['maximum_risk'] or current_profit >= VARIABLES['profit_risk']:
		print("Trading stopped:", str(current_profit))
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

		if isPurpleParaConfirmation(shift, direction, reverse=True):
			print("Attempting exit")
			is_exit = True
			for pos in utils.positions:
				pos.quickExit()

	if is_exit:
		pending_exits = []

def onTrade(pos, event):
	global entry_trigger_l, entry_trigger_s

	# listened_types = ['Take Profit', 'Stop Loss', 'Close Trade']

def onEntry(pos):
	print("onEntry")

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
	while not black_sar.isNewCycle(shift):
		shift += 1

	start = black_sar.get(shift, 1)[0]

	if black_sar.isRising(shift, 1)[0]:
		print("first rising black para")
		last_strand = getLastDirectionBlackStrand(Direction.SHORT)

		black_strands.append(Strand(Direction.SHORT, start))
	else:
		print("first falling black para")
		last_strand = getLastDirectionBlackStrand(Direction.LONG)

		black_strands.append(Strand(Direction.LONG, start))


def runSequence(shift):
	''' Main trade plan sequence '''

	print("O:", str(orange_sar.getCurrent()), "P:", str(purple_sar.getCurrent()), "B:", str(black_sar.getCurrent()))

	onNewOrangeStrand(shift)
	onNewPurpleStrand(shift)
	onNewYellowStrand(shift)
	onNewBlackStrand(shift)

	entrySetup(shift, long_trigger)
	entrySetup(shift, short_trigger)

def onNewOrangeStrand(shift):
	global current_strand

	print(orange_sar.isNewCycle(shift))
	if orange_sar.isNewCycle(shift):
		print("new orange")
		start = orange_sar.getCurrent()

		if orange_sar.isRising(shift, 1)[0]:
			last_strand = getLastDirectionOrangeStrand(Direction.LONG)

			new_strand = Strand(Direction.SHORT, start)
			orange_strands.append(new_strand)

			current_strand = new_strand
		else:
			last_strand = getLastDirectionOrangeStrand(Direction.SHORT)

			new_strand = Strand(Direction.LONG, start)
			orange_strands.append(new_strand)
			
			current_strand = new_strand
	
		if last_strand:
			last_strand.end = orange_sar.get(shift + 1, 1)[0]
	elif current_strand:
		current_strand.length += 1

def onNewPurpleStrand(shift):

	if purple_sar.isNewCycle(shift):
		start = purple_sar.getCurrent()

		if purple_sar.isRising(shift, 1)[0]:
			print("new rising purple para")
			last_strand = getNumberDirectionPurpleStrand(Direction.LONG, 0)

			purple_strands.append(Strand(Direction.SHORT, start))
		else:
			print("new falling purple para")
			last_strand = getNumberDirectionPurpleStrand(Direction.SHORT, 0)

			purple_strands.append(Strand(Direction.LONG, start))
	
		if last_strand:
			last_strand.end = purple_sar.get(shift + 1, 1)[0]

def onNewYellowStrand(shift):

	if yellow_sar.isNewCycle(shift):
		start = yellow_sar.getCurrent()

		if yellow_sar.isRising(shift, 1)[0]:
			print("new rising yellow para")
			last_strand = getNumberDirectionYellowStrand(Direction.LONG, 0)

			yellow_strands.append(Strand(Direction.SHORT, start))
		else:
			print("new falling yellow para")
			last_strand = getNumberDirectionYellowStrand(Direction.SHORT, 0)

			yellow_strands.append(Strand(Direction.LONG, start))
	
		if last_strand:
			last_strand.end = yellow_sar.get(shift + 1, 1)[0]

def onNewBlackStrand(shift):

	if black_sar.isNewCycle(shift):
		start = black_sar.getCurrent()

		if black_sar.isRising(shift, 1)[0]:
			print("new rising black para")
			last_strand = getLastDirectionBlackStrand(Direction.LONG)

			black_strands.append(Strand(Direction.SHORT, start))
		else:
			print("new falling black para")
			last_strand = getLastDirectionBlackStrand(Direction.SHORT)

			black_strands.append(Strand(Direction.LONG, start))
	
		if last_strand:
			last_strand.end = black_sar.get(shift + 1, 1)[0]


def getLastDirectionOrangeStrand(direction):
	for i in range(len(orange_strands)):
		if orange_strands[i].direction == direction:
			return orange_strands[i]

	return None

def getNumberDirectionPurpleStrand(direction, num):
	count = 0
	for i in range(len(purple_strands)):
		if purple_strands[i].direction == direction:
			if count == num:
				return purple_strands[i]
			count += 1

	return None

def getNumberDirectionYellowStrand(direction, num):
	count = 0
	for i in range(len(yellow_strands)):
		if yellow_strands[i].direction == direction:
			if count == num:
				return yellow_strands[i]
			count += 1

	return None

def getLastDirectionBlackStrand(direction):
	for i in range(len(black_strands)):
		if black_strands[i].direction == direction:
			return black_strands[i]

	return None

def entrySetup(shift, trigger):

	if trigger and not trigger.entry_state == EntryState.COMPLETE:

		if trigger.entry_state == EntryState.ONE:
			if isAllParaConfirmation(shift, trigger.direction):
				trigger.entry_state = EntryState.TWO
				trigger.entry_three_state = EntryThreeState.TWO
				return entrySetup(shift, trigger)

		elif trigger.entry_state == EntryState.TWO:
			if isPurpleParaConfirmation(shift, trigger.direction, reverse=True):
				trigger.entry_state = EntryState.THREE
				return entrySetup(shift, trigger)

		elif trigger.entry_state == EntryState.THREE:
			if entryOneConfirmation(shift, trigger):
				trigger.entry_state = EntryState.COMPLETE
				return confirmation(trigger)
			elif entryTwoConfirmation(shift, trigger.direction):
				trigger.entry_state = EntryState.COMPLETE
				return confirmation(trigger)

		# Entry Three
		if trigger.entry_three_state == EntryThreeState.TWO:
			if entryThreeConfirmation(shift, trigger.direction):
				trigger.entry_three_state = EntryThreeState.COMPLETE
				return confirmation(trigger)
			else:
				trigger.entry_three_state = EntryThreeState.ONE

		if isBlackParaConfirmation(shift, trigger.direction, reverse=True):
			trigger.entry_state = EntryState.ONE
			return

def entryOneConfirmation(shift, trigger):
	print("Entry ONE ("+str(trigger.direction)+"):", 
			str(isAllParaConfirmation(shift, trigger.direction)),
			str(isMacdConfirmation(trigger.direction)),
			str(isCciConfirmation(shift, trigger.direction)),
			str(isRsiConfirmation(shift, trigger.direction)),
			str(isCloseABBlackPara(shift, trigger.direction))
		)
	return (
			isAllParaConfirmation(shift, trigger.direction) and
			isMacdConfirmation(trigger.direction) and
			isCciConfirmation(shift, trigger.direction) and
			isRsiConfirmation(shift, trigger.direction) and
			isCloseABBlackPara(shift, trigger.direction)
		)

def entryTwoConfirmation(shift, direction):
	print("Entry TWO ("+str(direction)+"):",
			str(isAllParaConfirmation(shift, direction)),
			str(isCandleOutside(shift, direction))
		)

	return (
			isAllParaConfirmation(shift, direction) and
			isCandleOutside(shift, direction)
		)

def entryThreeConfirmation(shift, direction):
	print("Entry THREE ("+str(direction)+"):",
			str(isYellowABLast(shift, direction)),
			str(isPurpleABLast(shift, direction))
		)

	return isYellowABLast(shift, direction) and isPurpleABLast(shift, direction)

def isAllParaConfirmation(shift, direction, reverse=False):
	if reverse:
		return (
				isOrangeParaConfirmation(shift, direction, reverse=True) and
				isPurpleParaConfirmation(shift, direction, reverse=True) and
				isBlackParaConfirmation(shift, direction, reverse=True)
			)
	else:
		return (
				isOrangeParaConfirmation(shift, direction) and
				isPurpleParaConfirmation(shift, direction) and
				isBlackParaConfirmation(shift, direction)
			)

def isCandleOutside(shift, direction):
	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

	last_strand = getLastDirectionBlackStrand(direction)
	if last_strand:
		cross_sar = last_strand.start
	else:
		return False

	if direction == Direction.LONG:
		low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

		return low > cross_sar

	else:
		high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

		return high < cross_sar

def isCloseABBlackPara(shift, direction):
	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
	close = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	last_strand = getLastDirectionBlackStrand(direction)
	if last_strand and last_strand.end != 0:
		cross_sar = last_strand.end
	else:
		return False

	if direction == Direction.LONG:
		return close > cross_sar

	else:
		return close < cross_sar

def isYellowABLast(shift, direction):
	
	if direction == Direction.LONG:
		current = getNumberDirectionYellowStrand(Direction.SHORT, 0)
		last = getNumberDirectionYellowStrand(Direction.SHORT, 1)

		if current and last:
			return current.start > last.start + VARIABLES['sar_min_diff'] * 0.0001

	else:
		current = getNumberDirectionYellowStrand(Direction.LONG, 0)
		last = getNumberDirectionYellowStrand(Direction.LONG, 1)

		if current and last:
			return current.start < last.start - VARIABLES['sar_min_diff'] * 0.0001

	return False

def isPurpleABLast(shift, direction):
	
	if direction == Direction.LONG:
		current = getNumberDirectionPurpleStrand(Direction.SHORT, 0)
		last = getNumberDirectionPurpleStrand(Direction.SHORT, 1)

		if current and last:
			return current.start > last.start + VARIABLES['sar_min_diff'] * 0.0001

	else:
		current = getNumberDirectionPurpleStrand(Direction.LONG, 0)
		last = getNumberDirectionPurpleStrand(Direction.LONG, 1)

		if current and last:
			return current.start < last.start - VARIABLES['sar_min_diff'] * 0.0001

	return False

def isOrangeParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.LONG:
			return orange_sar.isFalling(shift, 1)[0]
		else:
			return orange_sar.isRising(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return orange_sar.isRising(shift, 1)[0]
		else:
			return orange_sar.isFalling(shift, 1)[0]

def isPurpleParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.LONG:
			return purple_sar.isFalling(shift, 1)[0]
		else:
			return purple_sar.isRising(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return purple_sar.isRising(shift, 1)[0]
		else:
			return purple_sar.isFalling(shift, 1)[0]

def isBlackParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.LONG:
			return black_sar.isFalling(shift, 1)[0]
		else:
			return black_sar.isRising(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return black_sar.isRising(shift, 1)[0]
		else:
			return black_sar.isFalling(shift, 1)[0]

def isMacdConfirmation(direction, reverse = False):
	hist = macd.getCurrent()[2]
	histz = macdz.getCurrent()[2]
	print("hist:", str(hist), "histz:", str(histz))

	if reverse:
		if direction == Direction.LONG:
			return hist <= -VARIABLES['macd_threshold'] * 0.00001 and histz <= 0
		else:
			return hist >= VARIABLES['macd_threshold'] * 0.00001 and histz >= 0

	else:
		if direction == Direction.LONG:
			return hist >= VARIABLES['macd_threshold'] * 0.00001 and histz >= 0
		else:
			return hist <= -VARIABLES['macd_threshold'] * 0.00001 and histz <= 0

def isCciConfirmation(shift, direction, reverse = False):
	chidx = cci.getCurrent()[0]
	cci_signal = cci.getSignalLine(2, shift, 1)[0]

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

def isRsiConfirmation(shift, direction, reverse = False):
	stridx = rsi.get(shift, 2)

	if reverse:
		if direction == Direction.LONG:
			return stridx[0] < stridx[1]
		else:
			return stridx[0] > stridx[1]
	else:
		if direction == Direction.LONG:
			return stridx[0] > stridx[1]
		else:
			return stridx[0] < stridx[1]

def confirmation(trigger):
	''' confirm entry '''

	print("confirmation:", str(trigger.direction), str(trigger.count))

	trigger.entry_state = EntryState.ONE
	trigger.entry_three_state = EntryThreeState.ONE
	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	print("ORANGE STRANDS:", str(len(orange_strands)))
	print("BLACK STRANDS:", str(len(black_strands)))
	if current_strand:
		print("Current strand:", str(current_strand.direction), str(current_strand.length)+"\n")

	print("LONG T:", str(long_trigger.entry_state))
	print("SHORT T:", str(short_trigger.entry_state)+"\n")

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
