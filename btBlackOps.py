from CMCTrader import Constants
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	'START_TIME' : '23:00',
	'END_TIME' : '19:00',
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
	'no_more_trades' : '18:00',
	'set_breakeven' : '15:50',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5,
	'TRIGGER' : None,
	'sar_size' : 25,
	'RSI' : None,
	'rsi_overbought' : 75,
	'rsi_oversold' : 25,
	'rsi_threshold' : 50,
	'CCI' : None,
	'cci_t_cross' : 80,
	'cci_ct_cross' : 50,
	'cci_entry_cross' : 0,
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
re_entry_trigger = None

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
	SWING_ONE = 1
	SWING_TWO = 2
	SWING_THREE = 3
	CROSS_NEGATIVE = 4
	ENTERED = 5

class Trigger(object):
	def __init__(self, direction, start, tradable = False):
		self.direction = direction
		self.start = start
		self.state = State.SWING_ONE
		self.tradable = tradable

class SARType(Enum):
	REG = 1
	SLOW = 2

class Strand(object):
	def __init__(self, direction, start):
		self.direction = direction
		self.start = start
		self.is_completed = False

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

	onNewCycle(0)	
	if (isCompletedStrand()):
		getTrigger(0)

	report()

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

	if (isCompletedStrand()):
		getTrigger(shift)

	entrySetup(shift, current_trigger)
	entrySetup(shift, re_entry_trigger, no_conf = True)

def getTrigger(shift):
	''' Form trigger in direction of black cross '''

	global current_trigger

	if (black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		
		if (black_sar.strandCount(VARIABLES['TICKETS'][0], shift + 1) >= VARIABLES['sar_size']):
			current_trigger = Trigger(strands[-2].direction, strands[-2].start, tradable = True)
		
		else:
			current_trigger = Trigger(strands[-2].direction, strands[-2].start)

	if (not current_trigger == None and not current_trigger.tradable):
		
		if (current_trigger.direction == Direction.LONG):
			if (hasCrossedAbove(shift)):
				current_trigger.tradable = True

		else:
			if (hasCrossedBelow(shift)):
				current_trigger.tradable = True

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''

	if (black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):

		if (len(strands) > 0):
			strands[-1].is_completed = True

		if (black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			direction = Direction.SHORT
		else:
			direction = Direction.LONG

		strand = Strand(direction, black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
		strands.append(strand)

		print("New Strand:", str(strand.direction), str(strand.start))

def isCompletedStrand():
	for strand in strands:
		if (strand.is_completed):
			return True

	return False

def hasCrossedBelow(shift):
	''' Check if black sar has passed the current max strand on falling black '''
	
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if (low < current_trigger.start):
		print("crossed black para below")
		return True

	return False

def hasCrossedAbove(shift):
	''' Check if black sar has passed the current min strand on rising black '''

	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]

	if (high > current_trigger.start):
		print("black para crossed above")
		return True

	return False

def entrySetup(shift, trigger, no_conf = False):
	''' Checks for swing sequence once trigger has been formed '''

	if (not trigger == None and trigger.tradable):

		if (trigger.state == State.SWING_ONE):
			if (swingOne(shift, trigger.direction)):
				trigger.state = State.SWING_TWO

		elif (trigger.state == State.SWING_TWO):
			if (swingTwo(shift, trigger.direction)):
				trigger.state = State.SWING_THREE

		elif (trigger.state == State.SWING_THREE):
			result = swingThree(shift, trigger.direction, no_conf)
			if (result == 1):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)
			elif (result == 0):
				trigger.state = State.CROSS_NEGATIVE
		
		elif (trigger.state == State.CROSS_NEGATIVE):
			if (crossNegative(shift, trigger.direction)):
				trigger.state = State.SWING_THREE
				
				entrySetup(shift, trigger)


def swingOne(shift, direction):
	''' Checks for swing to first be in negative direction '''

	print("swingOne")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (direction == Direction.LONG):
		if (ch_idx >= VARIABLES['cci_t_cross']):
			return True
	
	else:
		if (ch_idx <= -VARIABLES['cci_t_cross']):
			return True

	return False

def swingTwo(shift, direction):

	print("swingTwo")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (direction == Direction.LONG):
		if (ch_idx <= -VARIABLES['cci_ct_cross']):
			return True
	
	else:
		if (ch_idx >= VARIABLES['cci_ct_cross']):
			return True

	return False

def swingThree(shift, direction, no_conf):

	print("swingThree")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (direction == Direction.LONG):
		if (ch_idx > VARIABLES['cci_entry_cross']):

			if (no_conf):
				return 1

			if (str_idx > VARIABLES['rsi_threshold'] or hist > VARIABLES['macd_threshold']):
				if (isParaConfirmation(shift, Direction.LONG)):
					return 1
			return 0
		return -1
	
	else:
		if (ch_idx < VARIABLES['cci_entry_cross']):
			if (str_idx < VARIABLES['rsi_threshold'] or hist < VARIABLES['macd_threshold']):
				if (isParaConfirmation(shift, Direction.SHORT)):
					return 1
			return 0
		return -1

def isParaConfirmation(shift, direction):
	''' Finds if both sar are in correct direction for confirmation '''

	if (direction == Direction.LONG):
		return reg_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slow_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
	else:
		return reg_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slow_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def crossNegative(shift, direction):
	''' Checks for swing to be in positive direction '''

	print("crossNegative")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (direction == Direction.LONG):
		if (ch_idx < VARIABLES['cci_entry_cross']):
			return True
	
	else:
		if (ch_idx > VARIABLES['cci_entry_cross']):
			return True

	return False

def confirmation(shift, trigger):
	''' Checks for overbought, oversold and confirm entry '''

	global re_entry_trigger

	print("confirmation")

	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	
	if (trigger.direction == Direction.LONG):
		if (str_idx > VARIABLES['rsi_overbought']):
			trigger.state = State.CROSS_NEGATIVE
		else:
			pending_entries.append(trigger)
			re_entry_trigger = None
	
	else:
		if (str_idx < VARIABLES['rsi_oversold']):
			trigger.state = State.CROSS_NEGATIVE
		else:
			pending_entries.append(trigger)
			re_entry_trigger = None

def report():
	''' Prints report for debugging '''

	if (not current_trigger == None):
		print("CURRENT TRIGGER:", str(current_trigger.direction), "tradable:", str(current_trigger.tradable))
	else:
		print("CURRENT TRIGGER: None")

	if (not re_entry_trigger == None):
		print("RE-ENTRY TRIGGER:", re_entry_trigger.direction, re_entry_trigger.state)

	print("PENDING ENTRIES")
	count = 0
	for entry in pending_entries:
		count += 1
		print(str(count) + ":", str(entry.direction))

	print("--|\n")