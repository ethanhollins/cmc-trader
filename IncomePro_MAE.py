from CMCTrader import Constants
from CMCTrader.Backtester import Backtester
from enum import Enum
import datetime
import types
import copy

VARIABLES = {
	'TIMEZONE': 'America/New_York',
	'PAIRS': [Constants.GBPUSD],
	'BANK': None,
	'risk': 3.0,
	'PLAN': None,
	'stoprange': 130,
	'breakeven_min_pips': 3,
	'max_ct_entry_retries': 3,
	'ts_offset': 1,
	'doji_range': 1,
	'RSI': None,
	'rsi_long': 52,
	'rsi_short': 48,
	'MACD': None,
	'macd_one': 20,
	'macd_two': 10,
}

class Direction(Enum):
	LONG = 1
	SHORT = 2

class TMacdEntryState(Enum):
	ONE = 1
	COMPLETE = 2

class TRsiEntryState(Enum):
	ONE = 1
	TWO = 2
	CANCELLED = 3
	COMPLETE = 4

class CTEntryState(Enum):
	ONE = 1
	TWO = 2
	THREE = 3
	COMPLETE = 4

class EntryType(Enum):
	TEntry = 1
	CTEntry = 2

class TimeState(Enum):
	TRADING = 1
	NCT = 2
	STOP = 3

class StopState(Enum):
	ONE = 1
	WAIT = 2

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
		
		self.t_macd_entry_state = TMacdEntryState.ONE
		self.t_rsi_entry_state = TRsiEntryState.ONE
		self.t_rsi = False
		
		self.ct_entry_state = CTEntryState.ONE
		self.ct_so_count = 0
		self.ct_tag = False

		self.stop_state = StopState.ONE

		self.entry_type = None
		self.stop_range = 25

		self.count = Trigger.static_count
		Trigger.static_count += 1

	def __getattr__(self, key):
		return self[key]

	def __setattr__(self, key, value):
		self[key] = value

def init(utilities):
	''' Initialize utilities and indicators '''

	global utils
	global sma, inner_mae, outer_mae, limit_mae, short_boll, long_boll, macd, rsi, atr, chart

	utils = utilities

	sma = utils.SMA(Constants.GBPUSD, Constants.FOUR_HOURS, 10)
	inner_mae = utils.MAE(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 0.035)
	outer_mae = utils.MAE(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 0.09)
	limit_mae = utils.MAE(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 0.2)
	short_boll = utils.BOLL(Constants.GBPUSD, Constants.FOUR_HOURS, 10, 2.2)
	long_boll = utils.BOLL(Constants.GBPUSD, Constants.FOUR_HOURS, 20, 1.9)
	rsi = utils.RSI(Constants.GBPUSD, Constants.FOUR_HOURS, 10)
	macd = utils.MACD(Constants.GBPUSD, Constants.FOUR_HOURS, 4, 40, 3)
	atr = utils.ATR(Constants.GBPUSD, Constants.FOUR_HOURS, 20)
	chart = utils.getChart(Constants.GBPUSD, Constants.FOUR_HOURS)

	utils.setPositionNetting(False)

	setGlobalVars()

def onStartTrading():
	''' Function called on trade start time '''

	print("onStartTrading")

	setGlobalVars()
	
def setGlobalVars():
	global long_trigger, short_trigger
	global pending_entries, pending_breakevens, pending_exits
	global time_state, stop_state

	long_trigger = Trigger(Direction.LONG)
	short_trigger = Trigger(Direction.SHORT)

	pending_entries = []
	pending_breakevens = []
	pending_exits = []

	time_state = TimeState.TRADING

def onFinishTrading():
	''' Function called on trade end time '''

	print("onFinishTrading")

	print("Total PIPS gain:", str(utils.getTotalProfit()))

def onNewBar():
	''' Function called on every new bar '''
	print("\nonNewBar")
	utils.printTime(utils.getAustralianTime())
	
	checkTime()

	runSequence(0)
	# handleExits(0)

	report()

