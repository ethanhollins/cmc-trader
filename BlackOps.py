from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	'START_TIME' : '1:30',
	'END_TIME' : '19:00',
	'FIXED_SL' : 17,
	'FIXED_TP' : 200,
	'INDIVIDUAL' : None,
	'risk' : 1.0,
	'profit_limit' : 51,
	'maximum_bank' : 500,
	'PLAN' : None,
	'stoprange' : 17,
	'breakeven_point' : 34,
	'full_profit' : 200,
	'rounding' : 100,
	'breakeven_min_pips' : 2,
	'CLOSING SEQUENCE' : None,
	'no_more_trades_in_profit' : '16:00',
	'no_more_trades' : '18:00',
	'set_breakeven' : '15:50',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5,
	'TRIGGER' : None,
	'sar_size' : 30,
	'num_paras_momentum' : 4,
	'RSI' : None,
	'rsi_overbought' : 75,
	'rsi_oversold' : 25,
	'rsi_threshold' : 50,
	'CCI' : None,
	'cci_t_cross' : 75,
	'cci_ct_cross' : 50,
	'cci_entry_cross' : 0,
	'cci_obos' : 70,
	'MACD' : None,
	'macd_threshold' : 0
}

current_trigger = None
re_entry_trigger = None

block_direction = None

class Strands(list):
	def __getitem__(self, row):
		return sorted(list(self), key=lambda x: x.count, reverse = True)[row]

	def getSorted(self):
		return sorted(list(self), key=lambda x: x.count, reverse = True)

strands = Strands()
position_strands = Strands()
current_brown = None

pending_entries = []
pending_breakevens = []
pending_exits = []

is_position_breakeven = False

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
	SWING_TWO = 2
	SWING_THREE = 3
	CROSS_NEGATIVE = 4
	HIT_PARA = 5
	OBOS = 6
	ENTERED = 7

class Strand(dict):
	def __init__(self, direction, start):
		self.direction = direction
		self.start = start
		self.end = 0
		self.is_completed = False
		self.count = len(strands)

	@classmethod
	def fromDict(cls, dic):
		cpy = cls(dic['direction'], dic['start'])
		for key in dic:
			cpy[key] = dic[key]
		return cpy

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

	def __deepcopy__(self, memo):
		return Strand.fromDict(dict(self))

class Trigger(dict):
	def __init__(self, direction, start, tradable = False, is_re_entry = False):
		self.direction = direction
		self.start = start
		self.state = State.SWING_ONE
		self.tradable = tradable
		self.is_re_entry = is_re_entry
		self.last_obos = 0
		self.ct_conf = False

	@classmethod
	def fromDict(cls, dic):
		cpy = cls(dic['direction'], dic['start'], tradable = dic['tradable'], is_re_entry = dic['is_re_entry'])
		for key in dic:
			cpy[key] = dic[key]
		return cpy

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

	def __deepcopy__(self, memo):
		return Trigger.fromDict(dict(self))

class BrownStrand(dict):
	def __init__(self, shift):
		self.num_points = 2
		self.to_hit = self.getToHit(shift)
		self.is_hit = False

	@classmethod
	def fromDict(cls, dic):
		cpy = cls(0)
		for key in dic:
			cpy[key] = dic[key]
		return cpy
	
	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

	def __deepcopy__(self, memo):
		return BrownStrand.fromDict(dict(self))
	
	def getToHit(self, shift):
		for i in range(self.num_points):
			current_shift = shift + i
			if (brown_sar.isNewCycle(VARIABLES['TICKETS'][0], current_shift)):

				print("Brown sar:", str(brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]))
				return brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]

		print("Brown sar end:", str(brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]))
		return brown_sar.get(VARIABLES['TICKETS'][0], current_shift, 1)[0]

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global reg_sar, slow_sar, black_sar, brown_sar, rsi, cci, macd

	utils = utilities
	reg_sar = utils.SAR(1)
	black_sar = utils.SAR(2)
	slow_sar = utils.SAR(3)
	brown_sar = utils.SAR(4)
	rsi = utils.RSI(5, 1)
	cci = utils.CCI(6, 1)
	macd = utils.MACD(7, 1)

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

	resetPositionStrands(Direction.LONG)
	resetPositionStrands(Direction.SHORT)

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
	handleExits(0)

	report()

