from CMCTrader import Constants
from CMCTrader import Backtester

class KELT(object):

	def __init__(self, utils, index, chart, timeperiod, atr_period, atr_multi):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.timeperiod = timeperiod
		self.atr_period = atr_period
		self.atr_multi = atr_multi
		self.min_period = max(self.timeperiod, self.atr_period) + 1

		self.history = {}
		self.type = 'KELT'

	def insertValues(self, timestamp, ohlc):
		value = self._calculate(ohlc)

		self.history[int(timestamp)] = value
		return value

	def getValue(self, ohlc):
		value = self._calculate(ohlc)

		return value

	def _calculate(self, ohlc):

		def get_tr(shift):
			high = ohlc[1][shift]
			prev_high = ohlc[1][shift-1]

			low = ohlc[2][shift]
			prev_low = ohlc[2][shift-1]

			close = ohlc[3][shift]
			prev_close = ohlc[3][shift-1]

			if prev_close > high:
				return prev_close - low
			elif prev_close < low:
				return high - prev_close
			else:
				return high - low

		if len(ohlc[0]) > self.min_period:
			atr_l = []
			for i in range(1, len(ohlc[0])):
				if len(atr_l) > 0:
					prev_atr = atr_l[-1]
					tr = get_tr(i)
					atr_l.append(round((prev_atr * (self.atr_period-1) + tr) / self.atr_period, 5))

				elif i > self.atr_period:				
					tr_sum = 0
					for j in range(i-self.atr_period, i):
						if j == 0:
							high = ohlc[1][j]
							low = ohlc[2][j]
							tr_sum += (high - low)
						else:
							tr_sum += get_tr(j)
					
					atr_l.append(round(tr_sum/self.atr_period, 5))

			ema = self.calcEMA(ohlc[3], self.timeperiod)[-1]

			return [
				round(ema + (self.atr_multi * atr_l[-1]), 5),
				round(ema - (self.atr_multi * atr_l[-1]), 5)
			]

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

	def calcTypicalEMA(self, high, low, close, period):
		ema = []
		multi = float(2.0 / (period + 1.0))

		for i in range(len(close)):
			if i >= period and len(ema) == 0:
				ema.append(round(float((sum(high[i-period:i]) + sum(low[i-period:i]) + sum(close[i-period:i]))/3/period), 5))
			elif len(ema) > 0:
				ema.append(round(((high[i] + low[i] + close[i])/3 - ema[len(ema)-1]) * multi + ema[len(ema)-1], 5))

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