def onDownTime():
	''' Function called outside of trading time '''

	print("onDownTime")
	ausTime = utils.printTime(utils.getAustralianTime())

def onLoop():
	''' Function called on every program iteration '''

	handleEntries()		# Handle all pending entries
	# handleStop()	# Handle all stop modifications

def handleEntries():
	''' Handle all pending entries '''
	global pending_entries

	if len(pending_entries) > 0:
		local_storage = utils.getLocalStorage()

	for entry in pending_entries[:1]:
		
		if isOppDirectionPositionExists(local_storage, entry.direction):
			print("Attempting position enter long: stop and reverse")
			handleStopAndReverse(entry, local_storage)
		else:
			print("Attempting position enter long: regular")
			handleRegularEntry(entry)

		pending_entries = []

def isOppDirectionPositionExists(storage, direction):
	if 'POSITIONS' in storage:
		for p in storage['POSITIONS']:
			if p['data']['direction'] != direction.value:
				return True

	return False

def handleStopAndReverse(entry, storage):
	''' 
	Handle stop and reverse entries 
	and check if tradable conditions are met.
	'''
	if 'POSITIONS' in storage:
		for i in range(len(storage['POSITIONS'])-1, -1, -1):
			p = storage['POSITIONS'][i]
			pos = utils.getPosByOrderId(p['order_id'])
			if pos:
				pos.close()

	handleRegularEntry(entry)

def handleRegularEntry(entry):
	''' 
	Handle regular entries 
	and check if tradable conditions are met.
	'''

	bank = utils.getBankSize() + utils.external_bank
	if bank > utils.maximum_bank:
		bank = utils.maximum_bank

	if entry.direction == Direction.LONG:
		pos = utils.buy(
			utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), 
			pairs = VARIABLES['PAIRS'], 
			sl = VARIABLES['stoprange'],
			risk = VARIABLES['risk']
		)
	else:
		pos = utils.sell(
			utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), 
			pairs = VARIABLES['PAIRS'], 
			sl = VARIABLES['stoprange'],
			risk = VARIABLES['risk']
		)

	# if entry.direction == Direction.LONG:
	# 	pos = utils.buy(
	# 		utils.getLotsize(bank, VARIABLES['risk'], entry.stop_range), 
	# 		pairs = VARIABLES['PAIRS'], 
	# 		sl = entry.stop_range,
	# 		risk = VARIABLES['risk']
	# 	)
	# else:
	# 	pos = utils.sell(
	# 		utils.getLotsize(bank, VARIABLES['risk'], entry.stop_range), 
	# 		pairs = VARIABLES['PAIRS'], 
	# 		sl = entry.stop_range,
	# 		risk = VARIABLES['risk']
	# 	)
		
	local_storage = utils.getLocalStorage()

	for p in local_storage['POSITIONS']:
		if p['order_id'] == pos.orderID:
			p['data'] = {
				'direction': entry.direction.value,
				'type': entry.entry_type.value,
			}
			break

	print("s:", str(local_storage))
	utils.updateLocalStorage(local_storage)

# def handleCloseOppPositions(entry, storage):

# 	if entry.entry_type == EntryType.TEntry:
# 		if entry.direction == Direction.LONG:
# 			long_trigger.t_entry_state = TEntryState.TWO
# 		else:
# 			short_trigger.t_entry_state = TEntryState.TWO


# 	print('Close Opp positions on friday 16')
# 	if 'POSITIONS' in storage:
# 		for p in storage['POSITIONS']:
# 			if p['data']['direction'] != entry.direction.value:
# 				pos = utils.getPosByOrderId(p['order_id'])
# 				if pos:
# 					pos.close()

