from CMCTrader import Constants
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	'START_TIME' : '6:55',
	'END_TIME' : '16:00',
	'noNewTradesOnProfit' : '15:00',
	'noNewTrades' : '15:30',
	'setBE' : '15:50',
	'risk' : 1.0,
	'stoprange' : 17,
	'halfprofit' : 34,
	'fullprofit' : 140,
	'targetProfit' : 43,
	'rounding' : 100,
	'beRange' : 2,
	'minimumBarsForTrigger' : 2,
	'NEWS' : None,
	'newsTimeBeforeBE' : 1,
	'newsTimeBeforeBlock' : 5,
	'RSI' : None,
	'rsiOverbought' : 70,
	'rsiOversold' : 30,
	'longRsiSignal' : 60,
	'shortRsiSignal' : 40,
	'longZeroMACD' : 65,
	'shortZeroMACD' : 35,
	'MACD' : None,
	'macdSignal' : 0.00003,
	'CCI' : None,
	'cciTrendOverbought' : 70,
	'cciTrendOversold' : -70,
	'cciCTOverbought' : 60,
	'cciCTOversold' : -60,
	'ADX' : None,
	'adxThreshold' : 27.0
}

utils = None

regSAR = None
slowSAR = None
blackSAR = None
cci = None
sma3 = None
macd = None
rsi = None
adxr = None

pendingTriggers = []
pendingEntries = []
pendingExits = []
pendingBreakevens = []
strands = []

isInit = True

isLongSignal = False
isShortSignal = False
isTriggeredLong = False
isTriggeredShort = False

noNewTrades = False

canTradeLongMaster = True
canTradeShortMaster = True

currentNews = None
newsTradeBlock = False

maxStrand = None
minStrand = None
blockCount = 0
blockDirection = None

entryPrice = 0
exitPrice = 0
exitPos = None

bank = 0

isPositionHalved = False

isProfitTime = False
isNoTradesTime = False
isBETime = False

class Direction(Enum):
	LONG = 1
	SHORT = 2

class EntryState(Enum):
	RET_PARA = 1
	T_PARA = 2
	SWING_ONE = 3
	SWING_TWO = 4
	SWING_THREE = 5
	CONFIRMATION = 6
	ENTER = 7

class Trigger(object):
	def __init__(self, direction):
		self.direction = direction
		self.entryState = EntryState.RET_PARA
		self.entryPrice = 0
		self.isCancelled = False
		self.isBlocked = False
		self.macdConfirmed = False
		self.noCCIObos = False
		self.bothParaHit = False
		self.isObos = False
		self.waitForOppTrigger = False
		self.canTrade = True
		self.lastTriggerLength = 0

class Strand(object):
	def __init__(self, start, direction):
		self.start = start
		self.end = 0
		self.direction = direction
		self.isPassed = False

def init(utilities):
	global utils
	utils = utilities

	global regSAR
	regSAR = utils.SAR(1)
	
	global blackSAR
	blackSAR = utils.SAR(2)
	
	global slowSAR
	slowSAR = utils.SAR(3)

	global cci
	cci = utils.CCI(4, 2)

	global sma3
	sma3 = utils.CCI(5, 1)
	
	global macd
	macd = utils.MACD(6, 1)

	global rsi
	rsi = utils.RSI(7, 1)

	global adxr
	adxr = utils.ADXR(8, 1)

	# amount = 1
	# while (not preSequence(0, amount)):
	# 	amount += 1

	global isInit
	isInit = False
	for t in pendingTriggers:
		print(t.direction)

def onNewBar():
	if (isInit):
		return

	checkTime()
	ausTime = utils.getAustralianTime()
	print("\nTime:",str(ausTime.hour)+":"+str(ausTime.minute)+":"+str(ausTime.second))
	runSequence(0)

	for pos in utils.positions:
		immedExitSequence(pos, 0)
	
	print("PENDING TRIGGERS:")
	count = 0
	for t in pendingTriggers:
		if (not t.isCancelled):
			count += 1
			print(str(count) + ":", t.direction, "isBlocked:", str(t.isBlocked))
	print(" Block Count:", str(blockCount), "Block direction:", str(blockDirection))

	print("POSITIONS:")
	count = 0
	for pos in utils.positions:
		count += 1
		print(str(count) + ":", pos.direction)

def onStartTrading():
	print("onStartTrading")
	global noNewTrades
	noNewTrades = False
	global bank
	bank = utils.getBankSize()
	print(bank)
	global isProfitTime, isNoTradesTime, isBETime
	isProfitTime = False
	isNoTradesTime = False
	isBETime = False

	if len(pendingTriggers) >= 3:
		pendingTriggers[0].isCancelled = True

def onFinishTrading():
	print("FINISHED TRADING")
	print(str(utils.getTotalProfit()))

