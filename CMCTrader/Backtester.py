from enum import Enum
import pytz
import os
import json
import traceback
import datetime
import time as t

from CMCTrader import Constants

class State(Enum):
	NONE = 1
	RECOVER = 2
	BACKTEST = 3

class ActionType(Enum):
	CLOSE = 0
	ENTER = 1
	STOP_AND_REVERSE = 2
	MODIFY_POS_SIZE = 3
	MODIFY_TRAILING = 4
	MODIFY_SL = 5
	MODIFY_TP = 6
	REMOVE_SL = 7
	REMOVE_TP = 8
	BREAKEVEN = 9
	APPLY = 10
	CANCEL = 11
	MODIFY_ENTRY_PRICE = 12

class Action(object):
	def __init__(self, position, action, timestamp, args = None, kwargs = None):
		self.position = position
		self.action = action
		print("ARGS:", str(args))
		self.args = args[1:]
		self.kwargs = kwargs
		self.timestamp = timestamp

class Backtester(object):

	def __init__(self, utils, plan):
		global state, current_timestamp, pair, sorted_timestamps

		state = State.NONE
		current_timestamp = 0
		pair = None
		sorted_timestamps = []

		self.utils = utils
		self.plan = plan

		self.down_time = True
		self.has_run = False

		self.actions = []
		
	def runOnce(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if not self.has_run:
				self.has_run = True
				return func(*args, **kwargs)
		return wrapper

	def redirect_backtest( func):
		def wrapper(*args, **kwargs):
			if (not state == State.NONE):
				return
			else:
				return func(*args, **kwargs)
		return wrapper

	def bool_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			if (not state == State.NONE):
				return True
			else:
				return func(*args, **kwargs)
		return wrapper

	def dict_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			if (not state == State.NONE):
				return {}
			else:
				return func(*args, **kwargs)
		return wrapper

	def market_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (state == State.BACKTEST):
				chart = self.getLowestPeriodChart()
				close = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][3]

				pos = self.createPosition(self, args[2], 0, args[3], 'market', args[1])
				pos.lotsize = args[4]

				if (args[1] == 'buy'):
					pos.sl = close - self.convertToPrice(args[5])
					pos.tp = close + self.convertToPrice(args[6])
					event = 'Buy Trade'
				else:
					pos.sl = close + self.convertToPrice(args[5])
					pos.tp = close - self.convertToPrice(args[6])
					event = 'Sell Trade'
				
				pos.entryprice = close

				print(str(pos.direction), str(pos.entryprice), str(pos.sl), str(pos.tp))

				self.positions.append(pos)

				try:
					self.plan.onEntry(pos)
				except AttributeError as e:
					pass

				try:
					self.plan.onTrade(pos, event)
				except AttributeError as e:
					pass

				return pos
			elif (state == State.RECOVER):
				latest_history_timestamp = self.historyLog.getLatestHistoryTimestamp()

				pos = self.createPosition(self, args[2], 0, args[3], 'market', args[1])
				
				chart = self.getLowestPeriodChart()
				close = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][3]

				pos.entryprice = chart.ohlc[current_timestamp][3]
				pos.openTime = current_timestamp
				pos.isTemp = True
				self.backtester.actions.append(Action(pos, ActionType.ENTER, current_timestamp, args = args, kwargs = kwargs))
				self.positions.append(pos)

				if (args[1] == 'buy'):
					pos.sl = close - self.convertToPrice(args[5])
					pos.tp = close + self.convertToPrice(args[6])
					event = 'Buy Trade'
				else:
					pos.sl = close + self.convertToPrice(args[5])
					pos.tp = close - self.convertToPrice(args[6])
					event = 'Sell Trade'

				try:
					self.plan.onEntry(pos)
				except AttributeError as e:
					pass

				try:
					self.plan.onTrade(pos, event)
				except AttributeError as e:
					pass

				return pos

			else:
				return func(*args, **kwargs)
		return wrapper

	def price_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE and not self.isLive):
				chart = self.getLowestPeriodChart()
				return [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][3]
			else:
				return func(*args, **kwargs)
		return wrapper

	def time_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE):
				return self.backtester.getTime(current_timestamp, args[1])
			else:
				return func(*args, **kwargs)
		return wrapper

	def new_york_time_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE):
				return self.backtester.getNewYorkTime(current_timestamp)
			else:
				return func(*args, **kwargs)
		return wrapper

	def london_time_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE):
				return self.backtester.getLondonTime(current_timestamp)
			else:
				return func(*args, **kwargs)
		return wrapper

	def australian_time_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE):
				return self.backtester.getAustralianTime(current_timestamp)
			else:
				return func(*args, **kwargs)
		return wrapper

	def skip_on_backtest(func):
		def wrapper(*args, **kwargs):
			if (not state == State.NONE):
				return
			else:
				return func(*args, **kwargs)
		return wrapper

	def skip_on_recover(func):
		def wrapper(*args, **kwargs):
			if (state == State.RECOVER):
				return
			else:
				return func(*args, **kwargs)
		return wrapper

	def runBacktest(self):

		''' Get Times '''
		conf = ""
		while not conf.lower() == "y":
			startDate = input("Start Date: ")
			startTime = input("Start Time: ")
			conf = input("(Y/n): ")

		conf = ""
		while not conf.lower() == "y":
			endDate = input("End Date: ")
			endTime = input("End Time: ")
			conf = input("(Y/n): ")

		parts = startDate.split('/')
		day = parts[0]
		month = parts[1]
		parts = startTime.split(':')
		startTime = self.utils.convertTimeToTimestamp(int(day), int(month), int(parts[0]), int(parts[1]))

		parts = endDate.split('/')
		day = parts[0]
		month = parts[1]
		parts = endTime.split(':')
		endTime = self.utils.convertTimeToTimestamp(int(day), int(month), int(parts[0]), int(parts[1]))

		start_time = self.utils.convertTimestampToTime(startTime)
		end_time = self.utils.convertTimestampToTime(endTime)

		''' Perform data collection '''
		values = {}
		backtest_values = {}
		for chart in self.utils.charts:
			dt = start_time
			while dt < end_time:
				if (os.path.exists('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+str(dt.day)+'-'+str(dt.month)+'-'+str(dt.year)+'.json')):
					with open('recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+str(dt.day)+'-'+str(dt.month)+'-'+str(dt.year)+'.json', 'r') as f:
						values = json.load(f)
						chart.ohlc = {**chart.ohlc, **values}
				else:
					print("WARNING:", str(chart.pair)+'-'+str(chart.period)+'_'+str(dt.day)+'-'+str(dt.month)+'-'+str(dt.year), +"file was not found.")

				if Constants.STORAGE_DAY(chart.period):
					dt += datetime.timedelta(seconds=Constants.STORAGE_DAY_SECONDS)

				elif Constants.STORAGE_WEEK(chart.period):
					dt += datetime.timedelta(seconds=Constants.STORAGE_WEEK_SECONDS)

				elif Constants.STORAGE_MONTH(chart.period):
					dt += datetime.timedelta(seconds=Constants.STORAGE_MONTH_SECONDS)

				elif Constants.STORAGE_YEAR(chart.period):
					dt += datetime.timedelta(seconds=Constants.STORAGE_YEAR_SECONDS)

			chart.ohlc = {int(k):v for k,v in chart.ohlc.items()}

			chart_timestamps = [i[0] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0])]

			sorted_ohlc = [[],[],[],[]]
			for i in [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0])]:
				sorted_ohlc[0].append(i[0])
				sorted_ohlc[1].append(i[1])
				sorted_ohlc[2].append(i[2])
				sorted_ohlc[3].append(i[3])

			index = 0
			for i in chart_timestamps:

				if index > 80:
					for overlay in chart.overlays:
						overlay.insertValues(i, sorted_ohlc[:index])
					for study in chart.studies:
						study.insertValues(i, sorted_ohlc[:index])

				index += 1

			key = chart.pair + '-' + str(chart.period)
			backtest_values[key] = self.utils.formatForBacktest(chart, self.utils.convertDateTimeToTimestamp(start_time), chart_timestamps)

		name = self.utils.plan_name
		print(backtest_values)
		self.backtest(backtest_values)

	def manual(self):

		def runBacktest(filename):
			name = self.utils.plan_name

			if (os.path.exists(filename + '.json')):
				with open(filename + '.json', 'r') as f:
					values = json.load(f)

				for key in values:

					values[key]['ohlc'] = {int(k):v for k,v in values[key]['ohlc'].items()}

					for i in range(len(values[key]['overlays'])):
						values[key]['overlays'][i] = {int(k):v for k,v in values[key]['overlays'][i].items()}

					for j in range(len(values[key]['studies'])):
						values[key]['studies'][j] = {int(k):v for k,v in values[key]['studies'][j].items()}

				self.backtest(values)

			return

		result = input("Enter filename (Press enter for manual): ")

		if (not result.strip() == "" and os.path.exists(result.strip()+'.json')):
			runBacktest(result.strip())
			return

		conf = ""
		while not conf.lower() == "y":
			startDate = input("Start Date: ")
			startTime = input("Start Time: ")
			conf = input("(Y/n): ")

		conf = ""
		while not conf.lower() == "y":
			endDate = input("End Date: ")
			endTime = input("End Time: ")
			conf = input("(Y/n): ")

		timestamps = self.utils.backtestByTime(startDate.strip(), startTime.strip(), endDate.strip(), endTime.strip())

		parts = startDate.strip().split('/')
		day = parts[0]
		month = parts[1]
		parts = startTime.strip().split(':')
		startTime = self.utils.convertTimeToTimestamp(int(day), int(month), int(parts[0]), int(parts[1]))

		values = {}
		for key in timestamps:
			chart_timestamps = timestamps[key]

			pair = key.split('-')[0]
			period = int(key.split('-')[1])
			chart = self.utils.getChart(pair, period)

			chart_values = self.utils.formatForBacktest(chart, startTime, chart_timestamps, chart.ohlc)

			values[key] = chart_values

		filename = "bt" + str(self.utils.plan_name) + "_" + str('-'.join(startDate.split('/')))

		with open(filename+'.json', 'w') as f:
			json.dump(values, f)

		runBacktest(filename)

 
	def backtest(self, values):
		global state, pair, current_timestamp, sorted_timestamps
		state = State.BACKTEST

		start_time = t.time()

		# position_logs = None

		chart = self.utils.getLowestPeriodChart()

		pair = chart.pair
		period = chart.period
		key = '-'.join([pair, str(period)])

		sorted_timestamps = [i[0] for i in sorted(values[key]['ohlc'].items(), key=lambda kv: kv[0], reverse=False)]

		self.removeTimestampsUntil(chart, sorted_timestamps[0])

		for timestamp in sorted_timestamps:
			current_timestamp = timestamp

			self.insertValuesByTimestamp(timestamp, chart, values[key]['ohlc'], values[key]['overlays'], values[key]['studies'])

			time = self.getLondonTime(timestamp)

			if self.down_time:
				self.utils.setTradeTimes(currentTime = time)

			self.checkStopLoss()
			self.checkTakeProfit()

			if (timestamp > self.utils.convertDateTimeToTimestamp(self.utils.endTime - datetime.timedelta(days=1))):
				self.runMainLoop(time)

			input("Press enter to continue...")

		print(t.time() - start_time)

		state = State.NONE

	def recover(self, values):
		global state, pair, current_timestamp, sorted_timestamps
		state = State.RECOVER
		self.has_run = False

		print("start recovery")

		self.actions = []
		self.history = []

		position_logs = None

		# self.utils.positions = []
		# self.utils.closedPositions = []
		# self.resetBarValues()

		chart = self.utils.getLowestPeriodChart()

		pair = chart.pair
		period = chart.period
		key = '-'.join([pair, str(period)])

		sorted_timestamps = [i[0] for i in sorted(values['ohlc'].items(), key=lambda kv: kv[0], reverse=False)]

		self.removeTimestampsUntil(chart, sorted_timestamps[0])

		real_time = self.utils.getLondonTime()

		# if self.down_time:
		# 	self.utils.setTradeTimes(currentTime = real_time)
			
		for timestamp in sorted_timestamps:

			# if (timestamp > self.utils.convertDateTimeToTimestamp(self.utils.endTime - datetime.timedelta(days=1))):
				
			current_timestamp = timestamp

			self.insertValuesByTimestamp(timestamp, chart, values['ohlc'], values['overlays'], values['studies'])
			
			time = self.getLondonTime(timestamp)

			self.checkStopLoss()
			self.checkTakeProfit()
			
			self.runMainLoop(time)

		state = State.NONE

		print("POSITIONS:", str(self.utils.positions))
		print("CLOSED POSITIONS:", str(self.utils.closedPositions))

		if self.utils.isLive:
			self.resetTempPositions()

			position_logs = self.getPositionLogs()

			for log in position_logs:
				print("LOG:", str(log)) 
				self.history.append(log)
				self.utils.updateEvent(log, run_callback_funcs = False)

				print("posees")
				print(self.utils.positions)
				print(self.utils.closedPositions)

			self.updatePositions()
		else:
			for order_id in self.utils.positionLog.getCurrentPositions():
				history = self.utils.historyLog.getHistoryByOrderId(order_id)

				for event in history:
					self.utils.updateEvent(event, run_callback_funcs=False)
				
				new_pos = None
				for pos in self.utils.positions:
					if pos.orderID == order_id:
						new_pos = pos

				pos_found = False
				if new_pos and new_pos.openTime >= self.utils.convertDateTimeToTimestamp(self.utils.startTime):
					for pos in self.utils.positions:
						if pos.direction == new_pos.direction and pos.isTemp:
							print("pos found")
							pos_found = True
							del self.utils.positions[self.utils.positions.index(pos)]
					
					if not pos_found:
						print("pos not found")
						new_pos.close()

			for pos in self.utils.positions + self.utils.closedPositions:
				if pos.isTemp:
					pos.isTemp = False
					pos.isDummy = True

		print("POSITIONS:", str(self.utils.positions))
		print("CLOSED POSITIONS:", str(self.utils.closedPositions))

	def getAustralianTime(self, timestamp):
		time = self.utils.convertTimestampToTime(timestamp)
		tz = pytz.timezone('Australia/Melbourne')

		return tz.localize(time)

	def getLondonTime(self, timestamp):
		time = self.getAustralianTime(timestamp)
		tz = pytz.timezone('Europe/London')
		
		return time.astimezone(tz)

	def getNewYorkTime(self, timestamp):
		time = self.getAustralianTime(timestamp)
		tz = pytz.timezone('America/New_York')
		
		return time.astimezone(tz)

	def getTime(self, timestamp, timezone):
		time = self.getAustralianTime(timestamp)
		tz = pytz.timezone(timezone)
		
		return time.astimezone(tz)

	def runMainLoop(self, time):

		if (self.utils.isTradeTime(currentTime = time) or len(self.utils.positions) > 0):
			
			if (self.down_time):
				try:
					self.utils.is_downtime = False
					self.plan.onStartTrading()
				except AttributeError as e:
					print(str(e), "continuing...")
					pass
				except Exception as e:
					print(str(e), "continuing...")
					return

				self.down_time = False

			try:
				self.plan.onLoop()
			except AttributeError as e:
				# print(str(e), "continuing...")
				print(traceback.format_exc())
				pass
			except Exception as e:
				print(traceback.format_exc())
				# print(str(e), "continuing...")
				return

			try:
				self.plan.onNewBar()
			except AttributeError as e:
				print(str(e), "continuing...")
				print(traceback.format_exc())
				pass
			except Exception as e:
				print(traceback.format_exc())
				# print(str(e), "continuing...")
				return

			try:
				for key in self.utils.newsTimes.copy():
					self.plan.onNews(key, self.utils.newsTimes[key])
			except AttributeError as e:
				print(str(e), "continuing...")
				pass
			except Exception as e:
				print(str(e), "continuing...")
				return
		else:
			if (not self.down_time):

				try:
					self.plan.onFinishTrading()
				except AttributeError as e:
					print(str(e), "continuing...")
					pass
				except Exception as e:
					print(str(e), "continuing...")
					return

				if (len(self.utils.closedPositions) > 0):
					self.utils.closedPositions = []

				self.down_time = True

			try:
				self.plan.onDownTime()
			except AttributeError as e:
				print(str(e), "continuing...")
				pass
			except Exception as e:
				print(str(e), "continuing...")
				return

	def resetTempPositions(self):
		to_delete = []

		for pos in self.utils.positions:
			if pos.isTemp:
				to_delete.append(self.utils.positions.index(pos))
		for i in sorted(to_delete, reverse=True):
			del self.utils.positions[i]

		to_delete = []

		for cpos in self.utils.closedPositions:
			if cpos.isTemp:
				to_delete.append(self.utils.closedPositions.index(cpos))	
		for i in sorted(to_delete, reverse=True):
			del self.utils.closedPositions[i]

		to_delete = []

		for order in self.utils.orders:
			if order.isTemp:
				to_delete.append(self.utils.orders.index(order))
		for i in sorted(to_delete, reverse=True):
			del self.utils.orders[i]

	def resetBarValues(self):
		self.utils.ohlc = self.utils._initOHLC()
		
		for overlay in self.utils.indicators['overlays']:
			overlay.history = overlay.initHistory(self.utils.tickets)
		for study in self.utils.indicators['studies']:
			study.history = study.initHistory(self.utils.tickets)

	def removeTimestampsUntil(self, chart, until):
		reverse_sorted_timestamps = [i[0] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)]

		for timestamp in reverse_sorted_timestamps:

			if timestamp >= until:
				if timestamp in chart.ohlc:
					del chart.ohlc[timestamp]
				
				for overlay in chart.overlays:
					if timestamp in overlay.history:
						del overlay.history[timestamp]
				for study in chart.studies:
					if timestamp in study.history:
						del study.history[timestamp]
			else:
				break

	def insertValuesByTimestamp(self, timestamp, chart, ohlc, overlays, studies):
		chart.ohlc[timestamp] = ohlc[timestamp]

		print(len(overlays))
		for i in range(len(overlays)):

			history = chart.overlays[i].history
			indicator = overlays[i]

			if timestamp in indicator:
				history[timestamp] = indicator[timestamp]
			else:
				earliest_timestamp = [i[0] for i in sorted(indicator.items(), key=lambda kv:kv[0])][0]
				current_timestamp = timestamp - chart.timestamp_offset
				while current_timestamp >= earliest_timestamp:
					if current_timestamp in indicator:
						history[timestamp] = indicator[current_timestamp]
						break
					current_timestamp -= chart.timestamp_offset

				if current_timestamp < earliest_timestamp:
					continue

		for j in range(len(studies)):

			history = chart.studies[j].history
			indicator = studies[j]
			
			if timestamp in indicator:
				history[timestamp] = indicator[timestamp]
			else:
				earliest_timestamp = [i[0] for i in sorted(indicator.items(), key=lambda kv:kv[0])][0]
				current_timestamp = timestamp - chart.timestamp_offset
				while current_timestamp >= earliest_timestamp:
					if current_timestamp in indicator:
						history[timestamp] = indicator[current_timestamp]
						break
					current_timestamp -= chart.timestamp_offset

				if current_timestamp < earliest_timestamp:
					continue

	def getPositionLogs(self):
		print("getPositionLogs")

		listenedTypes = [
				'Buy Trade', 'Sell Trade',
				'Buy SE Order', 'Sell SE Order',
				'Take Profit', 'Stop Loss', 
				'Close Trade', 'Order Cancelled',
				'SE Order Sell Trade', 'SE Order Buy Trade', 'Limit Order Buy Trade', 'Limit Order Sell Trade',
				'Buy Trade Modified', 'Sell Trade Modified',
				'Buy SE Order Modified', 'Sell SE Order Modified',
				'Stop Loss Modified', 'Take Profit Modified'
			]

		return self.utils.historyLog.updateHistory(listenedTypes)

	def updatePositions(self):
		latest_history_timestamp = self.utils.historyLog.getLatestHistoryTimestamp()

		print("posees")
		print(self.utils.positions)
		print(self.utils.closedPositions)


		print("latest:", str(latest_history_timestamp))

		# for pos in self.utils.positions:
		# 	if pos.isTemp:
		# 		del self.utils.positions[self.utils.positions.index(pos)]

		updates = [i for i in self.actions if i.timestamp > latest_history_timestamp]

		new_index = 0

		for i in range(len(updates)):
			if (
				updates[i].action == ActionType.CLOSE
				or updates[i].action == ActionType.STOP_AND_REVERSE
				or updates[i].action == ActionType.ENTER # MIMIC POSITION APPENDING AND CLOSED POSITION APPENDING INSTEAD.. NEED TO REPLACE PLACEHOLDER POSITIONS ALSO
				):
				new_index = i

		updates = updates[new_index:]

		for update in updates:
			if len(self.utils.positions) > 0:
				current_pos = self.utils.positions[0]
			else:
				current_pos = None

			if update.action == ActionType.ENTER:
				self.utils._marketOrder(*update.args, **update.kwargs)
			elif update.action == ActionType.STOP_AND_REVERSE:
				if not current_pos == None:
					if update.position.direction == current_pos.direction:
						current_pos.stopAndReverse(*update.args, **update.kwargs)
				else:
					if update.position.direction == 'buy':
						self.utils.buy(update.args[1], sl = args[2], tp = args[3])
					elif update.position.direction == 'sell':
						self.utils.sell(update.args[1], sl = args[2], tp = args[3])
			
			elif not current_pos == None:
				if update.action == ActionType.CLOSE:
					if update.position.direction == current_pos.direction:
						current_pos.close()
					
				elif update.action == ActionType.MODIFY_POS_SIZE:
					if update.position.direction == current_pos.direction:
						current_pos.modifyPositionSize(*update.args, **update.kwargs)

				elif update.action == ActionType.MODIFY_TRAILING:
					if update.position.direction == current_pos.direction:
						current_pos.modifyTrailing(*update.args, **update.kwargs)

				elif update.action == ActionType.MODIFY_SL:
					if update.position.direction == current_pos.direction:
						current_pos.modifySL(*update.args, **update.kwargs)

				elif update.action == ActionType.MODIFY_TP:
					if update.position.direction == current_pos.direction:
						current_pos.modifyTP(*update.args, **update.kwargs)

				elif update.action == ActionType.REMOVE_SL:
					if update.position.direction == current_pos.direction:
						current_pos.removeSL()

				elif update.action == ActionType.REMOVE_TP:
					if update.position.direction == current_pos.direction:
						current_pos.removeTP()

				elif update.action == ActionType.BREAKEVEN:
					if update.position.direction == current_pos.direction:
						current_pos.breakeven()
				elif update.action == ActionType.APPLY:
					if update.position.direction ==current_pos.direction:
						current_pos.apply()

				elif update.action == ActionType.CANCEL:
					pass
				elif update.action == ActionType.MODIFY_ENTRY_PRICE:
					pass

	def checkStopLoss(self):

		chart = self.utils.getLowestPeriodChart()

		high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][1]
		low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][2]

		for pos in self.utils.positions:
			if not pos.sl == 0:
				if pos.direction == 'buy':
					if low <= pos.sl:
						pos.closeprice = pos.sl
						pos.close()
						try:
							self.utils.plan.onStopLoss(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Stop Loss')
						except AttributeError as e:
							pass
				else:
					if high >= pos.sl:
						pos.closeprice = pos.sl
						pos.close()
						try:
							self.utils.plan.onStopLoss(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Stop Loss')
						except AttributeError as e:
							pass

	def checkTakeProfit(self):

		chart = self.utils.getLowestPeriodChart()

		high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][1]
		low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][2]

		for pos in self.utils.positions:
			if not pos.tp == 0:
				if pos.direction == 'buy':
					if high >= pos.tp:
						pos.closeprice = pos.tp
						pos.close()
						try:
							self.utils.plan.onTakeProfit(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Take Profit')
						except AttributeError as e:
							pass
				else:
					if low <= pos.tp:
						pos.closeprice = pos.tp
						pos.close()
						try:
							self.utils.plan.onTakeProfit(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Take Profit')
						except AttributeError as e:
							pass

	def isNotBacktesting(self):
		return state == State.NONE

	def isBacktesting(self):
		return state == State.BACKTEST

	def isRecover(self):
		return state == State.RECOVER