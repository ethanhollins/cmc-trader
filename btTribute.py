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
	'cciTrendOverbought' : 0,
	'cciTrendOversold' : 0,
	'cciCTOverbought' : 60,
	'cciCTOversold' : -60,
}

utils = None

regSAR = None
slowSAR = None
blackSAR = None
cci = None
sma3 = None
macd = None
rsi = None

startDate = 0

pendingTriggers = []
pendingEntries = []
pendingExits = []
pendingBreakevens = []
strands = []
longStrands = []
shortStrands = []

currentPosition = None
positions = []

isInit = True

isLongSignal = False
isShortSignal = False
isHalfLongSignal = False
isHalfShortSignal = False
performedHalfSignal = False
isWaitForHit = True

noNewTrades = False

canTradeLongMaster = True
canTradeShortMaster = True

currentNews = None
newsTradeBlock = False

maxStrand = None
minStrand = None
blockCount = 0
blockDirection = None
futureCount = 0

entryPrice = 0
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
	SWING_ONE = 1
	SWING_TWO = 2
	SWING_THREE = 3
	CONFIRMATION = 4
	ENTER = 5

class Trigger(object):
	def __init__(self, direction, isHalfTrigger = False):
		self.direction = direction
		self.isHalfTrigger = isHalfTrigger
		self.entryState = EntryState.SWING_ONE
		self.entryPrice = 0
		self.exitPrice = 0
		self.isCancelled = False
		self.isBlocked = False
		self.macdConfirmed = False
		self.noCCIObos = False
		self.bothParaHit = False
		self.waitForOppTrigger = False
		self.canTrade = True
		self.isPositionHalved = False

class Strand(object):
	def __init__(self, start, direction):
		self.start = start
		self.end = 0
		self.direction = direction
		self.isPassed = False

def init(utilities): # swap entry line unblock, fix immedexit in trend trig func
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

def backtest():
	print("Trading time")
	runSequence(0)

	global startDate
	if (startDate == 0):
		startDate = [i[0] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][0]
		print(startDate)

	timestamp = [i[0] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][0]

	checkStoploss(0)
	checkTakeProfit(0)

	for t in pendingTriggers:
		if (not t.isCancelled):
			if (t.entryState == EntryState.CONFIRMATION):
				if (t.isHalfTrigger):
					backtestMomentumEntry(t, 0)
				else:
					backtestConfirmation(t, 0)

	backtestImmedExitSequence(0)

	print("PENDING TRIGGERS:")
	count = 0
	for t in pendingTriggers:
		if (not t.isCancelled):
			count += 1
			print(str(count) + ":", str(t.direction), "isBlocked:", str(t.isBlocked))
	print(" Block Count:", str(blockCount), "Block direction:", str(blockDirection))

	print("ALL POSITIONS:")
	count = 0
	for pos in positions:
		count += 1
		print(str(count) + ":", str(pos.direction))

	if (not currentPosition == None):
		print("CURRENT POSITION:", currentPosition.direction)

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

	startTime = utils.convertTimestampToTime(startDate)
	parts = VARIABLES['noNewTradesOnProfit'].split(':')
	noNewTradesOnProfitTime = utils.createLondonTime(startTime.year, startTime.month, startTime.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['noNewTrades'].split(':')
	noNewTradesTime = utils.createLondonTime(startTime.year, startTime.month, startTime.day, int(parts[0]), int(parts[1]), 0)
	parts = VARIABLES['setBE'].split(':')
	setBETime = utils.createLondonTime(startTime.year, startTime.month, startTime.day, int(parts[0]), int(parts[1]), 0)

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

def onDownTime():
	print("onDownTime")

	runSequence(0, isDownTime = True)

	for t in pendingTriggers:
		if (not t.isCancelled):
			if (t.entryState == EntryState.CONFIRMATION):
				if (t.isHalfTrigger):
					backtestMomentumEntry(t, 0)
				else:
					backtestConfirmation(t, 0)

	for entry in pendingEntries:
		del pendingEntries[pendingEntries.index(entry)]
	
	for pos in positions:
		del positions[positions.index(pos)]

	global currentPosition
	currentPosition = None

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
	trendTrigger(shift, isDownTime)
	onNewCycle(shift)

	if (not performedHalfSignal):
		setupSequence(shift, isDownTime)

def setupSequence(shift, isDownTime):
	global performedHalfSignal
	performedHalfSignal = False
	# BLACK PARA
	if (len(strands) > 0):
		cancelInvalidStrands(shift)
		getPassedStrands(shift, isDownTime = isDownTime)
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
			print("End of last strand:", str(strands[-1].end))
		print("New Strand:", str(direction), ":", str(regSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0]))
		strand = Strand(regSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0], direction)
		strands.append(strand)
		if (strand.direction == Direction.LONG):
			longStrands.append(strand)
		else:
			shortStrands.append(strand)