def checkTime():
	global isProfitTime, isNoTradesTime, isBETime

	londonTime = utils.getLondonTime()
	parts = VARIABLES['noNewTradesOnProfit'].split(':')
	noNewTradesOnProfitTime = utils.createLondonTime(londonTime.year, londonTime.month, londonTime.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['noNewTrades'].split(':')
	noNewTradesTime = utils.createLondonTime(londonTime.year, londonTime.month, londonTime.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['setBE'].split(':')
	setBETime = utils.createLondonTime(londonTime.year, londonTime.month, londonTime.day, int(parts[0]), int(parts[1]), 0)

	global noNewTrades
	if (londonTime > setBETime and not isBETime):
		print("IS BE TIME")
		noNewTrades = True
		isBETime = True
		for pos in utils.positions:
			if (pos.getProfit() >= VARIABLES['beRange']):
				if not pos in pendingBreakevens:
					pendingBreakevens.append(pos)
			else:
				pendingBreakevens.append(pos)
	elif (londonTime > noNewTradesTime and not isNoTradesTime and not isBETime0):
		print("IS NO NEW TRADES TIME")
		noNewTrades = True
		isNoTradesTime = True
	elif (londonTime > noNewTradesOnProfitTime and not isProfitTime and not isNoTradesTime and not isBETime):
		print("IS NO NEW TRADES ON PROFIT TIME")
		print("Total profit:", str(utils.getTotalProfit()))
		if (utils.getTotalProfit() >= VARIABLES['halfprofit']):
			isProfitTime = True
			noNewTrades = True

	# if (londonTime.weekday() == 4 and londonTime.hour >= int(VARIABLES['END_TIME'].split(':')[0]) + 1): # time checking is wrong
	# 	for pos in utils.positions:
	# 		pendingExits.append(pos)

def preSequence(shift, amount):
	global pendingTriggers
	pendingTriggers = []
	global pendingEntries
	pendingEntries = []
	global strands
	strands = []

	for i in range(amount):
		currShift = shift + amount - i
		runSequence(currShift)

	if (len(pendingTriggers) >= 3):
		pendingTriggers[0].isCancelled = True
		pendingEntries = []
		print(pendingTriggers)
		return True

	return False

def onDownTime():
	if (isInit):
		return

	print("onDownTime")
	ausTime = utils.getAustralianTime()
	print("\nTime:",str(ausTime.hour)+":"+str(ausTime.minute)+":"+str(ausTime.second))

	runSequence(0, isDownTime = True)

	for entry in pendingEntries:
		del pendingEntries[pendingEntries.index(entry)]

def onLoop():
	global isPositionHalved

	exitPositions()
	enterPositions()

	for pos in utils.positions:
		if (pos.getProfit() >= VARIABLES['halfprofit'] and not isPositionHalved):
			isPositionHalved = True
			pos.modifyPositionSize(pos.lotsize/2)
			pos.breakeven()
			if (not pos.apply()):
				pendingBreakevens.append(pos)

		if pos in pendingBreakevens:
			if (pos.getProfit() > VARIABLES['beRange']):
				pos.breakeven()
				if (pos.apply()):
					del pendingBreakevens[pendingBreakevens.index(pos)]

	for t in pendingTriggers:
		if (t.entryState == EntryState.CONFIRMATION and not t.isCancelled):
			price = utils.getBid(VARIABLES['TICKETS'][0])
			if (t.direction == Direction.LONG):
				if ((price > regSAR.getCurrent(VARIABLES['TICKETS'][0]) and price > slowSAR.getCurrent(VARIABLES['TICKETS'][0])) or t.bothParaHit):
					t.bothParaHit = True
					# print("price above sar:", "curr:", str(price), "entry:", str(t.entryPrice))
					if (price <= t.entryPrice or t.entryPrice == 0):
						if (rsi.getCurrent(VARIABLES['TICKETS'][0]) <= VARIABLES['rsiOverbought']):
							if (cancelOnBlocked(t)):
								return
							print("entered long onloop")
							t.entryPrice = price
							pendingEntries.append(t)
							t.isCancelled = True
						else:
							print("overbought")
							t.entryState = EntryState.SWING_TWO
							t.noCCIObos = True
							t.isObos = True
							t.lastTriggerLength = len(pendingTriggers)
							t.macdConfirmed = False
							t.entryPrice = price
							swingTwo(t, 0)
			else:
				if ((price < regSAR.getCurrent(VARIABLES['TICKETS'][0]) and price < slowSAR.getCurrent(VARIABLES['TICKETS'][0])) or t.bothParaHit):
					t.bothParaHit = True
					# print("price below sar:", "curr:", str(price), "entry:", str(t.entryPrice))
					if (price >= t.entryPrice or t.entryPrice == 0):
						if (rsi.getCurrent(VARIABLES['TICKETS'][0]) >= VARIABLES['rsiOversold']):
							if (cancelOnBlocked(t)):
								return
							print("entered short onloop")
							t.entryPrice = price
							pendingEntries.append(t)
							t.isCancelled = True
						else:
							print("overbought")
							t.entryState = EntryState.SWING_TWO
							t.noCCIObos = True
							t.isObos = True
							t.lastTriggerLength = len(pendingTriggers)
							t.macdConfirmed = False
							t.entryPrice = price
							swingTwo(t, 0)

def exitPositions():
	global pendingExits
	global exitPrice, exitPos
	global blockCount, blockDirection
	if (len(utils.positions) > 0):
		for pos in pendingExits:
			if (exitPos == pos and not exitPrice == 0):
				if (pos.direction == 'buy'):
					if (utils.getBid(VARIABLES['TICKETS'][0]) <= exitPrice):
						pos.quickExit()
						exitPrice = 0
				else:
					if (utils.getBid(VARIABLES['TICKETS'][0]) >= exitPrice):
						pos.quickExit()
						exitPrice = 0
			else:
				pos.quickExit()
			for t in pendingTriggers:
				if not t.isCancelled and t.isBlocked:
					t.isBlocked = False
					blockCount = 0
					blockDirection = None
	else:
		exitPrice = 0
		exitPos = None
		pendingExits = []

def enterPositions():
	global canTradeLongMaster, canTradeShortMaster
	global noNewTrades
	global entryPrice
	global isPositionHalved

	checkCurrentNews()

	for entry in pendingEntries:
		if (entry.direction == Direction.LONG):
			if (not entry.canTrade or not canTradeLongMaster):
				del pendingEntries[pendingEntries.index(entry)]
			else:
				canTradeShortMaster = True
				if (len(utils.positions) > 0):
					for pos in utils.positions:
						if (pos.direction == 'buy'):
							del pendingEntries[pendingEntries.index(entry)]
						else:
							isPositionHalved = False
							if (not noNewTrades and not newsTradeBlock and (utils.getTotalProfit() + pos.getProfit()) >= -VARIABLES['stoprange'] * 1.5 and (utils.getTotalProfit() + pos.getProfit()) < VARIABLES['targetProfit']):
								pos.stopAndReverse(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['fullprofit'])
								entryPrice = entry.entryPrice
							elif ((utils.getTotalProfit() + pos.getProfit()) < -VARIABLES['stoprange'] * 1.5 or (utils.getTotalProfit() + pos.getProfit()) >= VARIABLES['targetProfit']):
								pos.quickExit()
								noNewTrades = True
							else:
								pos.quickExit()
				else:
					isPositionHalved = False
					if (not noNewTrades and not newsTradeBlock and utils.getTotalProfit() >= -VARIABLES['stoprange'] * 1.5 and utils.getTotalProfit() < VARIABLES['targetProfit']):
						utils.buy(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['fullprofit'])
						entryPrice = entry.entryPrice
					else:
						print("Couldn't enter:", str(utils.getTotalProfit()))
						del pendingEntries[pendingEntries.index(entry)]
		else:
			if (not entry.canTrade or not canTradeShortMaster):
				del pendingEntries[pendingEntries.index(entry)]
			else:
				canTradeLongMaster = True
				if (len(utils.positions) > 0):
					for pos in utils.positions:
						if (pos.direction == 'sell'):
							del pendingEntries[pendingEntries.index(entry)]
						else:
							isPositionHalved = False
							if (not noNewTrades and not newsTradeBlock and (utils.getTotalProfit() + pos.getProfit()) >= -VARIABLES['stoprange'] * 1.5 and (utils.getTotalProfit() + pos.getProfit()) < VARIABLES['targetProfit']):
								pos.stopAndReverse(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['fullprofit'])
								entryPrice = entry.entryPrice
							elif ((utils.getTotalProfit() + pos.getProfit()) < -VARIABLES['stoprange'] * 1.5 or (utils.getTotalProfit() + pos.getProfit()) >= VARIABLES['targetProfit']):
								pos.quickExit()
								noNewTrades = True
							else:
								pos.quickExit()
				else:
					isPositionHalved = False
					if (not noNewTrades and not newsTradeBlock and utils.getTotalProfit() >= -VARIABLES['stoprange'] * 1.5 and utils.getTotalProfit() < VARIABLES['targetProfit']):
						utils.sell(utils.getLotsize(bank, VARIABLES['risk'], VARIABLES['stoprange']), sl = VARIABLES['stoprange'], tp = VARIABLES['fullprofit'])
						entryPrice = entry.entryPrice
					else:
						print("Couldn't enter:", str(utils.getTotalProfit()))
						del pendingEntries[pendingEntries.index(entry)]

def failsafe(timestamps):
	global pendingEntries
	global exitPrice
	print("Missing timestamps:", str(timestamps[VARIABLES['TICKETS'][0]]))

	earliest = utils.getEarliestTimestamp(timestamps[VARIABLES['TICKETS'][0]])
	offset = utils.getBarOffset(earliest) # find initial offset by getting index of timestamp

	i = 0
	for timestamp in timestamps[VARIABLES['TICKETS'][0]]:
		currShift = offset - i
		print("Time:", str(utils.convertTimestampToTime(timestamp)))
		runSequence(currShift)
		for t in pendingTriggers:
			if (t.entryState == EntryState.CONFIRMATION and not t.isCancelled):
				backtestConfirmation(t, currShift)

		high = utils.ohlc[VARIABLES['TICKETS'][0]][timestamp][1]
		low = utils.ohlc[VARIABLES['TICKETS'][0]][timestamp][2]
		pendingEntries = pendingEntries[-1:]
		if (len(pendingEntries) > 0):
			for pos in utils.positions:
				if ((pendingEntries[-1].direction == Direction.LONG and pos.direction == 'sell') or (pendingEntries[-1].direction == Direction.SHORT and pos.direction == 'buy')):
					if not pos in pendingExits:
						pendingExits.append(pos)
			backtestImmedExitSequence(pendingEntries[-1], currShift)
			if (exitPrice > 0):
				if (pendingEntries[-1].direction == Direction.LONG):
					if (low < exitPrice):
						del pendingEntries[pendingEntries.index(entry)]
						exitPrice = 0
						exitPos = None
				else:
					if (high > exitPrice):
						del pendingEntries[pendingEntries.index(entry)]
						exitPrice = 0
						exitPos = None
		else:
			for pos in utils.positions:
				immedExitSequence(pos, currShift)
				if (exitPrice > 0):
					if (pos.direction == 'buy'):
						if (low < exitPrice):
							if not pos in pendingExits:
								pendingExits.append(pos)
							exitPrice = 0
							exitPos = None
					else:
						if (high > exitPrice):
							if not pos in pendingExits:
								pendingExits.append(pos)
							exitPrice = 0
							exitPos = None
		i += 1

	global canTradeLongMaster
	global canTradeShortMaster
	if (len(pendingEntries) > 0):
		entry = pendingEntries[-1]
		if (entry.direction == Direction.LONG):
			if (utils.getBid(VARIABLES['TICKETS'][0]) > entry.entryPrice):
				del pendingEntries[pendingEntries.index(entry)]
				canTradeLongMaster = False
				canTradeShortMaster = True
				for pos in utils.positions:
					if (pos.direction == 'sell'):
						if not pos in pendingExits:
							pendingExits.append(pos)
		else:
			if (utils.getBid(VARIABLES['TICKETS'][0]) < entry.entryPrice):
				del pendingEntries[pendingEntries.index(entry)]
				canTradeLongMaster = True
				canTradeShortMaster = False
				for pos in utils.positions:
					if (pos.direction == 'buy'):
						if not pos in pendingExits:
							pendingExits.append(pos)

def backtest():
	runSequence(0)

	for t in pendingTriggers:
		if (t.entryState == EntryState.CONFIRMATION and not t.isCancelled):
			backtestConfirmation(t, 0)
	if (len(pendingEntries) > 0):
		backtestImmedExitSequence(pendingEntries[-1], 0)

	print("PENDING TRIGGERS:")
	count = 0
	for t in pendingTriggers:
		if (not t.isCancelled):
			count += 1
			print(str(count) + ":", str(t.direction), "isBlocked:", str(t.isBlocked))
	print(" Block Count:", str(blockCount), "Block direction:", str(blockDirection))

	print("PENDING ENTRIES:")
	count = 0
	for entry in pendingEntries:
		count += 1
		print(str(count) + ":", str(entry.direction))

def onNews(title, time):
	global currentNews
	print("NEWS:", str(title))
	beTime = time - datetime.timedelta(minutes = VARIABLES['newsTimeBeforeBE'])
	noTradeTime = time - datetime.timedelta(minutes = VARIABLES['newsTimeBeforeBlock'])
	
	if (beTime <= utils.getLondonTime() < time):
		print(str(title), "done")
		for pos in utils.positions:
			if not pos in pendingBreakevens:
				print(str(time), "set news to BE")
				pendingBreakevens.append(pos)
	
	if (noTradeTime <= utils.getLondonTime() < time):
		print("no trades, 5 mins")
		currentNews = time
	elif (utils.getLondonTime() > time):
		if (currentNews == time):
			print("reset current news")
			currentNews = None
		if (title.startswith('_')):
			del utils.newsTimes[title]

def checkCurrentNews():
	global newsTradeBlock
	if (not currentNews == None):
		newsTradeBlock = True
	else:
		newsTradeBlock = False

def runSequence(shift, isDownTime = False):
	trendTrigger(shift)
	onNewCycle(shift)

	# BLACK PARA
	if (len(strands) > 0):
		cancelInvalidStrands(shift)
		if (not isDownTime):
			getPassedStrands(shift)
			blockFollowingTriggers()
			unblockOnTag(shift)

	entrySetup(shift)

def onNewCycle(shift):
	if (regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			direction = Direction.LONG
		else:
			direction = Direction.SHORT

		if (len(strands) > 1):
			strands[-1].end = regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
		print(regSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0])
		strands.append(Strand(regSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0], direction))
		print("New Strand:", str(direction))

def cancelInvalidStrands(shift):
	if (blackSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		if (blackSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			longStrands = [i for i in strands if i.direction == Direction.LONG and not i.isPassed and not i.end == 0]
			for strand in longStrands:
				if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] > strand.end):
					strand.isPassed = True
		else:
			shortStrands = [i for i in strands if i.direction == Direction.SHORT and not i.isPassed and not i.end == 0]
			for strand in shortStrands:
				if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] < strand.end):
					strand.isPassed = True

