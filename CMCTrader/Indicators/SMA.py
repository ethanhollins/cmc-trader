VALUE_WIDTH = 123
VALUE_HEIGHT = 24
X_START = 180

class SMA(object):

	def __init__(self, utils, index, chart, timeperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod
		self.min_period = self.timeperiod

		self.history = {}
		self.type = 'SMA'

	def insertValues(self, timestamp, ohlc):
		value = self._calculate(ohlc)

		self.history[int(timestamp)] = value

	def getValue(self, ohlc):
		value = self._calculate(ohlc)

		return value

	def _calculate(self, ohlc):

		if len(ohlc[0]) >= self.timeperiod:
			length = len(ohlc[0])
			ma = 0
			for i in range(length-1, length-1-self.timeperiod, -1):
				ma += ohlc[3][i]

			return round(ma / self.timeperiod, 5)

		else:
			return None

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
		