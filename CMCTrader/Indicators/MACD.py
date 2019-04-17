import talib
import numpy as np
from CMCTrader import Constants

class MACD(object):

	def __init__(self, utils, index, chart, fastperiod, slowperiod, signalperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.fastperiod = fastperiod
		self.slowperiod = slowperiod
		self.signalperiod = signalperiod

		self.history = {}
		self.type = 'MACD'
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
		return list(talib.MACD(np.array(ohlc[3]), fastperiod=self.fastperiod, slowperiod=self.slowperiod, signalperiod=self.signalperiod))

	def getCurrent(self):
		timestamp = self.chart.getRelativeTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getRelativeTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]
		