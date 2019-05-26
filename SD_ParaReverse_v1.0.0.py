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
		self.trendline = None
		
		self.entry_state = EntryState.ONE

		self.count = Trigger.static_count
		Trigger.static_count += 1

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

class TrendLine(dict):
	static_count = 0

	def __init__(self, direction):
		self.direction = direction
		self.start = 0
		self.end = 0
		self.trend_state = TrendState.ONE
		self.tradable = False

		self.points = [100]
		self.active = []

		self.ret_state = RetState.ONE
		self.mom_state = MomState.ONE

		self.count = TrendLine.static_count
		TrendLine.static_count += 1

	def getPipRange(self):
		return utils.convertToPips(abs(self.start - self.end))

	def getFibPercent(self, percent):
		percent *= .01
		if self.end != 0:
			if self.direction == Direction.LONG:
				return round(self.end - ( abs( self.end - self.start ) * percent ), 5)
			else:
				return round(self.end + ( abs( self.end - self.start ) * percent ), 5)
		else:
			return None

	def getFibActive(self, shift):
		to_delete = []

		for pt in self.points:

			fib_val = self.getFibPercent(pt)

			chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

			high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
			low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

			if self.direction == Direction.LONG:

				if fib_val and ( (pt > 0 and low < fib_val) or (pt <= 0 and high > fib_val) ):

					if not pt in self.active:
						
						self.active.append(pt)
						self.ret_state = RetState.ONE
						self.mom_state = MomState.ONE

						# for i in long_trends + short_trends:
						# 	if i != self:
						# 		for a in i.active:
						# 			if a in i.points:
						# 				del i.points[i.points.index(a)]
						# 		i.active= []

			else:

				if fib_val and ( (pt > 0 and high > fib_val) or (pt <= 0 and low < fib_val) ):

					if not pt in self.active:
						
						self.active.append(pt)
						self.ret_state = RetState.ONE
						self.mom_state = MomState.ONE

						# for i in long_trends + short_trends:
						# 	if i != self:
						# 		for a in i.active:
						# 			if a in i.points:
						# 				del i.points[i.points.index(a)]
						# 		i.active= []

			if pt in self.active and isOneFastParaCrossedConfirmation(shift, self, pt):
				for i in self.active:
					if self.active.index(i) < self.active.index(pt) and i != pt:
						to_delete.append(i)

		for pt in to_delete:
			if pt in self.active:
				del self.active[self.active.index(pt)]

			if pt in self.points:
				del self.points[self.points.index(pt)]

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
	global fast_sar, slow_sar, rsi, macd, macdz, cci

	utils = utilities
	fast_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.2, 0.2)
	slow_sar = utils.SAR_M(Constants.GBPUSD, Constants.ONE_MINUTE, 0.017, 0.04)
	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)
	cci = utils.CCI(Constants.GBPUSD, Constants.ONE_MINUTE, 5)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)

	setGlobalVars()

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	setGlobalVars()
	# initTrendlines()
	getFirstTrigger(0, Direction.LONG)
	getFirstTrigger(0, Direction.SHORT)

	print("Starting Bank:", str(bank))

	
def setGlobalVars():
	global bank, stop_trading, no_new_trades
	global long_trigger, short_trigger, fast_strands, slow_strands
	global long_trends, short_trends, current_strand
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
	long_trends = SortedList()
	short_trends = SortedList()

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

	long_trigger.entry_state = EntryState.ONE
	long_trigger.cross_strand = None

	short_trigger.entry_state = EntryState.ONE
	short_trigger.cross_strand = None

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

	setCrossStrand(long_trigger)
	setCrossStrand(short_trigger)

	for t in long_trends + short_trends:
		trendSetup(shift, t)

	paraRevSetup(shift, long_trigger)
	paraRevSetup(shift, short_trigger)

	trendRetSetup(shift, long_trigger)
	trendRetSetup(shift, short_trigger)

	trendMomSetup(shift, long_trigger)
	trendMomSetup(shift, short_trigger)

