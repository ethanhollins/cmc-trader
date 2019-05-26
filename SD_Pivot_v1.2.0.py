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
	'SAR' : None,
	'sar_count_cancel_tolerance' : 4,
	'RSI' : None,
	'rsi_overbought': 70,
	'rsi_oversold': 30,
	'rsi_supply_t': 30,
	'rsi_supply_ct': 60,
	'rsi_demand_t': 70,
	'rsi_demand_ct': 40,
	'rsi_confirmed': 50
}

class Direction(Enum):
	LONG = 1
	SHORT = 2

class FibonacciRState(Enum):
	ONE = 1
	COMPLETE = 3

class FibonacciMState(Enum):
	ONE = 1
	COMPLETE = 3

class TrendState(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	COMPLETE = 4

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

	def __init__(self, direction, start, is_anchor = False):
		self.direction = direction
		self.start = start
		self.end = 0
		self.active = False
		self.tradable = False
		self.is_inside = False
		self.trendlines = []

		self.fib_points = [97, 100]
		self.fib_active = []

		self.fibonacci_r_state = FibonacciRState.ONE
		self.fibonacci_m_state = FibonacciMState.ONE

		self.is_orphan = False
		self.is_fifty = False
		self.is_eighty = False
		self.is_hit = False

		self.prev_trigger = None

		self.is_sub = False

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

	def getFibActive(self, shift):
		to_delete = []

		for pt in self.fib_points:

			fib_val = self.getFibPercent(pt)

			chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)

			high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]
			low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

			if self.direction == Direction.LONG:
				
				if fib_val and ( (pt > 0 and low < fib_val) or (pt <= 0 and high > fib_val) ):
					print("POINT:", str(pt), str(self.count))
					
					self.is_hit = True
					if not pt in self.fib_active:

						self.fib_active.append(pt)
						self.fibonacci_r_state = FibonacciRState.ONE
						self.fibonacci_m_state = FibonacciMState.ONE

						if pt == 73:
							to_delete.append(0)
						elif pt == 238.2:
							to_delete.append(-138.2)
						elif pt == -138.2:
							to_delete.append(238.2)

						if not self.is_sub:
							for t in current_triggers:
								if t != self:
									print("deactivate:", str(t.fib_active), ",", str(t.count))
									for fa in t.fib_active:
										if fa in t.fib_points:
											del t.fib_points[t.fib_points.index(fa)]
									t.fib_active = []

							for st in sub_triggers:
								for fa in st.fib_active:
									if fa in st.fib_points:
										del st.fib_points[st.fib_points.index(fa)]
								st.fib_active = []

							if not self.active:
								if not self.is_inside and self.tradable:
									print("delete other triggers")
									self.active = True
									deleteAllOtherTriggers(self)
						else:
							for st in sub_triggers:
								if st != self:
									st.fib_active = []

					elif not self.is_sub:

						for st in sub_triggers:
							for fa in st.fib_active:
								if fa in st.fib_points:
									del st.fib_points[st.fib_points.index(fa)]
							st.fib_active = []

			else:

				if fib_val and ( (pt > 0 and high > fib_val) or (pt <= 0 and low < fib_val) ):
					print("POINT:", str(pt), str(self.count), str(self.fib_active))
					
					self.is_hit = True
					if not pt in self.fib_active:

						self.fib_active.append(pt)
						self.fibonacci_r_state = FibonacciRState.ONE
						self.fibonacci_m_state = FibonacciMState.ONE

						if pt == 73:
							to_delete.append(0)
						elif pt == 238.2:
							to_delete.append(-138.2)
						elif pt == -138.2:
							to_delete.append(238.2)

						if not self.is_sub:
							for t in current_triggers:
								if t != self:
									print("deactivate:", str(t.fib_active), ",", str(t.count))
									for fa in t.fib_active:
										if fa in t.fib_points:
											del t.fib_points[t.fib_points.index(fa)]
									t.fib_active = []

							for st in sub_triggers:
								for fa in st.fib_active:
									if fa in st.fib_points:
										del st.fib_points[st.fib_points.index(fa)]
								st.fib_active = []

							if not self.active:
								if not self.is_inside and self.tradable:
									print("delete other triggers")
									self.active = True
									deleteAllOtherTriggers(self)
						else:
							for st in sub_triggers:
								if st != self:
									st.fib_active = []

					elif not self.is_sub:

						for st in sub_triggers:
							for fa in st.fib_active:
								if fa in st.fib_points:
									del st.fib_points[st.fib_points.index(fa)]
							st.fib_active = []

			if pt in self.fib_active and isOneFastParaCrossedConfirmation(shift, self, pt):
				for i in self.fib_active:
					print("delete active:", str(i))
					if self.fib_active.index(i) < self.fib_active.index(pt) and i != pt:
						to_delete.append(i)

		for pt in to_delete:
			if pt in self.fib_active:
				del self.fib_active[self.fib_active.index(pt)]

			if pt in self.fib_points:
				del self.fib_points[self.fib_points.index(pt)]

	def getPipRange(self):
		return utils.convertToPips(abs(self.start - self.end))

	def checkPipRange(self):
		if not self.is_fifty and self.getPipRange() >= 50:
			self.is_fifty = True

		elif not self.is_eighty and self.getPipRange() >= 80:
			self.is_eighty = True
			if not 62 in self.fib_points:
				self.fib_points.append(62)
				self.fib_points.sort()

			if 97 in self.fib_points:
				del self.fib_points[self.fib_points.index(97)]
			if not 95 in self.fib_points:
				self.fib_points.append(95)
				self.fib_points.sort()

	def isInsideBounds(self, trigger):
		if self.direction == Direction.LONG:
			if trigger.start > self.start and trigger.end < self.end:
				return True
		else:
			if trigger.start < self.start and trigger.end > self.end:
				return True

		return False

	def isOutsideTBounds(self, trend): # FIX
		if len(self.trendlines) > 1:
			if self.direction == Direction.LONG:
				if trend.start < self.start:
					return True
			else:
				if trend.start > self.start:
					print(str(trend.start), str(self.start))
					return True

		return False

	def isOutsideCTBounds(self, trend):
		if len(self.trendlines) > 1:
			if self.direction == Direction.LONG:
				if trend.end > self.end:
					return True
			else:
				if trend.end < self.end:
					return True

		return False

	def isWhollyOutsideCTBounds(self, trend):
		if len(self.trendlines) > 1:
			print(str(self.direction))
			print(str(trend.end) + str(self.start))
			if self.direction == Direction.LONG:
				if trend.start > self.end:
					return True
			else:
				if trend.start < self.end:
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
		self.trend_state = TrendState.ONE

	def getPipRange(self):
		return utils.convertToPips(abs(self.start - self.end))

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
	rsi = utils.RSI(Constants.GBPUSD, Constants.ONE_MINUTE, 10)
	macd = utils.MACD(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	macdz = utils.MACDZ(Constants.GBPUSD, Constants.ONE_MINUTE, 12, 26, 9)
	cci = utils.CCI(Constants.GBPUSD, Constants.ONE_MINUTE, 5)

	setGlobalVars()

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	setGlobalVars()
	
	getFirstTrigger(0, Direction.LONG)
	getFirstTrigger(0, Direction.SHORT)

	print("Starting Bank:", str(bank))

	
def setGlobalVars():
	global bank, stop_trading, no_new_trades
	global is_profit_nnt, is_nnt, is_be
	global current_triggers, sub_triggers, entry_trigger_l, entry_trigger_s
	global pending_entries, pending_breakevens, pending_exits
	global current_news, news_trade_block
	global time_state, stop_state
	global is_first_trigger

	if utils.getBankSize() > VARIABLES['maximum_bank']:
		bank = VARIABLES['maximum_bank']
	else:
		bank = utils.getBankSize()

	stop_trading = False
	no_new_trades = False

	is_profit_nnt = False
	is_nnt = False
	is_be = False

	current_triggers = SortedList()
	sub_triggers = SortedList()

	entry_trigger_l = None
	entry_trigger_s = None

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
	isCciConfirmation(0, Direction.LONG)

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

	listened_types = ['Take Profit', 'Stop Loss', 'Close Trade']

	if event in listened_types:
		if pos.direction == 'buy':
			entry_trigger_l = None
		else:
			entry_trigger_s = None

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
	
	if entry_trigger_l:
		entry_trigger_l.getFibActive(shift)
		fibonacciMSetup(shift, entry_trigger_l)
		fibonacciRSetup(shift, entry_trigger_l)

	if entry_trigger_s:
		entry_trigger_s.getFibActive(shift)
		fibonacciMSetup(shift, entry_trigger_s)
		fibonacciRSetup(shift, entry_trigger_s)

	for t in current_triggers:
		for trend in t.trendlines:
			trendSetup(shift, trend)

		if t == entry_trigger_l or t == entry_trigger_s:
			continue

		t.getFibActive(shift)

		fibonacciMSetup(shift, t)
		fibonacciRSetup(shift, t)

	st_delete = []
	for st in sub_triggers:

		if not st.prev_trigger in current_triggers:
			print("delete no parent")
			st_delete.append(st)
			continue

		if st.direction == Direction.LONG:
			if 73 in st.prev_trigger.fib_points and st.start < st.prev_trigger.getFibPercent(73):
				print("delete 73")
				print("DEL:", str(st.start) + ", " + str(st.prev_trigger.getFibPercent(73)))
				st_delete.append(st)
				continue
		else:
			if 73 in st.prev_trigger.fib_points and st.start > st.prev_trigger.getFibPercent(73):
				print("delete 73")
				print("DEL:", str(st.start) + ", " + str(st.prev_trigger.getFibPercent(73)))
				st_delete.append(st)
				continue

		for trend in st.trendlines:
			trendSetup(shift, trend)

		st.getFibActive(shift)

		fibonacciMSetup(shift, st)
		fibonacciRSetup(shift, st)

	for i in st_delete:
		del sub_triggers[sub_triggers.index(i)]

	getTrigger(shift)

def getFirstTrigger(shift, direction):
	stage = 1
	trigger = Trigger(direction, 0)
	trend = TrendLine(0, trigger)

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
			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

				if trend.start == 0 or high > trend.start:
					trend.start = high

				if stridx >= VARIABLES['rsi_supply_ct']:
					stage += 1
					continue

		elif stage == 2:
			if direction == Direction.LONG:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][2]

				if trend.start == 0 or low < trend.start:
					trend.start = low

				if stridx >= VARIABLES['rsi_demand_t']:
					break
			else:
				chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
				high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][1]

				if trend.start == 0 or high > trend.start:
					trend.start = high

				if stridx <= VARIABLES['rsi_supply_t']:
					break

		shift += 1

	trend.trend_state = TrendState.TWO
	trigger.start = trend.start
	trigger.trendlines.append(trend)

	current_triggers.append(trigger)