def getPassedStrands(shift):
	global blockCount, blockDirection
	getExtremeStrands()

	if (len(utils.positions) <= 0 and len(pendingEntries) <= 0):
		return
	
	if (not maxStrand == None):
		if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] < maxStrand.start and blackSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
			strands[strands.index(maxStrand)].isPassed = True
			print("black para crossed long")
			if (adxr.get(VARIABLES['TICKETS'][0], shift, 1)[0][0] >= VARIABLES['adxThreshold']):
				print("adx confirmation")
				canBlock = True
				if (len(utils.positions) > 0):
					if (utils.positions[0].direction == 'buy'):
						canBlock = False
				else:
					print(pendingEntries[-1].direction)
					if (pendingEntries[-1].direction == Direction.LONG):
						print("can't block")
						canBlock = False
				if (canBlock):
					blockCount = 0
					for t in pendingTriggers:
						if t.direction == Direction.LONG and not t.isCancelled and blockCount < 3:
							t.isBlocked = True
							blockCount += 1
					if (blockCount < 1):
						blockCount = 1
					blockDirection = Direction.LONG
				for t in pendingTriggers:
					if t.direction == Direction.SHORT and t.isBlocked:
						t.isBlocked = False
			else:
				print("no adx confirmation")

	if (not minStrand == None):
		if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] > minStrand.start and blackSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			strands[strands.index(minStrand)].isPassed = True
			print("black para crossed short")
			if (adxr.get(VARIABLES['TICKETS'][0], shift, 1)[0][0] >= VARIABLES['adxThreshold']):
				print("adx confirmation")
				canBlock = True
				if (len(utils.positions) > 0):
					if (utils.positions[0].direction == 'sell'):
						canBlock = False
				else:
					if (pendingEntries[-1].direction == Direction.SHORT):
						canBlock = False
				if (canBlock):
					blockCount = 0
					for t in pendingTriggers:
						if t.direction == Direction.SHORT and not t.isCancelled and blockCount < 3:
							t.isBlocked = True
							blockCount += 1
					if (blockCount < 1):
						blockCount = 1
					blockDirection = Direction.SHORT
				for t in pendingTriggers:
					if t.direction == Direction.LONG and t.isBlocked:
						t.isBlocked = False
			else:
				print("no adx confirmation")

