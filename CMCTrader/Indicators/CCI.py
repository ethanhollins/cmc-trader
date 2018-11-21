VALUE_WIDTH = 123
VALUE_HEIGHT = 24
VALUE_OFFSET = 27
X_START = 180

class CCI(object):
	
	def __init__(self, utils, index, valueCount):
		self.index = index
		self.utils = utils
		self.history = self.initHistory(utils.tickets)
		self.canBeNegative = True
		self.type = 'CCI'

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
		whitelist = set('0123456789.-')

		try:
			for i in range(self.valueCount):
				values[i] = str(values[i])
				print(values[i])
				values[i] = values[i].replace("D", "0")
				values[i] = ''.join(filter(whitelist.__contains__, values[i]))

				if "." not in values[i]:
					values[i] = values[i][:len(values[i]) - 5] + '.' + values[i][len(values[i]) - 5:]
				
				print(values[i])
				values[i] = float(values[i])

			self.history[pair][int(timestamp)] = values

		except:
			print("Attempting to fill data")
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
			print("Error filling cci data")
			return