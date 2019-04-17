import talib
import numpy as np
from CMCTrader import Constants

class CCI(object):
	
	def __init__(self, utils, index, chart, timeperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod

		self.history = {}
		self.type = 'CCI'
		self.collection_type = Constants.DATA_POINT_COLLECT

	def insertValues(self, timestamp, ohlc):
		array = self._calculate(ohlc)

		values = []
		val = array[len(array)-1]
		values.append(round(float(val), 5))

		self.history[int(timestamp)] = values

	def getValue(self, ohlc):
		array = self._calculate(ohlc)

		values = []
		val = array[len(array)-1]
		values.append(round(float(val), 5))

		return values

	def _calculate(self, ohlc):
		return list(talib.CCI(np.array(ohlc[1]), np.array(ohlc[2]), np.array(ohlc[3]), timeperiod=self.timeperiod))

	def getCurrent(self):
		timestamp = self.chart.getRelativeTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getRelativeTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]
