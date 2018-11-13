from CMCTrader import Constants
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	# 'START_TIME' : '23:00',
	# 'END_TIME' : '16:00',
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'profit_limit' : 85,
	'maximum_bank' : 1000,
	'PLAN' : None,
	'stoprange' : 17,
	'breakeven_point' : 34,
	'full_profit' : 200,
	'rounding' : 100,
	'breakeven_min_pips' : 2,
	'CLOSING SEQUENCE' : None,
	'no_more_trades_in_profit' : '15:00',
	'no_more_trades' : '15:30',
	'set_breakeven' : '15:50',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5,
	'RSI' : None,
	'rsi_overbought' : 75,
	'rsi_oversold' : 25,
	'rsi_threshold' : 50,
	'CCI' : None,
	'cci_threshold' : 0,
	'MACD' : None,
	'macd_threshold' : 0
}

utils = None

reg_sar = None
slow_sar = None
black_sar = None
rsi = None
cci = None
macd = None

current_trigger = None

strands = []
long_strands = []
short_strands = []
max_strand = None
min_strand = None

pending_entries = []
pending_breakevens = []

is_position_breakeven = False

current_news = None
news_trade_block = False

stop_trading = False
no_new_trades = False

is_profit_nnt = False
is_nnt = False
is_be = False

bank = 0

class Direction(Enum):
	LONG = 1
	SHORT = 2

class State(Enum):
	POSITIVE = 1
	NEGATIVE = 2
	ENTERED = 3

class Trigger(object):
	def __init__(self, direction, tradable):
		self.direction = direction
		self.state = State.POSITIVE
		self.tradable = tradable

class SARType(Enum):
	REG = 1
	SLOW = 2

class Strand(object):
	def __init__(self, direction, sar_type, start):
		self.direction = direction
		self.sar_type = sar_type
		self.start = start
		self.end = 0
		self.isPassed = False

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global reg_sar, slow_sar, black_sar, rsi, cci, macd

	utils = utilities
	reg_sar = utils.SAR(1)
	black_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	rsi = utils.RSI(4, 1)
	cci = utils.CCI(5, 1)
	macd = utils.MACD(6, 1)

	global current_trigger
	current_trigger = Trigger(Direction.SHORT, tradable = False)

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	global bank, stop_trading, no_new_trades
	global is_profit_nnt, is_nnt, is_be

	if (utils.getBankSize() > VARIABLES['maximum_bank']):
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

	if (stop_trading):
		onDownTime()
		return

	print("\nonNewBar")
	checkTime()

	utils.printTime(utils.getAustralianTime())

	runSequence(0)

	report()

def onDownTime():
	''' Function called outside of trading time '''

	print("onDownTime")
	ausTime = utils.printTime(utils.getAustralianTime())

	runSequence(0)

	report()

	for entry in pending_entries:
		del pending_entries[pending_entries.index(entry)]

def onLoop():
	''' Function called on every program iteration '''

	if (no_new_trades and len(utils.positions) <= 0):
		global stop_trading
		stop_trading = True

	if (stop_trading):
		return

	handleEntries()		# Handle all pending entries
	handleBreakeven()	# Handle all pending breakeven

def handleEntries():
	''' Handle all pending entries '''

	global no_new_trades, current_trigger

	for entry in pending_entries:
		
		if (entry.direction == Direction.LONG):
			
			if (len(utils.positions) > 0):
				for pos in utils.positions:
					if (pos.direction == 'buy'):
						del pending_entries[pending_entries.index(entry)]
						current_trigger = None
						break
				
				if (no_new_trades):
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					current_trigger = entry
					current_trigger.state = State.POSITIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: stop and reverse")
					handleStopAndReverse(pos)
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None

			else:

				if (no_new_trades):
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					current_trigger = entry
					current_trigger.state = State.POSITIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: regular")
					handleRegularEntry(entry)
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None

		else:

			if (len(utils.positions) > 0):
				for pos in utils.positions:
					if (pos.direction == 'sell'):
						del pending_entries[pending_entries.index(entry)]
						current_trigger = None
						break
				
				if (no_new_trades):
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					current_trigger = entry
					current_trigger.state = State.POSITIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter short: stop and reverse")
					handleStopAndReverse(pos)
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None

			else:

				if (no_new_trades):
					print("Trade blocked!")
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					current_trigger = entry
					current_trigger.state = State.POSITIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter short: regular")
					handleRegularEntry(entry)
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None


