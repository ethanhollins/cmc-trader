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

	def setChartRegions(self):

		print("Getting chart regions")

		for chart in self.utils.charts:
			chart.resetZoom()
			img = self._getImage(chart)
			arr = self._getImageArray(img)[:, Constants.READ_X-1:Constants.READ_X]

			last_window = -1
			for i in range(arr.shape[0]):
				new_window = chart.getWindowAt(Constants.READ_X, i)
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
			if chart.needsUpdate():
				if self._isBarCurrent(chart):
					missing_timestamps = self.getMissingBarData(chart)
					missing_timestamps_dict[chart.pair+"-"+str(chart.period)] = missing_timestamps
				else:
					print("Missed timestamp on chart", str(chart.pair), str(chart.period) + "!")
					return False, {}

		return True, missing_timestamps_dict
	
	def getMissingBarData(self, chart):
		chart.resetZoom()

		print("getMissingBarData:")
		latest_timestamp = chart.getCurrentTimestamp(debug=True)
		ohlc_timestamps = chart.getTimestamps()
		current_timestamp = chart.latest_timestamp

		if current_timestamp == 0:
			current_timestamp = latest_timestamp

		missing_timestamps = []

		while (current_timestamp <= latest_timestamp):
			if not current_timestamp in ohlc_timestamps:
				missing_timestamps.append(current_timestamp)

			current_timestamp += chart.timestamp_offset

		if (len(missing_timestamps) > 0):
			self.getBarDataByTimestamp(chart, missing_timestamps)

		if latest_timestamp > chart.latest_timestamp:
			chart.latest_timestamp = latest_timestamp
		
		return missing_timestamps

	@Backtester.skip_on_backtest
	def getMissingBarDataByTimestamp(self, chart, timestamp):
		chart.resetZoom()

		latest_timestamp = chart.getCurrentTimestamp()
		ohlc_timestamps = chart.getTimestamps()
		current_timestamp = timestamp

		missing_timestamps = []

		while (current_timestamp <= latest_timestamp):
			if not current_timestamp in ohlc_timestamps:
				missing_timestamps.append(current_timestamp)

			current_timestamp += chart.timestamp_offset

		if (len(missing_timestamps) > 0):
			self.getBarDataByTimestamp(chart, missing_timestamps)

		if latest_timestamp > chart.latest_timestamp:
			chart.latest_timestamp = latest_timestamp

		return missing_timestamps

	def getBarDataByStartEndTimestamp(self, start, end):
		missing_timestamps = {}
		for chart in self.utils.charts:
			req_timestamps = []
			current_timestamp = start
			while current_timestamp <= end:
				if not current_timestamp % chart.timestamp_offset == 0:
					current_timestamp -= current_timestamp % chart.timestamp_offset

				req_timestamps.append(current_timestamp)
				current_timestamp += chart.timestamp_offset

			self.getBarDataByTimestamp(chart, req_timestamps)
			missing_timestamps[chart.pair+"-"+str(chart.period)] = req_timestamps

		return missing_timestamps

	def getBarDataByTimestamp(self, chart, timestamps):
		chart.reloadData()
		chart.resetZoom()

		for timestamp in sorted(timestamps):
			self.performBarRead(chart, timestamp)

	def performBarRead(self, chart, timestamp):
			
		index = chart.getDataPointsLength()-1 - chart.getRealBarOffset(timestamp)

		if index < 0:
			index = 0
		elif index > chart.getDataPointsLength()-1:
			index = chart.getDataPointsLength()-1

		dp_timestamp = 0

		passed_fwd = False
		passed_back = False
		while not dp_timestamp == timestamp:
			try:
				dp_timestamp = chart.getTimestampFromDataPoint(index)
			except:
				print("ERROR: Index out of range")
				continue

			if passed_fwd and passed_back:
				print("Bar doesn't exist,", str(timestamp))
				break

			if dp_timestamp > timestamp:
				passed_fwd = True
				index -= 1
			elif dp_timestamp < timestamp:
				passed_back = True
				index += 1

		offset = chart.getDataPointsLength() - index

		# chart.panLeft(offset-2)

		bar_index = chart.getCurrentBarIndex()
		data_points = chart.getDataPoints()
		ohlc = [
			data_points[index]['open'], 
			data_points[index]['high'], 
			data_points[index]['low'], 
			data_points[index]['close']
		]

		print(ohlc)

		chart.ohlc[timestamp] = ohlc

		img = None

		if len(chart.overlays) > 0:
			img = self._getOverlayData(chart, img, timestamp, index, data_points, offset)
		
		if len(chart.studies) > 0:
			img = self._getStudyData(chart, img, timestamp, index, data_points, offset)

	def _getOverlayData(self, chart, img, timestamp, bar_index, data_points, offset):

		listened_colours = []
		do_pixel_collection = False

		for overlay in chart.overlays:
			if overlay.collection_type == Constants.PIXEL_COLLECT:
				listened_colours.append(overlay.colour)
				do_pixel_collection = True
			else:
				ohlc = [
					[i['open'] for i in data_points[:bar_index+1]],
					[i['high'] for i in data_points[:bar_index+1]],
					[i['low'] for i in data_points[:bar_index+1]],
					[i['close'] for i in data_points[:bar_index+1]]
				]
				overlay.insertValues(timestamp, ohlc)

				listened_colours.append([-1])

		if do_pixel_collection:
			collection_completed = False
			read_value_x = Constants.READ_X

			while not collection_completed:

				if not img:
					img = self._getImage(chart)

				region = chart.getRegionByIndex(0)
				arr = self._getImageArray(img)[region[1]['start']:int(region[1]['end']), Constants.READ_X:Constants.READ_X+1]

				for i in range(arr.shape[0]):
					colour = arr[i].tolist()[0]

					if colour in listened_colours:

						value = chart.getValueAt(read_value_x, i + region[1]['start'] - 0.5)

						chart.overlays[listened_colours.index(colour)].insertValues(timestamp, value)
						
						listened_colours[listened_colours.index(colour)] = [-1]

					not_done = False
					for colour in listened_colours:
						if not colour == [-1]:
							not_done = True
							
					if not_done:
						continue
					else:
						break

				if not_done:
					print("DID NOT FIND OVERLAY, TRYING AGAIN!")
					read_value_x = Constants.READ_X_2
					chart.resetZoom(zoom=1.05)
					chart.panLeft(offset-2)
					img = self._getImage(chart)
					continue

				collection_completed = True

		return img
	
	def _getStudyData(self, chart, img, timestamp, bar_index, data_points, offset):
		index = 0
		for study in chart.studies:
			
			if study.collection_type == Constants.DATA_POINT_COLLECT:
				ohlc = [
					[i['open'] for i in data_points[:bar_index+1]],
					[i['high'] for i in data_points[:bar_index+1]],
					[i['low'] for i in data_points[:bar_index+1]],
					[i['close'] for i in data_points[:bar_index+1]]
				]

				study.insertValues(timestamp, ohlc)
				
			elif study.collection_type == Constants.PIXEL_COLLECT:
				index += 1
				read_value_x = Constants.READ_X

				while True:

					if not img:
						img = self._getImage(chart)

					region = chart.getRegionByIndex(index)
					arr = self._getImageArray(img)[region[1]['start']:region[1]['end'], Constants.READ_X:Constants.READ_X+1]

					listened_colours = []
					for study in chart.studies:
						listened_colours = study.colours

					values = {}

					for i in range(arr.shape[0]):
						colour = arr[i].tolist()[0]
						if colour in listened_colours:
							value = chart.getValueAt(read_value_x, i + region[1]['start'])
							
							values[listened_colours.index(colour)] = value

							listened_colours[listened_colours.index(colour)] = [-1]

					retry = False
					for colour in listened_colours:
						if not colour == [-1]:
							print("DID NOT FIND STUDY, TRYING AGAIN!")
							read_value_x = Constants.READ_X_2
							chart.resetZoom(1.05)
							chart.panLeft(offset-2)
							img = self._getImage(chart)
							retry = True

					if retry:
						continue

					break

				values = [i[1] for i in sorted(values.items(), key=lambda kv: kv[0])]

				study.insertValues(timestamp, values)

		return img

	def _isBarCurrent(self, chart):
		chart.resetZoom()

		# try:
		wait = ui.WebDriverWait(self.driver, 59, poll_frequency=0.001)
		wait.until(lambda driver : self._isBarDateCurrent(chart))
		# except:
		# 	return False

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
