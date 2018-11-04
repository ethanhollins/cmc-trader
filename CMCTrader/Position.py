from selenium import webdriver
import selenium.webdriver.support.ui as ui
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

class Position(object):

	def __init__(self, utils, ticket, orderID, pair, ordertype, direction):
		self.utils = utils
		self.ticket = ticket
		self.orderID = orderID
		self.pair = pair
		self.ordertype = ordertype
		self.direction = direction

		self.driver = None
		self.modifyBtn = None
		self.openTime = None
		self.closeTime = None
		self.lotsize = 0
		self.sl = 0
		self.tp = 0
		self.entryprice = 0
		self.closeprice = 0

		self.isPending = False

		self.modifyTicket = None
		self.modifyTicketElements = None

	def stopAndReverse(self, lotsize, sl = 0, tp = 0):
		newPos = None
		if (self.direction == 'buy'):
			newPos = self.utils.sell(int(self.lotsize + lotsize), pairs = [self.pair], sl = sl, tp = tp)
		elif (self.direction == 'sell'):
			newPos = self.utils.buy(int(self.lotsize + lotsize), pairs = [self.pair], sl = sl, tp = tp)

		self.utils.closedPositions.append(self)
		del self.utils.positions[self.utils.positions.index(self)]

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getClosedPosition(self) is not None)

		values = self.utils.historyLog.getClosedPosition(self)

		self.closeprice = values[5]
		self.closeTime = self.utils.getAustralianTime()

		return newPos

	def modifyPositionSize(self, newSize):
		self.ticket.makeVisible()

		if (newSize > self.lotsize and (newSize - self.lotsize) >= 400):
			if (self.direction == 'buy'):
				self.ticket.selectBuy()
			elif (self.direction == 'sell'):
				self.ticket.selectSell()

			self.ticket.setMarketOrder()
			self.ticket.setLotsize(int(newSize - self.lotsize))

			self.ticket.placeOrder()
			self.lotsize = int(newSize - self.lotsize)
		elif (newSize < self.lotsize and (self.lotsize - newSize) >= 400):
			if (self.direction == 'buy'):
				self.ticket.selectSell()
			elif (self.direction == 'sell'):
				self.ticket.selectBuy()

			self.ticket.setMarketOrder()
			self.ticket.setLotsize(int(self.lotsize - newSize))

			self.ticket.placeOrder()
			self.lotsize = int(self.lotsize - newSize)
		else:
			print("ERROR: Unable to change position size, check if size change is greater than 400!")

	def _getModifyTicket(self):
		self.modifyTicket = self.driver.execute_script(
				'arguments[0].click();' +
				'var results = [];' +
				'query = document.evaluate("//div[@class=\'feature feature-next-gen-order-ticket\']", document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);' +
				'for (let i = 0, length=query.snapshotLength; i<length; ++i)' +
				'{' +
				'	results.push(query.snapshotItem(i));' +
				'}' +
				'for (let i = 0; i < results.length; i++)' +
				'{' +
				'  var elem = results[i];' +
				'  try' +
				'  {' +
				'    var title = elem.querySelector(\'[class="feature-header-label single-line-header"]\');' +
				'    console.log(title.innerHTML);' +
				'    if (title.innerHTML.includes(arguments[1]))' +
				'    {' +
				'      return elem;' +
				'    }' +
				'  }' +
				'  catch(err)' +
				'  {' +
				'    console.log(err.message);' +
				'  }' +
				'}' +
				'return null;',
				self.modifyBtn, self.orderID
			)

		return self.modifyTicket

	def _getModifyTicketBtns(self):
		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(lambda driver : self._getModifyTicket() is not None)

		self.modifyTicketElements = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");' +
				'attr.replace("display: none;", "");'+
				'var ticket_elements = {};' +
				'ticket_id = arguments[0].getAttribute("id");' +
				'ticket_elements[\'TICKET_ID\'] = ticket_id;' +
				'elem_stop_loss = arguments[0].querySelector(\'[class="stopLoss"]\').querySelector(\'[class*="add-child-order"]\');' +
				'ticket_elements[\'STOP_LOSS\'] = elem_stop_loss;'
				'elem_take_profit = arguments[0].querySelector(\'[class="takeProfit"]\').querySelector(\'[class*="add-child-order"]\');' +
				'ticket_elements[\'TAKE_PROFIT\'] = elem_take_profit;' +
				'elem_close_position_btn = arguments[0].querySelector(\'[class*="primary-order-side-button"]\');' +
				'ticket_elements[\'CLOSE_POSITION_BTN\'] = elem_close_position_btn;' +
				'elem_submit_btn = arguments[0].querySelector(\'button[class*="submit-button"]\');' +
				'ticket_elements[\'MODIFY_BTN\'] = elem_submit_btn;' +
				'elem_close_btn = arguments[0].querySelector(\'button[class*="close-button"]\');' +
				'ticket_elements[\'CLOSE_BTN\'] = elem_close_btn;'
				'return ticket_elements;',
				self.modifyTicket
			)

	def modifySL(self, stopLoss):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()
		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self._getStopLossPointsElem(), str(float(stopLoss))
			)
		print("Modified stoploss to " + str(stopLoss) + ".")

	def removeSL(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()
		self._getStopLossCloseElem().click()

		print("Removed stoploss.")

	def modifyTP(self, takeProfit):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()
		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self._getTakeProfitPointsElem(), str(float(takeProfit))
			)
		print("Modified take profit to " + str(takeProfit) + ".")

	def removeTP(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()
		self._getTakeProfitCloseElem().click()
		print("Removed take profit.")

	def breakeven(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()

		if (self.direction == 'buy'):
			if (self.ticket.getBidPrice() > self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getStopLossPointsElem(), str(float(0))
				)
			elif (self.ticket.getBidPrice() < self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getTakeProfitPointsElem(), str(float(0))
				)
			else:
				breakeven()
		elif (self.direction == 'sell'):
			if (self.ticket.getAskPrice() < self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getStopLossPointsElem(), str(float(0))
				)
			elif (self.ticket.getAskPrice() > self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getTakeProfitPointsElem(), str(float(0))
				)
			else:
				breakeven()

		print("Set position to breakeven.")

	def breakevenSL(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()

		if (self.direction == 'buy'):
			if (self.ticket.getBidPrice() > self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getStopLossPointsElem(), str(float(0))
				)
		elif (self.direction == 'sell'):
			if (self.ticket.getAskPrice() < self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getStopLossPointsElem(), str(float(0))
				)

		print("Set position breakeven stoploss.")


	def breakevenTP(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()

		if (self.direction == 'buy'):
			if (self.ticket.getBidPrice() < self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getTakeProfitPointsElem(), str(float(0))
				)
		elif (self.direction == 'sell'):
			if (self.ticket.getAskPrice() > self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getTakeProfitPointsElem(), str(float(0))
				)

		print("Set position breakeven take profit.")

	def apply(self):
		if self.modifyTicket is None:
			return True
		else:
			if ("disabled" in self.modifyTicketElements['MODIFY_BTN'].get_attribute("class")):
				print("Failed to apply changes.")
				return False

			self.driver.execute_script(
				'arguments[0].click();',
				self.modifyTicketElements['MODIFY_BTN']
			)

			wait = ui.WebDriverWait(self.driver, 10)

			wait.until(lambda driver : self._findCloseButton())

			text = self.driver.execute_script(
				'return arguments[0].innerHTML;',
				self.modifyTicketElements['MODIFY_BTN']
			)
			if (text == "Amend"):
				self.driver.execute_script(
					'arguments[0].click();',
					self.modifyTicketElements['MODIFY_BTN']
				)
				print("Failed to apply changes.")
				return False

			self.driver.execute_script(
					'arguments[0].click();',
					self.modifyTicketElements['CLOSE_BTN']
				)

			self.modifyTicket = None
			self.modifyTicketElements = None

			print("Position modifications applied")
			return True

	def close(self):
		if (not self.utils.positionExists(self)):
			self.utils.updatePositions()
			return

		if self.modifyTicket is None:
			self._getModifyTicketBtns()
		
		self.driver.execute_script(
			'arguments[0].click();',
			self.modifyTicketElements['CLOSE_POSITION_BTN']
		)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(lambda driver : self._findCloseTradeButton())

		self.driver.execute_script(
				'arguments[0].click();',
				self.modifyTicketElements['MODIFY_BTN']
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(lambda driver : self._findCloseButton())

		self.driver.execute_script(
				'arguments[0].click();',
				self.modifyTicketElements['CLOSE_BTN']
			)			

		self.modifyTicket = None
		self.modifyTicketElements = None

		self.utils.closedPositions.append(self)
		del self.utils.positions[self.utils.positions.index(self)]

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getClosedPosition(self) is not None)

		values = self.utils.historyLog.getClosedPosition(self)

		self.closeprice = values[5]
		self.closeTime = self.utils.getAustralianTime()

		print("Position closed (" + str(self.closeTime) + ") at " + str(self.closeprice))

	def _findCloseTradeButton(self):
		btnTextList = ["Close Sell Trade", "Close Buy Trade", "Cancel Buy Stop Entry Order", "Cancel Sell Stop Entry Order"]
		return self.modifyTicketElements['MODIFY_BTN'].text in btnTextList

	def _findCloseButton(self):
		html = self.driver.execute_script(
				'return arguments[0].innerHTML;',
				self.modifyTicketElements['MODIFY_BTN']
			)
		return "New" in html or "Amend" in html

	def quickExit(self):
		if (self.utils.positionExists(self)):
			if (self.utils.getPositionAmount(self.pair) > 1):
				self.close()
				return
		else:
			self.utils.updatePositions()
			return

		self.ticket.makeVisible()

		if (self.direction == 'buy'):
			self.ticket.selectSell()
		elif (self.direction == 'sell'):
			self.ticket.selectBuy()

		self.ticket.setMarketOrder()
		self.ticket.setLotsize(int(self.lotsize))

		self.ticket.setStopLoss(17)
		self.ticket.closeTakeProfit()

		self.ticket.placeOrder()

		self.utils.closedPositions.append(self)
		del self.utils.positions[self.utils.positions.index(self)]

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getClosedPosition(self) is not None)

		values = self.utils.historyLog.getClosedPosition(self)

		self.closeprice = values[5]
		self.closeTime = self.utils.getAustralianTime()

		print("Position closed (" + str(self.closeTime) + ") at " + str(self.closeprice))

	def getProfit(self):
		if (float(self.closeprice) == 0):
			if (self.direction == 'buy'):
				profit = self.utils.getBid(self.pair) - float(self.entryprice)
				profit = self.utils.convertToPips(profit)
			else:
				profit = float(self.entryprice) - self.utils.getAsk(self.pair)
				profit = self.utils.convertToPips(profit)
		else:
			if (self.direction == 'buy'):
				profit = float(self.closeprice) - float(self.entryprice)
				profit = self.utils.convertToPips(profit)
			else:
				profit = float(self.entryprice) - float(self.closeprice)
				profit = self.utils.convertToPips(profit)

		return round(profit, 1)

	def _getStopLossCloseElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");' +
				'attr.replace("display: none;", "");'+
				'arguments[1].click();',
				self.modifyTicket, self.modifyTicketElements['STOP_LOSS']
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@class='stopLoss']//a[@class='close']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@class='stopLoss']//a[@class='close']")

	def _getStopLossPointsElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");' +
				'attr.replace("display: none;", "");'+
				'arguments[1].click();',
				self.modifyTicket, self.modifyTicketElements['STOP_LOSS']
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@name='stopLossPoints']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@name='stopLossPoints']")

	def _getTakeProfitCloseElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");' +
				'attr.replace("display: none;", "");'+
				'arguments[1].click();',
				self.modifyTicket, self.modifyTicketElements['TAKE_PROFIT']
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@class='takeProfit']//a[@class='close']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@class='takeProfit']//a[@class='close']")

	def _getTakeProfitPointsElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");' +
				'attr.replace("display: none;", "");'+
				'arguments[1].click();',
				self.modifyTicket, self.modifyTicketElements['TAKE_PROFIT']
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@name='takeProfitPoints']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//div[@name='takeProfitPoints']")