def getExtremeStrands():
	global maxStrand
	global minStrand
	
	longStrands = [i for i in strands if i.direction == Direction.LONG and not i.isPassed and not i.end == 0]
	longStrands = longStrands[-2:]
	maxStrand = None
	for i in longStrands:
		if not maxStrand == None:
			if i.start > maxStrand.start:
				strands[strands.index(maxStrand)].isPassed = True
				maxStrand = i
		else:
			maxStrand = i

	shortStrands = [j for j in strands if j.direction == Direction.SHORT and not j.isPassed and not j.end == 0]
	shortStrands = shortStrands[-2:]
	minStrand = None
	for j in shortStrands:
		if not minStrand == None:
			if j.start < minStrand.start:
				strands[strands.index(minStrand)].isPassed = True
				minStrand = j
		else:
			minStrand = j

def blockFollowingTriggers():
	global blockCount

	if (not blockDirection == None):
		for trig in pendingTriggers:
			if (trig.direction == blockDirection and blockCount < 3 and not trig.isCancelled and not trig.isBlocked):
				print("blocked new trigger", str(trig.direction))
				trig.isBlocked = True
				blockCount += 1

def unblockOnTag(shift):
	global entryPrice
	global blockCount, blockDirection

	if (not entryPrice == 0):
		if (len(utils.positions) <= 0):
			print("no positions")
			entryPrice = 0
			if (blockCount > 0):
				blockDirection = None
				blockCount = 0
				for t in pendingTriggers:
					if not t.isCancelled and t.isBlocked:
						t.isBlocked = False
			return

		high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
		low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
		for pos in utils.positions:
			if pos.direction == 'buy':
				if (low <= entryPrice and blockCount > 0):
					print("Unblock all blocked SHORT triggers")
					blockDirection = None
					blockCount = 0
					for t in pendingTriggers:
						if t.direction == Direction.SHORT and not t.isCancelled and t.isBlocked:
							t.isBlocked = False
			else:
				if (high >= entryPrice and blockCount > 0):
					print("Unblock all blocked LONG triggers")
					blockDirection = None
					blockCount = 0
					for t in pendingTriggers:
						if t.direction == Direction.LONG and not t.isCancelled and t.isBlocked:
							t.isBlocked = False
	# entryPrice = 0
	# lastEntry = None
	# for entry in pendingEntries:
	# 	if lastEntry == None:
	# 		entryPrice = entry.entryPrice
	# 		lastEntry = entry
	# 	else:
	# 		if not lastEntry.direction == entry.direction:
	# 			entryPrice = entry.entryPrice
	# 		lastEntry = entry

	# if (not entryPrice == 0):
	# 	print("en price:", str(entryPrice))
	# 	pos = pendingEntries[-1]
	# 	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	# 	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
	# 	if pos.direction == Direction.LONG:
	# 		if (low <= entryPrice and blockCount > 0):
	# 			print("Unblock all blocked SHORT triggers")
	# 			blockDirection = None
	# 			blockCount = 0
	# 			for t in pendingTriggers:
	# 				if t.direction == Direction.SHORT and not t.isCancelled and t.isBlocked:
	# 					t.isBlocked = False
	# 	else:
	# 		if (high >= entryPrice and blockCount > 0):
	# 			print("Unblock all blocked LONG triggers")
	# 			blockDirection = None
	# 			blockCount = 0
	# 			for t in pendingTriggers:
	# 				if t.direction == Direction.LONG and not t.isCancelled and t.isBlocked:
	# 					t.isBlocked = False

