from selenium import webdriver
import selenium.webdriver.support.ui as ui
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from enum import Enum

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
from CMCTrader import Constants
from CMCTrader import RetrieveTicketElements

from CMCTrader.Chart import Chart
from CMCTrader.Ticket import Ticket
from CMCTrader.Position import Position
from CMCTrader.HistoryLog import HistoryLog
from CMCTrader.PositionLog import PositionLog
from CMCTrader.OrderLog import OrderLog
from CMCTrader.BarReader2 import BarReader
from CMCTrader.Backtester import Backtester
from CMCTrader import SocketManager

from CMCTrader.Indicators.SMA import SMA
from CMCTrader.Indicators.BOLL import BOLL
from CMCTrader.Indicators.MAE import MAE
from CMCTrader.Indicators.SAR import SAR
from CMCTrader.Indicators.SAR_M import SAR_M
from CMCTrader.Indicators.ATR import ATR
from CMCTrader.Indicators.RSI import RSI
from CMCTrader.Indicators.CCI import CCI
from CMCTrader.Indicators.MACD import MACD
from CMCTrader.Indicators.MACDZ import MACDZ
from CMCTrader.Indicators.MACDZ_M import MACDZ_M
from CMCTrader.Indicators.ADXR import ADXR
from CMCTrader.Indicators.DMI import DMI

CMC_WEBSITE = 'https://platform.cmcmarkets.com/'