def cancelInvalidStrands(shift):
	global longStrands, shortStrands

	if (blackSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
		if (blackSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			shortStrands = [i for i in strands if i.direction == Direction.SHORT and not i.isPassed and not i.end == 0]
			for strand in shortStrands:
				if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] > strand.end):
					print("passed rising:", str(strand.end))
					strands[strands.index(strand)].isPassed = True
					del shortStrands[shortStrands.index(strand)]
			shortStrands = shortStrands[-2:]
		else:
			longStrands = [i for i in strands if i.direction == Direction.LONG and not i.isPassed and not i.end == 0]
			for strand in longStrands:
				if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] < strand.end):
					print("passed falling:", str(strand.end))
					strands[strands.index(strand)].isPassed = True
					del longStrands[longStrands.index(strand)]
			longStrands = longStrands[-2:]

def getPassedStrands(shift, isDownTime = False):
	global blockCount, blockDirection, futureCount
	getExtremeStrands()

	if (len(utils.positions) <= 0 and len(pendingEntries) <= 0 and not isDownTime):
		return

	if (not maxStrand == None):
		if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] < maxStrand.start and blackSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
			strands[strands.index(maxStrand)].isPassed = True
			print("black para crossed long")
			canBlock = True
			if (len(utils.positions) > 0):
				if (utils.positions[0].direction == 'buy'):
					canBlock = False
			elif (len(pendingEntries) > 0):
				print(pendingEntries[-1].direction)
				if (pendingEntries[-1].direction == Direction.LONG):
					print("can't block")
					canBlock = False
			if (canBlock):
				blockCount = 0
				futureCount = 0
				for t in pendingTriggers:
					if t.direction == Direction.LONG and not t.isCancelled and not t.isHalfTrigger and blockCount < 3:
						t.isBlocked = True
						blockCount += 1
				if (blockCount < 1):
					blockCount = 1
				blockDirection = Direction.LONG
			for t in pendingTriggers:
				if t.direction == Direction.SHORT and t.isBlocked:
					t.isBlocked = False

	if (not minStrand == None):
		if (blackSAR.get(VARIABLES['TICKETS'][0], shift, 1)[0] > minStrand.start and blackSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			strands[strands.index(minStrand)].isPassed = True
			print("black para crossed short")
			canBlock = True
			if (len(utils.positions) > 0):
				if (utils.positions[0].direction == 'sell'):
					canBlock = False
			elif (len(pendingEntries) > 0):
				if (pendingEntries[-1].direction == Direction.SHORT):
					canBlock = False
			if (canBlock):
				blockCount = 0
				futureCount = 0
				for t in pendingTriggers:
					if t.direction == Direction.SHORT and not t.isCancelled and not t.isHalfTrigger and blockCount < 3:
						t.isBlocked = True
						blockCount += 1
				if (blockCount < 1):
					blockCount = 1
				blockDirection = Direction.SHORT
			for t in pendingTriggers:
				if t.direction == Direction.LONG and t.isBlocked:
					t.isBlocked = False

def getExtremeStrands():
	global maxStrand
	global minStrand
	
	maxStrand = None
	for i in longStrands:
		if not maxStrand == None:
			if i.start > maxStrand.start and not i.isPassed:
				maxStrand = i
		elif not i.isPassed:
			maxStrand = i

	minStrand = None
	for j in shortStrands:
		if not minStrand == None:
			if j.start < minStrand.start and not j.isPassed:
				minStrand = j
		elif not j.isPassed:
			minStrand = j

def blockFollowingTriggers():
	global blockCount, futureCount

	if (not blockDirection == None):
		for t in pendingTriggers:
			if (t.direction == blockDirection and blockCount < 2 and not t.isCancelled and not t.isBlocked and not t.isHalfTrigger):
				print("blocked new trigger", str(t.direction))
				t.isBlocked = True
				blockCount += 1
				futureCount += 1

def unblockOnTag(shift):
	global entryPrice
	global blockCount, blockDirection

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

	print(futureCount)
	if (not entryPrice == 0):
		print("en price:", str(entryPrice))
		pos = pendingEntries[-1]
		high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
		low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
		if pos.direction == Direction.LONG:
			if (low <= entryPrice and blockCount > 0 and futureCount > 0):
				print("Unblock all blocked SHORT triggers")
				blockDirection = None
				blockCount = 0
				for t in pendingTriggers:
					if t.direction == Direction.SHORT and not t.isCancelled and t.isBlocked:
						t.isBlocked = False
		else:
			if (high >= entryPrice and blockCount > 0 and futureCount > 0):
				print("Unblock all blocked LONG triggers")
				blockDirection = None
				blockCount = 0
				for t in pendingTriggers:
					if t.direction == Direction.LONG and not t.isCancelled and t.isBlocked:
						t.isBlocked = False

def getParaState(shift):
	global isWaitForHit

	if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isWaitForHit = False
		return True
	elif (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isWaitForHit = False
		return True
	else:
		isWaitForHit = True
		return False

def trendTrigger(shift, isDownTime):
	global isLongSignal, isShortSignal
	global isHalfLongSignal, isHalfShortSignal, performedHalfSignal

	if (isWaitForHit):
		if (not getParaState(shift)):
			return
	
	if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isShortSignal = False
		isHalfShortSignal = False
		if (not isLongSignal):
			print("new long trigger!")
			isLongSignal = True

			if (isHalfLongSignal):
				print("checking half signal")
				t = pendingTriggers[-1]
				isHalfLongSignal = False
				
				performedHalfSignal = True
				setupSequence(shift, isDownTime)
				
				if (t.entryState == EntryState.CONFIRMATION):
					print("half signal confirmed")
					if (not momentumEntry(t, shift)):
						print("half not momentum")
						t.entryState = EntryState.SWING_ONE
						t.isHalfTrigger = False
						swingOne(t, shift)
				else:
					print("half not confirmed")
					t.entryState = EntryState.SWING_ONE
					t.isHalfTrigger = False
					swingOne(t, shift)

			else:
				pendingTriggers.append(Trigger(Direction.LONG))

				if (len(pendingEntries) > 0):
					immedExitSequence(pendingEntries[-1], 0)

	elif (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] or slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
		if (isShortSignal and not isHalfLongSignal):
			isHalfLongSignal = True
			pendingTriggers.append(Trigger(Direction.LONG, isHalfTrigger = True))

	if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		isLongSignal = False
		isHalfLongSignal = False
		if (not isShortSignal):
			print("new short trigger!")
			isShortSignal = True

			if (isHalfShortSignal):
				t = pendingTriggers[-1]
				isHalfShortSignal = False

				performedHalfSignal = True
				setupSequence(shift, isDownTime)
				
				if (t.entryState == EntryState.CONFIRMATION):
					print("half signal confirmed")
					if (not momentumEntry(t, shift)):
						print("half not momentum")
						t.entryState = EntryState.SWING_ONE
						t.isHalfTrigger = False
						swingOne(t, shift)
				else:
					print("half not confirmed")
					t.entryState = EntryState.SWING_ONE
					t.isHalfTrigger = False
					swingOne(t, shift)

			else:
				pendingTriggers.append(Trigger(Direction.SHORT))

				if (len(pendingEntries) > 0):
					immedExitSequence(pendingEntries[-1], 0)

	elif (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] or slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
		if (isLongSignal and not isHalfShortSignal):
			isHalfShortSignal = True
			pendingTriggers.append(Trigger(Direction.SHORT, isHalfTrigger = True))

def entrySetup(shift):
	for t in pendingTriggers:
		if (not t.isCancelled):
			print("Trigger Sequence:", str(t.direction))
			if t.entryState == EntryState.SWING_ONE:
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

def cancelOnBlocked(t, shift):
	if t.isBlocked:
		t.isCancelled = True
		print("cancelled blocked entry")
		return True
	return False

def swingOne(t, shift):
	print("swingOne")
	chIdx, smaTwo = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	smaThree = sma3.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (t.direction == Direction.LONG):
		if (chIdx > VARIABLES['cciTrendOversold']):
			isPassed = False
			if (t.isHalfTrigger):
				if (chIdx > smaTwo and chIdx > smaThree):
					isPassed = True
			else:
				if (chIdx > smaTwo):
					isPassed = True

			if (isPassed):
				t.entryState = EntryState.SWING_TWO
				swingTwo(t, shift)
	else:
		if (chIdx < VARIABLES['cciTrendOverbought']):
			isPassed = False
			if (t.isHalfTrigger):
				if (chIdx < smaTwo and chIdx < smaThree):
					isPassed = True
			else:
				if (chIdx < smaTwo):
					isPassed = True

			if (isPassed):
				t.entryState = EntryState.SWING_TWO
				swingTwo(t, shift)

def swingTwo(t, shift):
	print("swingTwo")
	chIdx, smaTwo = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	smaThree = sma3.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]

	if (t.direction == Direction.LONG):
		if (chIdx <= VARIABLES['cciCTOverbought'] or t.noCCIObos):
			isPassed = False
			if (t.isHalfTrigger):
				if (chIdx < smaTwo and chIdx < smaThree):
					isPassed = True
			else:
				if (chIdx < smaTwo):
					isPassed = True

			if (isPassed):
				t.entryState = EntryState.SWING_THREE
				swingThree(t, shift)
	else:
		if (chIdx >= VARIABLES['cciCTOversold'] or t.noCCIObos):
			isPassed = False
			if (t.isHalfTrigger):
				if (chIdx > smaTwo and chIdx > smaThree):
					isPassed = True
			else:
				if (chIdx > smaTwo):
					isPassed = True

			if (isPassed):
				t.entryState = EntryState.SWING_THREE
				swingThree(t, shift)

def swingThree(t, shift):
	print("swingThree")
	chIdx, smaTwo = cci.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	smaThree = sma3.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (t.direction == Direction.LONG):
		if (chIdx > VARIABLES['cciTrendOversold']):
			isPassed = False
			if (t.isHalfTrigger):
				if (chIdx > smaTwo and chIdx > smaThree):
					isPassed = True
			else:
				if (chIdx > smaTwo):
					isPassed = True

			if (isPassed):
				if (currRsi > 50.0 and hist >= 0):
					t.entryState = EntryState.CONFIRMATION
					t.noCCIObos = True
					confirmation(t, shift)
				else:
					print("RSI or MACD not confirmed")
					t.entryState = EntryState.SWING_TWO
					t.noCCIObos = True
					swingTwo(t, shift)
	else:
		if (chIdx < VARIABLES['cciTrendOverbought']):
			isPassed = False
			if (t.isHalfTrigger):
				if (chIdx < smaTwo and chIdx < smaThree):
					isPassed = True
			else:
				if (chIdx < smaTwo):
					isPassed = True

			if (isPassed):
				if (currRsi < 50.0 and hist <= 0):
					t.entryState = EntryState.CONFIRMATION
					t.noCCIObos = True
					confirmation(t, shift)
				else:
					print("RSI or MACD not confirmed")
					t.entryState = EntryState.SWING_TWO
					t.noCCIObos = True
					swingTwo(t, shift)

def confirmation(t, shift):
	global currentPosition

	if (t.isHalfTrigger):
		print("Confirmed half trigger")
		return

	print("Confirmation:")
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	if (t.direction == Direction.LONG):
		if ((regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0] < VARIABLES['rsiOverbought']):
				if (cancelOnBlocked(t, shift)):
					return
				print("Position entered")
				t.entryState = EntryState.ENTER
				print("CLOSE:", str(close))
				t.entryPrice = close
				pendingEntries.append(t)
				
				if (currentPosition == None):
					currentPosition = t
					positions.append(currentPosition)
				elif (not t.direction == currentPosition.direction):
					currentPosition = t
					positions.append(currentPosition)
				
				t.isCancelled = True
			else:
				print("overbought")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				if (t.entryPrice == 0):
					t.entryPrice = close
				swingTwo(t, shift)
	else:
		if ((regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0] > VARIABLES['rsiOversold']):
				# if (close >= t.entryPrice or t.entryPrice == 0):
				if (cancelOnBlocked(t, shift)):
					return
				print("Position entered")
				t.entryState = EntryState.ENTER
				t.entryPrice = close
				pendingEntries.append(t)
				
				if (currentPosition == None):
					currentPosition = t
					positions.append(currentPosition)
				elif (not t.direction == currentPosition.direction):
					currentPosition = t
					positions.append(currentPosition)
				
				t.isCancelled = True
			else:
				print("oversold")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				if (t.entryPrice == 0):
					t.entryPrice = close
				swingTwo(t, shift)

def backtestConfirmation(t, shift):
	global currentPosition

	if (t.isHalfTrigger):
		return
		
	print("backtest confirmation")
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]

	if (t.direction == Direction.LONG):
		if ((regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] < VARIABLES['rsiOverbought']):
				t.entryState = EntryState.ENTER
				# if (close <= t.entryPrice or t.entryPrice == 0):
				if (cancelOnBlocked(t, shift)):
					return
				if (t.bothParaHit):
					t.entryPrice = close
				elif (regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] > slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]):
					t.entryPrice = regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
				else:
					t.entryPrice = slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
				pendingEntries.append(t)
				
				if (currentPosition == None):
					currentPosition = t
					positions.append(currentPosition)
				elif (not t.direction == currentPosition.direction):
					currentPosition = t
					positions.append(currentPosition)
				
				t.isCancelled = True
				print("Position entered")
			else:
				print("overbought")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				swingTwo(t, shift)
	else:
		if ((regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]) or t.bothParaHit):
			t.bothParaHit = True
			if (rsi.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] > VARIABLES['rsiOversold']):
				t.entryState = EntryState.ENTER
				# if (close >= t.entryPrice or t.entryPrice == 0):
				if (cancelOnBlocked(t, shift)):
					return
				if (t.bothParaHit):
					t.entryPrice = close
				elif (regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0] < slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]):
					t.entryPrice = regSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
				else:
					t.entryPrice = slowSAR.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]
				pendingEntries.append(t)
				
				if (currentPosition == None):
					currentPosition = t
					positions.append(currentPosition)
				elif (not t.direction == currentPosition.direction):
					currentPosition = t
					positions.append(currentPosition)
				
				t.isCancelled = True
				print("Position entered")
			else:
				print("oversold")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				swingTwo(t, shift)

