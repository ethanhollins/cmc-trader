VALUE_WIDTH = 123
VALUE_HEIGHT = 24
X_START = 180

class SMA(object):

	def __init__(self, utils, index, colour):
		self.utils = utils
		self.index = index
		self.colour = colour
		self.history = {}
		self.type = 'SMA'

	def insertValues(self, timestamp, value):
		self.history[int(timestamp)] = round(float(value), 5)

	def getCurrent(self, pair):
		timestamp = self.utils.getTimestampFromOffset(pair, 0, 1)
		self.utils.getMissingTimestamps(timestamp)

		return sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[0][1]

	def get(self, pair, shift, amount):
		timestamp = self.utils.getTimestampFromOffset(pair, shift, amount)
		self.utils.getMissingTimestamps(timestamp)

		return [i[1] for i in sorted(self.history.items(), key=lambda kv: kv[0], reverse=True)[shift:shift + amount]]

	def addFillerData(self, timestamp):
		if (int(timestamp) - 60) in self.history:
			self.history[int(timestamp)] = self.history[int(timestamp) - 60]
		else:
			return