def getFirstTrigger(shift, direction):
	stage = 1
	trend = TrendLine(direction)

	while True:
		stridx = rsi.get(shift, 1)[0][0]

		if stage == 1:
			if direction == Direction.LONG:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

				if trend.start == 0 or low < trend.start:
					trend.start = low

				if stridx <= VARIABLES['rsi_demand_ct']:
					stage += 1
					continue
				elif stridx >= VARIABLES['rsi_demand_t']:
					trend.trend_state = TrendState.ONE
					break
			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

				if trend.start == 0 or high > trend.start:
					trend.start = high

				if stridx >= VARIABLES['rsi_supply_ct']:
					stage += 1
					continue
				elif stridx <= VARIABLES['rsi_supply_t']:
					trend.trend_state = TrendState.ONE
					break

		elif stage == 2:
			if direction == Direction.LONG:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

				if trend.start == 0 or low < trend.start:
					trend.start = low
				if trend.end == 0 or high > trend.end:
					trend.end = high

				if stridx >= VARIABLES['rsi_demand_t']:
					trend.trend_state = TrendState.TWO
					break
			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

				if trend.start == 0 or high > trend.start:
					trend.start = high
				if trend.end == 0 or low < trend.end:
					trend.end = low

				if stridx <= VARIABLES['rsi_supply_t']:
					trend.trend_state = TrendState.TWO
					break

		shift += 1

	if trend.direction == Direction.LONG:
		long_trends.append(trend)
		long_trigger.trendline = trend
	else:
		short_trends.append(trend)
		short_trigger.trendline = trend

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
	if trigger.cross_strand:
		for i in range(len(fast_strands)):
			strand = fast_strands[i]
			if strand.direction == trigger.direction:
				if strand.count <= trigger.cross_strand.count:
					return
			
				elif strand.length >= VARIABLES['sar_min_length']:
					if trigger.direction == Direction.LONG:
						if strand.start < trigger.cross_strand.start:
							trigger.cross_strand = strand
							return
					else:
						if strand.start > trigger.cross_strand.start:
							trigger.cross_strand = strand
							return

	else:
		for i in range(len(fast_strands)):
			strand = fast_strands[i]
			if strand.direction == trigger.direction:
				if strand.length >= VARIABLES['sar_min_length']:
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

def initTrendlines():
	long_trends = [TrendLine(Direction.LONG)]
	short_trends = [TrendLine(Direction.SHORT)]

def trendSetup(shift, trend):

	if not trend.trend_state == TrendState.COMPLETE:

		if trend.trend_state == TrendState.ONE:
			if isObos(trend.direction):
				trend.start = 0
				return

		if trend.trend_state == TrendState.ONE or trend.trend_state == TrendState.TWO:

			if trend.direction == Direction.LONG:
				trend.start = getTrendLow(shift, trend.start)
			else:
				trend.start = getTrendHigh(shift, trend.start)

			if trend.trend_state == TrendState.ONE and isRsiCTPointConf(trend):
				trend.trend_state = TrendState.TWO

				return trendSetup(shift, trend)

			elif trend.trend_state == TrendState.TWO:

				if trend.direction == Direction.LONG:
					trend.end = getTrendHigh(shift, trend.end)
				else:
					trend.end = getTrendLow(shift, trend.end)

				if isRsiTPointConf(trend):
					trend.trend_state = TrendState.THREE

					setStartEndVals(shift, trend)

					if trend.direction == Direction.LONG:
						long_trends.append(TrendLine(trend.direction))
					else:
						short_trends.append(TrendLine(trend.direction))

					return trendSetup(shift, trend)

		elif trend.trend_state == TrendState.THREE:

			if trend.direction == Direction.LONG:
				trend.end = getTrendHigh(shift, trend.end)
			else:
				trend.end = getTrendLow(shift, trend.end)

			if isRsiConfirmationPointConf(trend) and not trend.tradable:
				trend.tradable = True
				trend.trend_state = TrendState.COMPLETE
				if trend.direction == Direction.LONG:
					long_trigger.trendline = trend
				else:
					short_trigger.trendline = trend
				

def setStartEndVals(shift, trend):
	if trend.direction == Direction.LONG:
		if trend.start == 0 or trend.start < trend.start:
			trend.start = trend.start

		trend.end = getTrendHigh(shift, trend.end)

		if trend.end == 0 or trend.end > trend.end:
			trend.end = trend.end
	else:
		if trend.start == 0 or trend.start > trend.start:
			trend.start = trend.start

		trend.end = getTrendLow(shift, trend.end)

		if trend.end == 0 or trend.end < trend.end:
			trend.end = trend.end

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

def isRsiTPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.direction == Direction.LONG:
		return stridx > VARIABLES['rsi_demand_t']
	else:
		return stridx < VARIABLES['rsi_supply_t']

def isRsiCTPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.direction == Direction.LONG:
		return stridx < VARIABLES['rsi_demand_ct']
	else:
		return stridx > VARIABLES['rsi_supply_ct']

def isRsiConfirmationPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.direction == Direction.LONG:
		return stridx < VARIABLES['rsi_confirmed']
	else:
		return stridx > VARIABLES['rsi_confirmed']

def isOneFastParaCrossedConfirmation(shift, trend, point):
	sar = fast_sar.getCurrent()

	val = trend.getFibPercent(point)
	
	if trend.direction == Direction.LONG:
		return sar < val
	else:
		return sar > val

def paraRevSetup(shift, trigger):

	if trigger and not trigger.entry_state == EntryState.COMPLETE:

		if trigger.entry_state == EntryState.ONE:
			if trigger.cross_strand and isParaCrossedConfirmation(shift, trigger):
				if trigger.direction == Direction.LONG:
					short_trigger.entry_state = EntryState.ONE
				else:
					long_trigger.entry_state = EntryState.ONE

				trigger.entry_state = EntryState.TWO
				return paraRevSetup(shift, trigger)

		if trigger.entry_state == EntryState.TWO:
			if isParaRevConfirmation(shift, trigger):
				trigger.entry_state = EntryState.COMPLETE
				return confirmation(trigger)