def momentumEntry(t, shift):
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]
	if (t.direction == Direction.LONG):
		if (momentumMacdRsiConf(t, shift)):
			if (currRsi < VARIABLES['rsiOverbought']):
				print("Momentum entry order placed")
				t.entryPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1] + utils.convertToPrice(0.2)
				
				newTrigger = Trigger(Direction.LONG)
				pendingTriggers.append(newTrigger)
				swingOne(newTrigger, shift)
			else:
				print("overbought on momentum entry")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				t.isHalfTrigger = False
				swingTwo(t, shift)

				if (len(pendingEntries) > 0):
					immedExitSequence(pendingEntries[-1], 0)
			return True
		else:
			return False
	else:
		if (momentumMacdRsiConf(t, shift)):
			if (currRsi > VARIABLES['rsiOversold']):
				print("Momentum entry order placed")
				t.entryPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2] - utils.convertToPrice(0.2)
				
				newTrigger = Trigger(Direction.SHORT)
				pendingTriggers.append(newTrigger)
				swingOne(newTrigger, shift)
			else:
				print("oversold on momentum entry")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				t.isHalfTrigger = False
				swingTwo(t, shift)

				if (len(pendingEntries) > 0):
					immedExitSequence(pendingEntries[-1], 0)
			return True
		else:
			return False