def onStopLoss(pos):
	print("onStopLoss")

	local_storage = utils.getLocalStorage()
	print("sl:", str(local_storage))
	p_data = None
	if 'POSITIONS' in local_storage:
		for p in local_storage['POSITIONS']:
			if p['order_id'] == pos.orderID:
				p_data = p

	if p_data:
		if p_data['data']['type'] == EntryType.CTEntry.value:
			if pos.direction == 'buy':
				long_trigger.ct_so_count += 1
				if long_trigger.ct_entry_state.value == CTEntryState.COMPLETE.value:
					long_trigger.ct_entry_state = CTEntryState.THREE
					long_trigger.ct_tag = False
			else:
				short_trigger.ct_so_count += 1
				if short_trigger.ct_entry_state.value == CTEntryState.COMPLETE.value:
					short_trigger.ct_entry_state = CTEntryState.THREE
					long_trigger.ct_tag = False

		elif p_data['data']['type'] == EntryType.TEntry.value:
			if pos.direction == 'buy':
				long_trigger.t_macd_entry_state = TMacdEntryState.ONE
				long_trigger.t_rsi_entry_state = TRsiEntryState.ONE
			elif pos.direction == 'sell':
				short_trigger.t_macd_entry_state = TMacdEntryState.ONE
				short_trigger.t_rsi_entry_state = TRsiEntryState.ONE

	return

def checkTime():
	''' 
	Checks current time and initiates 
	closing sequence where necessary.
	'''
	global time_state

	time = utils.convertTimestampToTime(chart.getLatestTimestamp(0))
	london_time = utils.convertTimezone(utils.setTimezone(time, 'Australia/Melbourne'), 'Europe/London')
	print('London Time:', str(london_time))
	if london_time.weekday() == 4 and london_time.hour >= 20:
		print('is STOP!')
		time_state = TimeState.STOP
	elif london_time.weekday() == 4 and london_time.hour >= 12:
		print('is NCT!')
		time_state = TimeState.NCT
	else:
		time_state = TimeState.TRADING

def runSequence(shift):
	''' Main trade plan sequence '''
	print(
		"SMA:", str(sma.getCurrent()),
		"RSI:", str(rsi.getCurrent()),
		"I_MAE:", str(inner_mae.getCurrent()),  
		"O_MAE:", str(outer_mae.getCurrent()), 
		"S_BOLL:", str(short_boll.getCurrent()),
		"L_BOLL:", str(long_boll.getCurrent()),
		"MACD:", str(macd.getCurrent()),
		"ATR:", str(atr.getCurrent())
	)

	if time_state == TimeState.STOP:
		return

	ctEntrySetup(shift, long_trigger)
	ctEntrySetup(shift, short_trigger)
	tMacdEntrySetup(shift, long_trigger)
	tMacdEntrySetup(shift, short_trigger)
	tRsiEntrySetup(shift, long_trigger)
	tRsiEntrySetup(shift, short_trigger)

def tMacdEntrySetup(shift, trigger):

	if trigger:

		if trigger.t_macd_entry_state == TMacdEntryState.ONE:
			if tMacdEntryConfirmationOne(shift, trigger.direction):
				trigger.t_macd_entry_state = TMacdEntryState.COMPLETE
				return confirmation(trigger, EntryType.TEntry)

			elif tMacdEntryConfirmationTwo(shift, trigger.direction):
				trigger.t_macd_entry_state = TMacdEntryState.COMPLETE
				return confirmation(trigger, EntryType.TEntry)

def tMacdEntryConfirmationOne(shift, direction):
	print('T Macd Entry One ('+str(direction)+'):',
		str(isMacdzDirOneConf(shift, direction)),
		str(isCloseABLMaeIn(shift, direction, reverse=True)),
		str(isCloseABSma(shift, direction, reverse=True)),
		str(isBB(shift, direction)),
		str(not isDoji(shift))
	)
	return (
		isMacdzDirOneConf(shift, direction) and
		isCloseABLMaeIn(shift, direction, reverse=True) and
		isCloseABSma(shift, direction, reverse=True) and
		not (isCloseABLongBoll(shift, direction) and
		isCloseABShortBoll(shift, direction)) and
		isBB(shift, direction) and
		not isDoji(shift)
	)

