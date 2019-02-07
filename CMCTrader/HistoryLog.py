from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains

import datetime

class HistoryLog(object):

	def __init__(self, driver, utils):
		self.driver = driver
		self.utils = utils
		self.historyLogElem = self.getHistoryLogElem()

		self.current_timestamp = self.setTimestamp()

	def reinit(self, driver):
		self.driver = driver
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
				# list = [0: id, 1: time, 2: type, 3: product, 4: units, 5: price, 6: sl, 7: tp, 8: closed id, 9: is_trailing]
				'  list.push(['
				'      cols[2].querySelector(\'span\').innerHTML,'
				'      cols[0].querySelector(\'span\').innerHTML,'
				'      cols[1].querySelector(\'span\').innerHTML,'
				'      cols[5].querySelector(\'span\').innerHTML,'
				'      cols[6].querySelector(\'span\').innerHTML,'
				'      cols[7].querySelector(\'span\').innerHTML,' 
				'      sl, tp,'
				'      cols[4].querySelector(\'span\').innerHTML,'
				'      false'
				'    ]);'
				'}'
				'return list;',
				self.historyLogElem
			)

		deleted_items = []

		for i in row_list:
			if i[0] == '':
				deleted_items.append(i)
			else:
				i[1] = self._convertTime(i[1])
				i[3] = self._convertPair(i[3])

				if (i[4].startswith("(T) ")):
					i[4].strip("(T) ")
					i[9] = True
				
				if (i[4] == '-'):
					i[4] = 0
				else:
					i[4] = self._convertUnits(i[4])

		for i in deleted_items:
			del row_list[row_list.index(i)]

		return row_list

	def getHistoryPropertiesById(self, historyID):
		return [i for i in self.getFilteredHistory() if i[0] == historyID]

	def getReleventPositions(self, listened_types):
		history = self.getFilteredHistory()
		return [i for i in history if i[2].strip() in listened_types]

	def updateHistory(self, listened_types):
		history = self.getReleventPositions(listened_types)
		history = [j for j in history if j[1] > self.current_timestamp]
		history = self.sortEvents(history)

		if (len(history) > 0):
			self.current_timestamp = history[-1][1]

		print("HISTORY:", str(history))

		return history

	def updateHistoryByTimestamp(self, listened_types, timestamp):
		history = self.getReleventPositions(listened_types)
		print(str(self.current_timestamp), str(timestamp))
		history = [j for j in history if j[1] > self.current_timestamp and j[1] <= timestamp]
		history = self.sortEvents(history)

		if (len(history) > 0):
			self.current_timestamp = history[-1][1]

		return history

	def getEvent(self, pos, event_type):
		history = self.getFilteredHistory()

		if (type(event_type) == list):
			events = []
			for e in event_type:
				for i in history:
					if (i[2].strip() == e and (pos.orderID == i[0].strip() or pos.orderID == i[8].strip()) and i[1] > self.current_timestamp):
						events.append(i)
						break
			
			if len(events) <= 0:
				return None
			else:
				return self.sortEvents(events)

		else:
			for i in history:
				if (i[2].strip() == event_type and (pos.orderID == i[0].strip() or pos.orderID == i[8].strip()) and i[1] > self.current_timestamp):
					return i

	def sortEvents(self, events):
		type_order = [
				'Close Trade', 'Order Cancelled',
				'Buy Trade', 'Sell Trade',
				'Buy SE Order', 'Sell SE Order',
				'SE Order Sell Trade', 'SE Order Buy Trade', 'Limit Order Buy Trade', 'Limit Order Sell Trade',
				'Buy Trade Modified', 'Sell Trade Modified',
				'Buy SE Order Modified', 'Sell SE Order Modified',
				'Stop Loss Modified', 'Take Profit Modified',
				'Take Profit', 'Stop Loss'
			]
		return sorted(events, key = lambda x : (x[1], type_order.index(x[2])))

	def getLatestHistoryTimestamp(self):
		history = self.getFilteredHistory()
		sorted_history = sorted(history, key=lambda x: x[1], reverse=True)
		if len(history) > 0:
			return sorted_history[0][1]
		else:
			return 0

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