def getTrigger(shift):

	new_direction = isRsiDirectionPointConf()

	if new_direction:
		t_dir = getDirectionTrigger(new_direction)
		if not t_dir:
			createNewTrigger(shift, new_direction)

def trendSetup(shift, trend):

	if not trend.trend_state == TrendState.COMPLETE:

		if trend.trend_state == TrendState.ONE:
			if isObos(shift, trend.trigger.direction):
				print("isObos")
				trend.start = 0
				trend.out_of_obs = False
				return

		if trend.trend_state == TrendState.ONE or trend.trend_state == TrendState.TWO:

			if not trend.trigger.is_sub and trend.trigger.is_hit:
				print("create")
				del trend.trigger.trendlines[trend.trigger.trendlines.index(trend)]

				t = createNewTrigger(shift, trend.trigger.direction, start = trend.start, trend = trend)

				return trendSetup(shift, t.trendlines[0])

			if trend.trigger.direction == Direction.LONG:
				trend.start = getTrendLow(shift, trend.start)
			else:
				trend.start = getTrendHigh(shift, trend.start)

			if trend.trend_state == TrendState.ONE and isRsiCTPointConf(trend):
				print("trend state one complete")
				trend.trend_state = TrendState.TWO

			elif trend.trend_state == TrendState.TWO and isRsiTPointConf(trend):
				print("trend state two complete")

				setPreviousTrendsToComplete(trend)

				trend.trend_state = TrendState.THREE

				if not trend.trigger.is_sub:

					if trend.trigger.isWhollyOutsideCTBounds(trend):
						print("IS OUTSIDE Wholly BOUNDS")
						del trend.trigger.trendlines[trend.trigger.trendlines.index(trend)]

						t = createNewTrigger(shift, trend.trigger.direction, start = trend.start, trend = trend)
						trend.trigger = t

						t.is_orphan = True
						t.fib_points.append(0)
						t.fib_points.sort()

						setStartEndVals(shift, trend)

						return trendSetup(shift, trend)

					elif trend.trigger.isOutsideTBounds(trend):
						print("IS OUTSIDE T BOUNDS")
						del trend.trigger.trendlines[trend.trigger.trendlines.index(trend)]

						t = createNewTrigger(shift, trend.trigger.direction, start = trend.start, trend = trend)
						trend.trigger = t

						setStartEndVals(shift, trend)

						return trendSetup(shift, trend)

					else:
						trend.trigger.trendlines.append(TrendLine(0, trend.trigger))

						print("NEW SUB TRIGGER:", str(trend.trigger.direction))
						st = Trigger(trend.trigger.direction, trend.start)
						st_trend = TrendLine(trend.start, st)
						st_trend.trend_state = TrendState.THREE
						st.trendlines.append(st_trend)
						st.is_sub = True
						st.prev_trigger = trend.trigger
						st.fib_points = [100]

						setStartEndVals(shift, st_trend)

						print(str(st_trend.start) + ", " + str(st_trend.end))

						sub_triggers.append(st)

				setStartEndVals(shift, trend)

				return trendSetup(shift, trend)

		elif trend.trend_state == TrendState.THREE:

			if trend.trigger.direction == Direction.LONG:
				trend.end = getTrendHigh(shift, trend.end)

				if trend.trigger.end == 0 or trend.end > trend.trigger.end:
					trend.trigger.end = trend.end
			else:
				trend.end = getTrendLow(shift, trend.end)

				if trend.trigger.end == 0 or trend.end < trend.trigger.end:
					trend.trigger.end = trend.end

			if isRsiConfirmationPointConf(trend):
				trend.trigger.tradable = True
				if trend.trigger.is_sub:
					trend.trigger.active = True
					print("delete subs")
					deleteSubTriggers(trend.trigger)

			if not trend.trigger.is_sub and isInsideActiveTrigger(trend.trigger):
				trend.trigger.is_inside = True
			else:
				trend.trigger.is_inside = False

			if not trend.trigger.is_sub and trend.trigger.is_hit:
				trend.trend_state = TrendState.COMPLETE
				return

			if isRsiCTPointConf(trend):
				if not trend.trigger.is_sub and not trend.trigger.is_inside and trend.getPipRange() >= 50 and len(trend.trigger.trendlines) > 1:
					del trend.trigger.trendlines[trend.trigger.trendlines.index(trend)]

					t = createNewTrigger(shift, trend.trigger.direction, start = trend.start, trend = trend)
					trend.trigger = t


