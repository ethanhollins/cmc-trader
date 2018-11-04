from os import path
from os import system
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import selenium.webdriver.support.ui as ui
from selenium.common.exceptions import StaleElementReferenceException

import sys
sys.path.insert(0, './Indicators')
import time
import importlib.util
import threading
import datetime
import pytz
import traceback

from CMCTrader.Ticket import Ticket
from CMCTrader.Utilities import Utilities
from CMCTrader import Constants
from CMCTrader import RetrieveTicketElements

import base64

class UserInstance(object):

	def __init__(self, NAME):
		self.NAME = NAME

		self.initDriver()

		self.isTrading = False
		self.initMainProgram()

	def initDriver(self, window_size=[1920,1080]):
		options = webdriver.ChromeOptions()
		options.add_argument('window-size='+ str(window_size[0]) + 'x'+ str(window_size[1]))

		self.driver = webdriver.Chrome(self.getChromeDriverPath(), chrome_options=options)
		self.driver.get(CMC_WEBSITE)
		self.driver.implicitly_wait(10)
		
	def initMainProgram(self):
		try:
			self.login('','')

			self.tickets = {}
			self.threads = []
			
			self.setup()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb, firstInit = True)

	def reinitMainProgram(self):
		self.isTrading = False
		try:
			# self.login(self.username, self.password)
			self.login("", "")
			self.tickets = {}
			self.reSetup()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb)

	def login(self, username, password):
		startTime = time.time()
		while 'login' not in self.driver.current_url:
			if 'error' in self.driver.current_url:
				self.driver.get(CMC_WEBSITE);
				self.login(username, password)
				return
			elapsedTime = time.time() - startTime
			if (elapsedTime > 30.0):
				print("Login page took too long to load, refreshing page...")
				self.driver.get(CMC_WEBSITE);
				self.login(username, password)
				return
			pass

		# if (username == '' or password == ''):
		# 	print("\n-----------------------------------------------------\n")
		# 	self.username = input("Enter Email: ")
		# 	self.password = input("\nEnter Password: ")
		# 	print("\n-----------------------------------------------------\n")
		# else:
		# 	self.username = username
		# 	self.password = password

		self.progressBar(0, 'Logging in')

		self.driver.find_element_by_css_selector("input[name='username']").send_keys("lennyh@iprimus.com.au")

		password = 'teddyh00'

		self.driver.find_element_by_css_selector("input[type='password']").send_keys(password.strip())

		self.driver.find_element_by_css_selector("input[type='submit']").click()

		startTime = time.time()
		while 'login' in self.driver.current_url:
			elapsedTime = time.time() - startTime
			if (elapsedTime > 4.0):
				print("Incorrect username or password, please try again")
				self.login('','')
				return
			pass

		self.progressBar(25, 'Logging in')
		accountSelected = False
		while 'loader' not in self.driver.current_url:
			if 'accountOptionsSelection' in self.driver.current_url and not accountSelected:
				account_btn = self.driver.find_element(By.XPATH, "//div[@id='11307219']")
				account_btn.click()
				accountSelected = True
			elif 'login' in self.driver.current_url:
				print("Unable to login, trying again.")
				self.login(username, password)
				return
			elif 'error' in self.driver.current_url:
				self.driver.get(CMC_WEBSITE);
				self.login(username, password)
				return

		self.progressBar(50, 'Logging in')

		while 'app' not in self.driver.current_url:
			if 'login' in self.driver.current_url:
				print("Unable to login, try again.")
				self.login(username, password)
				return
			elif 'error' in self.driver.current_url:
				self.driver.get(CMC_WEBSITE);
				self.login(username, password)
				return
			pass

		self.progressBar(75, 'Logging in')

		time.sleep(3)

		self.progressBar(100, 'Logging in')

		time.sleep(1)

	def progressBar(self, value, msg, barLength=20):
		percent = float(value) / 100
		loadBar = chr(0x2588) * int(round(percent * barLength))
		spaces = ' ' * (barLength - len(loadBar))

		sys.stdout.write("\r"+ msg + "... [{0}]".format(loadBar + spaces))
		sys.stdout.flush()

	def initTicketBtns(self, pair):

		'''

		Initialize and find ticket body

		'''

		print("Initializing", str(pair), "ticket data...")
		ticket_elements = RetrieveTicketElements.retrieveTicketElements(self.driver, pair)
		
		ticket = Ticket(driver=self.driver, pair=pair, ticket_elements=ticket_elements)

		print(str(pair), "initialized!\n")

		return ticket

	def setup(self):
		system('cls')

		print("Setting up platform...")

		# Setup tickets, by default set up GBPUSD ticket
		print("Setting up tickets...\n")

		try:
			for t in self.plan.VARIABLES['TICKETS']:
				self.tickets[t] = self.initTicketBtns(t)
		except:
			print("No tickets found in plan, defaulting to GBPUSD ticket...")
			self.tickets[Constants.GBPUSD] = self.initTicketBtns(Constants.GBPUSD)

		self.tAUDUSD = self.initTicketBtns(Constants.AUDUSD)

		print("\nTrading plan is LIVE...\n-----------------------\n")
		
	def reSetup(self):
		print("Setting up platform again...")
		print("Setting up tickets again...")

		self.tickets = {}
		try:
			for t in self.plan.VARIABLES['TICKETS']:
				self.tickets[t] = self.initTicketBtns(t)
		except:
			print("No tickets found in plan, defaulting to GBPUSD ticket...")
			self.tickets[Constants.GBPUSD] = self.initTicketBtns(Constants.GBPUSD)

		self.tAUDUSD = self.initTicketBtns(Constants.AUDUSD)

		# NEED TO REINIT TICKET VALUES FOR THIS INSTANCE
		# if (not hasattr(self, 'utils')):
		# 	self.utils = Utilities(self.driver, self.plan, self.NAME, self.tickets, self.tAUDUSD)
		# else:
		# 	self.utils.setTickets(self.tickets)
		# 	self.utils.setAUDUSDTicket(self.tAUDUSD)
		# 	self.utils.reinit()

	def handleLostConnection(self):
		while (True):
			self.driver.get(CMC_WEBSITE);
			time.sleep(2)
			if (self.driver.find_element(By.XPATH, '//body').get_attribute("class") == "neterror"):
				pass
			else:
				while not 'login' in self.driver.current_url:
					if ('error' in self.driver.current_url):
						self.handleLostConnection()
					if (self.driver.find_element(By.XPATH, '//body').get_attribute("class") == "neterror"):
						self.handleLostConnection()
					pass
				break

		self.reinitMainProgram()

	def handleError(self, e, tb, firstInit = False):
		print("Error occured:\n")
		print(e)
		with open("errorlog.txt", "a") as errlog:
			errmsg = "Error at " + str(self.getAustralianTime()) + ":\n" + str(tb) + "\n"
			errlog.write(errmsg)
			errlog.close()

		print("Error saved to errorlog...")
		self.restartCMC(firstInit = firstInit)

	def checkIfInApp(self):
		if 'app' not in self.driver.current_url:
			print("CMC timed out...")
			self.restartCMC()

	def restartCMC(self, firstInit = False):
		self.driver.get(CMC_WEBSITE);
		time.sleep(2)
		while 'login' not in self.driver.current_url:
			pass
		print("Logging back in...")
		if (firstInit):
			self.initMainProgram()
		else:
			self.reinitMainProgram()

	def getAustralianTime(self):
		tz = pytz.timezone('Australia/Melbourne')
		return datetime.datetime.now(tz = tz)

	def getChromeDriverPath(self):
		return '\\'.join(path.realpath(__file__).split('\\')[0:-1]) + "\\drivers\\chromedriver.exe"

	def getFilePath(self):
		return '\\'.join(path.realpath(__file__).split('\\')[0:-1])