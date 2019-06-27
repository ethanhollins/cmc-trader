import time
import datetime
import selenium.webdriver.support.ui as ui

from selenium import webdriver
from dateutil.parser import parse

from CMCTrader import Constants

class Chart(object):

	def __init__(self, driver, pair, period):
		self.driver = driver
		self.pair = pair
		self.period = period

		self.id = self.getId()
		self.canvas = self.getCanvas()
		self.parent = self.getParent()
		self.timestamp_offset = self.getTimestampOffset()

		self.zoom = 1.025
		self.latest_timestamp = 0
		self.last_reload = 0		

		self.regions = {}

		self.ohlc = {}
		self.overlays = []
		self.studies = []

	def reinit(self, driver):
		self.driver = driver
		self.id = self.getId()
		self.canvas = self.getCanvas()
		self.parent = self.getParent()

	def getObj(self):
		pair = self.pair[:3] + '/' + self.pair[3:]
		return (
				'var obj = null;'
				'var charts = window.ProChart.charts;'
				'for (var i=0; i < charts.length; i++)'
				'{'
				'    var chart = charts[i];'
				'    var pair = chart.reader.product.abbreviatedName;'
				'    var period = chart.reader.chartSettings.chartModel.chartTopNavConfig.featureWindow.feature.data.s.chi;'
				'    if (pair.localeCompare("'+str(pair)+'") == 0 && period == parseInt("'+str(self.period)+'"))'
				'    {'
				'        obj = chart;'
				'    }'
				'}'
			)

	def getId(self):
		return self.driver.execute_script(
			self.getObj() +
			'return obj.id;'
		)

	def getCanvas(self):
		return self.driver.execute_script(
			'var id = arguments[0];'
			'return document.querySelector("canvas#" + id);',
			self.id
		)

	def getWidth(self):
		return self.driver.execute_script(
			self.getObj() +
			'return obj.getWidth();'
		)

	def getHeight(self):
		return self.driver.execute_script(
			self.getObj() +
			'return obj.getHeight();'
		)

	def getParent(self):
		return self.driver.execute_script(
			'return arguments[0].parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.parentNode.parentNode;',
			self.canvas
			)

	def getTimestampOffset(self):
		if self.period == Constants.ONE_SECOND:
			return 1
		elif self.period == Constants.FIVE_SECONDS:
			return 5
		elif self.period == Constants.TEN_SECONDS:
			return 10
		elif self.period == Constants.THIRTY_SECONDS:
			return 30
		elif self.period == Constants.ONE_MINUTE:
			return 60
		elif self.period == Constants.TWO_MINUTES:
			return 60 * 2
		elif self.period == Constants.THREE_MINUTES:
			return 60 * 3
		elif self.period == Constants.FIVE_MINUTES:
			return 60 * 5
		elif self.period == Constants.TEN_MINUTES:
			return 60 * 10
		elif self.period == Constants.FIFTEEN_MINUTES:
			return 60 * 15
		elif self.period == Constants.THIRTY_MINUTES:
			return 60 * 30
		elif self.period == Constants.ONE_HOUR:
			return 60 * 60
		elif self.period == Constants.TWO_HOURS:
			return 60 * 60 * 2
		elif self.period == Constants.THREE_HOURS:
			return 60 * 60 * 3
		elif self.period == Constants.FOUR_HOURS:
			return 60 * 60 * 4
		elif self.period == Constants.ONE_DAY:
			return 60 * 60 * 24
		elif self.period == Constants.ONE_WEEK:
			return 60 * 60 * 24 * 5 #!
		elif self.period == Constants.ONE_MONTH:
			return 60 * 60 * 24 * 30 #!

	def reset(self):
		self.driver.execute_script(
			self.getObj() +
			'obj.reset();',
		)

	def resetZoom(self, zoom = None):
		if not zoom:
			zoom = self.zoom

		self.driver.execute_script(
			self.getObj() +
			'obj.reset();'
			'obj.zoomIn(arguments[0]);',
			zoom
		)

	def zoomIn(self, amount):
		self.driver.execute_script(
			self.getObj() +
			'obj.zoomIn(arguments[0]);',
			amount
		)

	def zoomOut(self, amount):
		self.driver.execute_script(
			self.getObj() +
			'obj.zoomOut(arguments[0]);',
			amount
		)

	def reloadData(self):
		self.driver.execute_script(
			self.getObj() +
			'obj.reloadData();'
		)

		wait = ui.WebDriverWait(self.driver, 10, poll_frequency=0.001)
		wait.until(lambda driver : self.hasReloadFinished())
		time.sleep(0.15)

	def getOHLCData(self, index):
		return self.driver.execute_script(
				self.getObj() +
				'var data_point = obj.reader.dataPoints[arguments[0]];'
				'return [data_point.open, data_point.high, data_point.low, data_point.close];',
				index
			)

	def getDataPoints(self):
		return self.driver.execute_script(
				self.getObj() +
				'return obj.reader.dataPoints;'
			)

	def getDataPointsLength(self):
		return self.driver.execute_script(
				self.getObj() +
				'return obj.reader.dataPoints.length;'
			)

	def hasReloadFinished(self):
		return not self.driver.execute_script(
			self.getObj() +
			'return obj.isDataRefreshing();'
		)

	def panLeft(self, amount):
		self.driver.execute_script(
			self.getObj() +
			'for (var i=0; i < arguments[0]; i++)'
			'{'
			'    obj.panLeft();'
			'}',
			amount
		)

	def panRight(self, amount):
		self.driver.execute_script(
			self.getObj() +
			'for (var i=0; i < arguments[0]; i++)'
			'{'
			'    obj.panRight();'
			'}',
			amount
		)

	def getTimestamps(self):
		return [i[0] for i in sorted(self.ohlc.items(), key=lambda kv: kv[0], reverse=True)]

	def getWindowAt(self, x, y):
		return self.driver.execute_script(
			self.getObj() +
			'var x = arguments[0];'
			'var y = arguments[1];'
			'return obj.getWindowAt(x, y);',
			x, y
		)

	def getValueAt(self, x, y):
		return float(self.driver.execute_script(
				self.getObj() +
				'var x = arguments[0];'
				'var y = arguments[1];'
				'return String(obj.getValueAt(x, y));',
				x, y
			))

	def getRegionByIndex(self, index):
		return sorted(self.regions.items(), key=lambda kv: kv[1]['index'])[index]

	def getCurrentBarIndex(self):
		return self.driver.execute_script(
			self.getObj() +
			'var x = arguments[0];'
			'var y = arguments[1];'
			'return obj.getBarAt(x, y);',
			self.getWidth() - Constants.READ_X, self.getRegionByIndex(0)[1]['start']
		)

	def getCurrentTimestamp(self, debug=False):
		# date = self.driver.execute_script(
		# 	self.getObj() +
		# 	'var x = arguments[0];'
		# 	'var y = arguments[1];'
		# 	'return String(obj.getDateAt(x, y));',
		# 	self.getWidth() - Constants.READ_X, self.getRegionByIndex(0)[1]['start']
		# )
		# date = ' '.join(date.split(' ')[:5])
		# if debug:
		# 	print(date)
		# dt = self.convertRawDateToDatetime(date)
		# return self.convertDatetimeToTimestamp(dt)
		return self.getTimestampFromDataPoint(self.getDataPointsLength() - 2)

	def getRealBarOffset(self, timestamp):
		current_timestamp = self.getCurrentTimestamp()

		return int((current_timestamp - timestamp) / self.timestamp_offset)

	def getOppositeRealBarOffset(self, timestamp):
		current_timestamp = self.getCurrentTimestamp()

		return int((timestamp - self.getTimestampFromDataPoint(0)) / self.timestamp_offset)

	def getRelativeOffset(self, timestamp):
		if self.latest_timestamp == 0:
			latest_timestamp = self.getCurrentTimestamp()
		else:
			latest_timestamp = self.latest_timestamp

		return int((latest_timestamp - timestamp) / self.timestamp_offset)

	def getRealTimestamp(self, offset):
		current_timestamp = self.getCurrentTimestamp()

		return int(current_timestamp - (offset * self.timestamp_offset))

	def getRelativeTimestamp(self, offset):
		if self.latest_timestamp == 0:
			latest_timestamp = self.getCurrentTimestamp()
		else:
			latest_timestamp = self.latest_timestamp

		return int(latest_timestamp - (offset * self.timestamp_offset))

	def getTimestampFromDataPoint(self, index):
		raw = self.driver.execute_script(
				self.getObj() +
				'var data_point = obj.reader.dataPoints[arguments[0]];'
				'return String(data_point.time);',
				index
			)

		raw = ' '.join(raw.split(' ')[:5])
		dt = self.convertRawDateToDatetime(raw)
		return self.convertDatetimeToTimestamp(dt)

	def getLatestTimestamp(self, index):
		return sorted(self.ohlc.items(), key=lambda kv: kv[0], reverse=True)[index][0]

	def needsUpdate(self):
		current_timestamp = self.getCurrentTimestamp()
		return current_timestamp > self.latest_timestamp

	def needsReload(self, utils):
		current_time = utils.getAustralianTime()
		current_hour = int(utils.hours_elem.text)
		current_min = int(utils.mins_elem.text)
		current_time = datetime.datetime(year = current_time.year, month = current_time.month, day = current_time.day, hour = current_hour, minute = current_min, second = 0)
		current_timestamp = utils.convertDateTimeToTimestamp(current_time)

		if current_timestamp >= self.last_reload + self.timestamp_offset:
			self.last_reload = current_timestamp
			return True
		else:
			return False

	def convertRawDateToDatetime(self, date):
		return parse(date)
	
	def convertDatetimeToTimestamp(self, dt):
		then = Constants.DT_START_DATE
		return int((dt - then).total_seconds())