def setStartEndVals(shift, trend):
	if trend.trigger.direction == Direction.LONG:
		if trend.trigger.start == 0 or trend.start < trend.trigger.start:
			trend.trigger.start = trend.start

		trend.end = getTrendHigh(shift, trend.end)

		if trend.trigger.end == 0 or trend.end > trend.trigger.end:
			trend.trigger.end = trend.end
	else:
		if trend.trigger.start == 0 or trend.start > trend.trigger.start:
			trend.trigger.start = trend.start

		trend.end = getTrendLow(shift, trend.end)

		if trend.trigger.end == 0 or trend.end < trend.trigger.end:
			trend.trigger.end = trend.end

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

def setPreviousTrendsToComplete(trend):
	print(len(trend.trigger.trendlines))
	for i in range(len(trend.trigger.trendlines) - 1, -1, -1):
		print("prev:", str(i))
		if trend.trigger.trendlines[i].trend_state != TrendState.COMPLETE and trend != trend.trigger.trendlines[i]:
			trend.trigger.trendlines[i].trend_state = TrendState.COMPLETE

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
		trend.trigger = t
		t.trendlines.append(trend)
	else:
		t.trendlines.append(TrendLine(start, t))

	t.prev_trigger = getParentTrigger(direction)

	current_triggers.append(t)

	return t

