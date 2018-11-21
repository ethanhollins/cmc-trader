from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
import selenium.webdriver.support.ui as ui
from PIL import Image
from io import BytesIO
from multiprocessing import Pool, cpu_count
from dateutil.tz import tzlocal
import pytesseract
import base64
import datetime
import numpy as np
import time

CANVAS_BAR_WIDTH = 115

TIMESTAMP_CROP = (204, 36, 303, 63)
VALUE_HEIGHT = 24
OHLC_X_START = 217
OHLC_Y_START = 63
OHLC_Y_OFFSET = 27
OHLC_WIDTH = 86
OVERLAY_X_START = 217
OVERLAY_Y_START = 334
OVERLAY_Y_OFFSET = 54
OVERLAY_WIDTH = 86
STUDIES_Y_START_OFFSET = 57
STUDIES_Y_OFFSET = 57

def performOCR(img):
	return ''.join(str(pytesseract.image_to_string(img)).strip().split(' '))

def modifyNegativeSign(array):
	croppedArray = array[[12, 13, 14],:]
	
	isNegative, xOff = isNegativePresent(croppedArray)

	if (isNegative):
		array[[12, 13, 14],:] = removeNegativeSign(croppedArray, xOff)
		return isNegative, array
	else:
		return isNegative, array

def isNegativePresent(array):
	xOff = 0
	negWidth = 5
	negHeight = 3
	clrBlack = [0,0,0,255]
	clrWhite = [255,255,255,255]
	
	while (True):
		try:
			if (compareLists(array[0, xOff], clrBlack)):
				for x in range(negWidth):
					for y in range(negHeight):
						if (not (compareLists(array[y, xOff + x], clrBlack))):
							return False, xOff
				return True, xOff
			xOff += 1
		except:
			return False, xOff

def removeNegativeSign(array, xOff):
	negWidth = 5
	negHeight = 3
	clrWhite = [255,255,255,255]

	for i in range(xOff-2, xOff + negWidth + 1):
		for j in range(negHeight):
			array[j, i] = clrWhite

	return array

def compareLists(list_a, list_b):
	count = 0
	while (count < len(list_a)):
		if (not (list_a[count] == list_b[count])):
			return False
		count += 1
	return True

class BarReader(object):

	def __init__(self, utils, driver):
		self.driver = driver
		self.utils = utils
		
		self.mins_elem = None
		self.setMins()
		
		self.chartDict = None
		self.setCharts(self.utils.tickets)
		
		self.canvasDict = None
		self.setCanvases(self.chartDict)

		self.chartValues = None
		self.setChartVals(utils.tickets)

	def reinit(self):
		self.setMins()
		self.setCharts(self.utils.tickets)
		self.setCanvases(self.chartDict)
		self.setChartVals(self.utils.tickets)

	def setCharts(self, tickets):
		chartDict = {}

		for key in tickets:
			pair_formatted = key[:3] + "/" + key[3:]
			chart = self.driver.execute_script(
				'var charts = document.querySelectorAll(\'div[class*="feature-product-chart"]\');'
				'for (let i = 0; i < charts.length; i++)'
				'{'
				'  var header = charts[i].querySelector(\'h2[class="feature-header-label single-line-header"]\').innerHTML;'
				'  if (header == arguments[0])'
				'  {'
				'    return charts[i];'
				'  }'
				'}'
				'return null;',
				pair_formatted
			)

			chartDict[key] = chart

		self.chartDict = chartDict

	def setCanvases(self, chartDict):
		canvasDict = {}

		for key in chartDict:
			canvas = self.driver.execute_script(
					'return arguments[0].querySelector(\'canvas[class="chart-canvas"]\');',
					chartDict[key]
				)

			canvasDict[key] = canvas

		self.canvasDict = canvasDict