def onDownTime():
	''' Function called outside of trading time '''

	print("onDownTime")
	ausTime = utils.printTime(utils.getAustralianTime())

	# onNewCycle(0)
	
	# if (isCompletedStrand()):
	# 	getTrigger(0)

	report()

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
						return
				
				if (no_new_trades):
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_re_entry = True)
					re_entry_trigger.state = State.CROSS_NEGATIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: stop and reverse")
					handleStopAndReverse(pos, entry)

			else:

				if (no_new_trades):
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_re_entry = True)
					re_entry_trigger.state = State.CROSS_NEGATIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter long: regular")
					handleRegularEntry(entry)

		else:

			if (len(utils.positions) > 0):
				for pos in utils.positions:
					if (pos.direction == 'sell'):
						del pending_entries[pending_entries.index(entry)]
						return
				
				if (no_new_trades):
					print("Trade blocked! Current position exited.")
					pos.quickExit()
					del pending_entries[pending_entries.index(entry)]
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_re_entry = True)
					re_entry_trigger.state = State.CROSS_NEGATIVE

					del pending_entries[pending_entries.index(entry)]
				else:
					print("Attempting position enter short: stop and reverse")
					handleStopAndReverse(pos, entry)

			else:

				if (no_new_trades):
					print("Trade blocked!")
					del pending_entries[pending_entries.index(entry)]
				elif (news_trade_block):
					print("Trade blocked on NEWS! Trigger reset.")
					re_entry_trigger = Trigger(entry.direction, entry.start, tradable = False, is_re_entry = True)
					re_entry_trigger.state = State.CROSS_NEGATIVE

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

	global is_position_breakeven

	current_profit = utils.getTotalProfit() + pos.getProfit()
	loss_limit = -VARIABLES['stoprange'] * 2
	
	if (current_profit < loss_limit or current_profit > VARIABLES['profit_limit']):
		print("Tradable conditions not met:", str(current_profit))
		pos.quickExit()
		stop_trading = True
	else:
		print("Entered")
		pos.stopAndReverse(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['full_profit'])
		
		is_position_breakeven = False

		resetPositionStrands(Direction.LONG)
		resetPositionStrands(Direction.SHORT)
		getPositionStrand(0)

	del pending_entries[pending_entries.index(entry)]

@Backtester.skip_on_recover
def handleRegularEntry(entry):
	''' 
	Handle regular entries 
	and check if tradable conditions are met.
	'''

	global is_position_breakeven

	current_profit = utils.getTotalProfit()
	loss_limit = -VARIABLES['stoprange'] * 2

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

		resetPositionStrands(Direction.LONG)
		resetPositionStrands(Direction.SHORT)
		getPositionStrand(0)

	del pending_entries[pending_entries.index(entry)]

@Backtester.skip_on_recover
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

@Backtester.skip_on_recover
def handleExits(shift):

	global pending_exits

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	is_exit = False

	for exit in pending_exits:

		if (exit.direction == Direction.LONG):
			if (ch_idx < VARIABLES['cci_entry_cross']):
				is_exit = True
				for pos in utils.positions:
					pos.quickExit()

		else:
			if (ch_idx > VARIABLES['cci_entry_cross']):
				is_exit = True
				for pos in utils.positions:
					pos.quickExit()

	if (is_exit):
		pending_exits = []
		resetPositionStrands(Direction.LONG)
		resetPositionStrands(Direction.SHORT)