def trendTrigger(shift):
	global isLongSignal, isShortSignal
	global isTriggeredLong, isTriggeredShort

	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		if (not isLongSignal):
			if ((currRsi > VARIABLES['longRsiSignal'] or hist >= VARIABLES['macdSignal'])):
				isLongSignal = True
	elif (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isLongSignal = False
		isTriggeredLong = False

	if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		if (not isShortSignal):
			if ((currRsi < VARIABLES['shortRsiSignal'] or hist <= -VARIABLES['macdSignal'])):
				isShortSignal = True
	elif (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isShortSignal = False
		isTriggeredShort = False

	isValidTriggerLong(shift)
	isValidTriggerShort(shift)

def isValidTriggerLong(shift):
	global isTriggeredLong
	if (isLongSignal and not isTriggeredLong):
		for i in range(VARIABLES['minimumBarsForTrigger']):
			if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift + i, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift + i, 1)[0]):
				return
			else:
				continue
		isTriggeredLong = True
		pendingTriggers.append(Trigger(Direction.LONG))
	
def isValidTriggerShort(shift):
	global isTriggeredShort
	if (isShortSignal and not isTriggeredShort):
		for i in range(VARIABLES['minimumBarsForTrigger']):
			if (regSAR.isRising(VARIABLES['TICKETS'][0], shift + i, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift + i, 1)[0]):
				return
			else:
				continue
		isTriggeredShort = True
		pendingTriggers.append(Trigger(Direction.SHORT))

