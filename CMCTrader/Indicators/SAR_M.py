import talib
import numpy as np
import time
import math
from CMCTrader import Constants
from CMCTrader import Backtester

class SAR_M(object):

	def __init__(self, utils, index, chart, acceleration, maximum):
		self.utils = utils
		self.index = index
		self.chart = chart

		self.acceleration = acceleration
		self.maximum = maximum

		self.history = {}
		self.type = 'SAR_M'
		self.collection_type = Constants.DATA_POINT_COLLECT

	def insertValues(self, timestamp, ohlc):
		real = self._calculate(ohlc)
		# real = math.floor(float(real) * 100000)/100000.0
		# real = round(float(real), 5)
		
		self.history[int(timestamp)] = real

	def getValue(self, ohlc):
		real = self._calculate(ohlc)
		# real = math.floor(float(real) * 100000)/100000.0
		# real = round(float(real), 5)
		
		return real

	def _calculate(self, ohlc):

		is_rising = False

		sars = [ohlc[1][0]]
		ep = ohlc[2][0]
		af = self.acceleration

		for i in range(1, len(ohlc[0])):
			high = ohlc[1][i]
			low = ohlc[2][i]

			if is_rising:

				if high > ep:
					ep = round(high, 5)
					af = min(af + self.acceleration, self.maximum)
				
				if low < sars[-1]:
					is_rising = False
					sars.append(ep)
					ep = round(low, 5)
					af = self.acceleration
					continue

				sar = sars[-1] + ( af * ( ep - sars[-1] ) )

				if sar > low:
					sar = low

			else:
				        
				if low < ep:
					ep = round(low, 5)
					af = min(af + self.acceleration, self.maximum)
				
				if high > sars[-1]:
					is_rising = True
					sars.append(ep)
					ep = round(high, 5)
					af = self.acceleration
					continue

				sar = sars[-1] - ( af * ( sars[-1] - ep ) )

				if sar < high:
					sar = high


			sars.append(sar)

		# if is_rising:
		# 	return math.floor(float("{0:.1f}".format(float(sars[-1]) * 100000)))/100000.0
		# else:
		# 	return math.ceil(float("{0:.1f}".format(float(sars[-1]) * 100000)))/100000.0

		return round(sars[-1], 5)

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

	def isRising(self, shift, amount):
		if Backtester.state == Backtester.State.NONE:
			timestamp = self.chart.getRealTimestamp(shift + amount-1)
		else:
			timestamp = self.chart.getLatestTimestamp(shift + amount-1)

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		sarVals = [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)]
		ohlcVals = [i[1] for i in sorted(self.chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)]
		boolList = []
		for i in range(amount):
			if (sarVals[i + shift] < ohlcVals[i + shift][1]):
				boolList.append(True)
			else:
				boolList.append(False)
		return boolList

	def isFalling(self, shift, amount):
		if Backtester.state == Backtester.State.NONE:
			timestamp = self.chart.getRealTimestamp(shift + amount-1)
		else:
			timestamp = self.chart.getLatestTimestamp(shift + amount-1)

		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		sarVals = [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)]
		ohlcVals = [i[1] for i in sorted(self.chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)]
		boolList = []
		for i in range(amount):
			if (sarVals[i + shift] > ohlcVals[i + shift][2]):
				boolList.append(True)
			else:
				boolList.append(False)
		return boolList

	def isNewCycle(self, shift):
		if (self.isRising(shift, 1)[0] and self.isFalling(shift + 1, 1)[0]):
			return True
		elif (self.isFalling(shift, 1)[0] and self.isRising(shift + 1, 1)[0]):
			return True
		return False

	def strandCount(self, shift):
		direction = None
		count = 0
		while True:
			if Backtester.state == Backtester.State.NONE:
				timestamp = self.chart.getRealTimestamp(shift)
			else:
				timestamp = self.chart.getLatestTimestamp(shift)
			
			self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

			if direction == None:
				direction = self.isRising(shift + count, 1)[0]
			elif not self.isRising(shift + count, 1)[0] == direction:
				return count

			count += 1
		