def onStopLoss(pos):
	print("onStopLoss")

	global re_entry_trigger

	if (pos.direction == 'buy'):
		re_entry_trigger = Trigger(Direction.LONG, 0, tradable = True, is_re_entry = True)
		re_entry_trigger.state = State.CROSS_NEGATIVE
	else:
		re_entry_trigger = Trigger(Direction.SHORT, 0, tradable = True, is_re_entry = True)
		re_entry_trigger.state = State.CROSS_NEGATIVE

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
			re_entry_trigger = Trigger(pending_entries[-1].direction, pending_entries[-1].start, tradable = False, is_re_entry = True)
			re_entry_trigger.state = State.CROSS_NEGATIVE

			for entry in pending_entries:
				del pending_entries[pending_entries.index(entry)]

def onNews(title, time):
	''' 
	Block new trades 
	and set current position to breakeven on news.
	'''

	global current_news

	print("NEWS:", str(title))
	be_time = time - datetime.timedelta(minutes = VARIABLES['time_threshold_no_trades'])
	no_trade_time = time - datetime.timedelta(minutes = VARIABLES['time_threshold_no_trades'])
	
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
		if (not re_entry_trigger == None and not re_entry_trigger.tradable):
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

	if (london_time.hour < utils.endTime.hour and london_time.hour >= 0):
		pass
	else:
		profit_nnt_time += datetime.timedelta(days=1)
		nnt_time += datetime.timedelta(days=1)
		be_time += datetime.timedelta(days=1)

	# if (london_time > be_time and not is_be):
	# 	print("Set breakeven")
	# 	no_new_trades = True
	# 	is_be = True
	# 	for pos in utils.positions:
	# 		if (pos.getProfit() >= VARIABLES['breakeven_min_pips']):
	# 			if not pos in pending_breakevens:
	# 				pending_breakevens.append(pos)
	# 		else:
	# 			pending_breakevens.append(pos)
	print(str(london_time), str(utils.endTime))
	if (london_time > utils.endTime and not is_end_time):
		is_endTime = True
		print("End time: looking to exit")
		for pos in utils.positions:
			if (pos.direction == 'buy'):
				pending_exits.append(Trigger(Direction.LONG, 0))
			else:
				pending_exits.append(Trigger(Direction.SHORT, 0))

	elif (london_time > nnt_time and not is_nnt and not is_end_time):
		print("No more trades")
		no_new_trades = True
		is_nnt = True
	
	elif (london_time > profit_nnt_time and not is_profit_nnt and not is_nnt and not is_end_time):
		print("No more trades in profit")
		print("Total profit:", str(utils.getTotalProfit()))
		if (utils.getTotalProfit() >= VARIABLES['breakeven_point']):
			is_profit_nnt = True
			no_new_trades = True


def runSequence(shift):
	''' Main trade plan sequence '''
	onNewCycle(shift)
	
	if (isCompletedStrand()):
		getTrigger(shift)

	entrySetup(shift, current_trigger)
	entrySetup(shift, re_entry_trigger, no_conf = True)

	momentumEntry(shift)