class Utilities:

	def __init__(self, driver, plan, user_info):
		self.driver = driver
		self.plan = plan
		self.charts = []
		self.tickets = []
		self.tAUDUSD = self.createTicket(Constants.AUDUSD)

		self.user_id = json.loads(user_info)['user_id']
		self.trader_id = self.user_id
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

		self.newsTimes = {}

		self.isStopped = False
		self.isLive = False
		self.manualEntry = False
		self.manualChartReading = False
		self.is_backtest = False

		self.latestTimestamp = {}

		self.setTime()
		self.startTime = None
		self.endTime = None
		self.open_time = self.setTimezone(Constants.DT_START_DATE, 'Pacific/Auckland')
		self.close_time = self.setTimezone(Constants.DT_START_DATE, 'America/New_York')

		self.is_downtime = True

		# Bank
		self.external_bank = 0
		self.maximum_bank = 0
		self.initBank()

		self.setTradeTimes()

		self.historyLog = HistoryLog(self.driver, self)

		self.startServer()
		
		self._startPrompt()

	def reinit(self, driver, get_chart_regions=True):
		self.driver = driver
		self.historyLog.reinit(self.driver)
		self.positionLog.reinit(self.driver)
		self.orderLog.reinit(self.driver)
		self.barReader.reinit(self.driver)

		all_positions = self.positions + self.closedPositions + self.orders
		for i in all_positions:
			i.driver = self.driver

		self.reinitCharts()
		self.reinitTickets()
		self.reinitAUDUSDTicket()
		self.setTime()

		if get_chart_regions:
			for chart in self.charts:
				self.barReader.setChartRegions(chart)

	def _initVARIABLES(self):
		result = db.getItems(self.user_id, 'user_variables')

		if result['user_variables']:
			db_vars = result['user_variables']
			if self.plan_name in db_vars:
				plan_vars = db_vars[self.plan_name]
			else:
				plan_vars = {}
		else:
			db_vars = {}
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
		
		for key in db_vars[self.plan_name]:
			if type(db_vars[self.plan_name][key]) == float:
				db_vars[self.plan_name][key] = str(db_vars[self.plan_name][key])

		db.updateItems(self.user_id, { 'user_variables' : db_vars })

	def _startPrompt(self):
		task = self._prompt
		t = threading.Thread(target = task)
		t.start()

	def initBank(self):
		result = db.getItems(self.user_id, 'account_bank')

		if result['account_bank']:
			self.external_bank = float(result['account_bank']['external'])
			self.maximum_bank = float(result['account_bank']['maximum'])
		else:
			self.external_bank = 0
			self.maximum_bank = 1000

	def updateBank(self, external_bank=None, maximum_bank=None):
		if external_bank:
			self.external_bank = external_bank
		if maximum_bank:
			self.maximum_bank = maximum_bank
		db.updateItems(self.user_id, {
			'account_bank' : {
				'external': format(self.external_bank, ".15g"),
				'maximum': format(self.maximum_bank, ".15g")
			} 
		})

	def startServer(self):
		task = SocketManager.init
		t = threading.Thread(target=task, args=(self,))
		t.start()

	def setTime(self):
		self.secs_elem = self.driver.execute_script(
			'return document.querySelector(\'[class="current-time"]\').querySelector(\'[class="s"]\');'
		)

		self.mins_elem = self.driver.execute_script(
			'return document.querySelector(\'[class="current-time"]\').querySelector(\'[class="m"]\');'
		)

		self.hours_elem  = self.driver.execute_script(
			'return document.querySelector(\'[class="current-time"]\').querySelector(\'[class="h"]\');'
		)

	def SMA(self, pair, chart_period, timeperiod):
		chart = self.getChart(pair, chart_period)
		sma = SMA(self, len(chart.overlays), chart, timeperiod)
		chart.overlays.append(sma)
		chart.overlays.sort(key=lambda x: x.index)
		return sma

	def MAE(self, pair, chart_period, timeperiod, percent_off):
		chart = self.getChart(pair, chart_period)
		mae = MAE(self, len(chart.overlays), chart, timeperiod, percent_off)
		chart.overlays.append(mae)
		chart.overlays.sort(key=lambda x: x.index)
		return mae

	def SAR(self, pair, chart_period, colour):
		chart = self.getChart(pair, chart_period)
		sar = SAR(self, len(chart.overlays), chart, colour)
		chart.overlays.append(sar)
		chart.overlays.sort(key=lambda x: x.index)
		return sar

	def SAR_M(self, pair, chart_period, acceleration, maximum):
		chart = self.getChart(pair, chart_period)
		sar_m = SAR_M(self, len(chart.overlays), chart, acceleration, maximum)
		chart.overlays.append(sar_m)
		chart.overlays.sort(key=lambda x: x.index)
		return sar_m

	def BOLL(self, pair, chart_period, timeperiod, stds):
		chart = self.getChart(pair, chart_period)
		boll = BOLL(self, len(chart.overlays), chart, timeperiod, stds)
		chart.overlays.append(boll)
		chart.overlays.sort(key=lambda x: x.index)
		return boll

	def ATR(self, pair, chart_period, timeperiod):
		chart = self.getChart(pair, chart_period)
		atr = ATR(self, len(chart.studies), chart, timeperiod)
		chart.studies.append(atr)
		chart.studies.sort(key=lambda x: x.index)
		return atr

	def RSI(self, pair, chart_period, timeperiod):
		chart = self.getChart(pair, chart_period)
		rsi = RSI(self, len(chart.studies), chart, timeperiod)
		chart.studies.append(rsi)
		chart.studies.sort(key=lambda x: x.index)
		return rsi

	def CCI(self, pair, chart_period, timeperiod):
		chart = self.getChart(pair, chart_period)
		cci = CCI(self, len(chart.studies), chart, timeperiod)
		chart.studies.append(cci)
		chart.studies.sort(key=lambda x: x.index)
		return cci

	def MACD(self, pair, chart_period, fastperiod, slowperiod, signalperiod):
		chart = self.getChart(pair, chart_period)
		macd = MACD(self, len(chart.studies), chart, fastperiod, slowperiod, signalperiod)
		chart.studies.append(macd)
		chart.studies.sort(key=lambda x: x.index)
		return macd

	def MACDZ(self, pair, chart_period, fastperiod, slowperiod, signalperiod):
		chart = self.getChart(pair, chart_period)
		macdz = MACDZ(self, len(chart.studies), chart, fastperiod, slowperiod, signalperiod)
		chart.studies.append(macdz)
		chart.studies.sort(key=lambda x: x.index)
		return macdz

	def MACDZ_M(self, pair, chart_period, fastperiod, slowperiod, signalperiod):
		chart = self.getChart(pair, chart_period)
		macdz_m = MACDZ_M(self, len(chart.studies), chart, fastperiod, slowperiod, signalperiod)
		chart.studies.append(macdz_m)
		chart.studies.sort(key=lambda x: x.index)
		return macdz_m

	def ADXR(self, pair, chart_period):
		chart = self.getChart(pair, chart_period)
		adxr = ADXR(self, len(chart.studies), chart)
		chart.studies.append(adxr)
		chart.studies.sort(key=lambda x: x.index)
		return adxr

	def DMI(self, pair, chart_period):
		chart = self.getChart(pair, chart_period)
		dmi = DMI(self, len(chart.studies), chart)
		chart.studies.append(dmi)
		chart.studies.sort(key=lambda x: x.index)
		return dmi

	def createChart(self, pair, period):
		self.getTicket(pair)
		chart = Chart(self.driver, pair, period)
		self.barReader.setChartRegions(chart)
		self.charts.append(chart)
		return chart

	def getChart(self, pair, period):
		for chart in self.charts:
			if chart.pair == pair and chart.period == period:
				return chart
		
		return self.createChart(pair, period)

	def createTicket(self, pair):
		print("Initializing", str(pair), "ticket data...")
		ticket_elements = RetrieveTicketElements.retrieveTicketElements(self.driver, pair)
		
		ticket = Ticket(driver=self.driver, pair=pair, ticket_elements=ticket_elements)
		self.tickets.append(ticket)

		print(str(pair), "initialized!\n")

		return ticket

	def getTicket(self, pair):
		for t in self.tickets:
			if t.pair == pair:
				return t

		return self.createTicket(pair)

	def getGlobalStorage(self):
		result = db.getItems(self.trader_id, 'user_global_storage')
		if result['user_global_storage'] and self.plan_name in result['user_global_storage']:
			return result['user_global_storage'][self.plan_name]
		else:
			return None

	def updateGlobalStorage(self, storage):
		temp = self.getGlobalStorage()
		if temp:
			temp[self.plan_name] = storage
		else:
			temp = {self.plan_name : storage}

		db.updateItems(self.trader_id, {'user_global_storage' : temp})

	@Backtester.get_local_storage_on_backtest
	def getLocalStorage(self):
		result = db.getItems(self.user_id, 'user_local_storage')
		if result['user_local_storage'] and self.plan_name in result['user_local_storage']:
			return result['user_local_storage'][self.plan_name]
		else:
			return {}

	def getLocalStorageParent(self):
		result = db.getItems(self.user_id, 'user_local_storage')
		if result['user_local_storage']:
			return result['user_local_storage']
		else:
			return {}

	@Backtester.update_local_storage_on_backtest
	def updateLocalStorage(self, storage):
		temp = self.getLocalStorageParent()
		if temp:
			temp[self.plan_name] = storage
		else:
			temp = {self.plan_name : storage}

		db.updateItems(self.user_id, {'user_local_storage' : temp})

	def addLocalStoragePosition(self, order_id):
		local_storage = self.getLocalStorage()


		if not "POSITIONS" in local_storage:
			local_storage["POSITIONS"] = []

		pos_properties = {
			'order_id': order_id,
			'data': {}
		}
		local_storage["POSITIONS"].append(pos_properties)
		self.updateLocalStorage(local_storage)

	def deleteLocalStoragePosition(self, order_id):
		local_storage = self.getLocalStorage()
		if "POSITIONS" in local_storage:
			for p in local_storage["POSITIONS"]:
				if order_id == p["order_id"]:
					del local_storage["POSITIONS"][local_storage["POSITIONS"].index(p)]
					self.updateLocalStorage(local_storage)
					break

	def convertToPips(self, price):
		return price / 0.00001 / 10

	def convertToPrice(self, pips):
		return pips * 0.00001 * 10

	def buy(self, lotsize, pairs = [], ordertype = 'market', entry = 0, sl = 0.0, tp = 0.0, risk=1.0):
		if (ordertype == 'market' or ordertype == 'm'):
			if (len(pairs) <= 0):
				for ticket in self.tickets:
					return self._marketOrder('buy', ticket, ticket.pair, lotsize, sl, tp, risk)
			else:
				for p in pairs:
					try:
						ticket = self.getTicket(p)
						return self._marketOrder('buy', ticket, p, lotsize, sl, tp, risk)
					except:
						print("ERROR: Pair " + p + " not found!")
						return None

		elif (ordertype == 'stopentry' or ordertype == 'se'):
			if (len(pairs) <= 0):
				for ticket in self.tickets:
					return self._stopentryOrder('buy', ticket, ticket.pair, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						ticket = self.getTicket(p)
						return self._stopentryOrder('buy', ticket, p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")
						return None

		elif (ordertype == 'limit' or  ordertype == 'l'):
			if (len(pairs) <= 0):
				for ticket in self.tickets:
					return self._limitOrder('buy', ticket, ticket.pair, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						ticket = self.getTicket(p)
						return self._limitOrder('buy', ticket, p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")
						return None

		else:
			print("ERROR: Buy type not recognised!")

		return None
	
	def sell(self, lotsize, pairs = [], ordertype = 'market', entry = 0, sl = 0.0, tp = 0.0, risk=1.0):
		if (ordertype == 'market' or ordertype == 'm'):
			if (len(pairs) <= 0):
				print(self.tickets)
				for ticket in self.tickets:
					return self._marketOrder('sell', ticket, ticket.pair, lotsize, sl, tp, risk)
			else:
				for p in pairs:
					try:
						ticket = self.getTicket(p)
						return self._marketOrder('sell', ticket, p, lotsize, sl, tp, risk)
					except:
						print("ERROR: Pair " + p + " not found!")
						return None

		elif (ordertype == 'stopentry' or ordertype == 'se'):
			if (len(pairs) <= 0):
				for ticket in self.tickets:
					return self._stopentryOrder('sell', ticket, ticket.pair, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						ticket = self.getTicket(p)
						return self._stopentryOrder('sell', ticket, p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")
						return None

		elif (ordertype == 'limit' or  ordertype == 'l'):
			if (len(pairs) <= 0):
				for ticket in self.tickets:
					return self._limitOrder('sell', ticket, ticket.pair, lotsize, entry, sl, tp)
			else:
				for p in pairs:
					try:
						ticket = self.getTicket(p)
						return self._limitOrder('sell', ticket, p, lotsize, entry, sl, tp)
					except:
						print("ERROR: Pair " + p + " not found!")
						return None

		else:
			print("ERROR: Sell type not recognised!")

		return None

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
		
	def updateEvent(self, event, run_callback_funcs = True):
		if event[2] == 'Buy Trade':
			position_id_list = [i.orderID for i in self.positions] + [j.orderID for j in self.closedPositions]

			if not event[0] in position_id_list:
				print("UTILITIES:", str(event))
				ticket = self.getTicket(event[3])
				pos = self.createPosition(utils = self, ticket = ticket, orderID = event[0], pair = event[3], ordertype = 'market', direction = 'buy')
				pos.openTime = event[1]
				pos.entryprice = float(event[5])
				pos.lotsize = int(event[4])
				pos.sl = float(event[6])
				pos.tp = float(event[7])
				pos.isTrailing = event[9]
				self.positions.append(pos)

				self.addLocalStoragePosition(pos.orderID)
				
			else:
				for pos in self.positions + self.closedPositions:
					if event[0] == pos.orderID:
						break

			if run_callback_funcs:
				try:
					self.plan.onEntry(pos)
				except AttributeError as e:
					pass

				try:
					self.plan.onTrade(pos, event[2])
				except AttributeError as e:
					pass

		elif event[2] == 'Sell Trade':
			position_id_list = [i.orderID for i in self.positions] + [j.orderID for j in self.closedPositions]

			if not event[0] in position_id_list:
				print("UTILITIES:", str(event))
				ticket = self.getTicket(event[3])
				pos = self.createPosition(utils = self, ticket = ticket, orderID = event[0], pair = event[3], ordertype = 'market', direction = 'sell')
				pos.openTime = event[1]
				pos.entryprice = float(event[5])
				pos.lotsize = int(event[4])
				pos.sl = float(event[6])
				pos.tp = float(event[7])
				pos.isTrailing = event[9]
				self.positions.append(pos)

				self.addLocalStoragePosition(pos.orderID)
				
			else:
				for pos in self.positions + self.closedPositions:
					if event[0] == pos.orderID:
						break
			
			if run_callback_funcs:
				try:
					self.plan.onEntry(pos)
				except AttributeError as e:
					pass

				try:
					self.plan.onTrade(pos, event[2])
				except AttributeError as e:
					pass

		elif event[2] == 'Buy SE Order':
			order_id_list = [i.orderID for i in self.orders]

			if not event[0] in order_id_list:
				ticket = self.getTicket(event[3])
				pos = self.createPosition(utils = self, ticket = ticket, orderID = event[0], pair = event[3], ordertype = 'stopentry', direction = 'buy')
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
				ticket = self.getTicket(event[3])
				pos = self.createPosition(utils = self, ticket = ticket, orderID = event[0], pair = event[3], ordertype = 'stopentry', direction = 'sell')
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

					if run_callback_funcs:
						try:
							self.plan.onTrade(pos, event[2])
						except AttributeError as e:
							pass

					self.deleteLocalStoragePosition(pos.orderID)

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

					if run_callback_funcs:
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

						try:
							self.plan.onTrade(pos, event[2])
						except AttributeError as e:
							pass

					self.deleteLocalStoragePosition(pos.orderID)

		elif (event[2] == 'SE Order Sell Trade' or event[2] == 'SE Order Buy Trade' or
			event[2] == 'Limit Order Sell Trade' or event[2] == 'Limit Order Buy Trade'):
			for order in self.orders:
				if event[0] == order.orderID:
					print(str(order.orderID), str(event[2]))

					order.entryprice = float(event[5])
					order.isPending = False

					self.positions.append(order)
					del self.orders[self.orders.index(order)]

					if run_callback_funcs:
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

	def getPosByOrderId(self, order_id):
		for pos in self.positions:
			if pos.orderID == order_id:
				return pos

		return None

	def getAllOpenPositions(self):
		position_id_list = [i.orderID for i in self.positions + self.closedPositions]
		print(position_id_list)

		for order_id in self.positionLog.getCurrentPositions():
			if not order_id in position_id_list:
				print("adding pos:", str(order_id))
				history = self.historyLog.getHistoryByOrderId(order_id)

				for event in history:
					self.updateEvent(event, run_callback_funcs=False)
		print(self.positions)

	@Backtester.market_redirect_backtest
	def _marketOrder(self, direction, ticket, pair, lotsize, sl, tp, risk):
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

		# positionModifyBtn = None

		# wait = ui.WebDriverWait(self.driver, 10)
		# wait.until(lambda driver : self.positionLog.getPositionModifyButton(pos) is not None)

		# positionModifyBtn = self.positionLog.getPositionModifyButton(pos)

		# pos.modifyBtn = positionModifyBtn

		wait = ui.WebDriverWait(self.driver, 10, poll_frequency=0.001)
		wait.until(lambda driver : len(self.historyLog.getHistoryPropertiesById(orderID)[0]) > 0)

		properties = self.historyLog.getHistoryPropertiesById(orderID)[0]

		pos.openTime = properties[1]
		pos.lotsize = int(properties[4])
		pos.sl = float(properties[6])
		pos.tp = float(properties[7])
		pos.entryprice = float(properties[5])
		pos.stoprange = sl
		pos.risk = risk

		self.positions.append(pos)

		self.addLocalStoragePosition(pos.orderID)

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
		ticket = self.getTicket(pair)
		return float(ticket.getBidPrice())

	@Backtester.price_redirect_backtest
	def getAsk(self, pair):
		ticket = self.getTicket(pair)
		return float(ticket.getAskPrice())
	
	def getMissingValues(self, pair, shift, amount):
		print("getMissingValues")
		self.barReader.getBarInfo(pair, shift, amount)

	def backtestByTime(self, startDate, startTime, endDate, endTime):
		parts = startDate.split('/')
		day = parts[0]
		month = parts[1]
		year = parts[2]
		parts = startTime.split(':')
		startTime = self.convertTimeToTimestamp(int(day), int(month), int(year), int(parts[0]), int(parts[1]))

		parts = endDate.split('/')
		day = parts[0]
		month = parts[1]
		year = parts[2]
		parts = endTime.split(':')
		endTime = self.convertTimeToTimestamp(int(day), int(month), int(year), int(parts[0]), int(parts[1]))
		return self.barReader.getBarDataByStartEndTimestamp(startTime, endTime)

	def getCurrentTimestamp(self):
		tz = pytz.timezone('Australia/Melbourne')
		date = datetime.datetime.now(tz = tz)

		then = Constants.DT_START_DATE
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

	@Backtester.new_york_time_redirect_backtest
	def getNewYorkTime(self):
		tz = pytz.timezone('America/New_York')
		return datetime.datetime.now(tz = tz)

	@Backtester.time_redirect_backtest
	def getTime(self, timezone):
		tz = pytz.timezone(timezone)
		return datetime.datetime.now(tz = tz)

	def convertTimezone(self, time, timezone):
		tz = pytz.timezone(timezone)
		return time.astimezone(tz)

	def setTimezone(self, time, timezone):
		tz = pytz.timezone(timezone)
		return tz.localize(time)

	def createAustralianTime(self, year, month, day, hours, mins, seconds):
		tz = pytz.timezone('Australia/Melbourne')
		return tz.localize(datetime.datetime(
					year = year,
					month = month,
					day = day,
					hour = hours,
					minute = mins,
					second = seconds
				))

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

	def createNewYorkTime(self, year, month, day, hours, mins, seconds):
		tz = pytz.timezone('America/New_York')
		return tz.localize(datetime.datetime(
					year = year,
					month = month,
					day = day,
					hour = hours,
					minute = mins,
					second = seconds
				))

	def createTime(self, year, month, day, hours, mins, seconds, timezone):
		tz = pytz.timezone(timezone)
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

		then = Constants.DT_START_DATE
		now = now.astimezone(tz)
		now = now.replace(tzinfo=None)
		return int((now - then).total_seconds())

	def convertTimeToTimestamp(self, day, month, year, hour, minute):
		then = Constants.DT_START_DATE
		now = datetime.datetime(year = year, month = month, day = day, hour = hour, minute = minute, second = 0)

		return int((now - then).total_seconds())

	def convertTimestampToTime(self, timestamp):
		return Constants.DT_START_DATE + datetime.timedelta(seconds = timestamp)

	def convertTimestampToAustralianTime(self, timestamp):
		tz = pytz.timezone('Australia/Melbourne')
		return tz.localize(Constants.DT_START_DATE + datetime.timedelta(seconds = timestamp))

	def setTradeTimes(self, currentTime = None):
		if 'START_TIME' in self.plan.VARIABLES.keys() and 'END_TIME' in self.plan.VARIABLES.keys():

			startTimeParts = self.plan.VARIABLES['START_TIME'].split(':')
			endTimeParts = self.plan.VARIABLES['END_TIME'].split(':')

			if 'TIMEZONE' in self.plan.VARIABLES.keys():
				if not currentTime:
					time = self.getTime(self.plan.VARIABLES['TIMEZONE'])
					currentTime = self.convertTimezone(time, 'Europe/London')
				
				self.startTime = self.createTime(
						currentTime.year,
						currentTime.month,
						currentTime.day,
						int(startTimeParts[0]),
						int(startTimeParts[1]),
						0,
						self.plan.VARIABLES['TIMEZONE']
					)
				self.startTime = self.convertTimezone(self.startTime, 'Europe/London')

				self.endTime = self.createTime(
						currentTime.year,
						currentTime.month,
						currentTime.day,
						int(endTimeParts[0]),
						int(endTimeParts[1]),
						0,
						self.plan.VARIABLES['TIMEZONE']
					)
				self.endTime = self.convertTimezone(self.endTime, 'Europe/London')
			
			else:
				if not currentTime:
					currentTime = self.getLondonTime()

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

				if (self.startTime - datetime.timedelta(days=1) <= currentTime < self.endTime):
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

		if self.startTime and self.endTime:
			if (self.startTime <= currentTime <= self.endTime):
				return True
			else:
				return False

		else:
			return True

	def setWeekendTime(self, time):

		self.open_time = self.convertTimezone(time, 'America/New_York')
		self.open_time = datetime.datetime(
					year = self.open_time.year,
					month = self.open_time.month,
					day = self.open_time.day,
					hour = 17,
					minute = 0,
					second = 0
				)
		self.open_time = self.setTimezone(self.open_time, 'America/New_York')

		while True:
			if self.open_time > time and self.open_time.weekday() == 6:
				break

			self.open_time += datetime.timedelta(days=1)

		self.close_time = self.convertTimezone(time, 'America/New_York')
		self.close_time = datetime.datetime(
					year = self.close_time.year,
					month = self.close_time.month,
					day = self.close_time.day,
					hour = 17,
					minute = 0,
					second = 0
				)
		self.close_time = self.setTimezone(self.close_time, 'America/New_York')

		while True:
			if self.close_time.weekday() == 4 and self.close_time > self.open_time - datetime.timedelta(days=4):
				break
			elif self.close_time.weekday() > 4 and self.close_time > self.open_time - datetime.timedelta(days=4):
				self.close_time -= datetime.timedelta(days=1)
			else:
				self.close_time += datetime.timedelta(days=1)

	def isWeekendTime(self, time):
		if self.close_time < time < self.open_time:
			return True
		else:
			if time > self.open_time:
				self.setWeekendTime(time)
				return self.isWeekendTime(time)
			else:
				return False

	def printTime(self, time):
		print("Time:",str(time.hour)+":"+str(time.minute)+":"+str(time.second), str(time.day)+"/"+str(time.month)+"/"+str(time.year))

	def _prompt(self):
		x = input()

		if x == '':
			pass
		elif x == 'stop':
			if not self.isStopped:
				self.setStopped()
		elif x == 'start':
			if self.isStopped:
				self.setStarted()
		elif x == 'restart':
			if self.isStopped:
				self.restart()
		elif x == 'manual':
			self.setManualChartReading()
		elif x == 'backtest':
			self.backtest()
		elif x == 'vars':
			self.printVars()
		elif x.startswith('change'):
			self.changeVar(x)
		elif x.startswith('add news'):
			self.addNews(x)
		elif x.startswith('bank'):
			self.changeBank(x)
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

	def restart(self):
		print("Restarting")
		self.isLive = False

		self.updatePositions()

		is_updated, missing_timestamps = self.updateValues()

		if (is_updated):
			values = {}
			for key in missing_timestamps:
				pair = key.split('-')[0]
				period = int(key.split('-')[1])
				chart = self.getChart(pair, period)

				chart_values = self.formatForBacktest(chart, self.getEarliestTimestamp(missing_timestamps[key]), missing_timestamps[key])
				values[key] = chart_values

			self.backtester.recover(values)

		self.updateRecovery()
		self.isStopped = False

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
	
	def changeBank(self, cmd):
		parts = cmd.split(' ')
		if len(parts) == 1:
			print('External: {0:.2f}\nMaximum: {1:.2f}'.format(self.external_bank, self.maximum_bank))
		else:
			for p in parts:
				if p.startswith('-'):
					cmd = p.strip('-')
					if cmd == 'external' or cmd == 'e':
						try:
							self.updateBank(external_bank=float(parts[parts.index(p)+1]))
						except:
							print('Error: Illegal parameter for external bank.')
					if cmd == 'maximum' or cmd == 'm':
						try:
							self.updateBank(maximum_bank=float(parts[parts.index(p)+1]))
						except:
							print('Error: Illegal parameter for maximum bank.')

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

	def getTotalProfitPercent(self):
		totalProfit = 0
		for pos in self.closedPositions:
			totalProfit += pos.getPercentageProfit()

		return round(totalProfit, 2)

	def getEarliestTimestamp(self, timestamps):
		timestamps.sort()
		return timestamps[0]

	def getLatestTimestamp(self, timestamps):
		timestamps.sort(reverse = True)
		return timestamps[0]

	def getCurrentLatestTimestamp(self):
		return [i[0] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=False)][0]

	def getBarOffset(self, timestamp):
		currentTime = self.getCurrentTimestamp()
		return int((currentTime - timestamp) / 60)

	def getTimestampFromOffset(self, pair, shift, amount):
		if pair in self.latestTimestamp:
			currentTime = self.latestTimestamp[pair]
		else:
			currentTime = self.getCurrentTimestamp()
		return currentTime - (shift + amount + 1) * 60

	def updateValues(self):
		return self.barReader.updateAllBarData()

	def reinitCharts(self):
		for chart in self.charts:
			chart.reinit(self.driver)

	def reinitTickets(self):
		self.tickets = []
		for chart in self.charts:
			pair = chart.pair
			self.getTicket(pair)

	def reinitAUDUSDTicket(self):
		self.tAUDUSD = self.createTicket(Constants.AUDUSD)

	def setPositionNetting(self, x):
		Position.position_netting = x

	def isChartAvailable(self, chart_id):
		availability_checker = self.driver.find_element(By.XPATH, "//div[@id='"+str(chart_id)+"']//div[contains(@class, 'popup-container')]")

		checker_class = availability_checker.get_attribute("class")

		return 'active' in str(checker_class)

	def getLowestPeriodChart(self):
		lowest_chart = None
		for chart in self.charts:
			if lowest_chart:
				if chart.timestamp_offset < lowest_chart.timestamp_offset:
					lowest_chart = chart
			else:
				lowest_chart = chart

		return lowest_chart

	def chartTimestampCheck(self, pair):
		try:
			is_open = self.driver.execute_script(
					'if (arguments[0].hasAttribute("style"))'
					'{'
					'    return true;'
					'}'
					'else'
					'{'
					'    return false;'
					'}',
					self.barReader.canvasDict[pair]
				)

			return is_open
		except:
			return False

	def backtest(self):
		self.is_backtest = True
		self.setStopped()
		print("Starting Backtest")
		sys.exit()

	def formatForBacktest(self, chart, start_timestamp, timestamps):

		offset = 0
		for i in range(len(timestamps)):
			if timestamps[i] >= start_timestamp:
				offset = i
				break

		min_period = self.getMinPeriod(chart)

		values = {'ohlc': {}, 'overlays': [], 'studies': []}

		for timestamp in timestamps[offset:]:
			if timestamp in chart.ohlc:
				values['ohlc'][timestamp] = chart.ohlc[timestamp]
			else:
				del timestamps[timestamps.index(timestamp)]

		ohlc = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0])]
		ohlc_timestamps = [i[0] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0])]

		count = 0
		for overlay in chart.overlays:
			values['overlays'].append({})

			for timestamp in timestamps[offset:]:
				if timestamp in ohlc_timestamps and ohlc_timestamps.index(timestamp) + 1 > min_period:
					temp_ohlc = [
						[i[0] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1],
						[i[1] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1],
						[i[2] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1],
						[i[3] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1]
					]

					values['overlays'][count][timestamp] = overlay.getValue(temp_ohlc)

			count += 1

		count = 0
		for study in chart.studies:
			values['studies'].append({})
			
			for timestamp in timestamps[offset:]:
				if timestamp in ohlc_timestamps and ohlc_timestamps.index(timestamp) + 1 > min_period:
					temp_ohlc = [
						[i[0] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1],
						[i[1] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1],
						[i[2] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1],
						[i[3] for i in ohlc][:ohlc_timestamps.index(timestamp) + 1]
					]

					values['studies'][count][timestamp] = study.getValue(temp_ohlc)

			count += 1

		return values

	def updateRecovery(self):
		print("UPDATE RECOVERY")

		for chart in self.charts:

			min_period = self.getMinPeriod(chart)
			earliest_ts = chart.getTimestampFromDataPoint(min_period)

			then = self.getStorageDay(earliest_ts, chart.period, periods_ago=1)
			then = self.convertDateTimeToTimestamp(then)

			until = chart.getCurrentTimestamp()

			last_ts = self.getLastSavedTimestamp(then, until, chart)

			# ts = self.adjustTimestamp(chart, earliest_ts, last_ts)

			if last_ts and last_ts != 0 and last_ts > earliest_ts:
				ts = last_ts
			else:
				ts = earliest_ts


			self.barReader.getMissingBarDataByTimestamp(chart, ts)
			sorted_timestamps = [i[0] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0]) if i[0] > ts]

			write_vals = {}
			
			for t in sorted_timestamps:

				storage_day = self.getStorageDay(int(t), chart.period)
				date = str(storage_day.day)+'-'+str(storage_day.month)+'-'+str(storage_day.year)
				if date in write_vals:
					write_vals[date][t] = chart.ohlc[t]
				else:
					write_vals[date] = {t: chart.ohlc[t]}
					
			for date in write_vals:
				if os.path.exists('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+date+'.json'):
					with open('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+date+'.json', 'r') as f:
						data = json.load(f)
					
					with open('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+date+'.json', 'w') as f:
						json.dump({**data, **write_vals[date]}, f)
				else:
					with open('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+date+'.json', 'w') as f:
						json.dump(write_vals[date], f)

		self.updated = True

	def getRecovery(self):
		print("GET RECOVERY")
		
		values = {}
		new_values = {}

		current_time = self.getAustralianTime()

		for chart in self.charts:

			min_period = self.getMinPeriod(chart)
			print("MIN PERIOD:", str(min_period))
			earliest_ts = chart.getTimestampFromDataPoint(min_period)

			then = self.getStorageDay(earliest_ts, chart.period, periods_ago=1)
			until = self.getStorageDay(chart.getCurrentTimestamp(), chart.period)

			all_timestamps = []

			while then <= until:

				if os.path.exists('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+str(then.day)+'-'+str(then.month)+'-'+str(then.year)+'.json'):
					with open('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+str(then.day)+'-'+str(then.month)+'-'+str(then.year)+'.json', 'r') as f:
						values = json.load(f)
				else:

					then = self.getStorageDay(self.convertDateTimeToTimestamp(then), chart.period, periods_ago=-1)
					continue

				
				values = {int(k):v for k,v in values.items()}

				sorted_timestamps = [i[0] for i in sorted(values.items(), key=lambda kv: kv[0])]
				# print(str(sorted_timestamps[0]), ",", str(sorted_timestamps[-1]))
				
				sorted_ohlc = [[],[],[],[]]
				for i in [i[1] for i in sorted(values.items(), key=lambda kv: kv[0])]:
					sorted_ohlc[0].append(i[0])
					sorted_ohlc[1].append(i[1])
					sorted_ohlc[2].append(i[2])
					sorted_ohlc[3].append(i[3])

				all_timestamps += sorted_timestamps
				print("all_timestamps:", str(all_timestamps[-1]))

				chart.ohlc = {**chart.ohlc, **values}

				index = 0
				for i in sorted_timestamps:

					if index > min_period:
						for overlay in chart.overlays:
							overlay.insertValues(i, [
									sorted_ohlc[0][:index],
									sorted_ohlc[1][:index],
									sorted_ohlc[2][:index],
									sorted_ohlc[3][:index]
								])
						for study in chart.studies:
							study.insertValues(i, [
									sorted_ohlc[0][:index],
									sorted_ohlc[1][:index],
									sorted_ohlc[2][:index],
									sorted_ohlc[3][:index]
								])

					index += 1
				
				then = self.getStorageDay(self.convertDateTimeToTimestamp(then), chart.period, periods_ago=-1)

			if chart.getTimestampFromDataPoint(min_period) > self.getEarliestTimestamp(all_timestamps):
				earliest_timestamp = chart.getTimestampFromDataPoint(min_period)
			else:
				earliest_timestamp = self.getEarliestTimestamp(all_timestamps)
			print("get missing:", earliest_timestamp)
			missing_timestamps = self.barReader.getMissingBarDataByTimestamp(chart, earliest_timestamp)
			all_timestamps += missing_timestamps
			all_timestamps.sort()
			chart_values = self.formatForBacktest(chart, all_timestamps[min_period], all_timestamps)
			new_values[str(chart.pair) + '-' + str(chart.period)] = chart_values

		print(new_values.keys())
		self.backtester.recover(new_values)

	def adjustTimestamp(self, chart, x, y):
		p = chart.getTimestampOffset()
		multi = math.ceil(x/p) - math.floor(y/p)
		diff = y + (p * multi) - x

		return y - diff

	def getMinPeriod(self, chart):
		return max([i.min_period for i in chart.overlays + chart.studies])

	def getStorageDay(self, timestamp, period, periods_ago=0):
		time = self.convertTimestampToTime(timestamp)

		if Constants.STORAGE_DAY(period):
			time -= datetime.timedelta(seconds=Constants.STORAGE_DAY_SECONDS * periods_ago)

			time = datetime.datetime(year=time.year, month=time.month, day=time.day, hour=0, minute=0, second=0)
			time = self.setTimezone(time, 'Australia/Melbourne')

			delta = -Constants.STORAGE_DAY_SECONDS if periods_ago < 0 else Constants.STORAGE_DAY_SECONDS

			self.setWeekendTime(time)
			while self.isWeekendTime(time) and not time.weekday() == 0:
				time -= datetime.timedelta(seconds=delta)

			return datetime.datetime(year=time.year, month=time.month, day=time.day, hour=0, minute=0, second=0)

		if Constants.STORAGE_WEEK(period):
			time -= datetime.timedelta(seconds=Constants.STORAGE_WEEK_SECONDS * periods_ago)
			while time.weekday() != 0:
				time -= datetime.timedelta(days=1)
			return datetime.datetime(year=time.year, month=time.month, day=time.day, hour=0, minute=0, second=0)

		if Constants.STORAGE_MONTH(period):
			time -= datetime.timedelta(seconds=Constants.STORAGE_MONTH_SECONDS * periods_ago)
			return datetime.datetime(year=time.year, month=time.month, day=1, hour=0, minute=0, second=0)

		if Constants.STORAGE_YEAR(period):
			time -= datetime.timedelta(seconds=Constants.STORAGE_YEAR_SECONDS * periods_ago)
			return datetime.datetime(year=time.year, month=1, day=1, hour=0, minute=0, second=0)

	def getLastSavedTimestamp(self, then, until, chart):

		then = self.getStorageDay(then, chart.period)
		until = self.getStorageDay(until, chart.period)

		if Constants.STORAGE_DAY(chart.period):
			period_offset = Constants.STORAGE_DAY_SECONDS

		if Constants.STORAGE_WEEK(chart.period):
			period_offset = Constants.STORAGE_WEEK_SECONDS

		if Constants.STORAGE_MONTH(chart.period):
			period_offset = Constants.STORAGE_MONTH_SECONDS

		if Constants.STORAGE_YEAR(chart.period):
			period_offset = Constants.STORAGE_YEAR_SECONDS

		last_ts = 0
		while then <= until:
			f_name = 'recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+str(then.day)+'-'+str(then.month)+'-'+str(then.year)+'.json'

			if os.path.exists(f_name):
				with open(f_name, 'r') as f:
					data = json.load(f)
					latest = int([i[0] for i in sorted(data.items(), key=lambda kv: kv[0], reverse=True)][0])
					if latest > last_ts:
						last_ts = latest
			
			then += datetime.timedelta(seconds=period_offset)
			
		return None if last_ts == 0 else last_ts

	def createPosition(self, utils, ticket, orderID, pair, ordertype, direction):
		return Position(utils, ticket, orderID, pair, ordertype, direction)