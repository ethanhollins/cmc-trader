VALUE_WIDTH = 123
VALUE_HEIGHT = 24
X_START = 180

class SMA(object):

	def __init__(self, utils, index):
		self.utils = utils
		self.index = index
		self.history = self.initHistory(utils.tickets)
		self.type = 'SMA'

		self.valueCount = 1

	def initHistory(self, tickets):
		tempDict = {}
		for key in tickets:
			tempDict[key] = {}
		return tempDict

	def getValueRegions(self, startY):
		return [
			(X_START, startY, X_START + VALUE_WIDTH, startY + VALUE_HEIGHT)
		]

	def insertValues(self, pair, timestamp, values):
		try:
			self.history[pair][int(timestamp)] = float(str(values[0]).replace("D", "0"))
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