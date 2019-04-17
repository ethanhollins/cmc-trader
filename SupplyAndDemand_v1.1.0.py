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
	'close_exit_only' : '13:00',
	'NEWS' : None,
	'time_threshold_breakeven' : 1,
	'time_threshold_no_trades' : 5,
	'CONFIRMATION' : None,
	'min_diff' : 0.2,
	'SAR' : None,
	'sar_count_cancel_tolerance' : 4,
	'MACD H' : None,
	'macdh_ct_threshold' : 4,
	'RSI' : None,
	'rsi_overbought': 70,
	'rsi_oversold': 30,
	'rsi_supply_start': 70,
	'rsi_supply_end': 40,
	'rsi_demand_start': 30,
	'rsi_demand_end': 60,
	'rsi_confirmed': 50
}

class SortedList(list):
	def __getitem__(self, row):
		return sorted(list(self), key=lambda x: x.count, reverse = True)[row]

	def getSorted(self):
		return sorted(list(self), key=lambda x: x.count, reverse = True)

on_down_time = False

current_triggers = SortedList()

strands = SortedList()

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

class FibOneState(Enum):
	ONE = 1
	TWO = 2
	COMPLETE = 3

class FibTwoState(Enum):
	ONE = 1
	TWO = 2
	COMPLETE = 3

class TriggerMomentumState(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	COMPLETE = 4

class TrendVertexCrossState(Enum):
	ONE = 1
	TWO = 2
	COMPLETE = 3

class TriggerAnchorState(Enum):
	NONE = 1
	ACTIVE = 2
	COMPLETE = 3

class TrendState(Enum):
	ONE = 1
	TWO = 2
	COMPLETE = 3

class TimeState(Enum):
	TRADING = 1
	NNT = 2
	CLOSE = 3

class ExitType(Enum):
	NONE = 1
	IMMEDIATE = 2
	CROSS = 3

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

class Trigger(dict):
	static_count = 0

	def __init__(self, direction, start, is_anchor = False):
		self.direction = direction
		self.start = start
		self.end = 0
		self.tradable = False
		self.trendlines = []

		self.fib_one_state = FibOneState.ONE
		self.fib_two_state = FibTwoState.ONE
		self.t_momentum_state = TriggerMomentumState.ONE

		if is_anchor:
			self.t_anchor = TriggerAnchorState.ACTIVE
		else:
			self.t_anchor = TriggerAnchorState.NONE

		self.count = Trigger.static_count

		Trigger.static_count += 1

	def getFibPercent(self, percent):
		percent *= .01
		if self.end != 0:
			if self.direction == Direction.LONG:
				return round(self.end - ( abs( self.end - self.start ) * percent ), 5)
			else:
				return round(self.end + ( abs( self.end - self.start ) * percent ), 5)
		else:
			return None

	def deleteOnCompleted(self):
		if (
			self.fib_one_state == FibOneState.COMPLETE and
			# self.t_momentum_state == TriggerMomentumState.COMPLETE and
			(self.t_anchor == TriggerAnchorState.NONE or self.t_anchor == TriggerAnchorState.COMPLETE)
			):
			print("DELETED")
			del current_triggers[current_triggers.index(self)]

	def isOutsideBounds(self, trend):
		if self.t_anchor == TriggerAnchorState.ACTIVE:
			if self.direction == Direction.LONG:
				if trend.start < self.start:
					self.t_anchor = TriggerAnchorState.COMPLETE
					return True
			else:
				if trend.start > self.start:
					self.t_anchor = TriggerAnchorState.COMPLETE
					return True

		return False

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class TrendLine(dict):
	def __init__(self, start, trigger):
		self.start = start
		self.trigger = trigger
		self.end = 0
		self.tradable = False
		self.trend_state = TrendState.ONE

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class StopState(Enum):
	NONE = 1
	BREAKEVEN = 2
	FIRST = 3

time_state = TimeState.TRADING
stop_state = StopState.NONE

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global sar, cci, macd, macdz, rsi

	utils = utilities
	sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.2, 0.2)
	cci = utils.CCI(Constants.GBPUSD, Constants.ONE_MINUTE, 5)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)

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

	for direction in pending_exits:

		if isParaConfirmation(shift, direction, reverse = True):
			print("Attempting exit")
			is_exit = True
			for pos in utils.positions:
				pos.quickExit()

	if is_exit:
		pending_exits = []

def onTrade(pos, event):
	return

