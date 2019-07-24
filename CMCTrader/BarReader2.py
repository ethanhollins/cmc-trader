from selenium import webdriver
import selenium.webdriver.support.ui as ui
from PIL import Image
from io import BytesIO
from multiprocessing import Pool, cpu_count
from dateutil.tz import tzlocal
import base64
import datetime
import time
import threading
import traceback
import talib
import numpy as np

from CMCTrader import Constants
from CMCTrader.Backtester import Backtester

class BarReader(object):

	def __init__(self, utils, driver):
		self.driver = driver
		self.utils = utils

	def reinit(self, driver):
		self.driver = driver

	def setChartRegions(self, chart):

		print("Getting chart regions")

		chart.resetZoom()

		read_value_x = chart.getWidth() - Constants.READ_X

		img = self._getImage(chart)
		arr = self._getImageArray(img)[:, read_value_x-1:read_value_x]

		last_window = -1
		for i in range(arr.shape[0]):
			new_window = chart.getWindowAt(read_value_x, i)
			if not new_window == last_window:
				if new_window == -1:
					chart.regions[last_window]["end"] = int(i)
				else:
					chart.regions[new_window] = {"start": int(i), "index": len(chart.regions)}

				last_window = new_window

		print(chart.regions)

	def updateAllBarData(self):
		charts = self.utils.charts

		missing_timestamps_dict = {}
		for chart in charts:
			if self._isBarCurrent(chart):
				chart.reloadData()
				chart.resetZoom()

				missing_timestamps = self.getMissingBarData(chart)
				if len(missing_timestamps) > 0:
					missing_timestamps_dict[chart.pair+"-"+str(chart.period)] = missing_timestamps
				else:
					return False, {}
			else:
				return False, {}

		return True, missing_timestamps_dict
	
	# def getMissingBarData(self, chart):
	# 	chart.resetZoom()

	# 	print("getMissingBarData:")
	# 	latest_timestamp = chart.getCurrentTimestamp(debug=True)
	# 	ohlc_timestamps = chart.getTimestamps()
	# 	current_timestamp = chart.latest_timestamp

	# 	if current_timestamp == 0:
	# 		current_timestamp = chart.getLatestTimestamp(0)

	# 	missing_timestamps = []

	# 	while (current_timestamp <= latest_timestamp):
	# 		dt = self.utils.setTimezone(self.utils.convertTimestampToTime(current_timestamp), 'Australia/Melbourne')
	# 		self.utils.setWeekendTime(dt)
	# 		if not current_timestamp in ohlc_timestamps and not self.utils.isWeekendTime(dt):
	# 			missing_timestamps.append(current_timestamp)

	# 		current_timestamp = self.utils.addTimestampOffset(current_timestamp, chart.timestamp_offset)

	# 	if (len(missing_timestamps) > 0):
	# 		self.getBarDataByTimestamp(chart, missing_timestamps)

	# 	if latest_timestamp > chart.latest_timestamp:
	# 		chart.latest_timestamp = latest_timestamp
		
	# 	self.utils.setWeekendTime(self.utils.getAustralianTime())
	# 	return missing_timestamps

	def getMissingBarData(self, chart):
		chart.resetZoom()

		print("getMissingBarData:")
		current_timestamp = chart.latest_timestamp

		if current_timestamp == 0:
			current_timestamp = chart.getLatestTimestamp(0)

		missing_timestamps = self.getMissingBarDataByTimestamp(chart, current_timestamp)

		if len(missing_timestamps) > 0:
			latest_timestamp = sorted(missing_timestamps, reverse=True)[0]
			if latest_timestamp > chart.latest_timestamp:
				chart.latest_timestamp = latest_timestamp
		
		return missing_timestamps

	# @Backtester.skip_on_backtest
	# def getMissingBarDataByTimestamp(self, chart, timestamp):
	# 	chart.resetZoom()

	# 	latest_timestamp = chart.getCurrentTimestamp(debug=True)
	# 	ohlc_timestamps = chart.getTimestamps()
	# 	current_timestamp = timestamp
	# 	ny_time = self.utils.setTimezone(self.utils.convertTimestampToTime(current_timestamp), 'Australia/Melbourne')
	# 	ny_time = self.utils.convertTimezone(ny_time, 'America/New_York')

	# 	missing_timestamps = []

	# 	comp_timestamp = latest_timestamp
	# 	while current_timestamp < comp_timestamp:
	# 		comp_timestamp -= chart.timestamp_offset

	# 	offset = current_timestamp % comp_timestamp
	# 	current_timestamp -= offset

	# 	while current_timestamp <= latest_timestamp:
	# 		dt = self.utils.setTimezone(self.utils.convertTimestampToTime(current_timestamp), 'Australia/Melbourne')
	# 		self.utils.setWeekendTime(dt)
	# 		if not current_timestamp in ohlc_timestamps and not self.utils.isWeekendTime(dt):
	# 			missing_timestamps.append(current_timestamp)

	# 		current_timestamp, ny_time = self.utils.addTimestampOffset(ny_time, chart.timestamp_offset)

	# 	if (len(missing_timestamps) > 0):
	# 		self.getBarDataByTimestamp(chart, missing_timestamps)

	# 	if latest_timestamp > chart.latest_timestamp:
	# 		chart.latest_timestamp = latest_timestamp

	# 	self.utils.setWeekendTime(self.utils.getAustralianTime())
	# 	return missing_timestamps

	# def getBarDataByStartEndTimestamp(self, start, end):
	# 	missing_timestamps = {}
		
	# 	for chart in self.utils.charts:
	# 		latest_timestamp = chart.getCurrentTimestamp(debug=True)
	# 		req_timestamps = []

	# 		if len(chart.overlays) > 0 or len(chart.studies) >  0:
	# 			current_timestamp = start - 80 * chart.timestamp_offset
	# 		else:
	# 			current_timestamp = start

	# 		comp_timestamp = latest_timestamp
	# 		while current_timestamp < comp_timestamp:
	# 			comp_timestamp -= chart.timestamp_offset

	# 		offset = current_timestamp % comp_timestamp
			
	# 		current_timestamp -= offset

	# 		while current_timestamp <= end:
	# 			req_timestamps.append(current_timestamp)
	# 			current_timestamp += chart.timestamp_offset

	# 		found_timestamps = self.getBarDataByTimestamp(chart, req_timestamps)
	# 		missing_timestamps[chart.pair+"-"+str(chart.period)] = found_timestamps

	# 	return missing_timestamps

	@Backtester.skip_on_backtest
	def getMissingBarDataByTimestamp(self, chart, timestamp):
		print(timestamp)
		for i in range(chart.getDataPointsLength()-2, -1, -1):
			# print(i)
			if chart.getTimestampFromDataPoint(i) == timestamp:
				if i == chart.getDataPointsLength()-2:
					print('already got it')
					return []
				else:
					index = i + 1
					break
			elif chart.getTimestampFromDataPoint(i-1) in chart.ohlc:
				index = i
				break

		return self.getBarDataByIndex(chart, index)

	def getBarDataByIndex(self, chart, index):

		found_timestamps = []
		timestamp = None
		offset = 0

		for i in range(index, chart.getDataPointsLength()-1):
			timestamp, offset = self.performBarRead(chart, i, timestamp, offset)
			found_timestamps.append(timestamp)

		return found_timestamps

	def performBarRead(self, chart, index, prev_timestamp, offset):
		if prev_timestamp:
			temp_ts = chart.getTimestampFromDataPoint(index-1 - offset)
			if temp_ts != prev_timestamp:
				chart.reloadData()
				temp_ts = chart.getTimestampFromDataPoint(index-1 - offset)
				while temp_ts != prev_timestamp:
					if temp_ts > prev_timestamp:
						offset += 1
					else:
						offset -= 1

					temp_ts = chart.getTimestampFromDataPoint(index-1 - offset)

		timestamp = chart.getTimestampFromDataPoint(index - offset)
		data_points = chart.getDataPoints()
		ohlc = [
			data_points[index]['open'], 
			data_points[index]['high'], 
			data_points[index]['low'], 
			data_points[index]['close']
		]

		print("INDEX:", str(index))
		print("time:", str(self.utils.convertTimestampToTime(timestamp)))
		print("ohlc:", str(ohlc))

		chart.ohlc[timestamp] = ohlc

		if len(chart.overlays) > 0:
			self._getOverlayData(chart, timestamp, index, data_points)
		
		if len(chart.studies) > 0:
			self._getStudyData(chart, timestamp, index, data_points)

		return timestamp, offset

	# def performBarRead(self, chart, timestamp):
		
	# 	index = chart.getDataPointsLength()-1 - chart.getRealBarOffset(timestamp)
	# 	if index < 0:
	# 		index = chart.getOppositeRealBarOffset(timestamp)
			
	# 		if index < 0:
	# 			index = 0
	# 		elif index > chart.getDataPointsLength()-1:
	# 			index = chart.getDataPointsLength()-1

	# 	elif index > chart.getDataPointsLength()-1:
	# 		index = chart.getDataPointsLength()-1

	# 	dp_timestamp = 0

	# 	passed_fwd = False
	# 	passed_back = False

	# 	while not dp_timestamp == timestamp:
	# 		try:
	# 			dp_timestamp = chart.getTimestampFromDataPoint(index)
	# 		except:
	# 			if index < 0:
	# 				index = 0
	# 			elif index > chart.getDataPointsLength()-1:
	# 				index = chart.getDataPointsLength()-1

	# 			break

	# 		if passed_fwd and passed_back:
	# 			print("Bar doesn't exist,", str(self.utils.convertTimestampToTime(timestamp)))
	# 			return False

	# 		if dp_timestamp > timestamp:
	# 			passed_fwd = True
	# 			index -= 1
	# 		elif dp_timestamp < timestamp:
	# 			passed_back = True
	# 			index += 1

	# 	offset = chart.getDataPointsLength() - index

	# 	# chart.panLeft(offset-2)

	# 	bar_index = chart.getCurrentBarIndex()
	# 	data_points = chart.getDataPoints()
	# 	ohlc = [
	# 		data_points[index]['open'], 
	# 		data_points[index]['high'], 
	# 		data_points[index]['low'], 
	# 		data_points[index]['close']
	# 	]

	# 	print("INDEX:", str(index))
	# 	print("time:", str(self.utils.convertTimestampToTime(timestamp)))
	# 	print("ohlc:", str(ohlc))

	# 	chart.ohlc[timestamp] = ohlc

	# 	if len(chart.overlays) > 0:
	# 		self._getOverlayData(chart, timestamp, index, data_points, offset)
		
	# 	if len(chart.studies) > 0:
	# 		self._getStudyData(chart, timestamp, index, data_points, offset)

	# 	return True

	def _getOverlayData(self, chart, timestamp, bar_index, data_points):

		for overlay in chart.overlays:
			ohlc = [
				[i['open'] for i in data_points[:bar_index+1]],
				[i['high'] for i in data_points[:bar_index+1]],
				[i['low'] for i in data_points[:bar_index+1]],
				[i['close'] for i in data_points[:bar_index+1]]
			]
			overlay.insertValues(timestamp, ohlc)
	
	def _getStudyData(self, chart, timestamp, bar_index, data_points):
		for study in chart.studies:
			ohlc = [
				[i['open'] for i in data_points[:bar_index+1]],
				[i['high'] for i in data_points[:bar_index+1]],
				[i['low'] for i in data_points[:bar_index+1]],
				[i['close'] for i in data_points[:bar_index+1]]
			]
			study.insertValues(timestamp, ohlc)

	def _isBarCurrent(self, chart):
		chart.resetZoom()

		try:
			wait = ui.WebDriverWait(self.driver, 59, poll_frequency=0.001)
			wait.until(lambda driver : self._isBarDateCurrent(chart))
		except:
			return False

		return True

	def _isBarDateCurrent(self, chart):
		return chart.getCurrentTimestamp() > chart.latest_timestamp

	def _getImage(self, chart):
		self.driver.execute_script(
			'var attr = arguments[0].getAttribute("style");'
			'attr = attr.replace("display: none;", "");'
			'arguments[0].setAttribute("style", attr);',
			chart.parent
		)

		canvas_base64 = self.driver.execute_script("return arguments[0].toDataURL('image/png').substring(21);", chart.canvas)
		canvas_png = base64.b64decode(canvas_base64)

		image = Image.open(BytesIO(canvas_png))
		# image.show()

		return image

	def _getImageArray(self, image):
		return np.array(image)

	def _convertImageToBase64(self, image):
		buffered = BytesIO()
		image.save(buffered, format="PNG")
		return base64.b64encode(buffered.getvalue())

	def _convertBase64ToImage(self, string):
		img = base64.b64decode(string)
		return Image.open(BytesIO(img))