def getTrigger(shift):
	''' Form trigger in direction of black cross '''

	global current_trigger

	if (black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):

		if (black_sar.strandCount(VARIABLES['TICKETS'][0], shift + 1) > VARIABLES['sar_size']):
			
			if (black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
				direction = Direction.LONG
				setCurrentTrigger(direction)

				current_trigger.tradable = True

			elif (black_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
				direction = Direction.SHORT
				setCurrentTrigger(direction)

				current_trigger.tradable = True
		
		else:
			
			if (black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
				direction = Direction.LONG
				setCurrentTrigger(direction)

			elif (black_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
				direction = Direction.SHORT
				setCurrentTrigger(direction)

	if (not current_trigger == None and not current_trigger.tradable):
		
		if (current_trigger.direction == Direction.LONG):
			if (hasCrossedAbove(shift, current_trigger)):
				current_trigger.tradable = True

		else:
			if (hasCrossedBelow(shift, current_trigger)):
				current_trigger.tradable = True

def setCurrentTrigger(direction):
	global current_trigger

	if (not current_trigger == None and current_trigger.direction == direction):
		return
			
	start = getLastStrandStart(direction)

	current_trigger = Trigger(direction, start)

def getLastStrandStart(direction):
	for strand in strands.getSorted():
		if (not strand.direction == direction):
			return strand.start

def onNewCycle(shift):
	''' 
	Capture regular and slow sar strands once
	a strand has started their new cycle.
	'''

	if (black_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):

		if (len(strands) > 0):
			strands[0].is_completed = True
			strands[0].end = black_sar.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
		
		if (len(strands) > 1):
			isWhollyCrossed()

		if (black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			direction = Direction.SHORT
		else:
			direction = Direction.LONG

		strand = Strand(direction, black_sar.get(VARIABLES['TICKETS'][0], shift, 1)[0])
		strands.append(strand)

		print("New Strand:", str(strand.direction), str(strand.start))

		getPositionStrand(shift)


	global current_brown
	
	if (brown_sar.isNewCycle(VARIABLES['TICKETS'][0], shift)):

		if (not current_trigger == None):
			
			if (current_trigger.direction == Direction.LONG and brown_sar.isFalling(VARIABLES['TICKETS'][0], shift + 1, 1)[0]):
				current_brown = BrownStrand(shift + 1)
			
			elif (current_trigger.direction == Direction.SHORT and brown_sar.isRising(VARIABLES['TICKETS'][0], shift + 1, 1)[0]):
				current_brown = BrownStrand(shift + 1)

def isWhollyCrossed():

	global block_direction

	first = strands[1]
	second = strands[0]

	if (second.direction == Direction.SHORT):
		if (second.start < first.start and second.end > first.end):
			block_direction = Direction.SHORT
		else:
			block_direction = None

	else:
		if (second.start > first.start and second.end < first.end):
			block_direction = Direction.LONG
		else:
			block_direction = None

def isCompletedStrand():
	for strand in strands:
		if (strand.is_completed):
			return True

	return False

def hasCrossedBelow(shift, item):
	''' Check if black sar has passed the current max strand on falling black '''
	
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if (low < item.start):
		print("crossed black para below")
		return True

	return False

def hasCrossedAbove(shift, item):
	''' Check if black sar has passed the current min strand on rising black '''

	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]

	if (high > item.start):
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
			if (swingTwo(shift, trigger)):
				trigger.ct_conf = False
				trigger.state = State.SWING_THREE

		elif (trigger.state == State.SWING_THREE):
			result = swingThree(shift, trigger.direction, no_conf)
			if (result == 1):
				trigger.state = State.HIT_PARA

				entrySetup(shift, trigger, no_conf = no_conf)
			
			elif (result == 0):
				trigger.state = State.CROSS_NEGATIVE
		
		elif (trigger.state == State.CROSS_NEGATIVE):
			if (crossNegative(shift, trigger)):
				trigger.ct_conf = False
				trigger.state = State.SWING_THREE
				
				entrySetup(shift, trigger, no_conf = no_conf)

		elif (trigger.state == State.HIT_PARA):
			result = paraHit(shift, trigger.direction, no_conf)

			if (result == 1):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)
			elif (result == 0):
				trigger.state = State.CROSS_NEGATIVE

				entrySetup(shift, trigger, no_conf = no_conf)

		elif (trigger.state == State.OBOS):
			if (onOBOS(shift, trigger)):
				trigger.state = State.ENTERED
				confirmation(shift, trigger)


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

def swingTwo(shift, trigger):

	print("swingTwo")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (trigger.direction == Direction.LONG):
		if (ch_idx <= -VARIABLES['cci_ct_cross'] or trigger.ct_conf):
			trigger.ct_conf = True
			if (isBrownParaConfirmation(shift, trigger.direction)):
				return True
	
	else:
		if (ch_idx >= VARIABLES['cci_ct_cross'] or trigger.ct_conf):
			trigger.ct_conf = True
			if (isBrownParaConfirmation(shift, trigger.direction)):
				return True

	return False

def swingThree(shift, direction, no_conf):

	print("swingThree")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (direction == Direction.LONG):
		if (ch_idx > VARIABLES['cci_entry_cross']):

			if (no_conf):
				return 1

			if (swingConfirmation(shift, direction)):
				return 1
			else:
				return 0

		return -1
	
	else:
		if (ch_idx < VARIABLES['cci_entry_cross']):

			if (no_conf):
				return 1

			if (swingConfirmation(shift, direction)):
				return 1
			else:
				return 0

		return -1

def swingConfirmation(shift, direction):
	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (direction == Direction.LONG):

		if (str_idx > VARIABLES['rsi_threshold'] or hist > VARIABLES['macd_threshold']):
			if (isRegParaConfirmation(shift, direction)):
				return True
		return False
	
	else:

		if (str_idx < VARIABLES['rsi_threshold'] or hist < VARIABLES['macd_threshold']):
			if (isRegParaConfirmation(shift, direction)):
				return True
		return False

def isRegParaConfirmation(shift, direction):
	''' Finds if both sar are in correct direction for confirmation '''

	if (direction == Direction.LONG):
		return reg_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
	else:
		return reg_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def isBrownParaConfirmation(shift, direction, reverse = False):
	if (not reverse):
		if (direction == Direction.SHORT):
			return brown_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
		else:
			return brown_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]
	
	else:
		if (direction == Direction.LONG):
			return brown_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
		else:
			return brown_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def paraHit(shift, direction, no_conf):
	
	brownHit(shift, direction)

	if (current_brown.is_hit and isSlowParaConfirmation(shift, direction) and isBrownParaConfirmation(shift, direction, reverse = True)):
		
		if (no_conf):
			return 1

		if (swingConfirmation(shift, direction)):
			return 1
		else:
			return 0

	return -1

def brownHit(shift, direction):

	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if (direction == Direction.LONG):
		if (high > current_brown.to_hit):
			current_brown.is_hit = True

	else:
		if (low < current_brown.to_hit):
			current_brown.is_hit = True

def isSlowParaConfirmation(shift, direction):

	if (direction == Direction.LONG):
		return slow_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]
	else:
		return slow_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]