def tMacdEntryConfirmationTwo(shift, direction):
	print('T Macd Entry Two ('+str(direction)+'):',
		str(isMacdzDirTwoConf(shift, direction)),
		str(isCloseABSma(shift, direction)),
		str(isBB(shift, direction)),
		str(not isDoji(shift))
	)

	return (
		isMacdzDirTwoConf(shift, direction) and
		isCloseABSma(shift, direction) and
		not (isCloseABLongBoll(shift, direction) and
		isCloseABShortBoll(shift, direction)) and
		isBB(shift, direction) and
		not isDoji(shift)
	)

def tRsiEntrySetup(shift, trigger):

	if trigger:

		if trigger.t_rsi_entry_state == TRsiEntryState.ONE:

			if isRetHitCtOMae(shift, trigger.direction):
				trigger.t_rsi_entry_state = TRsiEntryState.TWO
				return tRsiEntrySetup(shift, trigger)

		elif trigger.t_rsi_entry_state == TRsiEntryState.TWO:
			if tRsiEntryConfirmation(shift, trigger.direction):
				trigger.t_rsi_entry_state = TRsiEntryState.COMPLETE
				return confirmation(trigger, EntryType.TEntry)

		if (
			isRetHitCtLMae(shift, trigger.direction) and 
			not isRetHitCtOMae(shift, trigger.direction)
		):
			trigger.t_rsi_entry_state = TRsiEntryState.ONE
			return

def tRsiEntryConfirmation(shift, direction):
	print('T Rsi Entry One ('+str(direction)+'):',
		str(isPriorRsiConf(shift, direction)),
		str(isCloseABIMaeIn(shift, direction, reverse=True)),
		str(isCloseABLMaeIn(shift, direction)),
		str(isBB(shift, direction)),
		str(not isDoji(shift))
	)
	return (
		isPriorRsiConf(shift, direction) and
		isCloseABIMaeIn(shift, direction, reverse=True) and
		isCloseABLMaeIn(shift, direction) and
		isBB(shift, direction) and
		not isDoji(shift)
	)

def isTEntryPosition(direction):
	local_storage = utils.getLocalStorage()

	if 'POSITIONS' in local_storage:
		for p in local_storage['POSITIONS']:
			if (
				p['data']['direction'] == direction.value and
				p['data']['type'] == EntryType.TEntry.value
				):
				return True

	return False

def isDirectionPosition(direction):
	for pos in utils.positions:
		if pos.direction == 'buy' and direction == Direction.LONG:
			return True
		elif pos.direction == 'sell' and direction == Direction.SHORT:
			return True
	return False