def getDirectionTrigger(direction):
	t_dirs = [i for i in current_triggers if i.direction == direction]

	if len(t_dirs) > 0:
		return t_dirs[-1]

	return None

def getActiveTrigger(direction):
	for t in current_triggers:
		if t.active and t.direction == direction:
			return t

	return None

def getRecentTrigger(direction):
	for i in range(len(current_triggers)):
		t = current_triggers[i]
		if t.direction == direction:
			return t

	return None

def getParentTrigger(direction):
	for i in range(len(current_triggers)):
		t = current_triggers[i]
		if t.direction == direction and t.trendlines[0].trend_state.value >= TrendState.THREE.value and not t.is_inside:
			return t

	return None

def deleteSubTriggers(trigger):
	st_dir = [i for i in sub_triggers if i.direction == trigger.direction and sub_triggers.index(trigger) > sub_triggers.index(i)]

	for st in st_dir:
		if st != trigger:
			del sub_triggers[sub_triggers.index(st)]

def deleteDirectionSubTriggers(direction):
	st_dir = [i for i in sub_triggers if i.direction == direction]

	for st in st_dir:
		del sub_triggers[sub_triggers.index(st)]

def isRsiDirectionPointConf():
	stridx = rsi.getCurrent()[0]

	if stridx > VARIABLES['rsi_demand_t']:
		return Direction.LONG
	elif stridx < VARIABLES['rsi_supply_t']:
		return Direction.SHORT

	return None

def isRsiTPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.trigger.direction == Direction.LONG:
		return stridx > VARIABLES['rsi_demand_t']
	else:
		return stridx < VARIABLES['rsi_supply_t']

def isRsiCTPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.trigger.direction == Direction.LONG:
		return stridx < VARIABLES['rsi_demand_ct']
	else:
		return stridx > VARIABLES['rsi_supply_ct']

def isRsiConfirmationPointConf(trend):
	stridx = rsi.getCurrent()[0]

	if trend.trigger.direction == Direction.LONG:
		return stridx < VARIABLES['rsi_confirmed']
	else:
		return stridx > VARIABLES['rsi_confirmed']

def isInsideActiveTrigger(trigger):
	t_active = None

	for i in range(len(current_triggers) - 1, -1, -1):
		if (current_triggers[i] != trigger and 
			current_triggers[i].active and 
			current_triggers[i].direction == trigger.direction):

			t_active = current_triggers[i]
			break

	if t_active and t_active.isInsideBounds(trigger):
		return True

	return False

def deleteAllOtherTriggers(trigger):
	for i in range(len(current_triggers) - 1, -1, -1):
		t = current_triggers.getUnsorted()[i]
		if (t == trigger.direction and t != trigger 
			and (t.is_hit or (current_triggers.index(current_triggers[i]) < current_triggers.index(trigger) 
					and t.direction == trigger.direction)) ):
			print("delete:", str(t.count))
			del current_triggers[current_triggers.index(t)]