def onEntry(pos):
	print("onEntry")

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

	if not (time.hour < utils.endTime.hour and time.hour >= 0):
		profit_nnt_time += datetime.timedelta(days=1)
		nnt_time += datetime.timedelta(days=1)

	print(str(time), str(utils.endTime))

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
	onNewCycle(shift)

	getTrigger(shift)

	for t in current_triggers:
		for trend in t.trendlines:
			trendSetup(shift, trend)

		fibOneSetup(shift, t)
		fibTwoSetup(shift, t)
		# triggerMomentumSetup(shift, t)
	
	for t in current_triggers:
		t.deleteOnCompleted() 

def getTrigger(shift):

	new_direction = isRsiStartPointConf()

	if new_direction:
		
		t_dir = getDirectionTrigger(new_direction)
		if t_dir:
			current_trend = t_dir.trendlines[-1]
			if current_trend.trend_state == TrendState.TWO:
				current_trend.trend_state = TrendState.COMPLETE

			chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

			if current_trend.trend_state == TrendState.COMPLETE:
				if new_direction == Direction.LONG:

					# Delete long direction inside trend-lines
					if t_dir.end != 0 and (current_trend.start > t_dir.start and current_trend.end < t_dir.end):
						del t_dir.trendlines[t_dir.trendlines.index(current_trend)]

					start = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
				else:

					# Delete short direction inside trend-lines
					if t_dir.end != 0 and (current_trend.start < t_dir.start and current_trend.end > t_dir.end):
						del t_dir.trendlines[t_dir.trendlines.index(current_trend)]

					start = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

				if t_dir.fib_one_state.value > FibOneState.ONE.value:
					createNewTrigger(shift, new_direction)
				else:
					t_dir.trendlines.append(TrendLine(start, t_dir))
					
		else:
			createNewTrigger(shift, new_direction)

def trendSetup(shift, trend):

	if not trend.trend_state == TrendState.COMPLETE:

		if trend.trend_state == TrendState.ONE:

			if trend.trigger.direction == Direction.LONG:
				trend.start = getTrendLow(shift, trend.start)

				if trend.trigger.start == 0 or trend.start < trend.trigger.start:
					trend.trigger.start = trend.start
			else:
				trend.start = getTrendHigh(shift, trend.start)

				if trend.trigger.start == 0 or trend.start > trend.trigger.start:
					trend.trigger.start = trend.start

			if isRsiEndPointConf(trend):
				last_trend = getLastIncompleteTrend(trend.trigger)

				if last_trend:
					last_trend.trend_state = TrendState.COMPLETE

				trend.trend_state = TrendState.TWO

				for trigger in current_triggers:
					if trigger.t_anchor == TriggerAnchorState.ACTIVE and trigger.direction != trend.trigger.direction:
						if trigger.isOutsideBounds(trend):
							print("IS OUTSIDE BOUNDS")
							del trend.trigger.trendlines[trend.trigger.trendlines.index(trend)]

							createNewTrigger(shift, trend.trigger.direction, start = trend.start, trend = trend)

				return trendSetup(shift, trend)

		elif trend.trend_state == TrendState.TWO:

			if trend.trigger.direction == Direction.LONG:
				trend.end = getTrendHigh(shift, trend.end)

				if trend.trigger.end == 0 or trend.end > trend.trigger.end:
					trend.trigger.end = trend.end
			else:
				trend.end = getTrendLow(shift, trend.end)

				if trend.trigger.end == 0 or trend.end < trend.trigger.end:
					trend.trigger.end = trend.end

			if isRsiConfirmationPointConf(trend):
				trend.tradable = True
				trend.trigger.tradable = True

def getTrendLow(shift, x):
	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

	low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]
	if low < x or x == 0:
		return low
	else:
		return x

def getTrendHigh(shift, x):
	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

	high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	if high > x or x == 0:
		return high
	else:
		return x

def getLastIncompleteTrend(trigger):
	for i in range(len(trigger.trendlines) - 1, -1, -1):
		if trigger.trendlines[i].tradable and trigger.trendlines[i].trend_state != TrendState.COMPLETE:
			return trigger.trendlines[i]

	return None