def handleStopAndReverse(pos):
	''' 
	Handle stop and reverse entries 
	and check if tradable conditions are met.
	'''

	global is_position_breakeven

	current_profit = utils.getTotalProfit() + pos.getProfit()
	loss_limit = -VARIABLES['stoprange'] * 1.5
	
	if (current_profit < loss_limit or current_profit > VARIABLES['profit_limit']):
		print("Tradable conditions not met:", str(current_profit))
		pos.quickExit()
		stop_trading = True
	else:
		print("Entered")
		pos.stopAndReverse(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		is_position_breakeven = False

def handleRegularEntry(entry):
	''' 
	Handle regular entries 
	and check if tradable conditions are met.
	'''

	global is_position_breakeven

	current_profit = utils.getTotalProfit()
	loss_limit = -VARIABLES['stoprange'] * 1.5

	if (current_profit < loss_limit or current_profit > VARIABLES['profit_limit']):
		print("Tradable conditions not met:", str(current_profit))
		stop_trading = True
	else:
		print("Entered")
		if (entry.direction == Direction.LONG):
			utils.buy(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		else:
			utils.sell(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		is_position_breakeven = False

def handleBreakeven():
	''' 
	Handle all pending breakevens
	and positions that have exceeded breakeven threshold
	'''

	global is_position_breakeven

	for pos in utils.positions:
		
		if (pos.getProfit() >= VARIABLES['breakeven_point'] and not is_position_breakeven):
			print("Reached BREAKEVEN point:", str(pos.getProfit()))
			is_position_breakeven = True
			pos.breakeven()
			if (not pos.apply()):
				pending_breakevens.append(pos)

		if pos in pending_breakevens:
			if (pos.getProfit() > VARIABLES['breakeven_min_pips']):
				pos.breakeven()
				if (pos.apply()):
					del pending_breakevens[pending_breakevens.index(pos)]

def failsafe(timestamps):
	''' Function called on any error or interuption '''

	global current_trigger

	print("failsafe")
	print("Missing timestamps:", str(timestamps[VARIABLES['TICKETS'][0]]))

	earliest = utils.getEarliestTimestamp(timestamps[VARIABLES['TICKETS'][0]])
	offset = utils.getBarOffset(earliest)

	i = 0
	for timestamp in timestamps[VARIABLES['TICKETS'][0]]:
		
		current_shift = offset - i
		print("Backtesting Time:", str(utils.convertTimestampToTime(timestamp)))

		runSequence(current_shift)

		if (len(pending_entries) > 0):
			current_trigger = pending_entries[-1]
			current_trigger.state = State.POSITIVE

			for entry in pending_entries:
				del pending_entries[pending_entries.index(entry)]

def onNews(title, time):
	''' 
	Block new trades 
	and set current position to breakeven on news.
	'''

	global current_news

	print("NEWS:", str(title))
	be_time = time - datetime.timedelta(minutes = VARIABLES['newsTimeBeforeBE'])
	no_trade_time = time - datetime.timedelta(minutes = VARIABLES['newsTimeBeforeBlock'])
	
	if (be_time <= utils.getLondonTime() < time):
		print(str(title), "done")
		for pos in utils.positions:
			if not pos in pending_breakevens:
				print(str(time), "current pos to breakeven on NEWS")
				pending_breakevens.append(pos)
	
	if (no_trade_time <= utils.getLondonTime() < time):
		print("no trades, 5 mins")
		current_news = time
	
	elif (utils.getLondonTime() > time):
		if (current_news == time):
			print("reset current news")
			current_news = None
		if (title.startswith('_')):
			del utils.newsTimes[title]

def checkCurrentNews():
	''' Block new trades if there is news currently in action '''

	global news_trade_block

	if (not current_news == None):
		news_trade_block = True
	else:
		news_trade_block = False

def checkTime():
	''' 
	Checks current time and initiates 
	closing sequence where necessary.
	'''

	global is_profit_nnt, is_nnt, is_be, no_new_trades

	london_time = utils.getLondonTime()
	parts = VARIABLES['no_more_trades_in_profit'].split(':')
	profit_nnt_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['no_more_trades'].split(':')
	nnt_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['set_breakeven'].split(':')
	be_time = utils.createLondonTime(london_time.year, london_time.month, london_time.day, int(parts[0]), int(parts[1]), 0)

	if (london_time > be_time and not is_be):
		print("Set breakeven")
		no_new_trades = True
		is_be = True
		for pos in utils.positions:
			if (pos.getProfit() >= VARIABLES['breakeven_min_pips']):
				if not pos in pending_breakevens:
					pending_breakevens.append(pos)
			else:
				pending_breakevens.append(pos)
	
	elif (london_time > nnt_time and not is_nnt and not is_be):
		print("No more trades")
		no_new_trades = True
		is_nnt = True
	
	elif (london_time > profit_nnt_time and not is_profit_nnt and not is_nnt and not is_be):
		print("No more trades in profit")
		print("Total profit:", str(utils.getTotalProfit()))
		if (utils.getTotalProfit() >= VARIABLES['breakeven_point']):
			is_profit_nnt = True
			no_new_trades = True

	return

def runSequence(shift):
	''' Main trade plan sequence '''
	onNewCycle(shift)
	cancelInvalidStrands(shift)
	getExtremeStrands()
	getTrigger(shift)

	entrySetup(shift)

def getTrigger(shift):
	''' Form trigger in direction of black cross '''

	global current_trigger

	if (isCrossedLong(shift)):
		if (current_trigger == None or current_trigger.direction == Direction.SHORT):
			print("New trigger long!")
			current_trigger = Trigger(Direction.LONG)
			getMostRecentStrands(Direction.LONG)

	elif (isCrossedShort(shift)):
		if (current_trigger == None or current_trigger.direction == Direction.LONG):
			print("New trigger short!")
			current_trigger = Trigger(Direction.SHORT)
			getMostRecentStrands(Direction.SHORT)

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''

	if (reg_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		
		for strand in strands[::-1]:
			if (strand.sar_type == SARType.REG and strand.end == 0):
				strand.end = reg_sar.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
				print("End of last strand:", str(strand.end))
				break

		if (reg_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			strand = Strand(Direction.LONG, SARType.REG, reg_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])

			strands.append(strand)
			long_strands.append(strand)
		else:
			strand = Strand(Direction.SHORT, SARType.REG, reg_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
			
			strands.append(strand)
			short_strands.append(strand)

		print("New REG Strand:", str(strand.direction), ":", str(strand.start))
		

	if (slow_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		
		for strand in strands[::-1]:
			if (strand.sar_type == SARType.SLOW and strand.end == 0):
				strand.end = slow_sar.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
				print("End of last strand:", str(strand.end))
				break

		if (slow_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			strand = Strand(Direction.LONG, SARType.SLOW, slow_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])

			strands.append(strand)
			long_strands.append(strand)
		else:
			strand = Strand(Direction.SHORT, SARType.SLOW, slow_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
			
			strands.append(strand)
			short_strands.append(strand)

		print("New SLOW Strand:", str(strand.direction), ":", str(strand.start))

def cancelInvalidStrands(shift):
	''' 
	Cancel any short strands that are not wholly above (on rising black)
	or long strands wholly below (on falling black) on new black cycle.
	'''

	global long_strands, short_strands

	if (black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		
		if (black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			for strand in getShortStrands():
				if (black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0] > strand.end):
					print("passed rising:", str(strand.end))
					strand.isPassed = True
		
		else:
			for strand in getLongStrands():
				if (black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0] < strand.end):
					print("passed falling:", str(strand.end))
					strand.isPassed = True

def isCrossedLong(shift):
	''' Check if black sar has passed the current max strand on falling black '''
	print(max_strand)
	if (not max_strand == None):
		print(max_strand.start)
		if (black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0] < max_strand.start and black_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
	
			strands[strands.index(max_strand)].isPassed = True
			print("black para crossed long")

			return True

	return False

def isCrossedShort(shift):
	''' Check if black sar has passed the current min strand on rising black '''
	print(min_strand)
	if (not min_strand == None):
		print(min_strand.start)
		if (black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0] > min_strand.start and black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			
			strands[strands.index(min_strand)].isPassed = True
			print("black para crossed short")

			return True

	return False

def getExtremeStrands():
	''' 
	Get current short strand at the highest point
	and current long strand at the lowest point
	of all valid strands.
	'''

	global max_strand, min_strand
	
	max_strand = None
	for i in getLongStrands():
		if not max_strand == None:
			if i.start > max_strand.start and not i.isPassed:
				max_strand = i
		elif not i.isPassed:
			max_strand = i

	min_strand = None
	for j in getShortStrands():
		if not min_strand == None:
			if j.start < min_strand.start and not j.isPassed:
				min_strand = j
		elif not j.isPassed:
			min_strand = j

def getMostRecentStrands(direction):
	''' 
	Gets the most recent reg and slow sar strand
	in specified direction and deletes all other strands.
	'''

	resetStrands(direction)
	
	direction_strands = [i for i in strands if i.direction == direction and not i.isPassed and not i.end == 0]
	isFoundReg = False
	isFoundSlow = False
	for strand in direction_strands[::-1]:

		if (strand.sar_type == SARType.REG):
			if (isFoundReg):
				del strands[strands.index(strand)]
			else:
				isFoundReg = True

		elif (strand.sar_type == SARType.SLOW):
			if (isFoundSlow):
				del strands[strands.index(strand)]
			else:
				isFoundSlow = True

def resetStrands(direction):
	''' Resets all strands in specified direction to not passed '''

	for strand in strands:
		if (strand.direction == direction and strand.isPassed):
			strand.isPassed = False

def getLongStrands():
	return [i for i in strands if i.direction == Direction.LONG and not i.isPassed and not i.end == 0]

def getShortStrands():
	return [i for i in strands if i.direction == Direction.SHORT and not i.isPassed and not i.end == 0]

def entrySetup(shift):
	''' Checks for swing sequence once trigger has been formed '''

	if (not current_trigger == None and current_trigger.tradable):
		if (current_trigger.state == State.POSITIVE):
			crossNegative(shift)
		elif (current_trigger.state == State.NEGATIVE):
			crossPositive(shift)

def crossNegative(shift):
	''' Checks for swing to first be in negative direction '''

	print("crossNegative")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (current_trigger.direction == Direction.LONG):
		if (ch_idx < VARIABLES['cci_threshold']):
			current_trigger.state = State.NEGATIVE
	
	else:
		if (ch_idx > VARIABLES['cci_threshold']):
			current_trigger.state = State.NEGATIVE

def crossPositive(shift):
	''' Checks for swing to be in positive direction '''

	print("crossPositive")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (current_trigger.direction == Direction.LONG):
		if (ch_idx > VARIABLES['cci_threshold']):
			if (str_idx > VARIABLES['rsi_threshold']):
				if (hist >= VARIABLES['macd_threshold'] or isParaConfirmation(shift, Direction.LONG)):
					current_trigger.state = State.ENTERED
					confirmation(shift)
					return
			
			current_trigger.state = State.POSITIVE
	
	else:
		if (ch_idx < VARIABLES['cci_threshold']):
			if (str_idx < VARIABLES['rsi_threshold']):
				if (hist <= VARIABLES['macd_threshold'] or isParaConfirmation(shift, Direction.SHORT)):
					current_trigger.state = State.ENTERED
					confirmation(shift)
					return
			
			current_trigger.state = State.POSITIVE

def isParaConfirmation(shift, direction):
	''' Finds if both sar are in correct direction for confirmation '''

	if (direction == Direction.LONG):
		return reg_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slow_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
	else:
		return reg_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slow_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def confirmation(shift):
	''' Checks for overbought, oversold and confirm entry '''

	print("confirmation")

	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	
	if (current_trigger.direction == Direction.LONG):
		if (str_idx > VARIABLES['rsi_overbought']):
			current_trigger.state = State.POSITIVE
		else:
			pending_entries.append(current_trigger)
	
	else:
		if (str_idx < VARIABLES['rsi_oversold']):
			current_trigger.state = State.POSITIVE
		else:
			pending_entries.append(current_trigger)


def report():
	''' Prints report for debugging '''

	if (not current_trigger == None):
		print("CURRENT TRIGGER:", current_trigger.direction, current_trigger.state)
	else:
		print("CURRENT TRIGGER: None")

	print("CLOSED POSITIONS:")
	count = 0
	for pos in utils.closedPositions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit())

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", pos.direction, "Profit:", pos.getProfit())