def entrySetup(shift):
	regulateTriggers()
	for t in pendingTriggers:
		if (not t.isCancelled):

			if (t.isObos):
				if (cancelOnNewTrigger(t)):
					continue

			print("Trigger Sequence:", str(t.direction))
			if t.entryState == EntryState.RET_PARA:
				retPara(t, shift)
			elif t.entryState == EntryState.T_PARA:
				tPara(t, shift)
			elif t.entryState == EntryState.SWING_ONE:
				if (not cancelOnRetPara(t, shift)):
					swingOne(t, shift)
			elif t.entryState == EntryState.SWING_TWO:
				if (not cancelOnRetPara(t, shift)):
					swingTwo(t, shift)
			elif t.entryState == EntryState.SWING_THREE:
				if (not cancelOnRetPara(t, shift)):
					swingThree(t, shift)
			else:
				cancelOnRetPara(t, shift)
			print("\n")

def cancelOnRetPara(t, shift):
	if (t.direction == Direction.LONG):
		if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
			t.isCancelled = True
			print("cancelled long: ret para")
			return True
	else:
		if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			t.isCancelled = True
			print("cancelled short: ret para")
			return True
	return False

def cancelOnBlocked(t):
	if t.isBlocked:
		t.isCancelled = True
		print("cancelled blocked entry")
		return True
	return False

def cancelOnNewTrigger(t):
	if (len(pendingTriggers) > t.lastTriggerLength):
		t.isCancelled = True
		print("Cancelled on new trigger")
		return True
	return False