def backtestMomentumEntry(t, shift):
	global currentPosition
	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift + 1, 1)[0]

	if (t.direction == Direction.LONG):
		if (high > t.entryPrice):
			if (currRsi <= VARIABLES['rsiOverbought']):
				if (cancelOnBlocked(t, 0)):
					return
				print("entered long momentum onloop")
				pendingEntries.append(t)
				
				if (currentPosition == None):
					currentPosition = t
					positions.append(currentPosition)
				elif (not t.direction == currentPosition.direction):
					currentPosition = t
					positions.append(currentPosition)
				
				t.isCancelled = True
			else:
				print("overbought momentum onloop")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				swingTwo(t, 0)
	else:
		if (low < t.entryPrice):
			if (currRsi >= VARIABLES['rsiOversold']):
				if (cancelOnBlocked(t, 0)):
					return
				print("entered short momentum onloop")
				pendingEntries.append(t)
				
				if (currentPosition == None):
					currentPosition = t
					positions.append(currentPosition)
				elif (not t.direction == currentPosition.direction):
					currentPosition = t
					positions.append(currentPosition)
				
				t.isCancelled = True
			else:
				print("oversold momentum onloop")
				t.entryState = EntryState.SWING_TWO
				t.noCCIObos = True
				t.macdConfirmed = False
				swingTwo(t, 0)

