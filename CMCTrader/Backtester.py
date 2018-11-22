from CMCTrader.Position import Position
import pytz

class Backtester(object):

	def __init__(self, utils, plan):
		self.utils = utils
		self.plan = plan

	def backtest(self, ohlc, indicators):
		for pair in ohlc:
			sortedTimestamps = [i[0] for i in sorted(ohlc[pair].items(), key=lambda kv: kv[0], reverse=False)]

			for timestamp in sortedTimestamps:
				self.insertValuesByTimestamp(timestamp, pair, ohlc, indicators)

				time = self.utils.convertTimestampToTime(timestamp)
				tz = pytz.timezone('Australia/Melbourne')
				time = tz.localize(time)
				tz = pytz.timezone('Europe/London')
				londonTime = time.astimezone(tz)

				if (self.utils.isTradeTime(currentTime = londonTime)):
					try:
						self.plan.onNewBar()
					except AttributeError as e:
						pass
					except Exception as e:
						print("not quite")
						continue
				else:
					try:
						self.plan.onDownTime()
					except AttributeError as e:
						pass
					except Exception as e:
						continue

		self.updatePositions(sortedTimestamps[0])

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

	def updatePositions(self, timestamp):
		history = self.utils.historyLog.getFilteredHistory()

		listened_types = ['Take Profit', 'Stop Loss', 'Buy Trade', 'Sell Trade', 'Close Trade']
		filtered_history = [i for i in history if int(i[1]) >= int(timestamp) and i[2] in listened_types]
		filtered_history.sort(key=lambda i: i[1])

		for i in filtered_history:

			if i[2] == 'Buy Trade':
				pos = Position(utils = self.utils, ticket = self.utils.tickets[i[3]], orderID = i[0], pair = i[3], ordertype = 'market', direction = 'buy')
				pos.entryprice = float(i[5])
				pos.lotsize = int(i[4])
				pos.sl = float(i[6])
				pos.tp = float(i[7])
				self.utils.positions.append(pos)

			elif i[2] == 'Sell Trade':
				pos = Position(utils = self.utils, ticket = self.utils.tickets[i[3]], orderID = i[0], pair = i[3], ordertype = 'market', direction = 'sell')
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
						break

			elif i[2] == 'Stop Loss':
				for pos in self.utils.positions:
					if i[0] == pos.orderID:
						del self.utils.positions[self.utils.positions.index(pos)]
						pos.closeprice = float(i[5])
						self.utils.closedPositions.append(pos)
						break