def crossNegative(shift, trigger):
	''' Checks for swing to be in positive direction '''

	print("crossNegative")

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (trigger.direction == Direction.LONG):
		if (ch_idx < VARIABLES['cci_entry_cross'] or trigger.ct_conf):
			if (isBrownParaConfirmation(shift, trigger.direction)):
				return True
	
	else:
		if (ch_idx > VARIABLES['cci_entry_cross'] or trigger.ct_conf):
			if (isBrownParaConfirmation(shift, trigger.direction)):
				return True

	return False

def onOBOS(shift, trigger):

	ch_idx = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (trigger.direction == Direction.LONG):

		if (str_idx < VARIABLES['rsi_overbought']):
			if (str_idx > trigger.last_obos and ch_idx > -VARIABLES['cci_obos']):
				return True

		else:
			trigger.last_obos = str_idx
			return False

	else:

		if (str_idx > VARIABLES['rsi_oversold']):
			if (str_idx < trigger.last_obos and ch_idx < VARIABLES['cci_obos']):
				return True

		else:
			trigger.last_obos = str_idx
			return False

def confirmation(shift, trigger):
	''' Checks for overbought, oversold and confirm entry '''

	global re_entry_trigger, block_direction

	print("confirmation")

	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	
	if (trigger.direction == Direction.LONG):
		
		if (block_direction == Direction.LONG and not trigger.is_re_entry):
			trigger.state = State.CROSS_NEGATIVE
			block_direction = None

		elif (str_idx >= VARIABLES['rsi_overbought']):
			trigger.state = State.OBOS
			current_trigger.last_obos = str_idx
		
		else:
			pending_entries.append(trigger)
			re_entry_trigger = None
	
	else:
		if (block_direction == Direction.SHORT and not trigger.is_re_entry):
			trigger.state = State.CROSS_NEGATIVE
			block_direction = None

		elif (str_idx <= VARIABLES['rsi_oversold']):
			trigger.state = State.OBOS
			current_trigger.last_obos = str_idx
		
		else:
			pending_entries.append(trigger)
			re_entry_trigger = None

