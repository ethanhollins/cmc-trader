import talib
import numpy as np
from CMCTrader import Constants
from CMCTrader import Backtester

class RSI(object):
	
	def __init__(self, utils, index, chart, timeperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod
		self.min_period = self.timeperiod+1

		self.history = {}
		self.type = 'RSI'

	def insertValues(self, timestamp, ohlc):
		value = self._calculate(ohlc)

		self.history[int(timestamp)] = value
		return value

	def getValue(self, ohlc):
		value = self._calculate(ohlc)

		return value

	# def _calculate(self, ohlc):
	# 	return list(talib.RSI(np.array(ohlc[3]), timeperiod=self.timeperiod))

	def _calculate(self, ohlc):
		rsi = []
		gain = []
		loss = []
		if len(ohlc[0]) > self.min_period:
			for i in range(1, len(ohlc[0])):
				gain_sum = 0
				loss_sum = 0
				if len(rsi) > 0:
					prev_gain = gain[-1]
					prev_loss = loss[-1]

					change = ohlc[3][i] - ohlc[3][i-1]
					if change >= 0:
						gain_sum += change
					else:
						loss_sum += abs(change)

					gain_avg = (prev_gain * (self.timeperiod-1) + gain_sum)/self.timeperiod
					loss_avg = (prev_loss * (self.timeperiod-1) + loss_sum)/self.timeperiod

					gain.append(gain_avg)
					loss.append(loss_avg)

					if loss_avg == 0:
						rsi.append(100)
					else:
						rsi.append(100 - (100 / (1 + gain_avg / loss_avg)))

				elif i > self.min_period:
					for j in range(i-self.min_period, i):
						if j != 0:
							change = ohlc[3][j] - ohlc[3][j-1]

							if change >= 0:
								gain_sum += change
							else:
								loss_sum += abs(change)

					gain_avg = (gain_sum / self.timeperiod)
					loss_avg = (loss_sum / self.timeperiod)

					gain.append(gain_avg)
					loss.append(loss_avg)
					
					# if loss_avg == 0:
					# 	rsi.append(100)
					# else:
					if loss_avg == 0:
						rsi.append(100)
					else:
						rsi.append(100 - (100 / (1 + gain_avg / loss_avg)))

		return [round(rsi[-1], 2)]

	def getCurrent(self):
		if self.utils.backtester.isNotBacktesting():
			timestamp = self.chart.getRealTimestamp(0)
			print()
		else:
			timestamp = self.chart.getLatestTimestamp(0)
			
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		if self.utils.backtester.isNotBacktesting():
			timestamp = self.chart.getRealTimestamp(shift + amount-1)
			print(self.utils.convertTimestampToTime(timestamp))
		else:
			timestamp = self.chart.getLatestTimestamp(shift + amount-1)

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]

	def getByTime(self, dt):

		timestamp = self.utils.convertDateTimeToTimestamp(dt)
		latest_timestamp = self.chart.getCurrentTimestamp()

		while timestamp < latest_timestamp:
			latest_timestamp -= self.chart.timestamp_offset

		offset = timestamp % latest_timestamp
		timestamp -= offset

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return self.history[timestamp]