def ctEntrySetup(shift, trigger):

	if trigger:

		if trigger.ct_entry_state == CTEntryState.ONE:			
			if closeBelowBollConf(shift, trigger.direction) or isHitBoll(shift, trigger.direction, reverse=True):
				return

			if isRetHitCtIMae(shift, trigger.direction, reverse=True):
				trigger.ct_entry_state = CTEntryState.TWO
				return

		elif trigger.ct_entry_state == CTEntryState.TWO:
			if isCloseABOMaeOut(shift, trigger.direction, reverse=True):

				if ctEntryConfirmation(shift, trigger.direction):
					trigger.ct_entry_state = CTEntryState.COMPLETE

					long_trigger.t_macd_entry_state = TMacdEntryState.COMPLETE
					long_trigger.t_rsi_entry_state = TRsiEntryState.COMPLETE
					short_trigger.t_macd_entry_state = TMacdEntryState.COMPLETE
					short_trigger.t_rsi_entry_state = TRsiEntryState.COMPLETE

					return confirmation(trigger, EntryType.CTEntry)
				elif closeBelowBollConf(shift, trigger.direction):
					trigger.ct_entry_state = CTEntryState.ONE
					return
				else:
					trigger.ct_entry_state = CTEntryState.THREE
					return

			if closeBelowBollConf(shift, trigger.direction):
				trigger.ct_entry_state = CTEntryState.ONE
				return

		elif trigger.ct_entry_state == CTEntryState.THREE:
			if isRetHitIMae(shift, trigger.direction, reverse=True):
				trigger.ct_entry_state = CTEntryState.ONE
				trigger.ct_tag = False
				return
			elif ctEntryConfirmation(shift, trigger.direction):
				trigger.ct_entry_state = CTEntryState.COMPLETE

				long_trigger.t_macd_entry_state = TMacdEntryState.COMPLETE
				long_trigger.t_rsi_entry_state = TRsiEntryState.COMPLETE
				short_trigger.t_macd_entry_state = TMacdEntryState.COMPLETE
				short_trigger.t_rsi_entry_state = TRsiEntryState.COMPLETE

				return confirmation(trigger, EntryType.CTEntry)

		elif trigger.ct_entry_state == CTEntryState.COMPLETE:
			if ctReverseTagConfirmation(shift, trigger.direction):
				trigger.ct_tag = True

			if isCloseABLMaeIn(shift, trigger.direction, reverse=True):
				trigger.ct_entry_state = CTEntryState.ONE
				trigger.ct_tag = False

				long_trigger.t_macd_entry_state = TMacdEntryState.ONE
				long_trigger.t_rsi_entry_state = TRsiEntryState.ONE
				short_trigger.t_macd_entry_state = TMacdEntryState.ONE
				short_trigger.t_rsi_entry_state = TRsiEntryState.ONE

				return

			if trigger.ct_tag and ctReverseEntryConfirmation(shift, trigger.direction):
				trigger.ct_entry_state = CTEntryState.ONE
				trigger.ct_tag = False

				long_trigger.t_macd_entry_state = TMacdEntryState.ONE
				long_trigger.t_rsi_entry_state = TRsiEntryState.ONE
				short_trigger.t_macd_entry_state = TMacdEntryState.ONE
				short_trigger.t_rsi_entry_state = TRsiEntryState.ONE

				if trigger.direction == Direction.LONG:
					return confirmation(short_trigger, EntryType.TEntry)
				else:
					return confirmation(long_trigger, EntryType.TEntry)
		

def ctEntryConfirmation(shift, direction):
	print('CT Init Conf ('+str(direction)+'):',
			str(isRsiDirConf(shift, direction, reverse=True)),
			str(isBollAboveLMae(shift, direction, reverse=True)),
			str(isCloseABOMaeOut(shift, direction, reverse=True)),
		)
	

	if (
		isRsiDirConf(shift, direction, reverse=True) and
		isBollAboveLMae(shift, direction, reverse=True) and
		isCloseABOMaeOut(shift, direction, reverse=True)
	):
		print('CT Entry ('+str(direction)+'): ('+
			str(isHitLongBoll(shift, direction, reverse=True) and 
				isHitShortBoll(shift, direction, reverse=True)), 'or',
			str(isCloseABShortBoll(shift, direction, reverse=True)), 'or',
			str(isCloseABLongBoll(shift, direction, reverse=True))+')'
		)

		if (isHitLongBoll(shift, direction, reverse=True) and 
			isHitShortBoll(shift, direction, reverse=True)):
			return True

		elif isCloseABLongBoll(shift, direction, reverse=True):
			return True

		elif isCloseABShortBoll(shift, direction, reverse=True):
			return time_state.value < TimeState.NCT.value

	return False

def closeBelowBollConf(shift, direction):
	if (isHitLongBoll(shift, direction, reverse=True) and 
		isHitShortBoll(shift, direction, reverse=True)):
		return True

	elif isCloseABLongBoll(shift, direction, reverse=True):
		return True

	elif isCloseABShortBoll(shift, direction, reverse=True):
		return True

	return False

