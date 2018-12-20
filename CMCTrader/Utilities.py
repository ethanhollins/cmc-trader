from selenium import webdriver
import selenium.webdriver.support.ui as ui
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import numpy as np
import time
import threading
import sys
import datetime
import pytz
import math
import uuid
import json
import os

import boto3
import decimal
from botocore.exceptions import ClientError

from CMCTrader import DBManager as db
from CMCTrader import Log
from CMCTrader.Position import Position
from CMCTrader.HistoryLog import HistoryLog
from CMCTrader.PositionLog import PositionLog
from CMCTrader.OrderLog import OrderLog
from CMCTrader.BarReader import BarReader
from CMCTrader.Backtester import Backtester
from CMCTrader.SocketManager import SocketManager

from CMCTrader.Indicators.SMA import SMA
from CMCTrader.Indicators.SAR import SAR
from CMCTrader.Indicators.RSI import RSI
from CMCTrader.Indicators.CCI import CCI
from CMCTrader.Indicators.MACD import MACD
from CMCTrader.Indicators.ADXR import ADXR

CMC_WEBSITE = 'https://platform.cmcmarkets.com/'

class Utilities:

	def __init__(self, driver, plan, user_info, tickets, tAUDUSD):
		self.driver = driver
		self.plan = plan
		self.tickets = tickets
		self.tAUDUSD = tAUDUSD

		self.user_id = json.loads(user_info)['user_id']
		self.plan_name = json.loads(user_info)['user_program']

		Log.set_utils(self)

		self._initVARIABLES()

		self.positionLog = PositionLog(self.driver)
		self.orderLog = OrderLog(self.driver)
		self.barReader = BarReader(self, self.driver)
		self.backtester = Backtester(self, self.plan)

		self.orders = []
		self.positions = []
		self.closedPositions = []

		self.ohlc = self._initOHLC()
		self.indicators = {"overlays" : [], "studies" : []}

		self.newsTimes = {}

		self.isStopped = False
		self.isLive = False
		self.manualEntry = False
		self.manualChartReading = False

		self.latestTimestamp = {}

		self.startTime = None
		self.endTime = None

		self.setTradeTimes()

		self.historyLog = HistoryLog(self.driver, self)

		self.save_state = self.plan.SaveState(self)
		
		# self.socket_manager = SocketManager(self)
		# self.socket_manager.send("cmd", "lololol")

		self._startPrompt()

	def reinit(self, init_bar_reader = True):
		self.historyLog.reinit(self.driver)
		self.positionLog.reinit(self.driver)
		self.orderLog.reinit(self.driver)

		if (init_bar_reader):
			self.barReader.reinit(self.driver)

	def _initOHLC(self):
		temp = {}
		for key in self.tickets:
			temp[key] = {}
		return temp

	def _initVARIABLES(self):
		result = db.getItems(self.user_id, 'user_variables')

		if (result['user_variables'] == None):
			db_vars = {}
		else:
			db_vars = json.loads(result['user_variables'])
			if (self.plan_name in db_vars):
				plan_vars = db_vars[self.plan_name]
			else:
				plan_vars = {}

		set_current, set_past = set(self.plan.VARIABLES.keys()), set(plan_vars.keys())
		intersect = set_current.intersection(set_past)

		for i in set_past - intersect:
			del plan_vars[i]

		for i in set_current - intersect:
			plan_vars[i] = self.plan.VARIABLES[i]

		changed = set(i for i in intersect if plan_vars[i] != self.plan.VARIABLES[i])
		
		for i in changed:
			self.plan.VARIABLES[i] = type(self.plan.VARIABLES[i])(plan_vars[i])

		db_vars[self.plan_name] = { k : v for k,v in sorted(plan_vars.items(), key = lambda kv: list(self.plan.VARIABLES.keys()).index(kv[0])) }
		update_dict = { 'user_variables' : json.dumps(db_vars) }
		
		db.updateItems(self.user_id, update_dict)

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

# for pos in self.positions:
# 						if value[0] == pos.orderID:
# 							if not pos.sl == value[6]:
# 								if ()
# 									pos.modifySL(self.utils.convertToPips())

