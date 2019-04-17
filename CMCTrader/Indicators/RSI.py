import talib
import numpy as np
from CMCTrader import Constants

class RSI(object):
	
	def __init__(self, utils, index, chart, timeperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod

		self.history = {}
		self.type = 'RSI'
		self.collection_type = Constants.DATA_POINT_COLLECT

	def insertValues(self, timestamp, ohlc):
		array = self._calculate(ohlc)

		values = []
		val = array[len(array)-1]
		values.append(round(float(val), 2))

		self.history[int(timestamp)] = values

	def getValue(self, ohlc):
		array = self._calculate(ohlc)

		values = []
		val = array[len(array)-1]
		values.append(round(float(val), 2))

		return values

	def _calculate(self, ohlc):
		return list(talib.RSI(np.array(ohlc[3]), timeperiod=self.timeperiod))

	def getCurrent(self):
		timestamp = self.chart.getRelativeTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getRelativeTimestamp(shift + amount-1)
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