def momentumMacdRsiConf(pos, shift):
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (pos.direction == Direction.LONG):
		if (currRsi >= VARIABLES['longRsiSignal'] and hist > 0):
			return True
		elif (currRsi >= VARIABLES['longZeroMACD'] and hist >= 0):
			return True
	else:
		if (currRsi <= VARIABLES['shortRsiSignal'] and hist < 0):
			return True
		elif (currRsi <= VARIABLES['shortZeroMACD'] and hist <= 0):
			return True

	return False

def immedExitSequence(t, shift):
	if (immedMacdRsiConf(t, shift)):
		if (isPosAtLoss(t, shift)):
			print("Immediate exit activated.")
			global exitPos
			if (t.direction == Direction.LONG):
				t.exitPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2] - utils.convertToPrice(0.2)
				exitPos = t
				pendingExits.append(exitPos)
				print("Exit at", str(t.exitPrice))
			else:
				t.exitPrice = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1] + utils.convertToPrice(0.2)
				exitPos = t
				pendingExits.append(exitPos)
				print("Exit at", str(t.exitPrice))
		elif (isPosInProfit(t, shift)):
			print("Set position to breakeven.")

	return False

def backtestImmedExitSequence(shift):
	global currentPosition
	global exitPos, pendingExits

	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
	if (not currentPosition == None and not exitPos == None):
		for t in pendingExits:
			if (exitPos == currentPosition):
				if (exitPos == t):
					if (t.direction == Direction.LONG):
						if (low < t.exitPrice):
							print("exited long on momentum")
							currentPosition = None
							exitPos = None
							pendingExits = []
					else:
						if (high > t.exitPrice):
							print("exited long on momentum")
							currentPosition = None
							exitPos = None
							pendingExits = []
				return

	exitPos = None
	pendingExits = []

