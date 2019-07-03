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
	'macd_z_threshold': 5,
	'SAR': None,
	'sar_min_diff': 0.5,
	'sar_e2_min_diff': 1,
	'RSI': None,
	'rsi_overbought': 75,
	'rsi_oversold': 25
}

class Direction(Enum):
	LONG = 1
	SHORT = 2

class EntryState(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	FOUR = 4
	COMPLETE = 5

class EntryTwoState(Enum):
	ONE = 1
	COMPLETE = 2

class EntryThreeState(Enum):
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
		
		self.entry_state = EntryState.ONE
		self.entry_two_state = EntryTwoState.ONE
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
	global purple_sar, black_sar, yellow_sar, macd, macdz, rsi, cci

	utils = utilities
	purple_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.06, 0.2) # 0.06
	yellow_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.04, 0.2) # 0.04
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

	print("Starting Bank:", str(bank))

	
def setGlobalVars():
	global bank, stop_trading, no_new_trades
	global long_trigger, short_trigger
	global purple_strands, black_strands, yellow_strands
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
	tz_start_time = utils.convertTimezone(utils.startTime, VARIABLES['TIMEZONE'])
	nnt_time = utils.createNewYorkTime(tz_start_time.year, tz_start_time.month, tz_start_time.day, int(parts[0]), int(parts[1]), 0)
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
	print("Y:", str(yellow_sar.getCurrent()),  "P:", str(purple_sar.getCurrent()), "B:", str(black_sar.getCurrent()))

	onNewPurpleStrand(shift)
	onNewYellowStrand(shift)
	onNewBlackStrand(shift)

	entrySetup(shift, long_trigger)
	entrySetup(shift, short_trigger)
	entryTwoSetup(shift, long_trigger)
	entryTwoSetup(shift, short_trigger)
	entryThreeSetup(shift, long_trigger)
	entryThreeSetup(shift, short_trigger)

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

def getNumberDirectionBlackStrand(direction, num):
	count = 0
	for i in range(len(black_strands)):
		if black_strands[i].direction == direction:
			if count == num:
				return black_strands[i]
			count += 1

	return None

def getLastDirectionBlackStrand(direction):
	for i in range(len(black_strands)):
		if black_strands[i].direction == direction:
			return black_strands[i]

	return None

def entrySetup(shift, trigger):

	if trigger:

		if trigger.entry_state == EntryState.ONE:
			if isAllParaConfirmation(shift, trigger.direction):
				trigger.entry_state = EntryState.TWO
				return entrySetup(shift, trigger)

		elif trigger.entry_state == EntryState.TWO:
			if entryThreeParaConf(shift, trigger.direction, reverse=True):
				trigger.entry_state = EntryState.THREE
				return entrySetup(shift, trigger)

		elif trigger.entry_state == EntryState.THREE:
			if entryThreeParaConf(shift, trigger.direction):
				trigger.entry_state = EntryState.FOUR
				return entrySetup(shift, trigger)

		elif trigger.entry_state == EntryState.FOUR:
			if entryOneConfirmation(shift, trigger):
				trigger.entry_state = EntryState.COMPLETE
			# if entryTwoConfirmation(shift, trigger.direction):
			# 	trigger.entry_state = EntryState.COMPLETE

		if isBlackParaConfirmation(shift, trigger.direction, reverse=True):
			trigger.entry_state = EntryState.ONE
			return

def entryThreeSetup(shift, trigger):
	if trigger:

		if trigger.entry_three_state == EntryThreeState.ONE:
			if entryThreeParaConf(shift, trigger.direction):
				trigger.entry_three_state = EntryThreeState.TWO
				return entryThreeSetup(shift, trigger)

		elif trigger.entry_three_state == EntryThreeState.TWO:
			if entryThreeParaConf(shift, trigger.direction, reverse=True):
				trigger.entry_three_state = EntryThreeState.ONE
				return entryThreeSetup(shift, trigger)

			elif trigger.entry_state.value >= EntryState.FOUR.value:

				if trigger.entry_state == EntryState.COMPLETE:
					if entryThreeConfirmation(shift, trigger.direction):
						trigger.entry_three_state = EntryThreeState.COMPLETE
						return confirmation(trigger)

			elif entryThreeConfirmation(shift, trigger.direction):
				trigger.entry_three_state = EntryThreeState.COMPLETE
				return confirmation(trigger)

def entryTwoSetup(shift, trigger):
	if trigger:

		if trigger.entry_two_state == EntryTwoState.ONE:
			if entryTwoConfirmation(shift, trigger.direction):
				trigger.entry_two_state = EntryTwoState.COMPLETE
				return confirmation(trigger)


def entryOneConfirmation(shift, trigger):
	print("Entry ONE ("+str(trigger.direction)+"):",
			str(isAllParaConfirmation(shift, trigger.direction)),
			str(isMacdConfirmation(trigger.direction)),
			str(isRsiConfirmation(shift, trigger.direction)),
			str(isCciConfirmation(shift, trigger.direction)),
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
			str(isCloseHLPrevBlackPara(shift, direction)),
			str(isAllParaConfirmation(shift, direction)),
			str(isMacdEntryTwoConfirmation(shift, direction)),
			str(isRsiConfirmation(shift, direction)),
			str(isRsiObos(shift, direction))
		)

	return (
			isCloseHLPrevBlackPara(shift, direction) and
			isAllParaConfirmation(shift, direction) and
			isMacdEntryTwoConfirmation(shift, direction) and
			isRsiConfirmation(shift, direction) and
			isRsiObos(shift, direction)
		)