def retPara(t, shift):
	print("retPara")

	if (t.direction == Direction.LONG):
		if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.T_PARA
		elif (slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.T_PARA
	else:
		if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.T_PARA
		elif (slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.T_PARA

def tPara(t, shift):
	print("tPara")
	if (t.direction == Direction.LONG):
		if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.SWING_ONE
			swingOne(t, shift)
		elif (slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.SWING_ONE
			swingOne(t, shift)
	else:
		if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.SWING_ONE
			swingOne(t, shift)
		elif (slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
			t.entryState = EntryState.SWING_ONE
			swingOne(t, shift)

def swingOne(t, shift):
	print("swingOne")
	chIdx, smaTwo = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	smaThree = sma3.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (t.direction == Direction.LONG):
		if (chIdx > VARIABLES['cciTrendOversold']):
			if (chIdx > smaTwo and chIdx > smaThree):
				t.entryState = EntryState.SWING_TWO
				swingTwo(t, shift)
	else:
		if (chIdx < VARIABLES['cciTrendOverbought']):
			if (chIdx < smaTwo and chIdx < smaThree):
				t.entryState = EntryState.SWING_TWO
				swingTwo(t, shift)

def swingTwo(t, shift):
	print("swingTwo")
	chIdx, smaTwo = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	smaThree = sma3.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (t.direction == Direction.LONG):
		if (chIdx <= VARIABLES['cciCTOverbought'] or t.noCCIObos):
			if (chIdx < smaTwo and chIdx < smaThree):
				t.entryState = EntryState.SWING_THREE
				swingThree(t, shift)
	else:
		if (chIdx >= VARIABLES['cciCTOversold'] or t.noCCIObos):
			if (chIdx > smaTwo and chIdx > smaThree):
				t.entryState = EntryState.SWING_THREE
				swingThree(t, shift)

def swingThree(t, shift):
	print("swingThree")
	chIdx, smaTwo = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	smaThree = sma3.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (t.direction == Direction.LONG):
		if (chIdx > VARIABLES['cciTrendOversold'] or t.noCCIObos):
			if (chIdx > smaTwo and chIdx > smaThree):
				if (hist > 0 or t.macdConfirmed):
					t.entryState = EntryState.CONFIRMATION
					t.noCCIObos = True
					t.macdConfirmed = True
					confirmation(t, shift)
				elif((hist == 0 and currRsi > 50.0) or t.macdConfirmed):
					t.entryState = EntryState.CONFIRMATION
					t.noCCIObos = True
					t.macdConfirmed = True
					confirmation(t, shift)
				else:
					print("MACD not confirmed")
					t.entryState = EntryState.SWING_TWO
					swingTwo(t, shift)
	else:
		if (chIdx < VARIABLES['cciTrendOverbought'] or t.noCCIObos):
			if (chIdx < smaTwo and chIdx < smaThree):
				if (hist < 0 or t.macdConfirmed):
					t.entryState = EntryState.CONFIRMATION
					t.noCCIObos = True
					t.macdConfirmed = True
					confirmation(t, shift)
				elif((hist == 0 and currRsi < 50.0) or t.macdConfirmed):
					t.entryState = EntryState.CONFIRMATION
					t.noCCIObos = True
					t.macdConfirmed = True
					confirmation(t, shift)
				else:
					print("MACD not confirmed")
					t.entryState = EntryState.SWING_TWO
					swingTwo(t, shift)

def confirmation(t, shift):
	print("confirmation:")
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	if (t.direction == Direction.LONG):
		if ((regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (t.isObos):
				if (cancelOnBlocked(t)):
					return
				print("Position entered")
				t.entryState = EntryState.ENTER
				t.entryPrice = close
				pendingEntries.append(t)
				t.isCancelled = True
			elif (rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0] < VARIABLES['rsiOverbought']):
				if (close <= t.entryPrice or t.entryPrice == 0):
					if (cancelOnBlocked(t)):
						return
					print("Position entered")
					t.entryState = EntryState.ENTER
					t.entryPrice = close
					pendingEntries.append(t)
					t.isCancelled = True
			else:
				print("overbought")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.isObos = True
				t.lastTriggerLength = len(pendingTriggers)
				t.macdConfirmed = False
				if (t.entryPrice == 0):
					t.entryPrice = close
				swingTwo(t, shift)
	else:
		if ((regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (t.isObos):
				if (cancelOnBlocked(t)):
					return
				print("Position entered")
				t.entryState = EntryState.ENTER
				t.entryPrice = close
				pendingEntries.append(t)
				t.isCancelled = True
			elif (rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0] > VARIABLES['rsiOversold']):
				if (close >= t.entryPrice or t.entryPrice == 0):
					if (cancelOnBlocked(t)):
						return
					print("Position entered")
					t.entryState = EntryState.ENTER
					t.entryPrice = close
					pendingEntries.append(t)
					t.isCancelled = True
			else:
				print("oversold")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.isObos = True
				t.lastTriggerLength = len(pendingTriggers)
				t.macdConfirmed = False
				if (t.entryPrice == 0):
					t.entryPrice = close
				swingTwo(t, shift)

def backtestConfirmation(t, shift):
	print("backtest confirmation")
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	if (t.direction == Direction.LONG):
		if ((regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] < VARIABLES['rsiOverbought']):
				t.entryState = EntryState.ENTER
				if (close <= t.entryPrice or t.entryPrice == 0):
					if (cancelOnBlocked(t)):
						return
					if (t.bothParaHit):
						t.entryPrice = close
					elif (regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] > slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]):
						t.entryPrice = regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
						pendingEntries.append(t)
						t.isCancelled = True
					else:
						t.entryPrice = slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
						pendingEntries.append(t)
						t.isCancelled = True
					print("Position entered")
			else:
				print("overbought")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.isObos = True
				t.lastTriggerLength = len(pendingTriggers)
				t.macdConfirmed = False
				if (t.entryPrice == 0):
					t.entryPrice = close
				pendingEntries.append(t)
				swingTwo(t, shift)
	else:
		if ((regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] > VARIABLES['rsiOversold']):
				t.entryState = EntryState.ENTER
				if (close >= t.entryPrice or t.entryPrice == 0):
					if (cancelOnBlocked(t)):
						return
					if (t.bothParaHit):
						t.entryPrice = close
					elif (regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] < slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]):
						t.entryPrice = regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
					else:
						t.entryPrice = slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
					pendingEntries.append(t)
					t.isCancelled = True
					print("Position entered")
			else:
				print("oversold")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.isObos = True
				t.lastTriggerLength = len(pendingTriggers)
				t.macdConfirmed = False
				if (t.entryPrice == 0):
					t.entryPrice = close
				swingTwo(t, shift)

def regulateTriggers():
	lastTrigger = None
	for t in pendingTriggers[::-1]:
		t.canTrade = False
		if (not lastTrigger == None):
			if (t.isObos and t.isCancelled and lastTrigger.direction == t.direction and not lastTrigger.canTrade):
				lastTrigger.waitForOppTrigger = True
			if (t.direction == Direction.LONG and lastTrigger.direction == Direction.SHORT):
				t.canTrade = True
				t.waitForOppTrigger = False
				if (not lastTrigger.waitForOppTrigger):
					lastTrigger.canTrade = True
					lastTrigger.waitForOppTrigger = False
			elif (t.direction == Direction.SHORT and lastTrigger.direction == Direction.LONG):
				t.canTrade = True
				t.waitForOppTrigger = False
				if (not lastTrigger.waitForOppTrigger):
					lastTrigger.canTrade = True
					lastTrigger.waitForOppTrigger = False

		lastTrigger = t

def immedExitSequence(pos, shift):
	if (isRegRetParaHit(pos, shift)):
		if (immedMacdRsiConf(pos, shift)):
			if (isPosAtLoss(pos)):
				print("immedExitSequence")
				global exitPrice, exitPos
				if (pos.direction == 'buy'):
					exitPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2] - utils.convertToPrice(0.2)
					exitPos = pos
					pendingExits.append(pos)
					print("Will exit at", str(exitPrice))
				else:
					exitPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1] + utils.convertToPrice(0.2)
					exitPos = pos
					pendingExits.append(pos)
					print("Will exit at", str(exitPrice))
			elif (isPosInProfit(pos)):
				if not pos in pendingBreakevens:
					pendingBreakevens.append(pos)
					print("Attempting to set pos to breakeven.")
			else:
				print("Within 2 pips profit, exit ignored")

