VALUE_WIDTH = 123
VALUE_HEIGHT = 24
VALUE_OFFSET = 27
X_START = 180

class MACD(object):

	def __init__(self, utils, index, valueCount):
		self.index = index
		self.utils = utils
		self.history = self.initHistory(utils.tickets)
		self.canBeNegative = True
		self.type = 'MACD'

		self.valueCount = valueCount

	def initHistory(self, tickets):
		tempDict = {}
		for key in tickets:
			tempDict[key] = {}
		return tempDict

	def getValueRegions(self, startY):
		regions = []
		for i in range(self.valueCount):
			regions.append((X_START, startY + (VALUE_OFFSET * i), X_START + VALUE_WIDTH, startY + VALUE_HEIGHT + (VALUE_OFFSET * i)))
		return regions

	def insertValues(self, pair, timestamp, values):
		try:
			for i in range(self.valueCount):
				if "." not in str(values[i]):
					values[i] = str(values[i])[:len(str(values[i])) - 5] + '.' + str(values[i])[len(str(values[i])) - 5:]
				values[i] = float(values[i].replace("D", "0"))

			self.history[pair][int(timestamp)] = values
		except:
			self._addFillerData(pair, timestamp)

	def getCurrent(self, pair):
		timestamp = self.utils.getTimestampFromOffset(pair, 0, 1)
		self.utils.getMissingTimestamps(timestamp)

		return sorted(self.history[pair].items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, pair, shift, amount):
		timestamp = self.utils.getTimestampFromOffset(pair, shift, amount)
		self.utils.getMissingTimestamps(timestamp)

		return [i[1] for i in sorted(self.history[pair].items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]

	def _addFillerData(self, pair, timestamp):
		if (int(timestamp) - 60) in self.history[pair]:
			self.history[pair][int(timestamp)] = self.history[pair][int(timestamp) - 60]
		else:
			return