def ctReverseTagConfirmation(shift, direction):
	return (
		isRetHitLMae(shift, direction, reverse=True) and
		isCloseInsideBoll(shift, direction, reverse=True)
	)

def ctReverseEntryConfirmation(shift, direction):
	return (
		isRsiDirConf(shift, direction, reverse=True) and
		isCloseInsideBoll(shift, direction, reverse=True) and
		isBB(shift, direction, reverse=True) and
		not isDoji(shift)
	)

def isCtEntryPosition(direction):
	local_storage = utils.getLocalStorage()

	if 'POSITIONS' in local_storage:
		for p in local_storage['POSITIONS']:
			if (
				p['data']['direction'] == direction.value and
				p['data']['type'] == EntryType.CTEntry.value
				):
				return True

	return False

def isCloseABSma(shift, direction, reverse=False):
	val = sma.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close < val
		else:
			return close > val
	else:
		if direction == Direction.LONG:
			return close > val
		else:
			return close < val

def isCloseABOMaeOut(shift, direction, reverse=False):
	upper, lower = outer_mae.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close < lower
		else:
			return close > upper
	else:
		if direction == Direction.LONG:
			return close > upper
		else:
			return close < lower

def isCloseABOMaeIn(shift, direction, reverse=False):
	upper, lower = outer_mae.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close > lower
		else:
			return close < upper
	else:
		if direction == Direction.LONG:
			return close < upper
		else:
			return close > lower

def isCloseABIMaeOut(shift, direction, reverse=False):
	upper, lower = inner_mae.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close < lower
		else:
			return close > upper
	else:
		if direction == Direction.LONG:
			return close > upper
		else:
			return close < lower

def isCloseABIMaeIn(shift, direction, reverse=False):
	upper, lower = inner_mae.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close > lower
		else:
			return close < upper
	else:
		if direction == Direction.LONG:
			return close < upper
		else:
			return close > lower

def isCloseABLMaeOut(shift, direction, reverse=False):
	upper, lower = limit_mae.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close < lower
		else:
			return close > upper
	else:
		if direction == Direction.LONG:
			return close > upper
		else:
			return close < lower

def isCloseABLMaeIn(shift, direction, reverse=False):
	upper, lower = limit_mae.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close > lower
		else:
			return close < upper
	else:
		if direction == Direction.LONG:
			return close < upper
		else:
			return close > lower

def isRsiDirConf(shift, direction, reverse=False):
	stridx = rsi.getCurrent()[0]

	if reverse:
		if direction == Direction.LONG:
			return stridx < VARIABLES['rsi_short']
		else:
			return stridx > VARIABLES['rsi_long']
	else:
		if direction == Direction.LONG:
			return stridx > VARIABLES['rsi_long']
		else:
			return stridx < VARIABLES['rsi_short']

def isPriorRsiConf(shift, direction, reverse=False):
	stridx = rsi.get(1, 1)[0][0]

	if reverse:
		if direction == Direction.LONG:
			return stridx < VARIABLES['rsi_short']
		else:
			return stridx > VARIABLES['rsi_long']
	else:
		if direction == Direction.LONG:
			return stridx > VARIABLES['rsi_long']
		else:
			return stridx < VARIABLES['rsi_short']

def isMacdzDirOneConf(shift, direction, reverse=False):
	hist = macd.getCurrent()[2]

	if reverse:
		if direction == Direction.LONG:
			return hist <= round(-VARIABLES['macd_two'] * 0.00001, 5)
		else:
			return hist >= round(VARIABLES['macd_two'] * 0.00001, 5)
	else:
		if direction == Direction.LONG:
			return hist >= round(VARIABLES['macd_two'] * 0.00001, 5)
		else:
			return hist <= round(-VARIABLES['macd_two'] * 0.00001, 5)