def fibonacciRSetup(shift, trigger):

	for pt in trigger.fib_active:
		if (trigger and trigger.tradable and not trigger.is_inside and not trigger.fibonacci_r_state == FibonacciRState.COMPLETE):

			fib_val = trigger.getFibPercent(pt)

			if isRetracementEntryConfirmation(shift, trigger, pt):
				trigger.fibonacci_r_state = FibonacciRState.COMPLETE

				if trigger.active:
					return confirmation(trigger)

def fibonacciMSetup(shift, trigger):

	for pt in trigger.fib_active:
		if trigger and trigger.tradable and not trigger.is_inside and not trigger.fibonacci_m_state == FibonacciMState.COMPLETE:

			fib_val = trigger.getFibPercent(pt)

			if isMomentumEntryConfirmation(shift, trigger, pt):
				trigger.fibonacci_m_state = FibonacciMState.COMPLETE

				if trigger.active:
					return confirmation(trigger, opp_entry = True)

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

def isRetracementEntryConfirmation(shift, trigger, point):
	print("ret conf:", 
			str(isFastParaConfirmation(shift, trigger.direction)),
			str(isMacdConfirmation(trigger.direction)),
			str(isFastParaCrossedConfirmation(shift, trigger, point)),
			str(isBarCloseConfirmation(shift, trigger, point)),
			str(isCciConfirmation(shift, trigger.direction))
		)
	return (
			isFastParaConfirmation(shift, trigger.direction) and
			isMacdConfirmation(trigger.direction) and
			isFastParaCrossedConfirmation(shift, trigger, point) and
			isBarCloseConfirmation(shift, trigger, point) and
			isCciConfirmation(shift, trigger.direction)
		)

def isMomentumEntryConfirmation(shift, trigger, point):
	print("mom conf:", 
			str(isFastParaConfirmation(shift, trigger.direction, reverse = True)),
			str(isMacdConfirmation(trigger.direction, reverse = True)),
			str(isFastParaCrossedConfirmation(shift, trigger, point, reverse = True)),
			str(isBarCloseConfirmation(shift, trigger, point, reverse = True)),
			str(isCciConfirmation(shift, trigger.direction, reverse = True))
		)

	return (
			isFastParaConfirmation(shift, trigger.direction, reverse = True) and
			isMacdConfirmation(trigger.direction, reverse = True) and
			isFastParaCrossedConfirmation(shift, trigger, point, reverse = True) and 
			isBarCloseConfirmation(shift, trigger, point, reverse = True) and
			isCciConfirmation(shift, trigger.direction, reverse = True)
		)

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

def isFastParaCrossedConfirmation(shift, trigger, point, reverse = False):
	sar = fast_sar.get(shift, 2)

	val = trigger.getFibPercent(point)

	for i in sar:

		if reverse:
			if trigger.direction == Direction.LONG:
				if not i < val and fast_sar.isFalling(shift, 1)[0]:
					return False
			else:
				if not i > val and fast_sar.isRising(shift, 1)[0]:
					return False
		else:
			if trigger.direction == Direction.LONG:
				if not i > val and fast_sar.isRising(shift, 1)[0]:
					return False
			else:
				if not i < val and fast_sar.isFalling(shift, 1)[0]:
					return False

	return True

def isOneFastParaCrossedConfirmation(shift, trigger, point):
	sar = fast_sar.getCurrent()

	val = trigger.getFibPercent(point)
	
	if trigger.direction == Direction.LONG:
		return sar < val
	else:
		return sar > val

	return False

def isMacdConfirmation(direction, reverse = False):
	hist = macd.getCurrent()[2]
	histz = macdz.getCurrent()[2]
	print("hist:", str(hist), "histz:", str(histz))

	if reverse:
		if direction == Direction.LONG:
			return (hist < 0 and histz < 0)
		else:
			return (hist > 0 and histz > 0)

	else:
		if direction == Direction.LONG:
			return (hist > 0 and histz > 0)
		else:
			return (hist < 0 and histz < 0)

