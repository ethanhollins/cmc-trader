import talib
import numpy as np
from CMCTrader import Constants

class MACDZ_M(object):

	def __init__(self, utils, index, chart, fastperiod, slowperiod, signalperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.fastperiod = fastperiod
		self.slowperiod = slowperiod
		self.signalperiod = signalperiod
		self.req_val_count = 38 + slowperiod

		self.history = {}
		self.type = 'MACDZ_M'
		self.collection_type = Constants.DATA_POINT_COLLECT

	def insertValues(self, timestamp, ohlc):
		arrays = self._calculate(ohlc)

		values = []
		for arr in arrays:
			val = arr[arr.size-1]
			values.append(round(float(val), 5))

		self.history[int(timestamp)] = values

	def _calculate(self, ohlc):
		closes = np.array(ohlc[3])

		fast_lag = (self.fastperiod - 1)/2

		sub = np.array(ohlc[3])
		for i in range(int(fast_lag)):
			sub[-i] = 0

		fast_ema_data = closes + (closes - sub)
		zl_fast_ema = talib.EMA(fast_ema_data, timeperiod=self.fastperiod)

		slow_lag = (self.slowperiod - 1)/2

		sub = np.array(ohlc[3])
		for i in range(int(slow_lag)):
			sub[-i] = 0

		slow_ema_data = closes + (closes - sub)
		zl_slow_ema = talib.EMA(slow_ema_data, timeperiod=self.slowperiod)

		macd = zl_fast_ema - zl_slow_ema

		# print(macd)

		print("macd:", str(talib.MACDEXT(closes, fastperiod=self.fastperiod, fastmatype=2, slowperiod=self.slowperiod, slowmatype=2, signalperiod=self.signalperiod, signalmatype=2)))


		return [macd]

	def getCurrent(self):
		timestamp = self.chart.getRelativeTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getRelativeTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]
		