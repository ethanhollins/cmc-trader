from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains

import datetime

class HistoryLog(object):

	def __init__(self, driver, utils):
		self.driver = driver
		self.utils = utils
		self.historyLogElem = self.getHistoryLogElem()

		# self.current_timestamp = self.setTimestamp()

	def reinit(self):
		self.historyLogElem = self.getHistoryLogElem()

	def makeVisible(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr = attr.replace("display: none;", "");'
				'arguments[0].setAttribute("style", attr);',
				self.historyLogElem
			)
		ActionChains(self.driver).move_to_element(self.historyLogElem).perform()

	def getHistoryLogElem(self):
		return self.driver.execute_script(
				'var feature = document.querySelector(\'[class="feature feature-account-main-menu feature-account-history"]\');' +
				'return feature.querySelector(\'[class="tables"]\').querySelector(\'[class="rows"]\');'
			)

	def setTimestamp(self):
		return self.utils.convertDateTimeToTimestamp(self.utils.startTime)

	def getFilteredHistory(self):
		row_list = self.driver.execute_script(
				'var list = [];'
				# 'var rows = arguments[0].querySelectorAll(\'div[class="row"]\');' +
				'console.log(arguments[0]);'
				'var rows = arguments[0].childNodes;'
				# 'console.log(rows);'
				'for (let i = 0; i < rows.length; i++)'
				'{'
				'  console.log(rows[i]);'
				'  var cols = rows[i].querySelectorAll(\'div\');'
				'  var sl = cols[8].querySelector(\'span[class="label"]\').innerHTML;'
				'  if (sl == "-")'
				'  {'
				'    sl = "0";'
				'  }'
				'  var tp = cols[9].querySelector(\'span\').innerHTML;'
				'  if (tp == "-")'
				'  {'
				'    tp = "0";'
				'  }'
				# list = [0: id, 1: time, 2: type, 3: product, 4: units, 5:price, 6: sl, 7: tp, 8: closed id]
				'  list.push(['
				'      cols[2].querySelector(\'span\').innerHTML,'
				'      cols[0].querySelector(\'span\').innerHTML,'
				'      cols[1].querySelector(\'span\').innerHTML,'
				'      cols[5].querySelector(\'span\').innerHTML,'
				'      cols[6].querySelector(\'span\').innerHTML,'
				'      cols[7].querySelector(\'span\').innerHTML,' 
				'      sl, tp,'
				'      cols[4].querySelector(\'span\').innerHTML'
				'    ]);'
				'}'
				'return list;',
				self.historyLogElem
			)

		for i in row_list:
			if (i[0] == ''):
				del row_list[row_list.index(i)]
			else:
				i[1] = self._convertTime(i[1])
				i[3] = self._convertPair(i[3])
				if (i[4] == '-'):
					i[4] = 0
				else:
					i[4] = self._convertUnits(i[4])

		return row_list

	def getHistoryPropertiesById(self, historyID):
		return [i for i in self.getFilteredHistory() if i[0] == historyID]

	def getReleventPositions(self, listenedTypes):
		history = self.getFilteredHistory()
		return [i for i in history if i[2].strip() in listenedTypes]

	def updateHistory(self, listenedTypes):
		history = self.getReleventPositions(listenedTypes)
		# history = [j for j in row_list if row_list[1] >= self.current_timestamp]
		history.sort(key = lambda x : x[1])

		print("History:", str(history))

		# if (len(history) > 0):
		# 	self.current_timestamp = history[-1][1]

		return history


	def getClosedPosition(self, pos):
		self.makeVisible()
		history = self.getFilteredHistory()
		for i in history:
			if (i[2].strip() == 'Close Trade' and pos.orderID == i[8].strip()):
				return i

		return None

	def _convertTime(self, time):
		time.strip()
		parts = time.split(' ')
		
		year = int(parts[2])
		mon = self._getMonth(parts[1])
		day = int(parts[0])
		hour = int(parts[3].split(':')[0])
		minute = int(parts[3].split(':')[1])
		second = int(parts[3].split(':')[2])

		then = datetime.datetime(year = 2018, month = 1, day = 1)
		now = datetime.datetime(year = year, month = mon, day = day, hour = hour, minute = minute, second = second)

		return int((now - then).total_seconds())

	def _getMonth(self, month):
		return{
			'Jan' : 1,
			'Feb' : 2,
			'Mar' : 3,
			'Apr' : 4,
			'May' : 5,
			'Jun' : 6,
			'Jul' : 7,
			'Aug' : 8,
			'Sep' : 9, 
			'Oct' : 10,
			'Nov' : 11,
			'Dec' : 12
		}[month]

	def _convertPair(self, pair):
		return ''.join(pair.split('/'))

	def _convertUnits(self, units):
		return float(''.join(units.split(',')))

