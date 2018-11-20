VALUE_WIDTH = 123
VALUE_HEIGHT = 24
X_START = 180

class SAR(object):
	
	def __init__(self, utils, index):
		self.index = index
		self.utils = utils
		self.history = self.initHistory(utils.tickets)
		self.type = 'SAR'

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
		whitelist = set('0123456789.-')

		try:
			values[0] = str(values[0])
			values[0] = values[0].replace("D", "0")
			values[0] = ''.join(filter(whitelist.__contains__, values[0]))

			self.history[pair][int(timestamp)] = float(values[0])
			print(self.history[pair])
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

	def isRising(self, pair, shift, amount):
		timestamp = self.utils.getTimestampFromOffset(pair, shift, amount)
		self.utils.getMissingTimestamps(timestamp)

		sarVals = [i[1] for i in sorted(self.history[pair].items(), key=lambda kv: kv[0], reverse=True)]
		ohlcVals = [i[1] for i in sorted(self.utils.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)]
		boolList = []
		for i in range(amount):
			if (sarVals[i + shift] <= ohlcVals[i + shift][2]):
				boolList.append(True)
			else:
				boolList.append(False)
		return boolList

	def isFalling(self, pair, shift, amount):
		timestamp = self.utils.getTimestampFromOffset(pair, shift, amount)
		self.utils.getMissingTimestamps(timestamp)

		sarVals = [i[1] for i in sorted(self.history[pair].items(), key=lambda kv: kv[0], reverse=True)]
		ohlcVals = [i[1] for i in sorted(self.utils.ohlc[pair].items(), key=lambda kv: kv[0], reverse=True)]
		boolList = []
		for i in range(amount):
			if (sarVals[i + shift] >= ohlcVals[i + shift][1]):
				boolList.append(True)
			else:
				boolList.append(False)
		return boolList

	def isNewCycle(self, pair, shift):
		if (self.isRising(pair, shift, 1)[0] and self.isFalling(pair, shift + 1, 1)[0]):
			return True
		elif (self.isFalling(pair, shift, 1)[0] and self.isRising(pair, shift + 1, 1)[0]):
			return True
		return False

	def strandCount(self, pair, shift):
		direction = None
		count = 0
		while True:
			timestamp = self.utils.getTimestampFromOffset(pair, shift + count, 1)
			self.utils.getMissingTimestamps(timestamp)

			if direction == None:
				direction = self.isRising(pair, shift + count, 1)[0]
			elif not self.isRising(pair, shift + count, 1)[0] == direction:
				return count

			count += 1

	def _addFillerData(self, pair, timestamp):
		if (int(timestamp) - 60) in self.history[pair]:
			self.history[pair][int(timestamp)] = self.history[pair][int(timestamp) - 60]
		else:
			return