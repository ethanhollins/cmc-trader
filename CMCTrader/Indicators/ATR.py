from CMCTrader import Constants
from CMCTrader import Backtester

class ATR(object):

	def __init__(self, utils, index, chart, timeperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod
		self.min_period = self.timeperiod + 1

		self.history = {}
		self.type = 'ATR'

	def insertValues(self, timestamp, ohlc):
		value = self._calculate(ohlc)

		self.history[int(timestamp)] = value
		return value

	def getValue(self, ohlc):
		value = self._calculate(ohlc)

		return value

	def _calculate(self, ohlc):

		def get_tr(shift):
			high = ohlc[1][shift]
			prev_high = ohlc[1][shift-1]

			low = ohlc[2][shift]
			prev_low = ohlc[2][shift-1]

			close = ohlc[3][shift]
			prev_close = ohlc[3][shift-1]

			if prev_close > high:
				return prev_close - low
			elif prev_close < low:
				return high - prev_close
			else:
				return high - low

		atr_l = []
		for i in range(1, len(ohlc[0])):
			if len(atr_l) > 0:
				prev_atr = atr_l[-1]
				tr = get_tr(i)
				# print(str(ts)+':', 'prev:', str(prev_atr), 'tr:', str(tr))
				# print('res:', str(round((prev_atr * (self.timeperiod-1) + tr) / self.timeperiod, 5)))
				atr_l.append(round((prev_atr * (self.timeperiod-1) + tr) / self.timeperiod, 5))

			elif i > self.timeperiod:				
				tr_sum = 0
				for j in range(i-self.timeperiod, i):
					if j == 0:
						high = ohlc[1][j]
						low = ohlc[2][j]
						tr_sum += (high - low)
					else:
						tr_sum += get_tr(j)
				
				atr_l.append(round(tr_sum/self.timeperiod, 5))

		return atr_l[-1]

	def getCurrent(self):
		if self.utils.backtester.isNotBacktesting():
			timestamp = self.chart.getRealTimestamp(0)
		else:
			timestamp = self.chart.getLatestTimestamp(0)

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		if self.utils.backtester.isNotBacktesting():
			timestamp = self.chart.getRealTimestamp(shift + amount-1)
		else:
			timestamp = self.chart.getLatestTimestamp(shift + amount-1)

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]
