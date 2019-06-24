from CMCTrader import Constants

VALUE_WIDTH = 123
VALUE_HEIGHT = 24
X_START = 180

class SAR(object):
	
	def __init__(self, utils, index, chart, colour):
		self.index = index
		self.utils = utils
		self.chart = chart
		self.colour = colour

		self.history = {}
		self.type = 'SAR'
		self.collection_type = Constants.PIXEL_COLLECT

	def insertValues(self, timestamp, value):
		print("insert:", str(value), str(self.chart.ohlc[int(timestamp)][1]), str(self.chart.ohlc[int(timestamp)][2]))
		value = round(float(value), 5)
		mp = (self.chart.ohlc[int(timestamp)][1] + self.chart.ohlc[int(timestamp)][2]) / 2
		print(mp)
		if value < self.chart.ohlc[int(timestamp)][1] and value >= mp:
			value = self.chart.ohlc[int(timestamp)][1]
		elif value > self.chart.ohlc[int(timestamp)][2] and value < mp:
			value = self.chart.ohlc[int(timestamp)][2]
		self.history[int(timestamp)] = value
			
	def getCurrent(self):
		timestamp = self.chart.getLatestTimestamp(0)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, shift, amount):
		timestamp = self.chart.getLatestTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]

	def isRising(self, shift, amount):
		timestamp = self.chart.getLatestTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		sarVals = [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)]
		ohlcVals = [i[1] for i in sorted(self.chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)]
		boolList = []
		for i in range(amount):
			if (sarVals[i + shift] < ohlcVals[i + shift][2]):
				print(str(sarVals[i + shift]), str(ohlcVals[i + shift][2]))
				boolList.append(True)
			else:
				print(str(sarVals[i + shift]), str(ohlcVals[i + shift][2]))
				boolList.append(False)
		return boolList

	def isFalling(self, shift, amount):
		timestamp = self.chart.getLatestTimestamp(shift + amount-1)
		self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

		sarVals = [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)]
		ohlcVals = [i[1] for i in sorted(self.chart.ohlc.items(), key=lambda kv: kv[0], reverse=True)]
		boolList = []
		for i in range(amount):
			if (sarVals[i + shift] > ohlcVals[i + shift][1]):
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
			timestamp = self.chart.getLatestTimestamp(shift)
			self.utils.barReader.getMissingBarDataByTimestamp(self.chart, timestamp)

			if direction == None:
				direction = self.isRising(shift + count, 1)[0]
			elif not self.isRising(shift + count, 1)[0] == direction:
				return count

			count += 1