def createNewTrigger(shift, direction, start = None, trend = None):
	print("NEW TRIGGER CREATED")


	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

	if not start:
		if direction == Direction.LONG:
			start = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
		else:
			start = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	t = Trigger(direction, start)

	if trend:
		t.trendlines.append(trend)
	else:
		t.trendlines.append(TrendLine(start, t))

	t_list = [i for i in current_triggers if i.direction == t.direction]
	
	if len(t_list) == 0:
		t.t_anchor = TriggerAnchorState.ACTIVE
	else:
		for trigger in t_list:
			if trigger.t_anchor == TriggerAnchorState.ACTIVE:
				break

			if t_list.index(trigger) == len(t_list) - 1:
				t.t_anchor = TriggerAnchorState.ACTIVE

	current_triggers.append(t)

def getDirectionTrigger(direction):
	t_dirs = [i for i in current_triggers if i.direction == direction]

	if len(t_dirs) > 0:
		return t_dirs[-1]

	return None

def isRsiStartPointConf():
	stridx = rsi.getCurrent()[0]

	if stridx < VARIABLES['rsi_demand_start']:
		return Direction.LONG
	elif stridx > VARIABLES['rsi_supply_start']:
		return Direction.SHORT

	return None

def isRsiEndPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.trigger.direction == Direction.LONG:
		return stridx > VARIABLES['rsi_demand_end']
	else:
		return stridx < VARIABLES['rsi_supply_end']

def isRsiConfirmationPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.trigger.direction == Direction.LONG:
		return stridx < VARIABLES['rsi_confirmed']
	else:
		return stridx > VARIABLES['rsi_confirmed']

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

			last_strand = getNthDirectionStrand(opp_direction, 1)

			last_strand.is_completed = True
			last_strand.end = sar.get(shift + 1, 1)[0]
			last_strand.length = sar.strandCount(shift + 1)

		strands.append(strand)
		print("New Strand:", str(strand.direction))

def getNthDirectionStrand(direction, count):

	current_count = 0
	for i in range(len(strands)):
		if strands[i].direction == direction:
			current_count += 1
			if count == current_count:
				return strands[i]

	return None

def fibOneSetup(shift, trigger):

	if not trigger == None and trigger.tradable and not trigger.fib_one_state == FibOneState.COMPLETE:

		if trigger.fib_one_state == FibOneState.ONE:
			fib_val = trigger.getFibPercent(72)
			print("72 Line", str(trigger.count)+": " + str(fib_val))

			if trigger.direction == Direction.LONG:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]
				
				if fib_val and low <= fib_val:
					trigger.fib_one_state = FibOneState.TWO
					return fibOneSetup(shift, trigger)

			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

				if fib_val and high >= fib_val:
					trigger.fib_one_state = FibOneState.TWO
					return fibOneSetup(shift, trigger)

		elif trigger.fib_one_state == FibOneState.TWO:

			if isFibEntryCancelled(shift, trigger, trigger.getFibPercent(72)):
				trigger.fib_one_state = FibOneState.COMPLETE
				return

			elif isEntryConfirmation(shift, trigger.direction):
				trigger.fib_one_state = FibOneState.COMPLETE
				return confirmation(trigger)

def fibTwoSetup(shift, trigger):

	if not trigger == None and trigger.tradable and not trigger.fib_two_state == FibTwoState.COMPLETE:

		if trigger.fib_two_state == FibTwoState.ONE:
			fib_val = trigger.getFibPercent(100)
			print("100 Line", str(trigger.count)+": " + str(fib_val))

			if trigger.direction == Direction.LONG:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]
				
				if fib_val and low <= fib_val:
					trigger.fib_two_state = FibTwoState.TWO
					return fibTwoSetup(shift, trigger)

			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

				if fib_val and high >= fib_val:
					trigger.fib_two_state = FibTwoState.TWO
					return fibTwoSetup(shift, trigger)

		elif trigger.fib_two_state == FibTwoState.TWO:

			if isFibEntryCancelled(shift, trigger, trigger.getFibPercent(100)):
				trigger.fib_two_state = FibOneState.COMPLETE

				if trigger.t_momentum_state == TriggerMomentumState.COMPLETE:
					del current_triggers[current_triggers.index(trigger)]
				
				return

			elif isEntryConfirmation(shift, trigger.direction):
				trigger.fib_two_state = FibTwoState.COMPLETE
				confirmation(trigger)

				if trigger.t_momentum_state == TriggerMomentumState.COMPLETE:
					del current_triggers[current_triggers.index(trigger)]

				return