def trendRetSetup(shift, trigger):

	if trigger.trendline:

		trigger.trendline.getFibActive(shift)

		for pt in trigger.trendline.active:
			if trigger.trendline.tradable and not trigger.trendline.ret_state == RetState.COMPLETE:
				fib_val = trigger.trendline.getFibPercent(pt)

				if isRetracementEntryConfirmation(shift, trigger.trendline, pt):
					trigger.trendline.ret_state = RetState.ONE
					del trigger.trendline.active[trigger.trendline.active.index(pt)]
					return confirmation(trigger)

def trendMomSetup(shift, trigger):

	if trigger.trendline:

		trigger.trendline.getFibActive(shift)

		for pt in trigger.trendline.active:
			if trigger.trendline.tradable and not trigger.trendline.mom_state == MomState.COMPLETE:
				fib_val = trigger.trendline.getFibPercent(pt)

				if isMomentumEntryConfirmation(shift, trigger.trendline, pt):
					trigger.trendline.mom_state = MomState.ONE
					del trigger.trendline.active[trigger.trendline.active.index(pt)]
					return confirmation(trigger, is_opp = True)

def isParaRevConfirmation(shift, trigger):
	print("Para Conf ("+str(trigger.direction)+"):", 
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

def isRetracementEntryConfirmation(shift, trend, point):
	print("Ret Conf ("+str(trend.direction)+"):", 
			str(isFastParaConfirmation(shift, trend.direction)),
			str(isSlowParaConfirmation(shift, trend.direction)),
			str(isMacdConfirmation(trend.direction)),
			str(isCciConfirmation(shift, trend.direction)),
			str(isRsiConfirmation(shift, trend.direction)),
			str(isParaCrossedTrendConfirmation(shift, trend, point))
		)
	return (
			isFastParaConfirmation(shift, trend.direction) and
			isSlowParaConfirmation(shift, trend.direction) and
			isMacdConfirmation(trend.direction) and
			isCciConfirmation(shift, trend.direction) and
			isRsiConfirmation(shift, trend.direction) and
			isParaCrossedTrendConfirmation(shift, trend, point)
		)

def isMomentumEntryConfirmation(shift, trend, point):
	print("Mom Conf ("+str(trend.direction)+"):", 
			str(isFastParaConfirmation(shift, trend.direction, reverse = True)),
			str(isSlowParaConfirmation(shift, trend.direction, reverse = True)),
			str(isMacdConfirmation(trend.direction, reverse = True)),
			str(isCciConfirmation(shift, trend.direction, reverse = True)),
			str(isRsiConfirmation(shift, trend.direction, reverse = True)),
			str(isParaCrossedTrendConfirmation(shift, trend, point, reverse = True))
		)
	return (
			isFastParaConfirmation(shift, trend.direction, reverse = True) and
			isSlowParaConfirmation(shift, trend.direction, reverse = True) and
			isMacdConfirmation(trend.direction, reverse = True) and
			isCciConfirmation(shift, trend.direction, reverse = True) and
			isRsiConfirmation(shift, trend.direction, reverse = True) and
			isParaCrossedTrendConfirmation(shift, trend, point, reverse = True)
		)

def isParaCrossedConfirmation(shift, trigger):
	sar = slow_sar.getCurrent()

	if trigger.direction == Direction.LONG:
		return sar > trigger.cross_strand.start and slow_sar.isRising(shift, 1)[0]
	else:
		return sar < trigger.cross_strand.start and slow_sar.isFalling(shift, 1)[0]

def isParaCrossedTrendConfirmation(shift, trend, point, reverse = False):
	sar = slow_sar.getCurrent()
	val = trend.getFibPercent(point)

	if reverse:
		if trend.direction == Direction.LONG:
			return sar < val and slow_sar.isFalling(shift, 1)[0]
		else:
			return sar > val and slow_sar.isRising(shift, 1)[0]
	else:
		if trend.direction == Direction.LONG:
			return sar > val and slow_sar.isRising(shift, 1)[0]
		else:
			return sar < val and slow_sar.isFalling(shift, 1)[0]

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
			return (hist < 0 and histz <= 0) or (hist <= 0 and histz < 0) or hist <= VARIABLES['macd_override'] * 0.00001
		else:
			return (hist > 0 and histz >= 0) or (hist >= 0 and histz > 0) or hist >= VARIABLES['macd_override'] * 0.00001

	else:
		if direction == Direction.LONG:
			return (hist > 0 and histz >= 0) or (hist >= 0 and histz > 0) or hist >= VARIABLES['macd_override'] * 0.00001
		else:
			return (hist < 0 and histz <= 0) or (hist <= 0 and histz < 0) or hist <= VARIABLES['macd_override'] * 0.00001

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

def isObos(direction):
	stridx = rsi.getCurrent()[0]

	if direction == Direction.LONG:
		return stridx > VARIABLES['rsi_overbought']
	else:
		return stridx < VARIABLES['rsi_oversold']

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

	print("Demand:", str(long_trigger.trendline))
	print("Support:", str(short_trigger.trendline)+"\n")

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
