from CMCTrader import Constants
from enum import Enum
import datetime

VARIABLES = {
	'TICKETS' : [Constants.GBPUSD],
	# 'START_TIME' : '6:55',
	# 'END_TIME' : '16:00',
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

	global isInit
	isInit = False
	for t in pendingTriggers:
		print(t.direction)

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
	elif (londonTime > noNewTradesTime and not isNoTradesTime):
		print("IS NO NEW TRADES TIME")
		noNewTrades = True
		isNoTradesTime = True
	elif (londonTime > noNewTradesOnProfitTime and not isProfitTime):
		print("IS NO NEW TRADES ON PROFIT TIME")
		print("Total profit:", str(utils.getTotalProfit()))
		if (utils.getTotalProfit() >= VARIABLES['halfprofit']):
			isProfitTime = True
			noNewTrades = True

	# if (londonTime.weekday() == 4 and londonTime.hour >= int(VARIABLES['END_TIME'].split(':')[0]) + 1): # time checking is wrong
	# 	for pos in utils.positions:
	# 		pendingExits.append(pos)

def onDownTime():
	if (isInit):
		return

	print("onDownTime")
	ausTime = utils.getAustralianTime()
	print("\nTime:",str(ausTime.hour)+":"+str(ausTime.minute)+":"+str(ausTime.second))

	runSequence(0, isDownTime = True)

	for entry in pendingEntries:
		del pendingEntries[pendingEntries.index(entry)]

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
	entryPrice = 0
	lastEntry = None
	for entry in pendingEntries:
		if lastEntry == None:
			entryPrice = entry.entryPrice
			lastEntry = entry
		else:
			if not lastEntry.direction == entry.direction:
				entryPrice = entry.entryPrice
			lastEntry = entry

	if (not entryPrice == 0):
		print("en price:", str(entryPrice))
		pos = pendingEntries[-1]
		high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
		low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
		if pos.direction == Direction.LONG:
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

def trendTrigger(shift):
	global isLongSignal
	global isShortSignal

	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		if (not isLongSignal):
			if ((currRsi > VARIABLES['longRsiSignal'] or hist >= VARIABLES['macdSignal'])):
				isLongSignal = True
				print("New long trigger!")
				pendingTriggers.append(Trigger(Direction.LONG))
	elif (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isLongSignal = False

	if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		if (not isShortSignal):
			if ((currRsi < VARIABLES['shortRsiSignal'] or hist <= -VARIABLES['macdSignal'])):
				isShortSignal = True
				print("New short trigger!")
				pendingTriggers.append(Trigger(Direction.SHORT))
	elif (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isShortSignal = False

def entrySetup(shift):
	regulateTriggers()
	for t in pendingTriggers:
		if (not t.isCancelled):
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
			if (rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0] < VARIABLES['rsiOverbought']):
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
				if (t.entryPrice == 0):
					t.entryPrice = close
				swingTwo(t, shift)
	else:
		if ((regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0] > VARIABLES['rsiOversold']):
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
	return pos.getProfit() < 0

def isPosInProfit(pos):
	return pos.getProfit() >= 2

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
		return close < pos.entryPrice
	else:
		return close > pos.entryPrice

def backtestIsPosInProfit(pos, shift):
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]
	if (pos.direction == Direction.LONG):
		return close >= (pos.entryPrice + utils.convertToPrice(VARIABLES['beRange']))
	else:
		return close <= (pos.entryPrice - utils.convertToPrice(VARIABLES['beRange']))