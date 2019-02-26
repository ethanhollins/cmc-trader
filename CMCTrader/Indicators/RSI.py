VALUE_WIDTH = 123
VALUE_HEIGHT = 24
VALUE_OFFSET = 27
X_START = 180

class RSI(object):

	def __init__(self, utils, index, colours):
		self.index = index
		self.utils = utils
		self.colours = colours
		self.history = {}
		self.canBeNegative = False
		self.type = 'RSI'

	def insertValues(self, timestamp, values):
		for i in range(len(values)):
			values[i] = round(float(values[i])*100, 2)

		self.history[int(timestamp)] = values

	def getCurrent(self, pair):
		timestamp = self.utils.getTimestampFromOffset(pair, 0, 1)
		self.utils.getMissingTimestamps(timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, pair, shift, amount):
		timestamp = self.utils.getTimestampFromOffset(pair, shift, amount)
		self.utils.getMissingTimestamps(timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]

	def _getMissingValues(self, pair, shift, amount):
		self.utils.getMissingValues(pair, shift, amount)

	def addFillerData(self, pair, timestamp):
		if (int(timestamp) - 60) in self.history:
			self.history[int(timestamp)] = self.history[int(timestamp) - 60]
		else:
			return