# 							if not pos.tp == value[7]:

	def updatePositions(self):
		print("Updating Positions")
		listenedTypes = [
				'Buy Trade', 'Sell Trade',
				'Buy SE Order', 'Sell SE Order',
				'SE Order Sell Trade', 'SE Order Buy Trade', 'Limit Order Buy Trade', 'Limit Order Sell Trade',
				'Buy Trade Modified', 'Sell Trade Modified',
				'Buy SE Order Modified', 'Sell SE Order Modified',
				'Stop Loss Modified', 'Take Profit Modified',
				'Take Profit', 'Stop Loss', 
				'Close Trade', 'Order Cancelled'
			]
		history = self.historyLog.updateHistory(listenedTypes)
		for event in history:
			self.updateEvent(event)
		
	def updateEvent(self, event):
		if event[2] == 'Buy Trade':
			position_id_list = [i.orderID for i in self.positions] + [j.orderID for j in self.closedPositions]

			if not event[0] in position_id_list:
				print("UTILITIES:", str(event))
				pos = self.createPosition(utils = self, ticket = self.tickets[event[3]], orderID = event[0], pair = event[3], ordertype = 'market', direction = 'buy')
				pos.openTime = event[1]
				pos.entryprice = float(event[5])
				pos.lotsize = int(event[4])
				pos.sl = float(event[6])
				pos.tp = float(event[7])
				pos.isTrailing = event[9]
				self.positions.append(pos)

				try:
					self.plan.onEntry(pos)
				except AttributeError as e:
					pass

		elif event[2] == 'Sell Trade':
			position_id_list = [i.orderID for i in self.positions] + [j.orderID for j in self.closedPositions]

			if not event[0] in position_id_list:
				print("UTILITIES:", str(event))
				pos = self.createPosition(utils = self, ticket = self.tickets[event[3]], orderID = event[0], pair = event[3], ordertype = 'market', direction = 'sell')
				pos.openTime = event[1]
				pos.entryprice = float(event[5])
				pos.lotsize = int(event[4])
				pos.sl = float(event[6])
				pos.tp = float(event[7])
				pos.isTrailing = event[9]
				self.positions.append(pos)

				try:
					self.plan.onEntry(pos)
				except AttributeError as e:
					pass

		elif event[2] == 'Buy SE Order':
			order_id_list = [i.orderID for i in self.orders]

			if not event[0] in order_id_list:
				pos = self.createPosition(utils = self, ticket = self.tickets[event[3]], orderID = event[0], pair = event[3], ordertype = 'stopentry', direction = 'buy')
				pos.openTime = event[1]
				pos.entryprice = float(event[5])
				pos.lotsize = int(event[4])
				pos.sl = float(event[6])
				pos.tp = float(event[7])
				pos.isPending = True
				pos.isTrailing = event[9]
				self.orders.append(pos)

		elif event[2] == 'Sell SE Order':
			order_id_list = [i.orderID for i in self.orders]

			if not event[0] in order_id_list:
				pos = self.createPosition(utils = self, ticket = self.tickets[event[3]], orderID = event[0], pair = event[3], ordertype = 'stopentry', direction = 'sell')
				pos.openTime = event[1]
				pos.entryprice = float(event[5])
				pos.lotsize = int(event[4])
				pos.sl = float(event[6])
				pos.tp = float(event[7])
				pos.isPending = True
				pos.isTrailing = event[9]
				self.orders.append(pos)

		elif event[2] == 'Close Trade':
			for pos in self.positions:
				if event[8] == pos.orderID:
					print("UTILITIES:", str(event))
					pos.closeTime = event[1]
					pos.closeprice = float(event[5])
					print("Close price:", str(pos.closeprice))
					self.closedPositions.append(pos)
					del self.positions[self.positions.index(pos)]

			for order in self.orders:
				if event[0] == order.orderID:
					del self.orders[self.orders.index(order)]

		elif event[2] == 'Order Cancelled':
			for order in self.orders:
				if event[0] == order.orderID:
					del self.orders[self.orders.index(order)]

		elif event[2] == 'Take Profit' or event[2] == 'Stop Loss':
			for pos in self.positions:
				if event[0] == pos.orderID:
					print(str(pos.orderID), str(event[2]))
					pos.closeTime = event[1]
					pos.closeprice = float(event[5])
					self.closedPositions.append(pos)
					del self.positions[self.positions.index(pos)]

					if event[2] == 'Take Profit':
						try:
							self.plan.onTakeProfit(pos)
						except AttributeError as e:
							pass
					elif event[2] == 'Stop Loss':
						try:
							self.plan.onStopLoss(pos)
						except AttributeError as e:
							pass

		elif (event[2] == 'SE Order Sell Trade' or event[2] == 'SE Order Buy Trade' or
			event[2] == 'Limit Order Sell Trade' or event[2] == 'Limit Order Buy Trade'):
			for order in self.orders:
				if event[0] == order.orderID:
					print(str(order.orderID), str(event[2]))

					order.entryprice = float(event[5])
					order.isPending = False

					self.positions.append(order)
					del self.orders[self.orders.index(order)]

					try:
						self.plan.onEntry(order)
					except AttributeError as e:
						pass

		elif event[2] == 'Buy Trade Modified' or event[2] == 'Sell Trade Modified':
			positions_list = self.positions + self.closedPositions
			for pos in positions_list:
				if event[0] == pos.orderID:
					print(str(pos.orderID), str(event[2]))

					pos.entryprice = float(event[5])
					pos.sl = float(event[6])
					pos.tp = float(event[7])
					pos.isTrailing = event[9]

		elif event[2] == 'Buy SE Order Modified' or event[2] == 'Sell SE Order Modified':
			for order in self.orders:
				if event[0] == order.orderID:
					print(str(order.orderID), str(event[2]))

					order.entryprice = float(event[5])
					order.sl = float(event[6])
					order.tp = float(event[7])
					order.isTrailing = event[9]

		elif event[2] == 'Stop Loss Modified':
			complete_list = self.positions + self.closedPositions + self.orders
			for pos in complete_list:
				if event[0] == pos.orderID:
					print(str(pos.orderID), str(event[2]))
					pos.entryprice = float(event[5])
					pos.sl = float(event[6])
					pos.isTrailing = event[9]

		elif event[2] == 'Take Profit Modified':
			complete_list = self.positions + self.closedPositions + self.orders
			for pos in complete_list:
				if event[0] == pos.orderID:
					print(str(pos.orderID), str(event[2]))
					pos.entryprice = float(event[5])
					pos.tp = float(event[7])

	def resetPositions(self):
		self.positions = []
		self.closedPositions = []
		self.orders = []

	def getPositionAmount(self, pair):
		return self.positionLog.getPairPositionAmount(pair)

	def positionExists(self, pos):
		return self.positionLog.positionExists(pos)

	@Backtester.market_redirect_backtest
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

		if (orderID == 0):
			print("Error occured on market order!")
			self.updatePositions()
			return None

		pos = Position(utils = self, ticket = ticket, orderID = orderID, pair = pair, ordertype = 'market', direction = direction)

		positionModifyBtn = None

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.positionLog.getPositionModifyButton(pos) is not None)

		positionModifyBtn = self.positionLog.getPositionModifyButton(pos)

		pos.modifyBtn = positionModifyBtn

		properties = self.historyLog.getHistoryPropertiesById(orderID)[0]

		pos.openTime = properties[1]
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
			ticket.selectBuy()
		elif (direction == 'sell'):
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

		if (orderID == 0):
			print("Error occured on stop entry order!")
			self.updatePositions()
			return None

		wait = ui.WebDriverWait(self.driver, 10)

		pos = Position(utils = self, ticket = ticket, orderID = orderID, pair = pair, ordertype = 'stopentry', direction = direction)

		orderModifyBtn = None

		wait.until(lambda driver : self.orderLog.getOrderModifyBtn(pos) is not None)

		orderModifyBtn = self.orderLog.getOrderModifyBtn(pos)

		pos.modifyBtn = orderModifyBtn

		properties = self.historyLog.getHistoryPropertiesById(orderID)[0]

		pos.openTime = properties[1]
		pos.lotsize = int(properties[4])
		pos.sl = float(properties[6])
		pos.tp = float(properties[7])
		pos.entryprice = float(properties[5])
		pos.isPending = True

		self.orders.append(pos)

		print("Stopentry " + str(direction) + " at " + str(pos.entryprice))

		return pos

	def _limitOrder(self, direction, ticket, pair, lotsize, entry, sl, tp):
		ticket.makeVisible()

		if (direction == 'buy'):
			ticket.selectBuy()
		elif (direction == 'sell'):
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

		if (orderID == 0):
			print("Error occured on limit order!")
			self.updatePositions()
			return None

		pos = Position(utils = self, ticket = ticket, orderID = orderID, pair = pair, ordertype = 'limit', direction = direction)

		orderModifyBtn = None

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(lambda driver : self.orderLog.getOrderModifyBtn(pos) is not None)

		orderModifyBtn = self.orderLog.getOrderModifyBtn(pos)
		
		pos.modifyBtn = orderModifyBtn

		properties = self.historyLog.getHistoryPropertiesById(orderID)[0]

		pos.openTime = properties[1]
		pos.lotsize = int(properties[4])
		pos.sl = float(properties[6])
		pos.tp = float(properties[7])
		pos.entryprice = float(properties[5])
		pos.isPending = True

		self.orders.append(pos)

		print("Limit " + str(direction) + " at " + str(pos.entryprice))

		return pos

	def getAUDPrice(self):
		return float(self.tAUDUSD.getBidPrice())

	@Backtester.price_redirect_backtest
	def getBid(self, pair):
		return float(self.tickets[pair].getBidPrice())

	@Backtester.price_redirect_backtest
	def getAsk(self, pair):
		return float(self.tickets[pair].getAskPrice())

	def updateValues(self):
		for key in self.tickets:
			if (not self.barReader.getCurrentBarInfo(key)):
				return False
			self.latestTimestamp[key] = self.barReader.getLatestBarTimestamp(key)
		return True
	
	def getMissingValues(self, pair, shift, amount):
		print("getMissingValues")
		self.barReader.getBarInfo(pair, shift, amount)

	@Backtester.dict_redirect_backtest
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
					if (currentTimestamp > currentTime - (60 * 50)):
						missingTimestamps.append(currentTimestamp)

				currentTimestamp += 60

			if (len(missingTimestamps) > 0):
				self.barReader.getBarInfoByTimestamp(pair, missingTimestamps)					
				allMissingTimestamps[pair] = missingTimestamps

		return allMissingTimestamps

	@Backtester.skip_on_backtest
	def getMissingTimestamps(self, timestamp):
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
					if (currentTimestamp > currentTime - (60 * 50)):
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

	@Backtester.australian_time_redirect_backtest
	def getAustralianTime(self):
		tz = pytz.timezone('Australia/Melbourne')
		return datetime.datetime.now(tz = tz)

	@Backtester.london_time_redirect_backtest
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

	def convertDateTimeToTimestamp(self, now):
		tz = pytz.timezone('Australia/Melbourne')

		then = datetime.datetime(year = 2018, month = 1, day = 1)
		print(now)
		now = now.astimezone(tz)
		print(now)
		now = now.replace(tzinfo=None)
		print(now)
		return int((now - then).total_seconds())

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

			if (self.startTime > self.endTime):

				if (self.startTime - datetime.timedelta(days=1) < currentTime < self.endTime):
					self.startTime -= datetime.timedelta(days=1)
				else:
					self.endTime += datetime.timedelta(days=1)

			else:
				if (currentTime > self.endTime):
					self.startTime += datetime.timedelta(days=1)
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

	@Backtester.redirect_backtest
	def refreshAll(self):
		for pair in self.tickets:
			self.refreshChart(pair)

			# timestamp = self.latestTimestamp[pair]
			# changed_timestamps = self.checkTimestampValues(pair, timestamp)

			# if (len(changed_timestamps) > 0):
			# 	self.refreshValues(pair, changed_timestamps)

	@Backtester.redirect_backtest
	def refreshChart(self, pair):
		chart = self.barReader.getChart(pair)

		self.barReader.moveToChart(pair)

		chart_id = self.driver.execute_script(
						'return arguments[0].getAttribute("id");',
						chart
					)

		chart_select = self.driver.execute_script(
						'var chart_select = arguments[0].querySelector(\'button[class="feature-window-saved-states-toggle"]\');'
						'chart_select.click();'
						'return chart_select;',
						chart
					)

		chart_title = self.driver.execute_script(
						'return arguments[0].getAttribute("title");',
						chart_select
					)

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(chart_id)+"']//div[contains(@class, 'feature-window-saved-states')]//li[contains(@title, '"+str(chart_title)+"')]")
		))

		refresh_btn = self.driver.find_element(By.XPATH, "//div[@id='"+str(chart_id)+"']//div[contains(@class, 'feature-window-saved-states')]//li[contains(@title, '"+str(chart_title)+"')]")

		refresh_btn.click()

		self.barReader.setCanvases(self.barReader.chartDict)

		wait = ui.WebDriverWait(self.driver, 60)
		wait.until(lambda driver : self.chartTimestampCheck(pair))
		
		self.barReader.dragCanvases()

	def refreshValues(self, pair, changed_timestamps):
		# timestamp = self.latestTimestamp[pair]

		# changed_timestamps = self.checkTimestampValues(pair, timestamp)

		# if (len(changed_timestamps) > 0):

		print(changed_timestamps)

		# self.save_state.load()

		print("Backtesting changed timestamps")
		
		values = self.formatForRecover(pair, changed_timestamps)
		self.backtester.recover(values['ohlc'], values['indicators'])

	def refreshAllValues(self, pair):

		self.plan.initVariables()
		# self.save_state.load()

		first_timestamp = [i[0] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=False)][0]

		print("Backtesting changed timestamps")
		
		values = self.formatForRecover(pair, first_timestamp)
		self.backtester.recover(values['ohlc'], values['indicators'])

	def formatForRecover(self, pair, missing_timestamps):
		if (type(missing_timestamps) == list):
			print("islist")
			earliest_timestamp = self.getEarliestTimestamp(missing_timestamps)
		else:
			print("isnt")
			earliest_timestamp = missing_timestamps

		missing_timestamps = []
		sorted_timestamps = [i[0] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)]
		for timestamp in sorted_timestamps:
			if (timestamp >= earliest_timestamp):
				missing_timestamps.append(timestamp)
			else:
				break

		# print(missing_timestamps)

		values = {}

		values['ohlc'] = {}
		values['indicators'] = { 'overlays' : [], 'studies' : [] }

		for pair in self.ohlc:
			values['ohlc'][pair] = {}
			for timestamp in missing_timestamps:
				values['ohlc'][pair][timestamp] = self.ohlc[pair][timestamp]

		count = 0
		for overlay in self.indicators['overlays']:
			for pair in overlay.history:
				values['indicators']['overlays'].append({ pair : {} })

				for timestamp in missing_timestamps:
					values['indicators']['overlays'][count][pair][timestamp] = overlay.history[pair][timestamp]
			count += 1

		count = 0
		for study in self.indicators['studies']:
			for pair in study.history:
				values['indicators']['studies'].append({ pair : {} })

				for timestamp in missing_timestamps:
					values['indicators']['studies'][count][pair][timestamp] = study.history[pair][timestamp]
			count += 1

		# print(values)
		return values

	def isChartAvailable(self, chart_id):
		availability_checker = self.driver.find_element(By.XPATH, "//div[@id='"+str(chart_id)+"']//div[contains(@class, 'popup-container')]")

		checker_class = availability_checker.get_attribute("class")

		return 'active' in str(checker_class)

	def chartTimestampCheck(self, pair):
		try:
			self.barReader.getLatestBarTimestamp(pair)
			return True
		except:
			return False

	def checkTimestampValues(self, pair, timestamp):
		return self.barReader.checkBarInfoByTimestamp(pair, [timestamp])

	def updateRecovery(self):
		values = {}

		values['timestamp'] = self.getCurrentTimestamp()
		values['ohlc'] = self.ohlc
		values['indicators'] = { 'overlays' : [], 'studies' : [] }

		for i in range(len(self.indicators['overlays'])):
			values['indicators']['overlays'].append(self.indicators['overlays'][i].history.copy()) 
		for j in range(len(self.indicators['studies'])):
			values['indicators']['studies'].append(self.indicators['studies'][j].history.copy())

		with open('recover.json', 'w') as f:
			json.dump(values, f)

	def getRecovery(self):
		if (os.path.exists('recover.json')):
			with open('recover.json', 'r') as f:
				values = json.load(f)

			if (self.getCurrentTimestamp() - int(values['timestamp']) <= 60 * 45):
				for pair in values['ohlc']:
					values['ohlc'][pair] = {int(k):v for k,v in values['ohlc'][pair].items()}

				for overlay in values['indicators']['overlays']:
					overlay[pair] = {int(k):v for k,v in overlay[pair].items()}

				for study in values['indicators']['studies']:
					study[pair] = {int(k):v for k,v in study[pair].items()}


				self.backtester.recover(values['ohlc'], values['indicators'])

			else:
				os.remove('recover.json')

	def createPosition(self, utils, ticket, orderID, pair, ordertype, direction):
		return Position(utils, ticket, orderID, pair, ordertype, direction)