from selenium import webdriver
import selenium.webdriver.support.ui as ui
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time
import threading

from CMCTrader.Backtester import Backtester

def stopandreverse_redirect_backtest(func):
	def wrapper(self, lotsize, sl = 0, tp = 0):
		if (not self.utils.backtester.isNotBacktesting()):
			if (self.direction == 'buy'):
				newPos = self.utils.sell(int(self.lotsize + lotsize), pairs = [self.pair], sl = sl, tp = tp)
			elif (self.direction == 'sell'):
				newPos = self.utils.buy(int(self.lotsize + lotsize), pairs = [self.pair], sl = sl, tp = tp)

			self.closeprice = self.utils.getBid(self.pair)
			self.closeTime = self.utils.getAustralianTime()

			self.utils.closedPositions.append(self)
			del self.utils.positions[self.utils.positions.index(self)]
		else:
			return func(self, lotsize, sl, tp)
	return wrapper

def close_redirect_backtest(func):
	def wrapper(*args, **kwargs):
		self = args[0]
		if (not self.utils.backtester.isNotBacktesting()):

			self.closeTime = self.utils.getAustralianTime()

			self.utils.closedPositions.append(self)
			del self.utils.positions[self.utils.positions.index(self)]
		else:
			return func(*args, **kwargs)
	return wrapper

def breakeven_redirect_backtest(func):
	def wrapper(*args, **kwargs):
		self = args[0]
		if (not self.utils.backtester.isNotBacktesting()):

			if (self.direction == 'buy'):
				if (self.utils.getBid(self.pair) > self.entryprice):
					self.sl = self.entryprice
				elif (self.utils.getBid(self.pair) < self.entryprice):
					self.tp = self.entryprice

			elif (self.direction == 'sell'):
				if (self.utils.getAsk(self.pair) < self.entryprice):
					self.sl = self.entryprice
				elif (self.utils.getAsk(self.pair) > self.entryprice):
					self.tp = self.entryprice

		else:
			return func(*args, **kwargs)
	return wrapper

def profit_redirect_backtest(func):
	def wrapper(*args, **kwargs):
		self = args[0]
		if (not self.utils.backtester.isNotBacktesting() and not self.utils.isLive):			
			return 0
		else:
			return func(*args, **kwargs)
	return wrapper

