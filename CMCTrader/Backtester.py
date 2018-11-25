from enum import Enum
import pytz
import os
import json
import traceback

class State(Enum):
	NONE = 1
	RECOVER = 2
	BACKTEST = 3

state = State.NONE
current_timestamp = 0
pair = None


class Backtester(object):

	def __init__(self, utils, plan):
		self.utils = utils
		self.plan = plan

		self.down_time = True
		
	def runOnce(func):
		def wrapper(*args, **kwargs):
			if not wrapper.has_run:
				wrapper.has_run = True
				return func(*args, **kwargs)
			wrapper.has_run = False
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

	def market_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (state == State.BACKTEST):
				close = [i[1] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)][0][3]

				pos = self.createPosition(self, args[2], 0, args[3], "", args[1])
				pos.lotsize = args[4]

				if (args[1] == 'buy'):
					pos.sl = close - self.convertToPrice(args[5])
					pos.tp = close + self.convertToPrice(args[6])
				else:
					pos.sl = close + self.convertToPrice(args[5])
					pos.tp = close - self.convertToPrice(args[6])
				
				pos.entryprice = close

				print(str(pos.direction), str(pos.entryprice), str(pos.sl), str(pos.tp))

				self.positions.append(pos)
				return pos
			elif (state == State.RECOVER):
				return None
			else:
				return func(*args, **kwargs)
		return wrapper

	def price_redirect_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE):
				return [i[1] for i in sorted(self.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)][0][3]
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

	def manual(self):

		def runBacktest(filename):
			if (os.path.exists(filename.strip()+'.json')):
				with open(filename.strip()+'.json', 'r') as f:
					values = json.load(f)

				for pair in values['ohlc']:
					values['ohlc'][pair] = {int(k):v for k,v in values['ohlc'][pair].items()}

				for overlay in values['indicators']['overlays']:
					overlay[pair] = {int(k):v for k,v in overlay[pair].items()}

				for study in values['indicators']['studies']:
					study[pair] = {int(k):v for k,v in study[pair].items()}

				self.backtest(values['ohlc'], values['indicators'])
			return

		result = input("Enter filename (Press enter for manual): ")

		if (not result.strip() == "" and os.path.exists(result.strip()+'.json')):
			runBacktest(result.strip())
			return

		pair = input("Enter pair: ")
		while (pair not in self.utils.tickets.keys()):
			print("Pair not found!")
			pair = input("Enter pair: ")

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

		print(self.utils.ohlc)

		self.utils.backtestByTime(pair, startDate.strip(), startTime.strip(), endDate.strip(), endTime.strip())

		values = {}

		values['ohlc'] = self.utils.ohlc
		values['indicators'] = { 'overlays' : [], 'studies' : [] }

		for i in range(len(self.utils.indicators['overlays'])):
			values['indicators']['overlays'].append(self.utils.indicators['overlays'][i].history.copy()) 
		for j in range(len(self.utils.indicators['studies'])):
			values['indicators']['studies'].append(self.utils.indicators['studies'][j].history.copy())

		filename = "bt" + str(self.utils.plan_name) + "_" + str('-'.join(startDate.split('/'))) + "(1)"

		with open(filename+'.json', 'w') as f:
			json.dump(values, f)

		runBacktest(filename)


	def backtest(self, ohlc, indicators):
		global state, pair, current_timestamp
		state = State.BACKTEST

		position_logs = None

		for pair in ohlc:
			pair = pair

			sorted_timestamps = [i[0] for i in sorted(ohlc[pair].items(), key=lambda kv: kv[0], reverse=False)]

			for timestamp in sorted_timestamps:
				current_timestamp = timestamp

				self.insertValuesByTimestamp(timestamp, pair, ohlc, indicators)

				time = self.getLondonTime(timestamp)

				self.utils.setTradeTimes(currentTime = time)

				# self.checkStopLoss()
				# self.checkTakeProfit()

				self.runMainLoop(time)

				input("Press enter to continue...")

		try:
			self.plan.onBacktestFinish()
		except AttributeError as e:
			pass

		self.backtesting = False

	def recover(self, ohlc, indicators):
		global state, pair, current_timestamp
		state = State.RECOVER

		position_logs = None

		for pair in ohlc:
			pair = pair

			sorted_timestamps = [i[0] for i in sorted(ohlc[pair].items(), key=lambda kv: kv[0], reverse=False)]

			position_logs = self.getPositionLogs(sorted_timestamps[0])

			for timestamp in sorted_timestamps:
				current_timestamp = timestamp
				
				if (len(position_logs) > 0 and position_logs[0][1] < timestamp):
					self.updatePosition(position_logs[0])

				self.insertValuesByTimestamp(timestamp, pair, ohlc, indicators)

				time = self.getLondonTime(timestamp)

				self.utils.setTradeTimes(currentTime = time)

				self.runMainLoop(time)

		try:
			self.plan.onBacktestFinish()
		except AttributeError as e:
			pass

		self.backtesting = False

	def getAustralianTime(self, timestamp):
		time = self.utils.convertTimestampToTime(timestamp)
		tz = pytz.timezone('Australia/Melbourne')

		return tz.localize(time)

	def getLondonTime(self, timestamp):
		time = self.getAustralianTime(timestamp)
		tz = pytz.timezone('Europe/London')
		
		return time.astimezone(tz)

	def runMainLoop(self, time):

		if (self.utils.isTradeTime(currentTime = time) or len(self.utils.positions) > 0):
			
			if (self.down_time):
				try:
					self.plan.onStartTrading()
				except AttributeError as e:
					pass
				except Exception as e:
					print(str(e), "continuing...")
					return

				self.down_time = False

			try:
				self.plan.onLoop()
			except AttributeError as e:
				pass
			except Exception as e:
				print(traceback.format_exc())
				# print(str(e), "continuing...")
				return

			try:
				self.plan.onNewBar()
			except AttributeError as e:
				pass
			except Exception as e:
				print(traceback.format_exc())
				# print(str(e), "continuing...")
				return

			try:
				for key in self.utils.newsTimes.copy():
					self.plan.onNews(key, self.utils.newsTimes[key])
			except AttributeError as e:
				pass
			except Exception as e:
				print(str(e), "continuing...")
				return
		else:
			if (not self.down_time):

				try:
					self.plan.onFinishTrading()
				except AttributeError as e:
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
				pass
			except Exception as e:
				print(str(e), "continuing...")
				return

	def insertValuesByTimestamp(self, timestamp, pair, ohlc, indicators):
		self.utils.ohlc[pair][timestamp] = ohlc[pair][timestamp]

		for i in range(len(indicators['overlays'])):

			history = self.utils.indicators['overlays'][i].history
			indicator = indicators['overlays'][i]
			try:
				history[pair][timestamp] = indicator[pair][timestamp]
			except:
				history[pair][timestamp] = indicator[pair][timestamp - 60]

		for j in range(len(indicators['studies'])):

			history = self.utils.indicators['studies'][j].history
			indicator = indicators['studies'][j]
			try:
				history[pair][timestamp] = indicator[pair][timestamp]
			except:
				history[pair][timestamp] = indicator[pair][timestamp - 60]
	@runOnce
	def getPositionLogs(self, timestamp):
		print("getPositionLogs")

		history = self.utils.historyLog.getFilteredHistory()

		listened_types = ['Take Profit', 'Stop Loss', 'Buy Trade', 'Sell Trade', 'Close Trade']
		sorted_history = [i for i in history if int(i[1]) >= timestamp and i[2] in listened_types]
		sorted_history.sort(key=lambda i: i[1])

		return sorted_history

	def updatePosition(self, i):

		if i[2] == 'Buy Trade':
			pos = self.utils.createPosition(utils = self.utils, ticket = self.utils.tickets[i[3]], orderID = i[0], pair = i[3], ordertype = 'market', direction = 'sell')
			pos.entryprice = float(i[5])
			pos.lotsize = int(i[4])
			pos.sl = float(i[6])
			pos.tp = float(i[7])
			self.utils.positions.append(pos)

		elif i[2] == 'Sell Trade':
			pos = self.utils.createPosition(utils = self.utils, ticket = self.utils.tickets[i[3]], orderID = i[0], pair = i[3], ordertype = 'market', direction = 'sell')
			pos.entryprice = float(i[5])
			pos.lotsize = int(i[4])
			pos.sl = float(i[6])
			pos.tp = float(i[7])
			self.utils.positions.append(pos)

		elif i[2] == 'Close Trade':
			for pos in self.utils.positions:
				if i[8] == pos.orderID:
					del self.utils.positions[self.utils.positions.index(pos)]
					pos.closeprice = float(i[5])
					self.utils.closedPositions.append(pos)
					break

		elif i[2] == 'Take Profit':
			for pos in self.utils.positions:
				if i[0] == pos.orderID:
					del self.utils.positions[self.utils.positions.index(pos)]
					pos.closeprice = float(i[5])
					self.utils.closedPositions.append(pos)

					try:
						self.plan.onTakeProfit(pos)
					except AttributeError as e:
						pass

					break

		elif i[2] == 'Stop Loss':
			for pos in self.utils.positions:
				if i[0] == pos.orderID:
					del self.utils.positions[self.utils.positions.index(pos)]
					pos.closeprice = float(i[5])
					self.utils.closedPositions.append(pos)

					try:
						self.plan.onStopLoss(pos)
					except AttributeError as e:
						pass

					break

	def checkStopLoss(self):
		high = [i[1] for i in sorted(self.utils.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)][0][1]
		low = [i[1] for i in sorted(self.utils.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)][0][2]

		for pos in self.utils.positions:
			if (pos.direction == 'buy'):
				if (low <= pos.sl):
					pos.closeprice = pos.sl
					pos.close()
			else:
				if (high >= pos.sl):
					pos.closeprice = pos.sl
					pos.close()

	def checkTakeProfit(self):
		high = [i[1] for i in sorted(self.utils.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)][0][1]
		low = [i[1] for i in sorted(self.utils.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)][0][2]

		for pos in self.utils.positions:
			if (pos.direction == 'buy'):
				if (high >= pos.tp):
					pos.closeprice = pos.tp
					pos.close()
			else:
				if (low <= pos.tp):
					pos.closeprice = pos.tp
					pos.close()

	def isNotBacktesting(self):
		return state == State.NONE

	def isBacktesting(self):
		return state == State.BACKTEST

	def isRecover(self):
		return state == State.RECOVER