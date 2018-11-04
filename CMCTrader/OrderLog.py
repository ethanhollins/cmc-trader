from selenium import webdriver

class OrderLog(object):

	def __init__(self, driver):
		self.driver = driver
		self.orderLogBodyElem = self.getOrderLogBodyElem()

	def reinit(self):
		self.orderLogBodyElem = self.getOrderLogBodyElem()

	def getOrderLogBodyElem(self):
		return self.driver.execute_script(
				'return document.querySelector(\'[class*="feature feature-account-main-menu feature-account-orders"]\');'
			)

	def getOrderLogTableElem(self):
		return self.driver.execute_script(
				'return arguments[0].querySelector(\'[class="new-table"]\').querySelector(\'[class="rows"]\');',
				self.orderLogBodyElem
			)

	def getOrderModifyBtn(self, position):
		orderLogTableElem = self.getOrderLogTableElem()
		return self.driver.execute_script(
				'var rows = arguments[0].querySelectorAll(\'[class="row clickable"]\');' +
				'for (let i = 0; i < rows.length; i++)' +
				'{' +
				'  var orderID = rows[i].querySelectorAll(\'div span\')[1].innerHTML;' +
				'  if (orderID.localeCompare(arguments[1]) == 0)' +
				'  {' +
				'    return rows[i].querySelectorAll(\'div\')[1];' +
				'  }' +
				'}' +
				'return null;',
				orderLogTableElem, position.orderID
			)
