from CMCTrader import Constants
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	'START_TIME' : '23:00',
	'END_TIME' : '16:00',
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
	def __init__(self, direction):
		self.direction = direction
		self.state = State.POSITIVE

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

def backtest():
	''' Run on every new backtest bar '''

	print("backtest")

	runSequence(0)

	report()


def onDownTime():
	''' Function called outside of trading time '''

	print("onDownTime")
	utils.printTime(utils.getAustralianTime())

	runSequence(0)

	for entry in pending_entries:
		del pending_entries[pending_entries.index(entry)]

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
					handleRegularEntry(entry)
					del pending_entries[pending_entries.index(entry)]
					current_trigger = None

def runSequence(shift):
	''' Main trade plan sequence '''
	onNewCycle(shift)
	cancelInvalidStrands(shift)
	getExtremeStrands()
	getTrigger(shift)

	entrySetup(shift)

def getTrigger(shift):
	''' Form trigger in direction of black cross '''

	if (isCrossedLong(shift)):
		if (current_trigger == None or current_trigger.direction == Direction.SHORT):
			current_trigger = Trigger(Direction.LONG)
			getMostRecentStrands(Direction.LONG)

	elif (isCrossedShort(shift)):
		if (current_trigger == None or current_trigger.direction == Direction.LONG):
			current_trigger = Trigger(Direction.SHORT)
			getMostRecentStrands(Direction.SHORT)

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''

	if (reg_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		
		for strand in strands[::-1]:
			if (strand.sar_type == SARType.REG and not strand.end == 0):
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

		print("New Strand:", str(strand.direction), ":", str(strand.start))
		

	if (slow_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		
		for strand in strands[::-1]:
			if (strand.sar_type == SARType.SLOW and not strand.end == 0):
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

		print("New Strand:", str(strand.direction), ":", str(strand.start))

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

	if (not max_strand == None):
		if (black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0] < max_strand.start and black_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
			
			strands[strands.index(max_strand)].isPassed = True
			print("black para crossed long")

			return True

	return False

def isCrossedShort(shift):
	''' Check if black sar has passed the current min strand on rising black '''

	if (not min_strand == None):
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
	for strand in direction[::-1]:

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

	for stand in strands:
		if (strand.direction == direction and strand.isPassed):
			strand.isPassed = False

def getLongStrands():
	return [i for i in strands if i.direction == Direction.LONG and not i.isPassed and not i.end == 0]

def getShortStrands():
	return [i for i in strands if i.direction == Direction.SHORT and not i.isPassed and not i.end == 0]

def entrySetup(shift):
	''' Checks for swing sequence once trigger has been formed '''

	if (not current_trigger == None):
		if (current_trigger.state == State.POSITIVE):
			crossNegative(shift)
		elif (current_trigger.state == State.NEGATIVE):
			crossPositive(shift)

def crossNegative(shift):
	''' Checks for swing to first be in negative direction '''

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (current_trigger.direction == Direction.LONG):
		if (ch_idx < VARIABLES['cci_threshold']):
			current_trigger.state = State.NEGATIVE
	
	else:
		if (ch_idx > VARIABLES['cci_threshold']):
			current_trigger.state = State.NEGATIVE

def crossPositive(shift):
	''' Checks for swing to be in positive direction '''

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
		print("CURRENT TRIGGER:", current_trigger.direction)
	else:
		print("CURRENT TRIGGER: None")

	print("PENDING ENTRIES")
	count = 0
	for entry in pending_entries:
		count += 1
		print(str(count) + ":", str(entry.direction))