import talib
import numpy as np
from CMCTrader import Constants

class MACDZ(object):

	def __init__(self, utils, index, chart, fastperiod, slowperiod, signalperiod):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.fastperiod = fastperiod
		self.slowperiod = slowperiod
		self.signalperiod = signalperiod
		self.req_val_count = 38 + slowperiod

		self.history = {}
		self.type = 'MACDZ'
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
		ema_f_one = talib.EMA(np.array(ohlc[3]), timeperiod=self.fastperiod)
		ema_f_two = talib.EMA(ema_f_one, timeperiod=self.fastperiod)
		fast_ema = (2 * ema_f_one) - ema_f_two

		ema_s_one = talib.EMA(np.array(ohlc[3]), timeperiod=self.slowperiod)
		ema_s_two = talib.EMA(ema_s_one, timeperiod=self.slowperiod)
		slow_ema = (2 * ema_s_one) - ema_s_two

		macd = fast_ema - slow_ema

		ema_sig_one = talib.EMA(macd, timeperiod=self.signalperiod)
		ema_sig_two = talib.EMA(ema_sig_one, timeperiod=self.signalperiod)
		signal = (2 * ema_sig_one) - ema_sig_two

		hist = macd - signal
		return [macd, signal, hist]

	def getCurrent(self):
		timestamp = self.chart.getRelativeTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getRelativeTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]
		