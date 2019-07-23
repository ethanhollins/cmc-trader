from enum import Enum
import pytz
import os
import json
import traceback
import datetime
import time as t
import random
import string
import matplotlib.pyplot as plt

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
	temp_local_storage = {}

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

				letters = string.ascii_lowercase
				order_id = ''.join(random.choice(letters) for i in range(10))

				pos = self.createPosition(self, args[2], order_id, args[3], 'market', args[1])
				pos.lotsize = args[4]
				pos.risk = args[7]
				pos.stoprange = args[5]

				self.addLocalStoragePosition(pos.orderID)

				if (args[1] == 'buy'):
					if args[5] != 0:
						pos.sl = round(close - self.convertToPrice(args[5]), 5)
					if args[6] != 0:
						pos.tp = round(close + self.convertToPrice(args[6]), 5)
					event = 'Buy Trade'
				else:
					if args[5] != 0:
						pos.sl = round(close + self.convertToPrice(args[5]), 5)
					if args[6] != 0:
						pos.tp = round(close - self.convertToPrice(args[6]), 5)
					event = 'Sell Trade'
				
				pos.entryprice = close
				pos.openTime = current_timestamp

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

				letters = string.ascii_lowercase
				order_id = ''.join(random.choice(letters) for i in range(10))

				pos = self.createPosition(self, args[2], order_id, args[3], 'market', args[1])
				pos.lotsize = args[4]
				pos.risk = args[7]
				pos.stoprange = args[5]
				
				self.addLocalStoragePosition(pos.orderID)

				chart = self.getLowestPeriodChart()
				close = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][3]

				pos.entryprice = chart.ohlc[current_timestamp][3]
				pos.openTime = current_timestamp
				pos.isTemp = True
				self.backtester.actions.append(Action(pos, ActionType.ENTER, current_timestamp, args = args, kwargs = kwargs))

				if (args[1] == 'buy'):
					if args[5] != 0:
						pos.sl = round(close - self.convertToPrice(args[5]), 5)
					if args[6] != 0:
						pos.tp = round(close + self.convertToPrice(args[6]), 5)
					event = 'Buy Trade'
				else:
					if args[5] != 0:
						pos.sl = round(close + self.convertToPrice(args[5]), 5)
					if args[6] != 0:
						pos.tp = round(close - self.convertToPrice(args[6]), 5)
					event = 'Sell Trade'

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

	def get_local_storage_on_backtest(func):
		def wrapper(*args, **kwargs):
			if (not state == State.NONE):
				return Backtester.temp_local_storage
			else:
				return func(*args, **kwargs)
		return wrapper

	def update_local_storage_on_backtest(func):
		def wrapper(*args, **kwargs):
			self = args[0]
			if (not state == State.NONE):
				Backtester.temp_local_storage = args[1]
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
		year = parts[2]
		parts = startTime.split(':')
		startTime = self.utils.convertTimeToTimestamp(int(day), int(month), int(year), int(parts[0]), int(parts[1]))

		parts = endDate.split('/')
		day = parts[0]
		month = parts[1]
		year = parts[2]
		parts = endTime.split(':')
		endTime = self.utils.convertTimeToTimestamp(int(day), int(month), int(year), int(parts[0]), int(parts[1]))

		''' Perform data collection '''
		values = {}
		backtest_values = {}
		for chart in self.utils.charts:
			min_period = self.utils.getMinPeriod(chart)
			start_time = self.utils.getStorageDay(startTime - chart.timestamp_offset * min_period, chart.period)
			end_time = self.utils.getStorageDay(endTime, chart.period)

			while start_time <= end_time:
				f_name = 'recovery/'+str(chart.pair)+'-'+str(chart.period)+'_'+str(start_time.day)+'-'+str(start_time.month)+'-'+str(start_time.year)+'.json'
				if (os.path.exists(f_name)):
					with open(f_name, 'r') as f:
						values = {int(k):v for k,v in json.load(f).items() if int(k) <= endTime}
						chart.ohlc = {**chart.ohlc, **values}
				else:
					print("WARNING:", f_name, "file was not found.")

				if Constants.STORAGE_DAY(chart.period):
					start_time += datetime.timedelta(seconds=Constants.STORAGE_DAY_SECONDS)

				elif Constants.STORAGE_WEEK(chart.period):
					start_time += datetime.timedelta(seconds=Constants.STORAGE_WEEK_SECONDS)

				elif Constants.STORAGE_MONTH(chart.period):
					start_time += datetime.timedelta(seconds=Constants.STORAGE_MONTH_SECONDS)

				elif Constants.STORAGE_YEAR(chart.period):
					start_time += datetime.timedelta(seconds=Constants.STORAGE_YEAR_SECONDS)

			chart.ohlc = {int(k):v for k,v in chart.ohlc.items()}

			chart_timestamps = [i[0] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0])]

			key = chart.pair + '-' + str(chart.period)
			start_ts = startTime

			for t in chart_timestamps[min_period:]:
				if t >= start_ts:
					start_ts = t
					break

			for t in chart_timestamps:
				if t > endTime:
					del chart_timestamps[chart_timestamps.index(t)]

			backtest_values[key] = self.utils.formatForBacktest(chart, start_ts, chart_timestamps)

		name = self.utils.plan_name

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

		Backtester.temp_local_storage = {}

		sorted_timestamps = []
		charts = []
		for key in values:			
			l = sorted([i[0] for i in values[key]['ohlc'].items()])

			pair = key.split('-')[0]
			period = int(key.split('-')[1])
			chart = self.utils.getChart(pair, period)
			charts.append(chart)

			if len(l) > 0:
				self.removeTimestampsUntil(chart, l[0])

			sorted_timestamps += l

		sorted_timestamps = list(dict.fromkeys(sorted_timestamps))
		sorted_timestamps.sort()
		aus_time = self.utils.convertTimestampToTime(sorted_timestamps[0])
		current_month = aus_time.month
		current_day = 0

		closed_positions = []
		global graph_vals
		graph_vals = ([], [], [], self.utils.plan_name)

		global method
		method = 'step'

		for timestamp in sorted_timestamps:
			current_timestamp = timestamp
			aus_time = self.utils.convertTimestampToTime(timestamp)

			for chart in charts:
				key = '-'.join([chart.pair, str(chart.period)])
				if timestamp in values[key]['ohlc']:
					self.insertValuesByTimestamp(timestamp, chart, values[key]['ohlc'], values[key]['overlays'], values[key]['studies'])
					self.checkStopLoss(chart)
					self.checkTakeProfit(chart)

			time = self.getLondonTime(timestamp)

			if self.down_time:
				self.utils.setTradeTimes(currentTime = time)

			if self.utils.endTime and timestamp > self.utils.convertDateTimeToTimestamp(self.utils.endTime - datetime.timedelta(days=1)):
				self.runMainLoop(time)
			else:
				self.runMainLoop(time)

			if method == 'step':
				self.execCmd(input('Enter Cmd or Continue: '))
			elif method == 'run':
				if aus_time.month != current_month:
					is_next_month = False
					if len(self.utils.positions) > 0:
						for pos in self.utils.positions:
							pos_time = self.utils.convertTimestampToTime(pos.openTime)
							if pos_time.month == current_month:
								is_next_month = True
								break
					else:
						is_next_month = True

					if is_next_month:
						profit_pips = 0
						profit_perc = 0
						for pos in self.utils.closedPositions:
							pos_time = self.utils.convertTimestampToTime(pos.openTime)
							if pos_time.month == current_month:
								profit_pips += pos.getProfit()
								profit_perc += pos.getPercentageProfit()

						print('Pips:', str(profit_pips)+'\n%:', str(profit_perc))
						print('End of month '+str(current_month))
						self.execCmd(input('Enter Cmd or Continue: '))
						closed_positions += self.utils.closedPositions
						self.utils.closedPositions = []
						current_month = aus_time.month

			if aus_time.day != current_day:
				profit, _ = self.getPercentageProfit(
					closed_positions + 
					self.utils.closedPositions + 
					self.utils.positions
				)
				graph_vals[0].append(aus_time.strftime('%d/%m'))
				graph_vals[1].append(profit)

				if aus_time.day == 1:
					graph_vals[2].append(aus_time.strftime('%d/%m'))

				current_day = aus_time.day

		closed_positions += self.utils.closedPositions
		self.utils.closedPositions = closed_positions

		profit, abs_dd = self.getPercentageProfit(closed_positions)
		print('\nEND OF BACKTEST')
		print('Pips:', str(self.utils.getTotalProfit())+'\n%:', str(round(profit, 2))+'\ndd:', str(round(abs_dd, 2)))
		
		start_bal = 100000
		end_bal, drawdown = self.getCompoundedBalanceProfit(start_bal, closed_positions)
		print('Start Bal:', str(start_bal), 'End Bal:', str(end_bal))
		print('Compounded %:', str(self.getBalancePercentProfit(start_bal, end_bal))+'%', 'Drawdown:', str(drawdown)+'%')
		
		wins, losses = self.getWinLoss(closed_positions)
		print('Wins:', str(wins), 'Losses:', str(losses), 'Ratio:', str(round(wins/losses, 2))+':1')
		total_trades = wins + losses
		print('Win %:', str(round(wins/total_trades * 100, 2)), 'Loss %:', str(round(losses/total_trades * 100, 2)))

		gain, pain = self.getGPR(closed_positions)
		gpr = round(gain/pain, 2)
		print('Total Gain %:', str(gain)+'%', 'Total Loss %:', str(pain)+'%', 'GPR Ratio:', str(gpr)+':1')
		print('Breakeven %:', str(round(1/(gpr+1)*100, 2)))

		print('\nCompounded Results:\n')

		for i in range(1,100):
			perc = float(i)/2.0
			end_bal, drawdown = self.getCompoundedBalanceProfit(start_bal, closed_positions, percent=perc)
			percent = self.getBalancePercentProfit(start_bal, end_bal)
			print(str(perc)+'%:', 'Compounded %:', str(self.getBalancePercentProfit(start_bal, end_bal))+'%', 'Drawdown:', str(drawdown)+'%')

		is_exit = False
		while not is_exit:
			is_exit = self.execCmd(input('Enter Cmd or Continue: '))

		self.utils.positions = []
		self.utils.closedPositions = []

		state = State.NONE

	def recover(self, values):
		global state, pair, current_timestamp, sorted_timestamps

		if self.utils.isLive:
			Backtester.temp_local_storage = self.utils.getLocalStorage()
			Backtester.temp_local_storage = Backtester.temp_local_storage if Backtester.temp_local_storage else {}
		else:
			Backtester.temp_local_storage = {}

		state = State.RECOVER
		self.has_run = False

		print("start recovery")

		self.actions = []
		self.history = []

		position_logs = None

		# self.utils.positions = []
		# self.utils.closedPositions = []
		# self.resetBarValues()
		sorted_timestamps = []
		charts = []
		for key in values:
			print(values[key])
			l = sorted([i[0] for i in values[key]['ohlc'].items()])

			pair = key.split('-')[0]
			period = int(key.split('-')[1])
			chart = self.utils.getChart(pair, period)
			charts.append(chart)

			if len(l) > 0:
				self.removeTimestampsUntil(chart, l[0])

			sorted_timestamps += l

		sorted_timestamps = list(dict.fromkeys(sorted_timestamps))
		sorted_timestamps.sort()

		real_time = self.utils.getLondonTime()

		# if self.down_time:
		# 	self.utils.setTradeTimes(currentTime = real_time)
			
		for timestamp in sorted_timestamps:

			# if (timestamp > self.utils.convertDateTimeToTimestamp(self.utils.endTime - datetime.timedelta(days=1))):
				
			current_timestamp = timestamp

			for chart in charts:
				key = '-'.join([chart.pair, str(chart.period)])
				if timestamp in values[key]['ohlc']:
					self.insertValuesByTimestamp(timestamp, chart, values[key]['ohlc'], values[key]['overlays'], values[key]['studies'])
					self.checkStopLoss(chart)
					self.checkTakeProfit(chart)
			
			time = self.getLondonTime(timestamp)
	
			self.runMainLoop(time)

		state = State.NONE

		print("POSITIONS:", str(self.utils.positions))
		print("CLOSED POSITIONS:", str(self.utils.closedPositions))

		local_storage = self.utils.getLocalStorage()
		local_storage = local_storage if local_storage else {}

		if not "POSITIONS" in local_storage:
			local_storage["POSITIONS"] = []

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
			self.resetTempPositions()
			self.actions = []

			for order_id in self.utils.positionLog.getCurrentPositions():
				history = self.utils.historyLog.getHistoryByOrderId(order_id)

				for event in history:
					self.utils.updateEvent(event, run_callback_funcs=False)

			# self.updatePositions(is_live=False)

		for pos in local_storage["POSITIONS"]:
			if not pos["order_id"] in [p.orderID for p in self.utils.positions if p.orderID != 0]:
				del local_storage["POSITIONS"][local_storage["POSITIONS"].index(pos)]

		for pos in self.utils.positions:
			if not pos.orderID in [p["order_id"] for p in local_storage["POSITIONS"] if p["order_id"] != 0]:
				pos_properties = {
					'order_id': pos.orderID,
					'data': {}
				}
				local_storage["POSITIONS"].append(pos_properties)


		# print("up:", str(local_storage))
		self.utils.updateLocalStorage(local_storage)

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

	def execCmd(self, x):
		global method
		if x == 'step' or x == 's':
			method = 'step'
		elif x == 'run' or x == 'r':
			method = 'run'
		elif x.startswith('graph'):
			parts = x.split(' ')
			if len(parts) == 2:
				plans = parts[1].split(',')
				try:
					vals = [graph_vals]
					for i in plans:
						vals.append(self.loadPlot(i))
					self.plot(vals)
				except:
					print('Error: Unable to load plots.')
			else:
				self.plot([graph_vals])

		elif x.startswith('save'):
			parts = x.split(' ')
			if len(parts) == 2:
				name = parts[1]
				self.savePlot(name, graph_vals)

		elif x == 'new':
			return True

		return False

	def plot(self, vals):
		plt.figure()

		colors = ['b','g','r','c','m','y']
		ticks = []
		for i in range(len(vals)):
			l = vals[i]
			c = colors[i%len(colors)]
			plt.plot(l[0], l[1], c, label=l[3])
			ticks.extend(x for x in l[2] if x not in ticks)

		plt.xticks(ticks, rotation=45)
		plt.ylabel('Percent')
		plt.xlabel('Date')
		plt.legend()

		plt.gcf().subplots_adjust(bottom=0.15)
		plt.show()

	def savePlot(self, name, vals):
		prefix = 'plot_'
		data = {
			'xvals': vals[0],
			'yvals': vals[1],
			'xticks': vals[2],
			'name': name
		}
		with open('plots/' + prefix + name + '.json', 'w') as f:
			json.dump(data, f)

	def loadPlot(self, name):
		prefix = 'plot_'

		with open('plots/' + prefix + name + '.json', 'r') as f:
			data = json.load(f)
			return (data['xvals'], data['yvals'], data['xticks'], data['name'])

	def getPercentageProfit(self, positions):
		percent = 0
		max_perc = 0
		drawdown = 0
		for pos in positions:
			percent += pos.getPercentageProfit()

			if percent > max_perc:
				max_perc = percent
			else:
				if max_perc - percent != 0:
					t_dd = max_perc - percent
					if t_dd > drawdown:
						drawdown = t_dd

		return percent, drawdown

	def getCompoundedBalanceProfit(self, start, positions, percent=1.0):
		balance = start
		b_max = start
		drawdown = 0
		for pos in positions:
			balance += (balance * ((pos.getPercentageProfit() * percent) / 100))

			if balance > b_max:
				b_max = balance
			else:
				if b_max - balance != 0:
					if ((b_max - balance) / b_max) * 100 > drawdown:
						drawdown = ((b_max - balance) / b_max) * 100

		return round(balance, 2), round(drawdown, 2)

	def getBalancePercentProfit(self, start, end):
		return round(((end / start) * 100) - 100, 2)

	def getWinLoss(self, positions):
		wins = 0
		losses = 0

		for pos in positions:
			if pos.getPercentageProfit() >= 0:
				wins += 1
			else:
				losses += 1
		return wins, losses

	def getGPR(self, positions):
		gain = 0
		pain = 0

		for pos in positions:
			perc = pos.getPercentageProfit()
			if perc >= 0:
				gain += abs(perc)
			else:
				pain += abs(perc)

		return round(gain, 2), round(pain, 2)

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

	def updatePositions(self, is_live=True):
		latest_history_timestamp = self.utils.historyLog.getLatestHistoryTimestamp()

		print("posees")
		print(self.utils.positions)
		print(self.utils.closedPositions)


		print("latest:", str(latest_history_timestamp))

		# for pos in self.utils.positions:
		# 	if pos.isTemp:
		# 		del self.utils.positions[self.utils.positions.index(pos)]

		print(self.actions)
		cutoff_pos = []
		for i in range(len(self.actions)-1, -1, -1):
			action = self.actions[i]
			if action.timestamp > latest_history_timestamp and not action.position in cutoff_pos:
				if action.action == ActionType.CLOSE or action.action == ActionType.STOP_AND_REVERSE:
					cutoff_pos.append(action.position)
			else:
				del self.actions[i]

		print(self.actions)

		for update in self.actions:
			pos = update.position

			if update.action == ActionType.ENTER and is_live:
				self.utils._marketOrder(*update.args, **update.kwargs)
			elif update.action == ActionType.STOP_AND_REVERSE and is_live:
				if not pos == None:
					if update.position.direction == pos.direction:
						pos.stopAndReverse(*update.args, **update.kwargs)
				else:
					if update.position.direction == 'buy':
						self.utils.buy(update.args[1], sl = args[2], tp = args[3])
					elif update.position.direction == 'sell':
						self.utils.sell(update.args[1], sl = args[2], tp = args[3])
			
			elif not pos == None:
				if update.action == ActionType.CLOSE and is_live:
					if update.position.direction == pos.direction:
						pos.close()
					
				elif update.action == ActionType.MODIFY_POS_SIZE:
					if update.position.direction == pos.direction:
						pos.modifyPositionSize(*update.args, **update.kwargs)

				elif update.action == ActionType.MODIFY_TRAILING:
					if update.position.direction == pos.direction:
						pos.modifyTrailing(*update.args, **update.kwargs)

				elif update.action == ActionType.MODIFY_SL:
					if update.position.direction == pos.direction:
						pos.modifySL(*update.args, **update.kwargs)

				elif update.action == ActionType.MODIFY_TP:
					if update.position.direction == pos.direction:
						pos.modifyTP(*update.args, **update.kwargs)

				elif update.action == ActionType.REMOVE_SL:
					if update.position.direction == pos.direction:
						pos.removeSL()

				elif update.action == ActionType.REMOVE_TP:
					if update.position.direction == pos.direction:
						pos.removeTP()

				elif update.action == ActionType.BREAKEVEN:
					if update.position.direction == pos.direction:
						pos.breakeven()
				elif update.action == ActionType.APPLY:
					if update.position.direction == pos.direction:
						pos.apply()

				elif update.action == ActionType.CANCEL:
					pass
				elif update.action == ActionType.MODIFY_ENTRY_PRICE:
					pass

		self.actions = []

	def checkStopLoss(self, chart):

		ohlc = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)]
		high = ohlc[0][1]
		low = ohlc[0][2]

		for i in range(len(self.utils.positions)-1, -1, -1):
			pos = self.utils.positions[i]
			if not pos.sl == 0:
				if pos.direction == 'buy':
					if low <= pos.sl:
						print('sl buy:', str(low), str(pos.sl))
						pos.closeprice = pos.sl
						try:
							self.utils.plan.onStopLoss(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Stop Loss')
						except AttributeError as e:
							pass
						pos.close()
						pos.closeprice = pos.sl
				else:
					if high >= pos.sl:
						print('sl sell:', str(high), str(pos.sl))
						pos.closeprice = pos.sl
						try:
							self.utils.plan.onStopLoss(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Stop Loss')
						except AttributeError as e:
							pass
							
						pos.close()
						pos.closeprice = pos.sl

	def checkTakeProfit(self, chart):

		high = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][1]
		low = [i[1] for i in sorted(chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)][0][2]

		for i in range(len(self.utils.positions)-1, -1, -1):
			pos = self.utils.positions[i]
			if not pos.tp == 0:
				if pos.direction == 'buy':
					if high >= pos.tp:
						pos.closeprice = pos.tp
						try:
							self.utils.plan.onTakeProfit(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Take Profit')
						except AttributeError as e:
							pass
						pos.close()
						pos.closeprice = pos.tp
				else:
					if low <= pos.tp:
						pos.closeprice = pos.tp
						try:
							self.utils.plan.onTakeProfit(pos)
						except AttributeError as e:
							pass

						try:
							self.plan.onTrade(pos, 'Take Profit')
						except AttributeError as e:
							pass
						pos.close()
						pos.closeprice = pos.tp

	def isNotBacktesting(self):
		return state == State.NONE

	def isBacktesting(self):
		return state == State.BACKTEST

	def isRecover(self):
		return state == State.RECOVER