def isRegRetParaHit(pos, shift):
	if (pos.direction == 'buy' or pos.direction == Direction.LONG):
		if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and  slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
			if (regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift) or slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
				return True
	else:
		if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			if (regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift) or slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
				return True
	return False

def immedMacdRsiConf(pos, shift):
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (pos.direction == 'buy' or pos.direction == Direction.LONG):
		if (currRsi <= VARIABLES['shortRsiSignal'] and hist < 0):
			return True
		elif (currRsi <= VARIABLES['shortZeroMACD'] and hist <= 0):
			return True
	else:
		if (currRsi >= VARIABLES['longRsiSignal'] and hist > 0):
			return True
		elif (currRsi >= VARIABLES['longZeroMACD'] and hist >= 0):
			return True

	return False

def isPosAtLoss(pos):
	return pos.getProfit() < 2.0

def isPosInProfit(pos):
	return pos.getProfit() >= 2.0

def backtestImmedExitSequence(pos, shift):
	if (isRegRetParaHit(pos, shift)):
		if (immedMacdRsiConf(pos, shift)):
			if (backtestIsPosAtLoss(pos, shift)):
				print("Immediate exit activated.")
				global exitPrice
				if (pos.direction == Direction.LONG):
					exitPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2] - utils.convertToPrice(0.2)
					exitPos = pos
					print("Exit at", str(exitPrice))
				else:
					exitPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1] + utils.convertToPrice(0.2)
					exitPos = pos
					print("Exit at", str(exitPrice))
			elif (backtestIsPosInProfit(pos, shift)):
				print("Set position to breakeven.")

	return False

def backtestIsPosAtLoss(pos, shift):
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]
	if (pos.direction == Direction.LONG):
		return close < pos.entryPrice + utils.convertToPrice(VARIABLES['beRange'])
	else:
		return close > pos.entryPrice - utils.convertToPrice(VARIABLES['beRange'])

def backtestIsPosInProfit(pos, shift):
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]
	if (pos.direction == Direction.LONG):
		return close >= (pos.entryPrice + utils.convertToPrice(VARIABLES['beRange']))
	else:
		return close <= (pos.entryPrice - utils.convertToPrice(VARIABLES['beRange']))