def resetPositionStrands(direction):
	global position_strands

	for strand in position_strands:
		if (strand.direction == direction):
			del position_strands[position_strands.index(strand)]

def getPositionStrand(shift):
	print("getPositionStrand")
	position_strands.append(strands[0])
	return

	for pos in utils.positions:
		if (pos.direction == 'buy'):
			print("get buy strand")
		if (black_sar.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			print("add strand")
			position_strands.append(strands[0])

		else:
			if (black_sar.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
				position_strands.append(strands[0])

def momentumEntry(shift):
	global re_entry_trigger, position_strands, current_trigger

	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (len(utils.positions) <= 0):

		handleMomentumEntry(shift, Direction.LONG)
		handleMomentumEntry(shift, Direction.SHORT)

	elif (utils.positions[0].direction == 'buy'):

		handleMomentumEntry(shift, Direction.SHORT)

	elif (utils.positions[0].direction == 'sell'):

		handleMomentumEntry(shift, Direction.LONG)

def getMomentumCrossStrand(count, direction):
	last_strands = []

	print(position_strands.getSorted())

	for strand in position_strands.getSorted():
		if (len(last_strands) >= count):
			break

		if (strand.direction == direction):
			last_strands.append(strand)

	if (len(last_strands) < count):
		return None

	if (direction == Direction.LONG):
		cross_strand = sorted(last_strands, key=lambda x: x.start, reverse=True)[0]
	else:
		cross_strand = sorted(last_strands, key=lambda x: x.start)[0]

	return cross_strand

def handleMomentumEntry(shift, direction):
	cross_strand = getMomentumCrossStrand(VARIABLES['num_paras_momentum'], direction)

	print("Cross Strand:", str(cross_strand))

	if (not cross_strand == None):

		if (hasCrossedBelow(shift, cross_strand)):

			if (current_trigger.direction == direction):
				if (current_trigger.state.value >= State.OBOS.value):
					print("Swing entry blocked momentum entry short!")
					position_strands = []
					return

			if (not isObos(shift, direction)):
				print("Entering on momentum entry short!")
				
				entry = Trigger(direction, 0, tradable = True)
				pending_entries.append(entry)
				re_entry_trigger = None

			else:
				print("Oversold on momentum entry")

				current_trigger = Trigger(direction, 0, tradable = True)
				current_trigger.state = State.OBOS
				current_trigger.last_obos = str_idx
		
			resetPositionStrands(direction)

def isObos(shift, direction):

	str_idx = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (direction == Direction.LONG):

		if (str_idx >= VARIABLES['rsi_overbought']):
			return True
		else:
			return False

	else:

		if (str_idx <= VARIABLES['rsi_oversold']):
			return True
		else:
			return False


def report():
	''' Prints report for debugging '''

	if (not current_trigger == None):
		print("CURRENT TRIGGER:", current_trigger.direction, current_trigger.state)
	else:
		print("CURRENT TRIGGER: None")

	if (not re_entry_trigger == None):
		print("RE-ENTRY TRIGGER:", re_entry_trigger.direction, re_entry_trigger.state)

	if (not block_direction == None):
		print("BLOCK DIRECTION:", str(block_direction))

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

	print("--|\n")

def onBacktestFinish():
	global pending_entries

	if (len(pending_entries) > 0):
		entry = pending_entries[-1]

		re_entry_trigger = Trigger(entry.direction, entry.start, tradable = True)
		re_entry_trigger.state = State.CROSS_NEGATIVE

		pending_entries = []

class SaveState(object):
	def __init__(self):
		self.saved_vars = {}
		self.saved_names = self.getCopyable()
		self.save()

	def getCopyable(self):
		names = []
		
		for i in globals():	
			try:
				copy.deepcopy(globals()[i])
				names.append(i)
			except:
				continue

		return names

	def save(self):
		self.saved_names = self.getCopyable()

		for name in self.saved_names:
			self.saved_vars[name] = copy.deepcopy(globals()[name])

	def load(self):
		for name in self.saved_names:
			globals()[name] = self.saved_vars[name]
