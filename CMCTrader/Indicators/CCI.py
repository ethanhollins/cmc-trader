import talib
import numpy as np
from CMCTrader import Constants
from CMCTrader import Backtester

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
		if Backtester.state == Backtester.State.NONE:
			timestamp = self.chart.getRealTimestamp(0)
		else:
			timestamp = self.chart.getLatestTimestamp(0)
			
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		if Backtester.state == Backtester.State.NONE:
			timestamp = self.chart.getRealTimestamp(shift + amount-1)
		else:
			timestamp = self.chart.getLatestTimestamp(shift + amount-1)

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]

	def getSignalLine(self, period, shift, amount):
		vals = self.get(shift, amount + period)
		result = []
		for i in range(amount):
			offset = i
			avg_sum = 0
			for j in range(period):
				avg_sum += vals[offset + j][0]
			result.append(avg_sum/period)
			offset += 1

		return result

