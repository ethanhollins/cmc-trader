from CMCTrader import Constants
from CMCTrader import Backtester

class MAE(object):

	def __init__(self, utils, index, chart, timeperiod, percent_off):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod
		self.percent_off = percent_off
		self.min_period = self.timeperiod

		self.history = {}
		self.type = 'MAE'

	def insertValues(self, timestamp, ohlc):
		values = self._calculate(ohlc)

		self.history[int(timestamp)] = values
		return values

	def getValue(self, ohlc):
		values = self._calculate(ohlc)

		return values

	def _calculate(self, ohlc):

		if len(ohlc[0]) >= self.timeperiod:
			length = len(ohlc[0])
			ma = 0
			for i in range(length-1, length-1-self.timeperiod, -1):
				ma += ohlc[3][i]

			ma /= self.timeperiod
			return [
				round(ma + ma * (self.percent_off / 100), 5), 
				round(ma - ma * (self.percent_off / 100), 5)
			]

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