def triggerMomentumSetup(shift, trigger):

	if trigger != getClosestTriggerMomentumLine(trigger.direction):
		trigger.t_momentum_state = TriggerMomentumState.COMPLETE

		if trigger.fib_two_state == FibTwoState.COMPLETE:
			del current_triggers[current_triggers.index(trigger)]

	if not trigger == None and trigger.tradable and not trigger.t_momentum_state == TriggerMomentumState.COMPLETE:

		if trigger.t_momentum_state == TriggerMomentumState.ONE:
			fib_val = trigger.getFibPercent(100)

			if trigger.direction == Direction.LONG:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]
				
				if fib_val and low <= fib_val:
					trigger.t_momentum_state = TriggerMomentumState.TWO
					return triggerMomentumSetup(shift, trigger)

			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

				if fib_val and high >= fib_val:
					trigger.t_momentum_state = TriggerMomentumState.TWO
					return triggerMomentumSetup(shift, trigger)

		elif trigger.t_momentum_state == TriggerMomentumState.TWO:
			if isRsiStartPointConf() == trigger.direction:
				trigger.t_momentum_state = TriggerMomentumState.THREE
				triggerMomentumSetup(shift, trigger)

		elif trigger.t_momentum_state == TriggerMomentumState.THREE:
			if isEntryConfirmation(shift, trigger.direction):
				trigger.t_momentum_state = TriggerMomentumState.COMPLETE
				confirmation(trigger)

				if trigger.fib_two_state == FibTwoState.COMPLETE:
					del current_triggers[current_triggers.index(trigger)]

def getClosestTriggerMomentumLine(direction):
	closest = None

	for t in current_triggers:

		if t.direction == direction:
			if direction == Direction.LONG:
				if not closest or t.getFibPercent(100) > closest.getFibPercent(100):
					closest = t

			else:
				if not closest or t.getFibPercent(100) < closest.getFibPercent(100):
					closest = t

	return closest

def isFibEntryCancelled(shift, trigger, val):
	sar_count = 0

	while sar_count < VARIABLES['sar_count_cancel_tolerance']:
		if trigger.direction == Direction.LONG:
			if sar.isFalling(shift + sar_count, 1)[0]:
				if sar.get(shift + sar_count, 1)[0] > val:
					print("not cancelled long")
					return False

			sar_count += 1
		else:
			if sar.isRising(shift + sar_count, 1)[0]:
				if sar.get(shift + sar_count, 1)[0] < val:
					print("not cancelled short")
					return False

			sar_count += 1

	print("cancelled")
	return True

def isEntryConfirmation(shift, direction):
	return (
			isParaConfirmation(shift, direction) and
			isCciBiasConfirmation(shift, direction) and
			isMacdHConfirmation(direction) and
			isMacdZConfirmation(direction) and
			isRsiOBOSConfirmation(direction)
		)

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

def isMacdHConfirmation(direction):
	hist = macd.getCurrent()[2]

	if direction == Direction.LONG:
		return hist >= -VARIABLES['macdh_ct_threshold'] * 0.00001
	else:
		return hist <= VARIABLES['macdh_ct_threshold'] * 0.00001

def isMacdZConfirmation(direction):

	histz = macdz.getCurrent()[2]

	if direction == Direction.LONG:
		return histz > 0
	else:
		return histz < 0

def isCciBiasConfirmation(shift, direction):
	
	last_chidx = cci.get(shift + 1, 1)[0][0]
	chidx = cci.get(shift, 1)[0][0]

	if direction == Direction.LONG:
		if chidx > last_chidx:
			return True
	else:
		if chidx < last_chidx:
			return True

	return False

def isRsiOBOSConfirmation(direction):
	stridx = rsi.getCurrent()[0]

	if direction == Direction.LONG:
		return stridx < VARIABLES['rsi_overbought']
	else:
		return stridx > VARIABLES['rsi_oversold']

def confirmation(trigger):
	''' Checks for overbought, oversold and confirm entry '''

	print("confirmation")

	if on_down_time:
		return

	if len(utils.positions) > 0:
		if utils.positions[0].direction == 'buy' and trigger.direction == Direction.LONG:
			return
		elif utils.positions[0].direction == 'sell' and trigger.direction == Direction.SHORT:
			return

	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	for trigger in current_triggers:
		print("TRIGGER", str(trigger.direction), "("+str(trigger.count)+"):")
		print(str(trigger.fib_one_state)+", "+str(trigger.fib_two_state)+", "+str(trigger.t_momentum_state)+", "+str(trigger.t_anchor))
		for trend in trigger.trendlines:
			if trend.trend_state.value < TrendState.COMPLETE.value:
				print(" -", str(trend))
		print("\n")

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