def isRegRetParaHit(t, shift):
	if (t.direction == Direction.LONG):
		if (regSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0] and  slowSAR.isFalling(VARIABLES['TICKETS'][0], shift, 1)[0]):
			if (regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift) or slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
				return True
	else:
		if (regSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0] and slowSAR.isRising(VARIABLES['TICKETS'][0], shift, 1)[0]):
			if (regSAR.isNewCycle(VARIABLES['TICKETS'][0], shift) or slowSAR.isNewCycle(VARIABLES['TICKETS'][0], shift)):
				return True
	return False

def immedMacdRsiConf(t, shift):
	hist = macd.get(VARIABLES['TICKETS'][0], shift, 1)[0][0]
	currRsi = rsi.get(VARIABLES['TICKETS'][0], shift, 1)[0]

	if (t.direction == Direction.LONG):
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

def isPosAtLoss(t, shift):
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]
	if (t.direction == Direction.LONG):
		return close < t.entryPrice + utils.convertToPrice(VARIABLES['beRange'])
	else:
		return close > t.entryPrice - utils.convertToPrice(VARIABLES['beRange'])

def isPosInProfit(t, shift):
	close = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][3]
	if (t.direction == Direction.LONG):
		return close >= (t.entryPrice + utils.convertToPrice(VARIABLES['beRange']))
	else:
		return close <= (t.entryPrice - utils.convertToPrice(VARIABLES['beRange']))

