from selenium import webdriver

import datetime

class PositionLog(object):

	def __init__(self, driver):
		self.driver = driver
		self.positionLogBodyElem = self.getPositionLogBodyElem()
		self.parentPositionGroupElems = None
		self.parentElemDict = {}
		self.childPositionDict = {}

	def reinit(self):
		self.positionLogBodyElem = self.getPositionLogBodyElem()
		self.parentPositionGroupElems = None
		self.parentElemDict = {}
		self.childPositionDict = {}

	def getPositionLogBodyElem(self):
		return self.driver.execute_script(
				'return document.querySelector(\'[class*="feature-account-positions"]\');'
			)

	def getPositionLogTableElem(self):
		return self.driver.execute_script(
				'return arguments[0].querySelector(\'[class="new-table"]\').querySelector(\'[class="rows"]\');',
				self.positionLogBodyElem
			)

	def getParentPositionGroupElems(self):
		self.parentPositionGroupElems = self.driver.execute_script(
			'return arguments[0].querySelectorAll(\'[class="row parent position-group clickable"]\');',
			self.getPositionLogTableElem()
		)

		return self.parentPositionGroupElems

	def getParentElemDict(self):
		self.parentElemDict = self.driver.execute_script(
			'var parentPositionAmountDict = {};' +
			'for (let i = 0; i < arguments[0].length; i++)' +
			'{' +
			'  var pair = arguments[0][i].querySelectorAll(\'div\')[1].querySelector(\'span\').innerHTML;' +
			'  pair = pair.split(\'/\').join(\'\');' +
			'  parentPositionAmountDict[pair] = arguments[0][i];' +
			'}' +
			'return parentPositionAmountDict;',
			self.parentPositionGroupElems
		)

		return self.parentElemDict

	def getParentPositionAmount(self, parent):
		return self.driver.execute_script(
			'var amount = arguments[0].querySelectorAll(\'div\')[2].querySelector(\'span\').innerHTML;' +
			'return amount.substring(1, amount.length - 1);',
			parent
		)

	def getPairPositionAmount(self, pair):
		self.getParentPositionGroupElems()
		self.getParentElemDict()

		try:
			return int(self.driver.execute_script(
				'var amount = arguments[0].querySelectorAll(\'div\')[2].querySelector(\'span\').innerHTML;' +
				'return amount.substring(1, amount.length - 1);',
				self.parentElemDict[pair]
			))
		except:
			return 0

	def positionExists(self, position):
		wasHidden = False

		self.getParentPositionGroupElems()
		self.getParentElemDict()

		try:
			for key in self.parentElemDict:
				try:
					amount = self.getParentPositionAmount(self.parentElemDict[key])
				except:
					return False
				if (int(amount) <= 1):
					values = self.driver.execute_script(
							'return [arguments[0].querySelectorAll(\'div\')[3].querySelector(\'span\').innerHTML, arguments[0].querySelectorAll(\'div\')[4].querySelector(\'span\').innerHTML];',
							self.parentElemDict[key]
						)
					if values[0].strip() == 'S':
						direction = 'sell'
					elif values[0].strip() == 'B':
						direction = 'buy'

					lotsize = int(''.join(values[1].split(',')))

					if key == position.pair and direction == position.direction and lotsize == int(position.lotsize):
						return True
					else:
						return False
				else:
					wasHidden = self.driver.execute_script(
							'var isChildrenOpen = true;'
							'var wasHidden = false;'
							'try'
							'{'
							'  var attr = arguments[2][0].getAttribute("style");'
							'  if (attr.includes("display: none;") || arguments[1])'
							'  {'
							'    isChildrenOpen = false;'
							'  }'
							'}'
							'catch'
							'{'
							'  isChildrenOpen = false;'
							'}'
							'if (!isChildrenOpen)'
							'{'
							'  arguments[0].querySelectorAll(\'div\')[2].click();'
							'  wasHidden = true;'
							'}'
							'return wasHidden;',
							self.parentElemDict[key], wasHidden, self.getChildPositionElems()
						)

			return self.driver.execute_script(
					'for (let i = 0; i < arguments[0].length; i++)'
					'{'
					'  var orderID = arguments[0][i].querySelectorAll(\'div\')[1].querySelector(\'span\').innerHTML;'
					'  orderID = orderID.split(\' \')[0];'
					'  if (orderID.localeCompare(arguments[1]) == 0)'
					'  {'
					'    return true;'
					'  }'
					'}'
					'return false;',
					self.getChildPositionElems(), position.orderID
				)
		except:
			return False
		return False

	def getChildPositionElems(self):
		return self.driver.execute_script(
			'return arguments[0].querySelectorAll(\'[class="row child trade clickable"]\');',
			self.getPositionLogTableElem()
		)

	def getPositionModifyButton(self, position):
		modifyBtn = None
		isFound = False
		wasHidden = False

		self.getParentPositionGroupElems()
		self.getParentElemDict()

		for key in self.parentElemDict:
			amount = self.getParentPositionAmount(self.parentElemDict[key])
			if (int(amount) <= 1):
				if key == position.pair:
					modifyBtn = self.parentElemDict[key]
					isFound = True
			else:
				wasHidden = self.driver.execute_script(
						'var isChildrenOpen = true;' +
						'var wasHidden = false;' +
						'try' +
						'{' +
						'  var attr = arguments[2][0].getAttribute("style");' +
						'  if (attr.includes("display: none;") || arguments[1])' +
						'  {' +
						'    isChildrenOpen = false;' +
						'  }'
						'}' +
						'catch' +
						'{' +
						'  isChildrenOpen = false;' +
						'}' +
						'if (!isChildrenOpen)' +
						'{' +
						'  arguments[0].querySelectorAll(\'div\')[2].click();' +
						'  wasHidden = true;' +
						'}' +
						'return wasHidden;',
						self.parentElemDict[key], wasHidden, self.getChildPositionElems()
					)

		if (not isFound):
			modifyBtn = self.driver.execute_script(
					'for (let i = 0; i < arguments[0].length; i++)' +
					'{' +
					'  var orderID = arguments[0][i].querySelectorAll(\'div\')[1].querySelector(\'span\').innerHTML;' +
					'  orderID = orderID.split(\' \')[0];' +
					'  if (orderID.localeCompare(arguments[1]) == 0)' +
					'  {' +
					'    return arguments[0][i].querySelectorAll(\'div\')[1];' +
					'  }'
					'}'
					'return null;',
					self.getChildPositionElems(), position.orderID
				)

		return modifyBtn