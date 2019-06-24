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

	def getValue(self, ohlc):
		arrays = self._calculate(ohlc)

		values = []
		for arr in arrays:
			val = arr[arr.size-1]
			values.append(round(float(val), 5))

		return values

	def _calculate(self, ohlc):
		# closes = np.array(ohlc[3])

		# fast_ema = self.calcEMA(ohlc[3], self.fastperiod)

		zl_fast_ema = np.array(self.calcZLEMA(ohlc[3], self.fastperiod))[self.slowperiod - self.fastperiod:]

		zl_slow_ema = np.array(self.calcZLEMA(ohlc[3], self.slowperiod))

		macd = zl_fast_ema - zl_slow_ema

		# print(macd)

		return [macd]

	def calcEMA(self, data, period):
		ema = []
		multi = float(2.0 / (period + 1.0))

		for i in range(len(data)):
			if i >= period and len(ema) == 0:
				ema.append(float(sum(data[i-period:i])/period))
			elif len(ema) > 0:
				ema.append((data[i] - ema[len(ema)-1]) * multi + ema[len(ema)-1])

		return ema

	def calcZLEMA(self, data, period):
		zlema = []
		multi = float(2.0 / (period + 1.0))
		lag = int((period - 1) / 2)

		for i in range(len(data)):
			if i >= period and len(zlema) == 0:
				zlema.append(float(sum(data[i-period:i])/period))
			elif len(zlema) > 0:
				val = data[i] + (data[i] - data[i-lag])
				zlema.append((val - zlema[len(zlema)-1]) * multi + zlema[len(zlema)-1])

		print(len(data))
		print(len(zlema))
		return zlema


	def getCurrent(self):
		timestamp = self.chart.getLatestTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getLatestTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]
		