def checkStoploss(shift):
	global currentPosition
	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]
	if (not currentPosition == None):
		if (currentPosition.direction == Direction.LONG):
			if (low < currentPosition.entryPrice - utils.convertToPrice(VARIABLES['stoprange'])):
				print("Long position stopped out!")
				currentPosition = None
		else:
			if (high > currentPosition.entryPrice + utils.convertToPrice(VARIABLES['stoprange'])):
				print("Short position stopped out!")
				currentPosition = None

def checkTakeProfit(shift):
	global currentPosition
	high = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][1]
	low = [i[1] for i in sorted(utils.ohlc[VARIABLES['TICKETS'][0]].items(), key=lambda kv: kv[0], reverse=True)][shift][2]

	if (not currentPosition == None):
		if (not currentPosition.isPositionHalved):
			if (currentPosition.direction == Direction.LONG):
				print("Entry price:", currentPosition.entryPrice)
				print("Half profit:", str(currentPosition.entryPrice + utils.convertToPrice(VARIABLES['halfprofit'])))
				if (high > currentPosition.entryPrice + utils.convertToPrice(VARIABLES['halfprofit'])):
					print("Long position halved!")
					currentPosition.isPositionHalved = True
			else:
				if (low < currentPosition.entryPrice - utils.convertToPrice(VARIABLES['halfprofit'])):
					print("Short position halved!")
					currentPosition.isPositionHalved = True
		else:
			if (currentPosition.direction == Direction.LONG):
				if (high > currentPosition.entryPrice + utils.convertToPrice(VARIABLES['fullprofit'])):
					print("Long position full profit!")
					currentPosition = None
			else:
				if (low < currentPosition.entryPrice - utils.convertToPrice(VARIABLES['fullprofit'])):
					print("Short position full profit!")
					currentPosition = None