def isMacdzDirTwoConf(shift, direction, reverse=False):
	hist = macd.getCurrent()[2]

	if reverse:
		if direction == Direction.LONG:
			return hist < round(-VARIABLES['macd_two'] * 0.00001, 5)
		else:
			return hist > round(VARIABLES['macd_two'] * 0.00001, 5)
	else:
		if direction == Direction.LONG:
			return hist > round(VARIABLES['macd_two'] * 0.00001, 5)
		else:
			return hist < round(-VARIABLES['macd_two'] * 0.00001, 5)

def isRetHitCtOMae(shift, direction, reverse=False):
	upper, lower = outer_mae.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return high >= upper
		else:
			return low <= lower
	else:
		if direction == Direction.LONG:
			return low <= lower
		else:
			return high >= upper

def isRetHitIMae(shift, direction, reverse=False):
	upper, lower = inner_mae.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return high >= lower
		else:
			return low <= upper
	else:
		if direction == Direction.LONG:
			return low <= upper
		else:
			return high >= lower

def isRetHitCtIMae(shift, direction, reverse=False):
	upper, lower = inner_mae.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return high >= upper
		else:
			return low <= lower
	else:
		if direction == Direction.LONG:
			return low <= lower
		else:
			return high >= upper

def isRetHitLMae(shift, direction, reverse=False):
	upper, lower = limit_mae.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return high >= lower
		else:
			return low <= upper
	else:
		if direction == Direction.LONG:
			return low <= upper
		else:
			return high >= lower

def isRetHitCtLMae(shift, direction, reverse=False):
	upper, lower = limit_mae.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return low <= lower
		else:
			return high >= upper
	else:
		if direction == Direction.LONG:
			return high >= upper
		else:
			return low <= lower

def getTsStopPrice(shift, direction):
	upper, lower = outer_mae.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)
	ask = utils.getAsk(chart.pair)
	bid = utils.getBid(chart.pair)

	if direction == Direction.LONG:
		mae_price = round(lower - utils.convertToPrice(VARIABLES['stoprange']), 5)
		bar_price = round(low - utils.convertToPrice(VARIABLES['ts_offset']), 5)
		bid_price = round(bid - utils.convertToPrice(VARIABLES['breakeven_min_pips']), 5)

		return min(mae_price, bar_price, bid_price)

	else:
		mae_price = round(upper + utils.convertToPrice(VARIABLES['stoprange']), 5)
		bar_price = round(high + utils.convertToPrice(VARIABLES['ts_offset']), 5)
		ask_price = round(ask + utils.convertToPrice(VARIABLES['breakeven_min_pips']), 5)
		
		return max(mae_price, bar_price, ask_price)

def isBB(shift, direction, reverse=False):
	_open, _, _, close = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return close < _open
		else:
			return close > _open

	else:
		if direction == Direction.LONG:
			return close > _open
		else:
			return close < _open

def isDoji(shift):
	_open, _, _, close = chart.getOHLC(shift)
	return not utils.convertToPips(abs(round(_open - close, 5))) >= VARIABLES['doji_range']

def isBollAboveLMae(shift, direction, reverse=False):
	l_mae_upper, l_mae_lower = limit_mae.getCurrent()
	s_boll_upper, s_boll_lower = short_boll.getCurrent()
	l_boll_upper, l_boll_lower = long_boll.getCurrent()

	if reverse:
		if direction == Direction.LONG:
			return s_boll_lower < l_mae_lower and l_boll_lower < l_mae_lower
		else:
			return s_boll_upper > l_mae_upper and l_boll_upper > l_mae_upper
	else:
		if direction == Direction.LONG:
			return s_boll_upper > l_mae_upper and l_boll_upper > l_mae_upper
		else:
			return s_boll_lower < l_mae_lower and l_boll_lower < l_mae_lower