def entryThreeConfirmation(shift, direction):
	print("Entry THREE ("+str(direction)+"):",
			str(isYellowABLast(shift, direction)),
			str(isPurpleABLast(shift, direction)),
			str(entryThreeParaConf(shift, direction)),
			str(isRsiConfirmation(shift, direction)),
			str(isMacdEntryThreeConfirmation(direction))
		)

	return (
			isYellowABLast(shift, direction) and 
			isPurpleABLast(shift, direction) and
			entryThreeParaConf(shift, direction) and
			isRsiConfirmation(shift, direction) and
			isMacdEntryThreeConfirmation(direction)
		)

def isAllParaConfirmation(shift, direction, reverse=False):

	return (
			isPurpleParaConfirmation(shift, direction, reverse=reverse) and
			isYellowParaConfirmation(shift, direction, reverse=reverse) and
			isBlackParaConfirmation(shift, direction, reverse=reverse)
		)


def entryThreeParaConf(shift, direction, reverse=False):
	return (
			isPurpleParaConfirmation(shift, direction, reverse=reverse) and
			isYellowParaConfirmation(shift, direction, reverse=reverse)
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

def isCloseHLPrevBlackPara(shift, direction):
	one = getNumberDirectionBlackStrand(direction, 0)
	two = getNumberDirectionBlackStrand(direction, 1)
	three = getNumberDirectionBlackStrand(direction, 2)
	four = getNumberDirectionBlackStrand(direction, 3)

	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
	close = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	if one and two and three and four:

		if direction == Direction.LONG:
			cross_sar = max(one.start, two.start, three.start, four.start)

			return close >= round(cross_sar + VARIABLES['sar_e2_min_diff'] * 0.0001, 5)
		else:
			cross_sar = min(one.start, two.start, three.start, four.start)

			return close <= round(cross_sar - VARIABLES['sar_e2_min_diff'] * 0.0001, 5)

def isYellowABLast(shift, direction):
	
	if direction == Direction.LONG:
		current = getNumberDirectionYellowStrand(Direction.SHORT, 0)
		last = getNumberDirectionYellowStrand(Direction.SHORT, 1)

		if current and last:
			return current.start >= round(last.start + VARIABLES['sar_min_diff'] * 0.0001, 5)

	else:
		current = getNumberDirectionYellowStrand(Direction.LONG, 0)
		last = getNumberDirectionYellowStrand(Direction.LONG, 1)

		if current and last:
			return current.start <= round(last.start - VARIABLES['sar_min_diff'] * 0.0001, 5)

	return False

def isPurpleABLast(shift, direction):
	
	if direction == Direction.LONG:
		current = getNumberDirectionPurpleStrand(Direction.SHORT, 0)
		last = getNumberDirectionPurpleStrand(Direction.SHORT, 1)

		if current and last:
			return current.start >= round(last.start + VARIABLES['sar_min_diff'] * 0.0001, 5)

	else:
		current = getNumberDirectionPurpleStrand(Direction.LONG, 0)
		last = getNumberDirectionPurpleStrand(Direction.LONG, 1)

		if current and last:
			return current.start <= round(last.start - VARIABLES['sar_min_diff'] * 0.0001, 5)

	return False

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

def isYellowParaConfirmation(shift, direction, reverse = False):

	if reverse:
		if direction == Direction.LONG:
			return yellow_sar.isFalling(shift, 1)[0]
		else:
			return yellow_sar.isRising(shift, 1)[0]
	
	else:
		if direction == Direction.LONG:
			return yellow_sar.isRising(shift, 1)[0]
		else:
			return yellow_sar.isFalling(shift, 1)[0]

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

	if reverse:
		if direction == Direction.LONG:
			return hist <= -round(VARIABLES['macd_threshold'] * 0.00001, 5)
		else:
			return hist >= round(VARIABLES['macd_threshold'] * 0.00001, 5)

	else:
		if direction == Direction.LONG:
			return hist >= round(VARIABLES['macd_threshold'] * 0.00001, 5)
		else:
			return hist <= -round(VARIABLES['macd_threshold'] * 0.00001, 5)

def isMacdEntryThreeConfirmation(direction, reverse = False):
	hist = macd.getCurrent()[2]
	histz = macdz.getCurrent()[2]
	print("hist:", str(hist), "histz:", str(histz))

	if reverse:
		if direction == Direction.LONG:
			return hist <= -round(VARIABLES['macd_threshold'] * 0.00001, 5) or histz <= -round(VARIABLES['macd_z_threshold'] * 0.00001, 5)
		else:
			return hist >= round(VARIABLES['macd_threshold'] * 0.00001, 5) or histz >= round(VARIABLES['macd_z_threshold'] * 0.00001, 5)

	else:
		if direction == Direction.LONG:
			return hist >= round(VARIABLES['macd_threshold'] * 0.00001, 5) or histz >= round(VARIABLES['macd_z_threshold'] * 0.00001, 5)
		else:
			return hist <= -round(VARIABLES['macd_threshold'] * 0.00001, 5) or histz <= -round(VARIABLES['macd_z_threshold'] * 0.00001, 5)

def isMacdEntryTwoConfirmation(direction, reverse=False):
	hist = macd.getCurrent()[2]

	if reverse:
		if direction == Direction.LONG:
			return hist < 0
		else:
			return hist > 0

	else:
		if direction == Direction.LONG:
			return hist > 0
		else:
			return hist < 0

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

def isRsiObos(shift, direction):
	stridx = rsi.getCurrent()[0]

	if direction == Direction.LONG:
		return stridx >= VARIABLES['rsi_overbought']
	else:
		return stridx <= VARIABLES['rsi_oversold']

def confirmation(trigger):
	''' confirm entry '''

	print("confirmation:", str(trigger.direction), str(trigger.count))

	trigger.entry_state = EntryState.ONE
	trigger.entry_two_state = EntryTwoState.ONE
	trigger.entry_three_state = EntryThreeState.ONE
	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

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
