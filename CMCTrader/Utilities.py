from selenium import webdriver
import selenium.webdriver.support.ui as ui

import numpy as np
import time
import threading
import sys
import datetime
import pytz
import math
import uuid
import json

import boto3
from botocore.exceptions import ClientError

from CMCTrader.Position import Position
from CMCTrader.HistoryLog import HistoryLog
from CMCTrader.PositionLog import PositionLog
from CMCTrader.OrderLog import OrderLog
from CMCTrader.BarReader import BarReader

from CMCTrader.Indicators.SMA import SMA
from CMCTrader.Indicators.SAR import SAR
from CMCTrader.Indicators.RSI import RSI
from CMCTrader.Indicators.CCI import CCI
from CMCTrader.Indicators.MACD import MACD
from CMCTrader.Indicators.ADXR import ADXR

class DecimalEncoder(json.JSONEncoder):
	def default(self, o):
		if isinstance(o, decimal.Decimal):
			if abs(o) % 1 > 0:
				return float(o)
			else:
				return int(o)
		return super(DecimalEncoder, self).default(o)

class Utilities:

	def __init__(self, driver, plan, name, tickets, tAUDUSD):
		self.driver = driver
		self.plan = plan
		self.tickets = tickets
		self.tAUDUSD = tAUDUSD

		# self.dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
		# self.dynamodbClient = boto3.client('dynamodb', region_name='ap-southeast-2')
		# self._initVARIABLES(name)

		self.historyLog = HistoryLog(self.driver)
		self.positionLog = PositionLog(self.driver)
		self.orderLog = OrderLog(self.driver)
		self.barReader = BarReader(self, self.driver)

		self.positions = []
		self.closedPositions = []

		self.ohlc = self._initOHLC()
		self.indicators = {"overlays" : [], "studies" : []}

		self.newsTimes = {}

		self.isStopped = False
		self.manualEntry = False
		self.manualChartReading = False

		self.latestTimestamp = {}

		self.startTime = None
		self.endTime = None

		self._startPrompt()

	def reinit(self):
		self.historyLog.reinit()
		self.positionLog.reinit()
		self.orderLog.reinit()
		self.barReader.reinit()

	def _initVARIABLES(self, name):
		if name in self.dynamodbClient.list_tables()['TableNames']:
			print("Updating table", name+"...")
			self.table = self.dynamodb.Table(name)
			try:
				response = self.table.get_item(
						Key = {
							'name' : 'VARIABLES'
						}
					)
			except ClientError as e:
				print(e.response['Error']['Message'])
				return

			item = response['Item']
			json_str = json.dumps(item, indent=4, cls=DecimalEncoder)
			dbVars = json.loads(json_str)['vars']
			dbVars = json.loads(dbVars)

			setCurrent, setPast = set(self.plan.VARIABLES.keys()), set(dbVars.keys())
			intersect = setCurrent.intersection(setPast)

			for i in setPast - intersect:
				del dbVars[i]

			for i in setCurrent - intersect:
				dbVars[i] = self.plan.VARIABLES[i]

			response = self.table.update_item(
				Key = {
					'name' : 'VARIABLES'
				},
				UpdateExpression = "set vars=:v",
				ExpressionAttributeValues = {
					':v' : json.dumps(dbVars)
				}
			)
		else:
			self._createTable(name)

	def _createTable(self, name):
		print("Creating new table", name+"...")
		self.table = self.dynamodb.create_table(
				TableName = name,
				KeySchema = [
					{
						'AttributeName' : 'name',
						'KeyType' : 'HASH' #Partition key
					}
				],
				AttributeDefinitions = [
					{
						'AttributeName' : 'name',
						'AttributeType' : 'S'
					}
				],
				ProvisionedThroughput = {
					'ReadCapacityUnits' : 1,
					'WriteCapacityUnits' : 1
				}
			)

		while not self.dynamodbClient.describe_table(TableName=name)['Table']['TableStatus'] == 'ACTIVE':
			time.sleep(0.5)

		self.table.put_item(
				Item = {
					'name' : 'VARIABLES',
					'vars' : json.dumps(self.plan.VARIABLES),
				}
			)
		self.table.put_item(
				Item = {
					'name' : 'CMD',
				}
			)

	def _initOHLC(self):
		temp = {}
		for key in self.tickets:
			temp[key] = {}
		return temp

	def _startPrompt(self):
		task = self._prompt
		t = threading.Thread(target = task)
		t.start()

	def SMA(self, index):
		sma = SMA(self, index)
		self.indicators['overlays'].append(sma)
		self.indicators['overlays'].sort(key = lambda x: x.index)
		return sma

	def SAR(self, index):
		sar = SAR(self, index)
		self.indicators['overlays'].append(sar)
		self.indicators['overlays'].sort(key = lambda x: x.index)
		return sar

	def RSI(self, index, count):
		rsi = RSI(self, index, count)
		self.indicators['studies'].append(rsi)
		self.indicators['studies'].sort(key = lambda x: x.index)
		return rsi

	def CCI(self, index, count):
		cci = CCI(self, index, count)
		self.indicators['studies'].append(cci)
		self.indicators['studies'].sort(key = lambda x: x.index)
		return cci

	def MACD(self, index, count):
		macd = MACD(self, index, count)
		self.indicators['studies'].append(macd)
		self.indicators['studies'].sort(key = lambda x: x.index)
		return macd

	def ADXR(self, index, count):
		adxr = ADXR(self, index, count)
		self.indicators['studies'].append(adxr)
		self.indicators['studies'].sort(key = lambda x: x.index)
		return adxr

	def convertToPips(self, price):
		return price / 0.00001 / 10

	def convertToPrice(self, pips):
		return pips * 0.00001 * 10

	def buy(self, lotsize, pairs = [], ordertype = 'market', entry = 0, sl = 0.0, tp = 0.0):
		if (ordertype == 'market' or ordertype == 'm'):
			if (len(pairs) <= 0):
				for key in self.tickets:
					return self._marketOrder('buy', self.tickets[key], key, lotsize, sl, tp)
			else:
				for p in pairs:
					try:
						return self._marketOrder('buy', self.tickets[p], p, lotsize, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")

		elif (ordertype == 'stopentry' or ordertype == 'se'):
			if (len(pairs) <= 0):
				for key in self.tickets:
					return self._stopentryOrder('buy', self.tickets[key], key, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						return self._stopentryOrder('buy', self.tickets[p], p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")

		elif (ordertype == 'limit' or  ordertype == 'l'):
			if (len(pairs) <= 0):
				for key in self.tickets:
					return self._limitOrder('buy', self.tickets[key], key, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						return self._limitOrder('buy', self.tickets[p], p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")

		else:
			print("ERROR: Buy type not recognised!")

	def sell(self, lotsize, pairs = [], ordertype = 'market', entry = 0, sl = 0.0, tp = 0.0):
		if (ordertype == 'market' or ordertype == 'm'):
			if (len(pairs) <= 0):
				for key in self.tickets:
					return self._marketOrder('sell', self.tickets[key], key, lotsize, sl, tp)
			else:
				for p in pairs:
					try:
						return self._marketOrder('sell', self.tickets[p], p, lotsize, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")

		elif (ordertype == 'stopentry' or ordertype == 'se'):
			if (len(pairs) <= 0):
				for key in self.tickets:
					return self._stopentryOrder('sell', self.tickets[key], key, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						return self._stopentryOrder('sell', self.tickets[p], p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")

		elif (ordertype == 'limit' or  ordertype == 'l'):
			if (len(pairs) <= 0):
				for key in self.tickets:
					return self._limitOrder('sell', self.tickets[key], key, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						return self._limitOrder('sell', self.tickets[p], p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")

		else:
			print("ERROR: Sell type not recognised!")

	def updatePositions(self):
		print("Updating Positions")
		listenedTypes = ['Take Profit', 'Stop Loss', 'SE Order Sell Trade', 'SE Order Buy Trade', 'Limit Order Buy Trade', 'Limit Order Sell Trade']
		releventPositions = self.historyLog.getReleventPositions(listenedTypes)
		for value in releventPositions:
			if value[2] == 'Take Profit' or value[2] == 'Stop Loss':
				for pos in self.positions:
					if value[0] == pos.orderID:
						print(str(pos.orderID), str(value[2]))
						pos.closeprice = float(value[5])
						self.closedPositions.append(pos)
						del self.positions[self.positions.index(pos)]
			elif (value[2] == 'SE Order Sell Trade' or value[2] == 'SE Order Buy Trade' or
				 value[2] == 'Limit Order Sell Trade' or value[2] == 'Limit Order Buy Trade'):
				for pos in self.positions:
					if value[0] == pos.orderID:
				 		print(str(pos.orderID), str(value[2]))
				 		properties = self.historyLog.getHistoryPropertiesById(pos.orderID)[0]
				 		pos.entryprice = self.properties[5]
				 		pos.isPending = False

	def getPositionAmount(self, pair):
		return self.positionLog.getPairPositionAmount(pair)

	def positionExists(self, pos):
		return self.positionLog.positionExists(pos)

	def _marketOrder(self, direction, ticket, pair, lotsize, sl, tp):
		ticket.makeVisible()

		if (direction == 'buy'):
			ticket.selectBuy()
		elif (direction == 'sell'):
			ticket.selectSell()

		ticket.setMarketOrder()
		ticket.setLotsize(int(lotsize))

		if (float(sl) == 0.0):
			ticket.closeStopLoss()
		else:
			ticket.setStopLoss(float(sl))

		if (float(tp) == 0.0):
			ticket.closeTakeProfit()
		else:
			ticket.setTakeProfit(float(tp))

		orderID = ticket.placeOrder()
		if (orderID == -1):
			print("ERROR: unable to fullfil order, shutting down CMCTrader!")
			sys.exit()

		pos = Position(utils = self, ticket = ticket, orderID = orderID, pair = pair, ordertype = 'stopentry', direction = direction)

		positionModifyBtn = None

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.positionLog.getPositionModifyButton(pos) is not None)

		positionModifyBtn = self.positionLog.getPositionModifyButton(pos)

		pos.modifyBtn = positionModifyBtn

		properties = self.historyLog.getHistoryPropertiesById(orderID)[0]

		pos.driver = self.driver
		pos.openTime = self.getAustralianTime()
		pos.lotsize = int(properties[4])
		pos.sl = float(properties[6])
		pos.tp = float(properties[7])
		pos.entryprice = float(properties[5])

		self.positions.append(pos)

		print("Market " + str(direction) + " at " + str(pos.entryprice))

		return pos

	def _stopentryOrder(self, direction, ticket, pair, lotsize, entry, sl, tp):
		ticket.makeVisible()

		if (direction == 'buy'):
			if (self.convertToPips(entry - ticket.getAskPrice()) < 1.0):
				print("ERROR (stopentry buy): entry must be atleast 1 pip above current price!")
				return None
			ticket.selectBuy()
		elif (direction == 'sell'):
			if (self.convertToPips(ticket.getBidPrice() - entry) < 1.0):
				print("ERROR (stopentry sell): entry must be atleast 1 pip below current price!")
				return None
			ticket.selectSell()
		ticket.setStopEntryOrder(float(entry))
		ticket.setLotsize(int(lotsize))

		if (float(sl) == 0.0):
			ticket.closeStopLoss()
		else:
			ticket.setStopLoss(float(sl))

		if (float(tp) == 0.0):
			ticket.closeTakeProfit()
		else:
			ticket.setTakeProfit(float(tp))

		orderID = ticket.placeOrder()
		if (orderID == -1):
			print("ERROR: unable to fullfil order, shutting down CMCTrader!")
			sys.exit()
		elif (orderID == 0):
			if (direction == 'buy'):
				if (self.getAsk(pair) > entryprice):
					self._limitOrder(direction, ticket, pair, lotsize, entry, sl, tp)
				else:
					while (self.getAsk(pair) == entryprice):
						pass
					self._stopentryOrder(direction, ticket, pair, lotsize, entry, sl, tp)
			else:
				if (self.getBid(pair) < entryprice):
					self._limitOrder(direction, ticket, pair, lotsize, entry, sl, tp)
				else:
					while (self.getBid(pair) == entryprice):
						pass
					self._stopentryOrder(direction, ticket, pair, lotsize, entry, sl, tp)

		wait = ui.WebDriverWait(self.driver, 10)

		pos = Position(utils = self, ticket = ticket, orderID = orderID, pair = pair, ordertype = 'stopentry', direction = direction)

		orderModifyBtn = None

		wait.until(lambda driver : self.orderLog.getOrderModifyBtn(pos) is not None)

		orderModifyBtn = self.orderLog.getOrderModifyBtn(pos)

		pos.modifyBtn = orderModifyBtn

		pos.driver = self.driver
		pos.openTime = self.getAustralianTime()
		pos.lotsize = int(lotsize)
		pos.sl = float(sl)
		pos.tp = float(tp)
		pos.entryprice = float(entry)
		pos.isPending = True

		self.positions.append(pos)

		print("Stopentry " + str(direction) + " at " + str(pos.entryprice))

		return pos

	def _limitOrder(self, direction, ticket, pair, lotsize, entry, sl, tp):
		ticket.makeVisible()

		if (direction == 'buy'):
			if (self.convertToPips(ticket.getAskPrice() - entry) < 1.0):
				print("ERROR (limit buy): entry must be atleast 1 pip below current price!")
				return None
			ticket.selectBuy()
		elif (direction == 'sell'):
			if (self.convertToPips(entry - ticket.getBidPrice()) < 1.0):
				print("ERROR (limit sell): entry must be atleast 1 pip above current price!")
				return None
			ticket.selectSell()
		ticket.setLimitOrder(float(entry))
		ticket.setLotsize(int(lotsize))

		if (float(sl) == 0.0):
			ticket.closeStopLoss()
		else:
			ticket.setStopLoss(float(sl))

		if (float(tp) == 0.0):
			ticket.closeTakeProfit()
		else:
			ticket.setTakeProfit(float(tp))

		orderID = ticket.placeOrder()
		if (orderID == -1):
			print("ERROR: unable to fullfil order, shutting down CMCTrader!")
			sys.exit()
		elif (orderID == 0):
			if (direction == 'buy'):
				if (self.getAsk(pair) < entryprice):
					self._stopentryOrder(direction, ticket, pair, lotsize, entry, sl, tp)
				else:
					while (self.getAsk(pair) == entryprice):
						pass
					self._limitOrder(direction, ticket, pair, lotsize, entry, sl, tp)
			else:
				if (self.getBid(pair) > entryprice):
					self._stopentryOrder(direction, ticket, pair, lotsize, entry, sl, tp)
				else:
					while (self.getBid(pair) == entryprice):
						pass
					self._limitOrder(direction, ticket, pair, lotsize, entry, sl, tp)

		pos = Position(utils = self, ticket = ticket, orderID = orderID, pair = pair, ordertype = 'stopentry', direction = direction)

		orderModifyBtn = None

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(lambda driver : self.orderLog.getOrderModifyBtn(pos) is not None)

		orderModifyBtn = self.orderLog.getOrderModifyBtn(pos)
		
		pos.modifyBtn = orderModifyBtn

		pos.driver = self.driver
		pos.openTime = self.getAustralianTime()
		pos.lotsize = int(lotsize)
		pos.sl = float(sl)
		pos.tp = float(tp)
		pos.entryprice = float(entry)
		pos.isPending = True

		self.positions.append(pos)

		print("Limit " + str(direction) + " at " + str(pos.entryprice))

		return pos

	def getAUDPrice(self):
		return float(self.tAUDUSD.getBidPrice())

	def getBid(self, pair):
		return float(self.tickets[pair].getBidPrice())

	def getAsk(self, pair):
		return float(self.tickets[pair].getAskPrice())

	def updateValues(self):
		for key in self.tickets:
			if (not self.barReader.getCurrentBarInfo(key)):
				return False
			self.latestTimestamp[key] = self.barReader.getLatestBarTimestamp(key)
		return True
	
	def getMissingValues(self, pair, shift, amount):
		self.barReader.getBarInfo(pair, shift, amount)

	def recoverMissingValues(self):
		allMissingTimestamps = {}
		for pair in self.tickets:
			if (len(self.ohlc[pair]) <= 0):
				continue

			oldestTimestamp = sorted(self.ohlc[pair].items(), key=lambda kv: kv[0])[0][0]
			currentTime = self.getCurrentTimestamp()

			ohlcTimestamps = [i[0] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)]

			currentTimestamp = oldestTimestamp
			missingTimestamps = []
			while (currentTimestamp < currentTime):
				if (currentTimestamp in ohlcTimestamps):
					pass
				else:
					missingTimestamps.append(currentTimestamp)

				currentTimestamp += 60

			if (len(missingTimestamps) > 0):
				self.barReader.getBarInfoByTimestamp(pair, missingTimestamps)					
				allMissingTimestamps[pair] = missingTimestamps

		return allMissingTimestamps

	def getMissingTimestamps(self, timestamp):
		if (not self.manualChartReading):
			for pair in self.tickets:
				oldestTimestamp = timestamp
				currentTime = self.getCurrentTimestamp()

				ohlcTimestamps = [i[0] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)]

				currentTimestamp = oldestTimestamp
				missingTimestamps = []
				while (currentTimestamp < currentTime):
					if (currentTimestamp in ohlcTimestamps):
						pass
					else:
						missingTimestamps.append(currentTimestamp)

					currentTimestamp += 60

				if (len(missingTimestamps) > 0):
					self.barReader.getBarInfoByTimestamp(pair, missingTimestamps)


	def backtestByTime(self, pair, startDate, startTime, endDate, endTime):
		parts = startDate.split('/')
		day = parts[0]
		month = parts[1]
		parts = startTime.split(':')
		startTime = self.convertTimeToTimestamp(int(day), int(month), int(parts[0]), int(parts[1]))
		parts = endDate.split('/')
		day = parts[0]
		month = parts[1]
		parts = endTime.split(':')
		endTime = self.convertTimeToTimestamp(int(day), int(month), int(parts[0]), int(parts[1]))
		self.barReader.manualBarCollectionByTimestamp(pair, startTime, endTime)

	def getCurrentTimestamp(self):
		tz = pytz.timezone('Australia/Melbourne')
		date = datetime.datetime.now(tz = tz)

		then = datetime.datetime(year = 2018, month = 1, day = 1)
		now = datetime.datetime(year = date.year, month = date.month, day = date.day, hour = date.hour, minute = date.minute, second = 0)

		return int((now - then).total_seconds())

	def getAustralianTime(self):
		tz = pytz.timezone('Australia/Melbourne')
		return datetime.datetime.now(tz = tz)

	def getLondonTime(self):
		tz = pytz.timezone('Europe/London')
		return datetime.datetime.now(tz = tz)

	def createLondonTime(self, year, month, day, hours, mins, seconds):
		tz = pytz.timezone('Europe/London')
		return tz.localize(datetime.datetime(
					year = year,
					month = month,
					day = day,
					hour = hours,
					minute = mins,
					second = seconds
				))

	def convertTimeToTimestamp(self, day, month, hour, minute):
		tz = pytz.timezone('Australia/Melbourne')
		date = datetime.datetime.now(tz = tz)

		then = datetime.datetime(year = 2018, month = 1, day = 1)
		now = datetime.datetime(year = date.year, month = month, day = day, hour = hour, minute = minute, second = 0)

		return int((now - then).total_seconds())

	def convertTimestampToTime(self, timestamp):
		then = datetime.datetime(year = 2018, month = 1, day = 1)
		return then + datetime.timedelta(seconds = timestamp)

	def setTradeTimes(self, currentTime = None):
		if ('START_TIME' in self.plan.VARIABLES.keys() and 'END_TIME' in self.plan.VARIABLES.keys()):
			if (currentTime == None):
				currentTime = self.getLondonTime()

			startTimeParts = self.plan.VARIABLES['START_TIME'].split(':')
			endTimeParts = self.plan.VARIABLES['END_TIME'].split(':')

			self.startTime = self.createLondonTime(
					currentTime.year,
					currentTime.month,
					currentTime.day,
					int(startTimeParts[0]),
					int(startTimeParts[1]),
					0
				)

			self.endTime = self.createLondonTime(
					currentTime.year,
					currentTime.month,
					currentTime.day,
					int(endTimeParts[0]),
					int(endTimeParts[1]),
					0
				)

			if (int(startTimeParts[0]) > int(endTimeParts[0])):

				if (currentTime.hour < self.endTime.hour and currentTime.hour >= 0):
					self.startTime -= datetime.timedelta(days=1)
				else:
					self.endTime += datetime.timedelta(days=1)
		else:
			self.startTime = None
			self.endTime = None

	def isTradeTime(self, currentTime = None):
		tz = pytz.timezone('Europe/London')

		if (currentTime == None):
			currentTime = self.getLondonTime()

		if (not self.startTime == None and not self.endTime == None):
			if (self.startTime < currentTime < self.endTime):
				return True
			else:
				return False

		else:
			return True

	def printTime(self, time):
		print("Time:",str(time.hour)+":"+str(time.minute)+":"+str(time.second))

	def _prompt(self):
		x = input()

		if x == '':
			pass
		elif x == 'stop':
			self.setStopped()
		elif x == 'start':
			self.setStarted()
		elif x == 'manual':
			self.setManualChartReading()
		elif x == 'vars':
			self.printVars()
		elif x.startswith('change'):
			self.changeVar(x)
		elif x.startswith('add news'):
			self.addNews(x)
		else:
			print("Didn't recognize command:", x)
			
			print("\n")
		self._prompt()

	def setStopped(self):
		self.isStopped = True
		print("Trading has been stopped.")

	def setStarted(self):
		self.isStopped = False
		print("Trading has been started.")

	def setManualChartReading(self):
		self.manualChartReading = True
		self.setStopped()
		print("Starting manualChartReading")
		sys.exit()

	def printVars(self):
		print("VARIABLES:")
		maxLen = 0
		for var in self.plan.VARIABLES:
			if (var == 'TICKETS' or self.plan.VARIABLES[var] == None):
				continue
			if len(str(var)) > maxLen:
				maxLen = len(str(var))
		
		maxTabs = math.floor(maxLen / 8.0)
		for var in self.plan.VARIABLES:
			if (var == 'TICKETS'):
				continue
			if (self.plan.VARIABLES[var] == None):
				printStr = "- " + str(var) + " -"
			else:
				varTabs = math.floor(len(str(var)) / 8.0)
				numTabs = maxTabs - varTabs + 1
				printStr = str(var) + ":"
				for i in range(numTabs):
					printStr += "\t"
				printStr += str(self.plan.VARIABLES[var])
			print(printStr)

	def changeVar(self, x):
		if (x == 'change'):
			print("Please enter variable and new value to change.\n e.g. change START_TIME 16:00")
		else:
			parts = x.split(' ')
			if (not len(parts) == 3):
				print("Please use 'change' command in this format:\n change VARIABLE_NAME NEW_VALUE")
				return
			try:
				castedVal = type(self.plan.VARIABLES[str(parts[1])])(parts[2])
				self.plan.VARIABLES[str(parts[1])] = castedVal
				print("Changed", parts[1], "to", parts[2])
			except:
				print("Unable to change", parts[1], "to", parts[2])
				return

	def addNews(self, x):
		if (x == 'add news'):
			print("Please enter time of news.\n e.g. add news 16:00")
		else:
			parts = x.strip().split(' ')
			if (not len(parts) == 4):
				print("Please use 'add news' command in this format:\n add news NEWS_TIME")
				return
			try:
				time = parts[2].split(':')
				date = parts[3].split('/')
				year = self.getLondonTime().year
				self.newsTimes["_" + str(uuid.uuid4())] = self.createLondonTime(year, int(date[1]), int(date[0]), int(time[0]), int(time[1]), 0)
				print("News added!")
			except:
				print("Unable to add", str(parts[2]), str(parts[3]), "to news items.")
				
	def getBankSize(self):
		text = self.driver.execute_script(
				'return document.querySelector(\'div[class="account-summary-item account-value"]\').querySelector(\'span[class="value"]\').innerHTML;'
			)
		return float(text.strip('$').replace(',', ''))

	def getLotsize(self, bank, risk, stoprange):
		return int(round(((bank * (risk/100.0) * self.getAUDPrice()) / stoprange * 10000)/100)*100)

	def getTotalProfit(self):
		totalProfit = 0
		for pos in self.closedPositions:
			totalProfit += pos.getProfit()

		return round(totalProfit, 1)

	def getEarliestTimestamp(self, timestamps):
		timestamps.sort()
		return timestamps[0]

	def getLatestTimestamp(self, timestamps):
		timestamps.sort()
		return timestamps[0]

	def getBarOffset(self, timestamp):
		currentTime = self.getCurrentTimestamp()
		return int((currentTime - timestamp) / 60)

	def getTimestampFromOffset(self, pair, shift, amount):
		if pair in self.latestTimestamp:
			currentTime = self.latestTimestamp[pair]
		else:
			currentTime = self.getCurrentTimestamp()
		return currentTime - (shift + amount + 1) * 60

	def isCurrentTimestamp(self, pair):
		currentTimestamp = self.getCurrentTimestamp()
		try:
			if (currentTimestamp - 60 == self.latestTimestamp[pair]):
				return True
		except:
			return False
		return False

	def setTickets(self, tickets):
		self.tickets = tickets

	def setAUDUSDTicket(self, tAUDUSD):
		self.tAUDUSD = tAUDUSD