def isCloseInsideBoll(shift, direction, reverse=False):
	close = chart.getOHLC(shift)[3]
	s_boll_upper, s_boll_lower = short_boll.getCurrent()
	l_boll_upper, l_boll_lower = long_boll.getCurrent()

	if reverse:
		if direction == Direction.LONG:
			return close > s_boll_lower and close > l_boll_lower
		else:
			return close < s_boll_upper and close < l_boll_upper
	else:
		if direction == Direction.LONG:
			return close < s_boll_upper and close < l_boll_upper
		else:
			return close > s_boll_lower and close > l_boll_lower

def isHitBoll(shift, direction, reverse=False):
	return isHitShortBoll(shift, direction, reverse=reverse) or isHitLongBoll(shift, direction, reverse=reverse)

def isHitShortBoll(shift, direction, reverse=False):
	upper, lower = short_boll.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return low <= lower
		else:
			return high >= upper
	else:
		if direction == Direction.LONG:
			return high >= upper
		else:
			return low <= lower

def isHitLongBoll(shift, direction, reverse=False):
	upper, lower = long_boll.getCurrent()
	_, high, low, _ = chart.getOHLC(shift)

	if reverse:
		if direction == Direction.LONG:
			return low <= lower
		else:
			return high >= upper
	else:
		if direction == Direction.LONG:
			return high >= upper
		else:
			return low <= lower

def isCloseABShortBoll(shift, direction, reverse=False):
	upper, lower = short_boll.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close <= lower
		else:
			return close >= upper
	else:
		if direction == Direction.LONG:
			return close >= upper
		else:
			return close <= lower

def isCloseABLongBoll(shift, direction, reverse=False):
	upper, lower = long_boll.getCurrent()
	close = chart.getOHLC(shift)[3]

	if reverse:
		if direction == Direction.LONG:
			return close <= lower
		else:
			return close >= upper
	else:
		if direction == Direction.LONG:
			return close >= upper
		else:
			return close <= lower

def isLBollABSBoll(shift, direction, reverse=False):
	l_upper, l_lower = long_boll.getCurrent()
	s_upper, s_lower = short_boll.getCurrent()

	if reverse:
		if direction == Direction.LONG:
			return l_upper < s_upper
		else:
			return l_lower > s_lower
	else:
		if direction == Direction.LONG:
			return l_upper > s_upper
		else:
			return l_lower < s_lower

def getStopRange():
	return round(utils.convertToPips(atr.getCurrent()), 1)

def confirmation(trigger, entry_type):
	''' confirm entry '''
	print('confirmation init')

	if entry_type == EntryType.TEntry:
		trigger.t_macd_entry_state = TMacdEntryState.ONE
		
		if isTEntryPosition(trigger.direction):
			return

	elif entry_type == EntryType.CTEntry:
		# if trigger.direction == Direction.LONG:
		# 	if isCtEntryPosition(Direction.SHORT):
		# 		trigger.ct_entry_state = CTEntryState.TWO
		# 		return
		# else:
		# 	if isCtEntryPosition(Direction.LONG):
		# 		trigger.ct_entry_state = CTEntryState.TWO
		# 		return

		if trigger.ct_so_count >= VARIABLES['max_ct_entry_retries']:
			trigger.ct_entry_state = CTEntryState.TWO
			return


	trigger.entry_type = entry_type
	trigger.stop_range = getStopRange()
	print("confirmation:", str(trigger.direction), str(entry_type), str(trigger.stop_range))
	pending_entries.append(trigger)

def report():
	''' Prints report for debugging '''

	print("\n")

	print("L:", str(long_trigger))
	print("S:", str(short_trigger))

	print("CLOSED POSITIONS:")
	count = 0
	for pos in utils.closedPositions:
		count += 1
		print(str(count) + ":", 
			str(pos.direction), 
			"Profit:", str(pos.getProfit(price_type = 'c')), '|',
			str(pos.getPercentageProfit(price_type='c'))+'%'
		)

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", 
			str(pos.direction), 
			"Profit:", str(pos.getProfit(price_type = 'c')), '|',
			str(pos.getPercentageProfit(price_type='c'))+'%'
		)

	print("--|\n")
