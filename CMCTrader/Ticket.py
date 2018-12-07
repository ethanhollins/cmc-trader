from selenium import webdriver
import selenium.webdriver.support.ui as ui
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime as dt
import numpy as np
import time
import threading

sleep_function = ('function sleep(ms)' +
				  '{' +
			  	  '  return new Promise(resolve => setTimeout(resolve, ms));' +
				  '}')

async_start_wrapper = ('async function wrapper()' +
					   '{')
async_end_wrapper =  ('}' +
					 'wrapper();')

class Ticket(object):

	def __init__(self, driver, pair, ticket_elements):
		self.driver = driver
		self.pair = pair
		self.ticketElements = ticket_elements

		self.ask_ohlc = np.empty((0, 4), dtype=float)
		self.bid_ohlc = np.empty((0, 4), dtype=float)

	def makeVisible(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr = attr.replace("display: none;", "");'
				'arguments[0].setAttribute("style", attr);',
				self.getTicketElem()
			)
		ActionChains(self.driver).move_to_element(self.getTicketElem()).perform()

	def getAskPrice(self):
		return float(self.driver.execute_script(
				'return arguments[0].innerHTML + arguments[1].innerHTML;',
				self.getPriceBuyElem(), self.getPriceBuyDecElem()
			))

	def getBidPrice(self):
		return float(self.driver.execute_script(
				'return arguments[0].innerHTML + arguments[1].innerHTML;',
				self.getPriceSellElem(), self.getPriceSellDecElem()
			))

	def getSpread(self):
		return float(self.driver.execute_script(
				'return arguments[0].innerHTML;',
				self.getSpreadElem()
			))

	def selectBuy(self):
		self.driver.execute_script(
				'arguments[0].click();',
				self.getBuySelectElem()
			)

	def selectSell(self):
		self.driver.execute_script(
				'arguments[0].click();',
				self.getSellSelectElem()
			)

	def setLotsize(self, lotsize):
		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self.getLotsizeElem(), str(int(lotsize))
			)

	def setStopLoss(self, stopLoss):
		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self.getStopLossPointsElem(), str(float(stopLoss))
			)

	def closeStopLoss(self):
		self.driver.execute_script(
				'arguments[0].click()',
				self.getStopLossCloseElem()
			)

	def setTakeProfit(self, takeProfit):
		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self.getTakeProfitPointsElem(), str(float(takeProfit))
			)

	def closeTakeProfit(self):
		self.driver.execute_script(
				'arguments[0].click()',
				self.getTakeProfitCloseElem()
			)

	def setMarketOrder(self):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.getOrderTypeEntryElem()))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//li[@data-value='MARKET']")))

	def setLimitOrder(self, price):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.getOrderTypeEntryElem()))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//li[@data-value='LIMIT']")))

		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self.getLimitOrderPriceElem(), str(float(price))
			)

	def setStopEntryOrder(self, price):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.getOrderTypeEntryElem()))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//li[@data-value='STOP_ENTRY']")))

		self.driver.execute_script(
				'arguments[0].textContent = arguments[1]',
				self.getStopEntryOrderPriceElem(), str(float(price))
			)

	def setRegularStop(self):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.getOrderTypeStopElem()))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//li[@data-value='Regular']")))

	def setTrailingStop(self):
		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.getOrderTypeStopElem()))

		wait = ui.WebDriverWait(self.driver, 5)
		wait.until(lambda driver : self.attemptBtnPress(self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//li[@data-value='Trailing']")))

	def attemptBtnPress(self, btn):
		try:
			btn.click()
			return True
		except:
			return False

	def placeOrder(self):
		failed = False

		if ("disabled" in self.getActionBtnElem().get_attribute("class")):
			return 0

		self.driver.execute_script(
				'arguments[0].click();',
				self.getActionBtnElem()
			)

		try:
			wait = ui.WebDriverWait(self.driver, 1.5)

			wait.until(lambda driver : self.isSecondButtonVisible())

			text = self.driver.execute_script(
				'return arguments[0].innerHTML;',
				self.getActionBtnElem()
			)

			if (text == "Amend"):
				failed = True

		except:
			pass

		if (not failed):
			try:
				orderID = self.driver.execute_script(
						'var orderID = arguments[1].querySelector(\'div[class="confirmation"]\').querySelector(\'p\').innerHTML;'
						'arguments[0].click();' +
						'return orderID;',
						self.getActionBtnElem(), self.getTicketElem()
					)
			except:
				wait = ui.WebDriverWait(self.driver, 10)
				wait.until(EC.presence_of_element_located(
					(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']")
				))

				actionBtn = self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//button[@class='action-button submit-button']")
				ticketElem = self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']")

				orderID = self.driver.execute_script(
						'var orderID = arguments[1].querySelector(\'div[class="confirmation"]\').querySelector(\'p\').innerHTML;'
						'arguments[0].click();'
						'return orderID;',
						actionBtn, ticketElem
					)

		try:
			wait = ui.WebDriverWait(self.driver, 1)

			wait.until(lambda driver : "disabled" in self.getActionBtnElem().get_attribute("class"))
		except:
			pass

		try:
			wait = ui.WebDriverWait(self.driver, 10)

			wait.until(lambda driver : "disabled" not in self.getActionBtnElem().get_attribute("class"))
		except Exception as e:
			print("ERROR: " + str(e))
			return 0

		if (failed):
			return 0
		else:
			return orderID

	def isSecondButtonVisible():
		text = self.driver.execute_script(
				'return arguments[0].innerHTML;',
				self.getActionBtnElem()
			)
		if (text == "New Order" or text == "Amend"):
			return True
		else:
			return False

	'''

	GETTERS

	'''

	def getPair(self):
		return self.pair

	def getTicketElements(self):
		return self.ticketElements

	def getTicketElem(self):
		return self.ticketElements['TICKET']

	def getTicketID(self):
		return self.ticketElements['TICKET_ID']

	def getOrderTypeEntryElem(self):
		return self.ticketElements['ORDER_TYPE_ENTRY']

	def getMarketOrderElem(self):
		return self.ticketElements['MARKET']

	def getLimitOrderElem(self):
		return self.ticketElements['LIMIT']

	def getLimitOrderPriceElem(self):
		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='limit']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='limit']")
		# return self.driver.execute_script(
		# 		'return arguments[0].querySelector(\'[name="limit"]\');',
		# 		self.getTicketElem()
		# 	)

	def getStopEntryOrderElem(self):
		return self.ticketElements['STOP_ENTRY']

	def getStopEntryOrderPriceElem(self):
		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='stopEntry']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='stopEntry']")
		# return self.driver.execute_script(
		# 		'return arguments[0].querySelector(\'[name="stopEntry"]\');',
		# 		self.getTicketElem()
		# 	)

	def getOrderTypeStopElem(self):
		return self.ticketElements['ORDER_TYPE_STOP']

	def getRegularStopElem(self):
		return self.ticketElements['REGULAR']

	def getTrailingStopElem(self):
		return self.ticketElements['TRAILING']

	def getBuySelectElem(self):
		return self.ticketElements['T_BUY']

	def getSellSelectElem(self):
		return self.ticketElements['T_SELL']

	def getPriceBuyElem(self):
		return self.ticketElements['PRICE_BUY']

	def getPriceBuyDecElem(self):
		return self.ticketElements['PRICE_BUY_DEC']

	def getPriceSellElem(self):
		return self.ticketElements['PRICE_SELL']

	def getPriceSellDecElem(self):
		return self.ticketElements['PRICE_SELL_DEC']

	def getSpreadElem(self):
		return self.ticketElements['SPREAD']

	def getLotsizeElem(self):
		return self.ticketElements['LOTSIZE']

	def getStopLossElem(self):
		return self.ticketElements['STOP_LOSS']

	def getStopLossCloseElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr = attr.replace("display: none;", "");'
				'arguments[0].setAttribute("style", attr);'
				'arguments[1].click();',
				self.getTicketElem(), self.getStopLossElem()
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@class='stopLoss']//a[@class='close']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@class='stopLoss']//a[@class='close']")

	def getStopLossPointsElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr = attr.replace("display: none;", "");'
				'arguments[0].setAttribute("style", attr);'
				'arguments[1].click();',
				self.getTicketElem(), self.getStopLossElem()
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='stopLossPoints']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='stopLossPoints']")

	def getTakeProfitElem(self):
		return self.ticketElements['TAKE_PROFIT']

	def getTakeProfitCloseElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr = attr.replace("display: none;", "");'
				'arguments[0].setAttribute("style", attr);'
				'arguments[1].click();',
				self.getTicketElem(), self.getTakeProfitElem()
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@class='takeProfit']//a[@class='close']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@class='takeProfit']//a[@class='close']")

	def getTakeProfitPointsElem(self):
		elem_id = self.driver.execute_script(
				'var attr = arguments[0].getAttribute("style");'
				'attr = attr.replace("display: none;", "");'
				'arguments[0].setAttribute("style", attr);'
				'arguments[1].click();',
				self.getTicketElem(), self.getTakeProfitElem()
			)

		wait = ui.WebDriverWait(self.driver, 10)

		wait.until(EC.presence_of_element_located(
			(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='takeProfitPoints']")
		))

		return self.driver.find_element(By.XPATH, "//div[@id='"+str(self.getTicketID())+"']//div[@name='takeProfitPoints']")

	def getActionBtnElem(self):
		return self.ticketElements['ACTION_BTN']