# 
	def setChartVals(self, tickets):
		chartValues = {}

		for key in tickets:
			pairFinished = False
			chart = self.chartDict[key]
			canvas = self.canvasDict[key]
			while (not pairFinished):
				chartValues[key] = self._iterateChartOfPair(chart, canvas, key)
				xOff = chartValues[key][0] - chartValues[key][1]
				img = self._getImage(chart, canvas, xOff, 300)
				firstTimestamp = self._getBarTimestamp(img)

				xOff = chartValues[key][0] - chartValues[key][1] * 2
				img = self._getImage(chart, canvas, xOff, 300)
				secondTimestamp = self._getBarTimestamp(img)
				if (firstTimestamp == (secondTimestamp + 60)):
					pairFinished = True
				else:
					print("ERROR: Incorrect chart values retrieved.. Retrying " + key + " chart...")

		self.chartValues = chartValues

	def setMins(self):
		self.mins_elem = self.driver.execute_script(
			'return document.querySelector(\'[class="current-time"]\').querySelector(\'[class="m"]\');'
		)

	def _iterateChartOfPair(self, chart, canvas, pair):
		print("Setting up " + pair + " chart...")

		width = int(self.driver.execute_script(
				'return arguments[0].getAttribute("width");',
				canvas
			))

		barsRead = 0

		xOff = width - CANVAS_BAR_WIDTH
		barShowing = False
		timestamp = 0
		prevTimestamp = 0
		barStart = 0
		barSize = 0

		while(True):
			img = self._getImage(chart, canvas, xOff, 300)
			if (not barShowing):
				barShowing = self._isBarShowing(img)

			if (barShowing):
				currTimestamp = self._getBarTimestamp(img)
				if (timestamp == 0):
					timestamp = currTimestamp
					prevTimestamp = currTimestamp
					barStart = xOff
				elif (currTimestamp > prevTimestamp):
					timestamp = currTimestamp
					prevTimestamp = currTimestamp
				elif (not (currTimestamp == prevTimestamp)):
					# if (barSize == 0):
					barEnd = xOff + 1
					barSize = barStart - barEnd
					barMP = barStart - barSize/2
					chartValues = [barMP, barSize]
					break
			xOff -= 1

		return chartValues

	def getCurrentBarInfo(self, pair):
		chart = self.chartDict[pair]
		canvas = self.canvasDict[pair]

		xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

		if (self._isCurrentBar(chart, canvas, xOff)):
			values = self._performBarInfoCapture(chart, canvas, pair, xOff, None)

			self._insertValues(pair, values)
			return True
		else:
			return False

	def getBarInfo(self, pair, shift, amount):
		chart = self.chartDict[pair]
		canvas = self.canvasDict[pair]

		xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

		fillValues = None
		if (self._isCurrentBar(chart, canvas, xOff)):
			prevTimestamp = None

			xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

			for i in range(amount):
				if (xOff < 340):
					print("BarReader: Tested too far back, filling remaining timestamps.")
					fillValues = values
					xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

				if (fillValues == None):
					print(str(prevTimestamp), str(xOff))
					values = self._performBarInfoCapture(chart, canvas, pair, xOff, prevTimestamp, reverse = False)
					self._insertValues(pair, values)

					prevTimestamp = values['timestamp']
					xOff = values['x'] - self.chartValues[pair][1]
				else:
					self._insertValues(pair, fillValues)

			return True
		else:
			return False

		print("done")

	def getBarInfoByTimestamp(self, pair, timestamps):
		chart = self.chartDict[pair]
		canvas = self.canvasDict[pair]

		xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

		if (self._isCurrentBar(chart, canvas, xOff)):
			timestamps.sort(reverse=True)

			fillValues = None
			values = None
			for timestamp in timestamps:
				xOff = self.chartValues[pair][0] - self.chartValues[pair][1] * self._getBarOffset(timestamp)

				if (xOff < 340):
					print("BarReader: Tested too far back, filling remaining timestamps.")
					fillValues = values
					xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

				if (fillValues == None):
					values = self._performBarInfoCapture(chart, canvas, pair, xOff, None, exactTimestamp = timestamp)
					self._insertValues(pair, values)
				else:
					self._insertValues(pair, fillValues)

	def manualBarCollectionByTimestamp(self, pair, startTimestamp, endTimestamp):
		if (startTimestamp > endTimestamp):
			print("ERROR: End time must be greater than start time!")
			return

		chart = self.chartDict[pair]
		canvas = self.canvasDict[pair]

		xOff = self.chartValues[pair][0] - self.chartValues[pair][1]
		time = self.utils.convertTimestampToTime(endTimestamp)
		print("Please move", str(time.hour)+":"+str(time.minute)+":"+str(time.second), "to start of chart!")
		input("Press enter once complete...")
		print("Commencing...")

		while True:
			img = self._getImage(chart, canvas, xOff, 300)
			
			try:
				temp = self._getBarTimestamp(img, date = self.utils.convertTimestampToTime(endTimestamp))
			except:
				time = self.utils.convertTimestampToTime(endTimestamp)
				print("ERROR: Couldn't find", str(time.hour)+":"+str(time.minute)+":"+str(time.second), "please re-adjust chart!")
				input("Press enter once completed...")
				print("Commencing...")
				xOff = self.chartValues[pair][0]
				pass
			if (temp == endTimestamp):
				break

			xOff += self.chartValues[pair][1]

		prevTimestamp = endTimestamp + 60
		isCompleted = False

		while (not (isCompleted)):
			values = self._performBarInfoCapture(chart, canvas, pair, xOff, prevTimestamp)

			self._insertValues(pair, values)

			prevTimestamp = values['timestamp']
			xOff = values['x'] - self.chartValues[pair][1]

			if (xOff < 340):
				time = self.utils.convertTimestampToTime(prevTimestamp)
				print("Please move", str(time.hour)+":"+str(time.minute)+":"+str(time.second), "to start of chart!")
				input("Press enter once completed...")
				print("Commencing...")

				xOff = self.chartValues[pair][0] - self.chartValues[pair][1]
				while True:
					img = self._getImage(chart, canvas, xOff, 300)
					
					try:
						temp = self._getBarTimestamp(img, date = self.utils.convertTimestampToTime(prevTimestamp))
					except:
						time = self.utils.convertTimestampToTime(prevTimestamp)
						print("ERROR: Couldn't find", str(time.hour)+":"+str(time.minute)+":"+str(time.second), "please re-adjust chart!")
						input("Press enter once completed...")
						print("Commencing...")
						xOff = self.chartValues[pair][0]
						pass
					
					if (temp == prevTimestamp):
						break

					xOff += self.chartValues[pair][1]

			isCompleted = prevTimestamp < startTimestamp



	def _insertValues(self, pair, values):
		# try:
		whitelist = set('0123456789.-')

		for i in range(len(values['ohlc'])):
			values['ohlc'][i] = str(values['ohlc'][i])
			values['ohlc'][i] = values['ohlc'][i].replace("D", "0")
			values['ohlc'][i] = ''.join(filter(whitelist.__contains__, values['ohlc'][i]))

			values['ohlc'][i] = float(values['ohlc'][i])

		self.utils.ohlc[pair][values['timestamp']] = values['ohlc']

		count = 0
		for overlay in self.utils.indicators['overlays']:
			overlay.insertValues(pair, values['timestamp'], values['overlays'][count])
			count += 1

		count = 0
		for study in self.utils.indicators['studies']:
			study.insertValues(pair, values['timestamp'], values['studies'][count])
			count += 1
		# except:
		# 	print("Filling data!")
		# 	self._insertValues(pair, self._getFillerData(pair, values))
		# 	return

	def _getFillerData(self, pair, values):
		for i in range(1, len(self.utils.ohlc[pair])):
			newTimestamp = int(values['timestamp']) - 60 * i
			if (newTimestamp) in self.utils.ohlc[pair]:
				values['ohlc'] = self.utils.ohlc[pair][newTimestamp]

				for overlay in self.utils.indicators['overlays']:
					values['overlays'].append(overlay.history[pair][newTimestamp])

				for study in self.utils.indicators['studies']:
					values['studies'].append(study.history[pair][newTimestamp])

				return values
		return None

	def _performBarInfoCapture(self, chart, canvas, pair, xOff, prevTimestamp, exactTimestamp = None, values = None):
		start_time = time.time()

		if (values == None):
			values = {'timestamp':None, 'x': xOff, 'ohlc':[], 'overlays':[], 'studies':[], 'hasLookedFwd' : False, 'hasLookedBack' : False}
		else:
			values['x'] = xOff
			values['ohlc'] = []
			values['overlays'] = []
			values['studies'] = []

		img = self._getImage(chart, canvas, xOff, 300)

		cropped_images = {}

		cropped_image = img.crop(TIMESTAMP_CROP)
		timestamp = performOCR(cropped_image)
		if (prevTimestamp == None):
			values['timestamp'] = self._convertRawTimestamp(timestamp)
		else:
			values['timestamp'] = self._convertRawTimestamp(timestamp, timestampDate = self.utils.convertTimestampToTime(prevTimestamp - 60))

		if (not prevTimestamp == None):
			if (not values['timestamp'] == prevTimestamp - 60):
				
				if (prevTimestamp - 60 > values['timestamp']):

					values['hasLookedBack'] = True

					if (values['hasLookedFwd']):
						values['hasLookedFwd'] = False
						values['hasLookedBack'] = False
						return self._getFillerData(pair, values)

					return self._performBarInfoCapture(chart, canvas, pair, xOff + self.chartValues[pair][1], prevTimestamp, values = values)
				
				else:
					values['hasLookedFwd'] = True

					if (values['hasLookedBack']):
						values['hasLookedFwd'] = False
						values['hasLookedBack'] = False
						return self._getillerData(pair, values)
						

					return self._performBarInfoCapture(chart, canvas, pair, xOff - self.chartValues[pair][1], prevTimestamp, values = values)

		if (not exactTimestamp == None):
			if (not values['timestamp'] == exactTimestamp):

				if (exactTimestamp > values['timestamp']):
					values['hasLookedBack'] = True

					if (values['hasLookedFwd']):
						values['hasLookedFwd'] = False
						values['hasLookedBack'] = False
						return self._getFillerData(pair, values)

					return self._performBarInfoCapture(chart, canvas, pair, xOff + self.chartValues[pair][1], None, exactTimestamp = exactTimestamp, values = values)
				else:
					values['hasLookedFwd'] = True

					if (values['hasLookedBack']):
						values['hasLookedFwd'] = False
						values['hasLookedBack'] = False
						return self._getFillerData(pair, values)

					return self._performBarInfoCapture(chart, canvas, pair, xOff - self.chartValues[pair][1], None, exactTimestamp = exactTimestamp, values = values)

		cropped_images['ohlc'] = []
		for i in range(4):
			img_crop = (OHLC_X_START, OHLC_Y_START + OHLC_Y_OFFSET * i, OHLC_X_START + OHLC_WIDTH, OHLC_Y_START + VALUE_HEIGHT + OHLC_Y_OFFSET * i)
			cropped_images['ohlc'].append(img.crop(img_crop))

		currentY = OVERLAY_Y_START
		for i in self.utils.indicators['overlays']:
			img_crop = i.getValueRegions(currentY)
			cropped_images[str(i.index)] = []
			for j in img_crop:
				cropped_images[str(i.index)].append(img.crop(j))
				currentY = j[1] + OVERLAY_Y_OFFSET

		currentY += STUDIES_Y_START_OFFSET - OVERLAY_Y_OFFSET

		count = len(self.utils.indicators['studies'])

		height = int(self.driver.execute_script(
				'return arguments[0].getAttribute("height");',
				canvas
			))

		studyGraphStartYOff = height
		studyGraphOffset = 61
		negativeImageArray = []
		for i in self.utils.indicators['studies']:
			img = self._getImage(chart, canvas, xOff, studyGraphStartYOff - (studyGraphOffset * count))
			img_crop = i.getValueRegions(currentY)
			cropped_images[str(i.index)] = []
			done = False
			for j in img_crop:
				cropped_img = img.crop(j)
				# cropped_img.show()
				imgArray = np.array(cropped_img)

				if (i.canBeNegative):
					negativeImageArray.append(imgArray)
				else:
					cropped_images[str(i.index)].append(cropped_img)

				currentY = j[1] + STUDIES_Y_OFFSET

			count -= 1

		pool = Pool(processes=cpu_count())

		negativeImageArray = pool.map(modifyNegativeSign, negativeImageArray)

		pool.close()
		pool.join()
		count = 0
		for study in self.utils.indicators['studies']:
			if (study.canBeNegative):
				cropped_images[str(study.index)] = []
				for i in range(study.valueCount):
					cropped_images[str(study.index)].append(Image.fromarray(negativeImageArray[count + i][1]))
				count += study.valueCount

		cropped_images_value_list = []
		for value in cropped_images.values():
			if (type(value) is list):
				for i in value:
					cropped_images_value_list.append(i)
			else:
				cropped_images_value_list.append(value)

		pool = Pool(processes=cpu_count())

		rec_values = pool.map(performOCR, cropped_images_value_list)

		pool.close()
		pool.join()

		values['ohlc'] = rec_values[0:4]

		count = 4
		for overlay in self.utils.indicators['overlays']:
			values['overlays'].append(rec_values[count:count + overlay.valueCount])
			count += overlay.valueCount

		negCount = 0
		for study in self.utils.indicators['studies']:
			for i in range(study.valueCount):
				if (study.canBeNegative):
					if (negativeImageArray[negCount][0]):
						rec_values[count] = ''.join(('-',rec_values[count]))
					negCount += 1
				count += 1
			
			values['studies'].append(rec_values[count - study.valueCount:count])

		elapsed_time = time.time() - start_time
		print("Elaspsed time:", elapsed_time)
		return values

	def _getImage(self, chart, canvas, xOff, yOff):
		self.driver.execute_script(
			'var attr = arguments[0].getAttribute("style");'
			'attr = attr.replace("display: none;", "");'
			'arguments[0].setAttribute("style", attr);',
			chart
		)

		ActionChains(self.driver).move_to_element_with_offset(canvas, xOff, yOff).click().perform()

		canvas_base64 = self.driver.execute_script("return arguments[0].toDataURL('image/png').substring(21);", canvas)
		canvas_png = base64.b64decode(canvas_base64)

		image = Image.open(BytesIO(canvas_png))
		return image

	def _convertImageToBase64(self, image):
		buffered = BytesIO()
		image.save(buffered, format="PNG")
		return base64.b64encode(buffered.getvalue())

	def _convertBase64ToImage(self, string):
		img = base64.b64decode(string)
		return Image.open(BytesIO(img))

	def _scrollChart(self, chart, canvas, xOff, end):
		self.driver.execute_script(
			'var attr = arguments[0].getAttribute("style");'
			'attr = attr.replace("display: none;", "");'
			'arguments[0].setAttribute("style", attr);',
			chart
		)

		yOff = 300

		ActionChains(self.driver).move_to_element_with_offset(canvas, end, yOff).click().perform()
		ActionChains(self.driver).click_and_hold(canvas).perform()
		ActionChains(self.driver).move_to_element_with_offset(canvas, xOff, yOff).click().perform()
		ActionChains(self.driver).release(canvas).perform()

	def _getBarTimestamp(self, img, date = None):
		cropped_img = img.crop(TIMESTAMP_CROP)
		timestamp = str(pytesseract.image_to_string(cropped_img)).strip()
		return self._convertRawTimestamp(timestamp, date)

	def getLatestBarTimestamp(self, pair):
		chart = self.chartDict[pair]
		canvas = self.canvasDict[pair]
		xOff = self.chartValues[pair][0] - self.chartValues[pair][1]

		img = self._getImage(chart, canvas, xOff, 300)
		return self._getBarTimestamp(img)

	def _getCurrentTime(self):
		date = datetime.datetime.now(tzlocal())
		then = datetime.datetime(year = 2018, month = 1, day = 1)
		now = datetime.datetime(year = date.year, month = date.month, day = date.day, hour = date.hour, minute = date.minute, second = 0)

		return int((now - then).total_seconds())

	def _getBarOffset(self, timestamp):
		currentTime = self._getCurrentTime()
		return int((currentTime - timestamp) / 60)

	def _convertRawTimestamp(self, timestamp, timestampDate = None):
		time = timestamp.split(':')

		date = datetime.datetime.now(tzlocal())
		hour = int(time[0].replace("D", "0"))
		minute = int(time[1].replace("D", "0"))
		second = int(time[2].replace("D", "0"))
		
		if (not timestampDate == None):
			date = datetime.datetime(
					year = date.year,
					month = timestampDate.month,
					day = timestampDate.day,
					hour = hour,
					minute = minute,
					second = second
				)
		else:
			if (date.hour - hour < 0):
				diffHour = 24 - hour + date.hour
			else:
				diffHour = date.hour - hour
			date = date - datetime.timedelta(hours = diffHour)

		then = datetime.datetime(year = 2018, month = 1, day = 1)
		now = datetime.datetime(year = date.year, month = date.month, day = date.day, hour = hour, minute = minute, second = second)

		return int((now - then).total_seconds())

	def _isBarShowing(self, img):
		crop_rect = (OVERLAY_X_START, OVERLAY_Y_START, OVERLAY_X_START + OVERLAY_WIDTH, OVERLAY_Y_START + VALUE_HEIGHT)
		cropped_img = img.crop(crop_rect)

		value = ''.join(str(pytesseract.image_to_string(cropped_img)).strip().split(' '))

		try:
			if (value == ''):
				return False
			value = float(value)
		except:
			return False

		return True

	def _isCurrentBar(self, chart, canvas, xOff):
		try:
			wait = ui.WebDriverWait(self.driver, 59, poll_frequency=0.05)
			wait.until(lambda driver : self._checkTimestampIsCurrent(chart, canvas, xOff))
		except:
			return False
			pass

		return True

	def _checkTimestampIsCurrent(self, chart, canvas, xOff):
		mins = int(self.mins_elem.text)

		if (mins == 0):
			mins = 60

		img = self._getImage(chart, canvas, xOff, 300)

		cropped_image = img.crop(TIMESTAMP_CROP)
		timestamp_mins = int(performOCR(cropped_image).split(':')[1])
		return (mins - 1) == timestamp_mins