class Position(object):

	def __init__(self, utils, ticket, orderID, pair, ordertype, direction):
		self.utils = utils
		self.ticket = ticket
		self.orderID = orderID
		self.pair = pair
		self.ordertype = ordertype
		self.direction = direction

		self.driver = self.utils.driver
		self.modifyBtn = None
		self.openTime = None
		self.closeTime = None
		
		self.lotsize = 0
		self.sl = 0
		self.tp = 0
		self.entryprice = 0
		self.closeprice = 0

		self.isTrailing = False
		self.isPending = False

		self.modifyTicket = None
		self.modifyTicketElements = None

	@stopandreverse_redirect_backtest
	def stopAndReverse(self, lotsize, sl = 0, tp = 0):
		newPos = None
		if (self.direction == 'buy'):
			newPos = self.utils.sell(int(self.lotsize + lotsize), pairs = [self.pair], sl = sl, tp = tp)
		elif (self.direction == 'sell'):
			newPos = self.utils.buy(int(self.lotsize + lotsize), pairs = [self.pair], sl = sl, tp = tp)

		self.utils.closedPositions.append(self)
		del self.utils.positions[self.utils.positions.index(self)]

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getEvent(self, ['Buy Trade', 'Sell Trade', 'Close Trade']) is not None)
		events = self.utils.historyLog.getEvent(self, ['Buy Trade', 'Sell Trade', 'Close Trade'])	

		for event in events:
			self.utils.updateEvent(event)

		return newPos

	@Backtester.redirect_backtest
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

	def _getModifyBtn(self):

		if (self.isPending):
			wait = ui.WebDriverWait(self.driver, 10)
			wait.until(lambda driver : self.utils.orderLog.getOrderModifyBtn(self) is not None)
			print("found order modify btn")
			self.modifyBtn = self.utils.orderLog.getOrderModifyBtn(self)
		else:
			wait = ui.WebDriverWait(self.driver, 10)
			wait.until(lambda driver : self.utils.positionLog.getPositionModifyButton(self) is not None)
			print("found position modify btn")
			self.modifyBtn = self.utils.positionLog.getPositionModifyButton(self)


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
		self._getModifyBtn()

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self._getModifyTicket() is not None)

		self.modifyTicketElements = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr.replace("display: none;", "");'
				'var ticket_elements = {};'
				'ticket_id = arguments[0].getAttribute("id");'
				'ticket_elements[\'TICKET_ID\'] = ticket_id;'
				'elem_stop_loss = arguments[0].querySelector(\'[class="stopLoss"]\').querySelector(\'[class*="add-child-order"]\');'
				'ticket_elements[\'STOP_LOSS\'] = elem_stop_loss;'
				'console.log(arguments[0].querySelector(\'div[class="stopLoss"]\').querySelector(\'[class="order-type"]\'));'
				'elem_order_type_stop = arguments[0].querySelector(\'div[class="stopLoss"]\').querySelector(\'[class="order-type"]\');'
				'ticket_elements[\'ORDER_TYPE_STOP\'] = elem_order_type_stop;'
				'elem_market = elem_order_type_stop.querySelector(\'[data-value="Regular"]\');'
				'ticket_elements[\'REGULAR\'] = elem_market;'
				'elem_limit = elem_order_type_stop.querySelector(\'[data-value="Trailing"]\');'
				'ticket_elements[\'TRAILING\'] = elem_limit;'
				'elem_take_profit = arguments[0].querySelector(\'[class="takeProfit"]\').querySelector(\'[class*="add-child-order"]\');'
				'ticket_elements[\'TAKE_PROFIT\'] = elem_take_profit;'
				'if (arguments[1])'
				'{'
				'  elem_cancel_order_btn = arguments[0].querySelector(\'a[class="primary-order-side-button"]\');'
				'  ticket_elements[\'CANCEL_ORDER_BTN\'] = elem_cancel_order_btn;'
				'  elem_stop_entry_price = arguments[0].querySelector(\'div[name="stopEntry"]\');'
				'  ticket_elements[\'STOP_ENTRY_PRICE\'] = elem_stop_entry_price;'
				'}'
				'else'
				'{'
				'  elem_close_position_btn = arguments[0].querySelector(\'[class*="primary-order-side-button"]\');'
				'  ticket_elements[\'CLOSE_POSITION_BTN\'] = elem_close_position_btn;'
				'}'
				'elem_submit_btn = arguments[0].querySelector(\'button[class*="submit-button"]\');'
				'ticket_elements[\'MODIFY_BTN\'] = elem_submit_btn;'
				'var elem_close_btn = null;'
				'elem_close_btn = arguments[0].querySelector(\'button[class*="close-button"]\');'
				'ticket_elements[\'CLOSE_BTN\'] = elem_close_btn;'
				'return ticket_elements;',
				self.modifyTicket, self.isPending
			)

	@Backtester.redirect_backtest
	def modifyTrailing(self, stop_loss):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()

		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self._getStopLossPointsElem(), str(float(stop_loss))
			)

		print("Modified trailing stoploss to " + str(stop_loss) + ".")

		self._clickTrailingStop()

	@Backtester.redirect_backtest
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

		self._clickRegularStop()

		print("Modified stoploss to " + str(stopLoss) + ".")

	@Backtester.redirect_backtest
	def removeSL(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()
		self._getStopLossCloseElem().click()

		print("Removed stoploss.")

	@Backtester.redirect_backtest
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

	@Backtester.redirect_backtest
	def removeTP(self):
		if self.modifyTicket is None:
			if (not self.utils.positionExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()
		self._getTakeProfitCloseElem().click()
		print("Removed take profit.")

	@breakeven_redirect_backtest
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

				self._clickRegularStop()

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

				self._clickRegularStop()

			elif (self.ticket.getAskPrice() > self.entryprice):
				self.driver.execute_script(
					'arguments[0].textContent = arguments[1]',
					self._getTakeProfitPointsElem(), str(float(0))
				)
			else:
				breakeven()

		print("Set position to breakeven.")

	@Backtester.redirect_backtest
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

		self._clickRegularStop()

		print("Set position breakeven stoploss.")

	@Backtester.redirect_backtest
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

	@Backtester.bool_redirect_backtest
	def apply(self):
		if self.modifyTicket is None:
			return True
		else:
			if ("disabled" in self.modifyTicketElements['MODIFY_BTN'].get_attribute("class")):
				print("Failed to apply changes.")
				self.utils.updatePositions()
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
				self.utils.updatePositions()
				return False

			self.driver.execute_script(
					'arguments[0].click();',
					self.modifyTicketElements['CLOSE_BTN']
				)

			self.modifyTicket = None
			self.modifyTicketElements = None

			wait = ui.WebDriverWait(self.driver, 10)

			if (self.isPending):
				wait.until(lambda driver : self.utils.historyLog.getEvent(self, ['Buy SE Order Modified', 'Sell SE Order Modified', 'Stop Loss Modified', 'Take Profit Modified']) is not None)
				events = self.utils.historyLog.getEvent(self, ['Buy SE Order Modified', 'Sell SE Order Modified', 'Stop Loss Modified', 'Take Profit Modified'])
			else:
				wait.until(lambda driver : self.utils.historyLog.getEvent(self, ['Buy Trade Modified', 'Sell Trade Modified', 'Stop Loss Modified', 'Take Profit Modified']) is not None)
				events = self.utils.historyLog.getEvent(self, ['Buy Trade Modified', 'Sell Trade Modified', 'Stop Loss Modified', 'Take Profit Modified'])	

			for event in events:
				self.utils.updateEvent(event)

			print("Position modifications applied")
			return True

	@close_redirect_backtest
	def close(self):
		if (self.isPending):
			print("Cannot close an order!")
			return

		if (not self.utils.positionExists(self)):
			print("Position doesn't exist!")
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

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getEvent(self, 'Close Trade') is not None)

		event = self.utils.historyLog.getEvent(self, 'Close Trade')

		self.utils.updateEvent(event)

		print("Position closed (" + str(self.closeTime) + ") at " + str(self.closeprice))

	@Backtester.redirect_backtest
	def modifyEntryPrice(self, price):
		if (not self.isPending):
			print("Cannot modify entry price of a position!")
			return

		if self.modifyTicket is None:
			if (not self.utils.orderLog.orderExists(self)):
				self.utils.updatePositions()
				return
			self._getModifyTicketBtns()

		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self.modifyTicketElements['STOP_ENTRY_PRICE'], str(float(price))
			)

		if (not self.sl == 0):
			sl_points = self.utils.convertToPips(abs(float(self.entryprice) - float(self.sl)))
			sl_points = round(sl_points, 1)
			self.modifySL(sl_points)
		
		if (not self.tp == 0):
			tp_points = self.utils.convertToPips(abs(float(self.entryprice) - float(self.tp)))
			tp_points = round(tp_points, 1)
			self.modifyTP(tp_points)

		print("Modified entry price to " + str(price) + ".")

	def cancel(self):
		if (not self.isPending):
			print("Cannot cancel a position!")
			return

		if (not self.utils.orderLog.orderExists(self)):
			print("Order doesn't exist!")
			self.utils.updatePositions()
			return

		if self.modifyTicket is None:
			self._getModifyTicketBtns()
		
		self.driver.execute_script(
			'arguments[0].click();',
			self.modifyTicketElements['CANCEL_ORDER_BTN']
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

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getEvent(self, 'Order Cancelled') is not None)

		event = self.utils.historyLog.getEvent(self, 'Order Cancelled')
		
		self.utils.updateEvent(event)

		print("Order cancelled at", str(self.closeTime))

	def _findCloseTradeButton(self):
		btnTextList = ["Close Sell Trade", "Close Buy Trade", "Cancel Buy Stop Entry Order", "Cancel Sell Stop Entry Order"]
		return self.modifyTicketElements['MODIFY_BTN'].text in btnTextList

	def _findCloseButton(self):
		html = self.driver.execute_script(
				'return arguments[0].innerHTML;',
				self.modifyTicketElements['MODIFY_BTN']
			)
		return "New" in html or "Amend" in html

	@close_redirect_backtest
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

		wait = ui.WebDriverWait(self.driver, 10)
		wait.until(lambda driver : self.utils.historyLog.getEvent(self, 'Close Trade') is not None)

		event = self.utils.historyLog.getEvent(self, 'Close Trade')

		self.utils.updateEvent(event)

		print("Position closed (" + str(self.closeTime) + ") at " + str(self.closeprice))

	@profit_redirect_backtest
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

	def _clickRegularStop(self):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.modifyTicketElements['ORDER_TYPE_STOP']))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//li[@data-value='Regular']")))

	def _clickTrailingStop(self):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.modifyTicketElements['ORDER_TYPE_STOP']))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnHold(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.modifyTicketElements['TICKET_ID'])+"']//li[@data-value='Trailing']")))

	def attemptBtnPress(self, btn):
		try:
			btn.click()
			return True
		except:
			return False

	def attemptBtnHold(self, btn):
		try:
			ActionChains(self.driver).move_to_element_with_offset(btn, 1, 1)
			ActionChains(self.driver).click_and_hold(btn).perform()
			
			task = self.apply
			t = threading.Thread(target = task)
			t.start()
			t.join()

			return True
		except:
			return False

	def _clickModifyBtn(self):
		self.driver.execute_script(
				'arguments[0].click();',
				self.modifyTicketElements['MODIFY_BTN']
			)

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