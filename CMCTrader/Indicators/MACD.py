import talib
import numpy as np
from CMCTrader import Constants
from CMCTrader import Backtester

class MACD(object):

	def __init__(self, utils, index, chart, fastperiod, slowperiod, signalperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.fastperiod = fastperiod
		self.slowperiod = slowperiod
		self.signalperiod = signalperiod
		self.min_period = max(fastperiod, slowperiod) + signalperiod

		self.history = {}
		self.type = 'MACD'
		self.collection_type = Constants.DATA_POINT_COLLECT

	def insertValues(self, timestamp, ohlc):
		values = self._calculate(ohlc)

		self.history[int(timestamp)] = values

	def getValue(self, ohlc):
		values = self._calculate(ohlc)

		return values

	# def _calculate(self, ohlc):
	# 	return list(talib.MACD(np.array(ohlc[3]), fastperiod=self.fastperiod, slowperiod=self.slowperiod, signalperiod=self.signalperiod))

	def _calculate(self, ohlc):
		if len(ohlc[0]) > self.min_period:
			fast_ema = self.calcEMA(ohlc[3], self.fastperiod)
			slow_ema = self.calcEMA(ohlc[3], self.slowperiod)

			macd = [i - j for i, j in zip(fast_ema[-self.min_period:], slow_ema[-self.min_period:])]
			signal = self.calcEMA(macd, self.signalperiod)

			hist = macd[-1] - signal[-1]

			return [round(macd[-1], 5), round(signal[-1], 5), round(hist, 5)]
		else:
			return None

	def calcEMA(self, close, period):
		ema = []
		multi = float(2.0 / (period + 1.0))

		for i in range(len(close)):
			if i >= period and len(ema) == 0:
				ema.append(round(float(sum(close[i-period:i])/period), 5))
			elif len(ema) > 0:
				ema.append(round((close[i] - ema[len(ema)-1]) * multi + ema[len(ema)-1], 5))

		return ema

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
		