def isBarCloseConfirmation(shift, trigger, point, reverse = False):
	chart = utils.getChart(Constants.GBPUSD, Constants.ONE_MINUTE)
	close = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][shift][3]
			
	val = trigger.getFibPercent(point)

	if reverse:
		if trigger.direction == Direction.LONG:
			return close < val
		else:
			return close > val
	else:
		if trigger.direction == Direction.LONG:
			return close > val
		else:
			return close < val

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

def isObos(shift, direction):
	stridx = rsi.getCurrent()[0]

	if direction == Direction.LONG:
		return stridx > VARIABLES['rsi_overbought']
	else:
		return stridx < VARIABLES['rsi_oversold']

def confirmation(trigger, opp_entry = False):
	''' Checks for overbought, oversold and confirm entry '''

	global entry_trigger_l, entry_trigger_s

	print("confirmation:", str(trigger.direction), str(opp_entry), str(trigger.count))

	if trigger.is_sub:
		trigger = getParentTrigger(trigger.direction)

	entry_trigger = None

	if opp_entry:
		if trigger.direction == Direction.LONG:
			entry_trigger = Trigger(Direction.SHORT, trigger.start)
		else:
			entry_trigger = Trigger(Direction.LONG, trigger.start)
	else:
		entry_trigger = trigger

	if len(utils.positions) > 0:
		if utils.positions[0].direction == 'buy' and entry_trigger.direction == Direction.LONG:
			return
		elif utils.positions[0].direction == 'sell' and entry_trigger.direction == Direction.SHORT:
			return

	if trigger.direction == Direction.LONG:
		entry_trigger_l = trigger
		if not -138.2 in trigger.fib_points and not -138.2 in trigger.fib_active:
			trigger.fib_points.append(-138.2)
		if not 238.2 in trigger.fib_points and not 238.2 in trigger.fib_active:
			trigger.fib_points.append(238.2)

		trigger.fib_points.sort()
	else:
		entry_trigger_s = trigger
		if not -138.2 in trigger.fib_points and not -138.2 in trigger.fib_active:
			trigger.fib_points.append(-138.2)
		if not 238.2 in trigger.fib_points and not 238.2 in trigger.fib_active:
			trigger.fib_points.append(238.2)

		trigger.fib_points.sort()

	pending_entries.append(entry_trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	for trigger in current_triggers:
		print("TRIGGER", str(trigger.direction), "("+str(trigger.count)+"):")
		print("Tradable:", str(trigger.tradable) + ", Active:", str(trigger.active) + ", Inside:", str(trigger.is_inside))
		print(trigger.fib_active)
		print(str(trigger.start) + ", " + str(trigger.end))
		print(str(trigger.fibonacci_r_state)+", "+str(trigger.fibonacci_m_state))
		print(len(trigger.trendlines))
		for trend in trigger.trendlines:
			print(str(trend.trend_state))
			# if trend.trend_state.value < TrendState.COMPLETE.value:
			# print(" -", str(trend))
		print("\n")

	for st in sub_triggers:
		print("SUB:", str(st.direction))
		print(st.fib_active)
		print(str(st.start) + ", " + str(st.end) + "\nTradable:", str(st.tradable) + ", Active:", str(st.active))
		print(str(st.fibonacci_r_state) + ", " + str(st.fibonacci_m_state))
		for st_trend in st.trendlines:
			print(str(st_trend.trend_state))
		print("\n")

	if entry_trigger_l:
		print("entry_trigger_l", str(entry_trigger_l.fib_points))
		print(entry_trigger_l.fib_active)
		print(str(entry_trigger_l.fibonacci_r_state)+", "+str(entry_trigger_l.fibonacci_m_state))
		print("\n")

	if entry_trigger_s:
		print("entry_trigger_s", str(entry_trigger_s.fib_points))
		print(entry_trigger_s.fib_active)
		print(str(entry_trigger_s.fibonacci_r_state)+", "+str(entry_trigger_s.fibonacci_m_state))
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
