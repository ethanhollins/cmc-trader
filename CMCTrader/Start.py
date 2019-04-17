from os import path
from os import system
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import WebDriverException
import selenium.webdriver.support.ui as ui

import sys
sys.path.insert(0, './Indicators')
import time
import importlib.util
import threading
import datetime
import pytz
import traceback
import pickle
import json
import base64

from CMCTrader.Ticket import Ticket
from CMCTrader.HistoryLog import HistoryLog
from CMCTrader.PositionLog import PositionLog
from CMCTrader.OrderLog import OrderLog
from CMCTrader.Utilities import Utilities
from CMCTrader.Chart import Chart
from CMCTrader import Constants
from CMCTrader import RetrieveTicketElements

CMC_WEBSITE = 'https://platform.cmcmarkets.com/'

DEBUG = True
test = True

class Start(object):

	def __init__(self, PATH, user_info):
		self.initConsole()
		
		print(user_info)

		self.PATH = PATH
		self.user_info = user_info
		self.username = json.loads(user_info)['account_username']
		self.password = json.loads(user_info)['account_password']
		self.account_name = json.loads(user_info)['account_name']
		self.account_id = json.loads(user_info)['account_id']

		self.driver = None
		self.initDriver()

		self.initMainProgram()

	def initConsole(self):
		system('PROMPT $E')
		system('cls')
		
		print(
			"      _    _      _                                  \n" +
			"     | |  | |    | |                                 \n" +
			"     | |  | | ___| | ___ ___  _ __ ___   ___         \n" +
			"     | |/\| |/ _ \ |/ __/ _ \| '_ ` _ \ / _ \        \n" +
			"     \  /\  /  __/ | (_| (_) | | | | | |  __/        \n" +
			"      \/  \/ \___|_|\___\___/|_| |_| |_|\___|        \n" +
			"                                                     \n" +
			"                                                     \n" +
			"                    _____                            \n" +
			"                   |_   _|                           \n" +
			"                     | | ___                         \n" +
			"                     | |/ _ \                        \n" +
			"                     | | (_) |                       \n" +
			"                     \_/\___/                        \n" +
			"                                                     \n" +
			"                                                     \n" +
			" _____ ___  ________   _____             _           \n" +
			"/  __ \|  \/  /  __ \ |_   _|           | |          \n" +
			"| /  \/| .  . | /  \/   | |_ __ __ _  __| | ___ _ __ \n" +
			"| |    | |\/| | |       | | '__/ _` |/ _` |/ _ \ '__|\n" +
			"| \__/\| |  | | \__/\   | | | | (_| | (_| |  __/ |   \n" +
			" \____/\_|  |_/\____/   \_/_|  \__,_|\__,_|\___|_|   \n\n" +
			"-----------------------------------------------------\n")


	def initDriver(self, isHeadless=False, window_size=[1920,1080]):
		if not self.driver == None:
			self.driver.close()

		options = webdriver.ChromeOptions()
		options.add_argument('--window-size='+ str(window_size[0]) + ',' + str(window_size[1]))

		self.driver = webdriver.Chrome(self.getChromeDriverPath(), chrome_options=options)
		self.driver.set_window_position(0, 0)
		self.driver.get(CMC_WEBSITE)
		
	def initMainProgram(self):
		try:
			self.login()

			self.tickets = {}
			self.charts = []
			self.threads = []
			
			self.setup()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb, firstInit = True)

	def reinitMainProgram(self):
		self.utils.isLive = False
		self.utils.driver = self.driver
		try:
			self.login()
			self.tickets = {}
			self.charts = []
			self.reSetup()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb)

	def login(self):
		startTime = time.time()
		while 'login' not in self.driver.current_url:
			if 'error' in self.driver.current_url:
				self.driver.get(CMC_WEBSITE);
				self.login()
				return
			elapsedTime = time.time() - startTime
			if (elapsedTime > 30.0):
				print("Login page took too long to load, refreshing page...")
				self.driver.get(CMC_WEBSITE);
				self.login()
				return
			pass

		self.progressBar(0, 'Logging in')

		elem_username = self.driver.find_element_by_css_selector("input[name='username']")
		elem_password = self.driver.find_element_by_css_selector("input[type='password']")

		elem_username.clear()
		elem_username.send_keys(self.username)
		elem_password.clear()
		elem_password.send_keys(self.password)

		self.driver.find_element_by_css_selector("input[type='submit']").click()

		startTime = time.time()
		while 'login' in self.driver.current_url:
			elapsedTime = time.time() - startTime
			if (elapsedTime > 4.0):
				print("Incorrect username or password, please try again")
				self.login()
				return
			pass

		self.progressBar(25, 'Logging in')
		accountSelected = False
		while 'loader' not in self.driver.current_url:
			if 'accountOptionsSelection' in self.driver.current_url and not accountSelected:
				account_type_btn = self.driver.find_element(By.XPATH, "//button[text() = '"+str(self.account_name)+"']")
				
				try:
					account_type_btn.click()
				except WebDriverException as e:
					pass

				wait = ui.WebDriverWait(self.driver, 10)
				wait.until(EC.presence_of_element_located(
					(By.XPATH, "//div[@id='"+str(self.account_id)+"']")
				))

				wait = ui.WebDriverWait(self.driver, 10)
				wait.until(EC.element_to_be_clickable(
					(By.XPATH, "//div[@id='"+str(self.account_id)+"']")
				))

				self.driver.implicitly_wait(2)

				account_btn = self.driver.find_element(By.XPATH, "//div[@id='"+str(self.account_id)+"']")
				account_btn.click()
				accountSelected = True
			elif 'login' in self.driver.current_url:
				print("Unable to login, trying again.")
				self.login()
				return
			elif 'error' in self.driver.current_url:
				self.driver.get(CMC_WEBSITE);
				self.login()
				return

		self.progressBar(50, 'Logging in')

		while 'app' not in self.driver.current_url:
			if 'login' in self.driver.current_url:
				print("Unable to login, try again.")
				self.login()
				return
			elif 'error' in self.driver.current_url:
				self.driver.get(CMC_WEBSITE);
				self.login()
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

	def setup(self):
		system('cls')

		self.plan = None

		try:
			import importlib.util
			name = self.PATH.split('\\')[len(self.PATH.split('\\'))-1].strip('.py')
			spec = importlib.util.spec_from_file_location(name, self.PATH)
			self.plan = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(self.plan)
		except FileNotFoundError as e:
			print(e)
			print("Path not found!")
			input("Press enter to continue...")
			sys.exit()

		print("Setting up platform...")

		self.utils = Utilities(self.driver, self.plan, self.user_info)

		try:
			self.plan.init(self.utils)
		except AttributeError as e:
			pass

		self.isDowntime = True
		
		# self.utils.getRecovery()

		self.utils.getAllOpenPositions()

		print("\nTrading plan is LIVE...\n-----------------------\n")

		self.functionCalls()
		
	def reSetup(self):
		print("Setting up platform again...")
		print("Setting up tickets again...")

		if (not hasattr(self, 'utils')):
			self.utils = Utilities(self.driver, self.plan, self.user_info)
		else:
			self.utils.reinit(self.driver)

		# self.recoverData()
		self.functionCalls()

	def recoverData(self):
		try:
			for chart in self.utils.charts:
				missingTimestamps = self.utils.barReader.getMissingBarData(chart)

				if (len(missingTimestamps) > 0):
					self.utils.recoverMissingData(chart, missingTimestamps)

		except StaleElementReferenceException as e:
			self.handleLostConnection()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb)

	def functionCalls(self):
		while (True):
			if (not self.utils.isStopped):
				self.utils.isLive = True
				try:
					# self.timedRestart()
					self.checkIfInApp()
					# try:
					if (self.utils.isTradeTime() or len(self.utils.positions) > 0):
						is_current = True
						for chart in self.utils.charts:
							if not chart.getCurrentTimestamp() <= chart.latest_timestamp:
								is_current = False
						if is_current:
							self.plan.onLoop()
					# except AttributeError as e:
					# 	pass

					if (self.needsUpdate()):
						self.utils.reinit(self.driver, get_chart_regions=False)

						self.utils.updatePositions()

						is_updated, missing_timestamps = self.updateBar()
					
						if (is_updated):
							# self.utils.save_state = self.plan.SaveState(self.utils)
							values = {}
							for key in missing_timestamps:
								pair = key.split('-')[0]
								period = int(key.split('-')[1])
								chart = self.utils.getChart(pair, period)

								if len(missing_timestamps[key]) > 1:
									chart_values = self.utils.formatForRecover(chart, missing_timestamps[key])
									values[key] = chart_values

							if len(values) > 0:
								print("recover")
								self.utils.backtester.recover(values)
							else:
								if (self.utils.isTradeTime() or len(self.utils.positions) > 0):
									if (self.isDowntime):
										try:
											self.plan.onStartTrading()
										except AttributeError as e:
											pass
										self.isDowntime = False

									# try:
									self.plan.onNewBar()
									# except AttributeError as e:
									# 	pass
									try:
										for key in self.utils.newsTimes.copy():
											self.plan.onNews(key, self.utils.newsTimes[key])
									except AttributeError as e:
										pass
								else:
									self.utils.setTradeTimes()

									try:
										self.plan.onDownTime()
									except AttributeError as e:
										pass
										
									if (not self.isDowntime):
										try:
											self.plan.onFinishTrading()
										except AttributeError as e:
											pass
										if (len(self.utils.closedPositions) > 0):
											# for pos in closedPositions:
											self.utils.closedPositions = []
										self.isDowntime = True

							
							self.utils.updateRecovery()
						# except Exception as e:
						# 	print(e)
						# 	print("Unable to update bar!")
						# 	pass

				except StaleElementReferenceException as e:
					print("ERROR: Element not found! Potentially lost internet connection!")
					print("Refreshing page...")
					tb = traceback.format_exc()
					self.handleError(e, tb)
					
				except Exception as e:
					tb = traceback.format_exc()
					self.handleError(e, tb)
			else:
				if (self.utils.manualChartReading):
					self.utils.isLive = False
					self.utils.backtester.manual()

	def needsUpdate(self):

		for chart in self.utils.charts:
			if chart.needsUpdate():
				return True

		return False

	def updateBar(self):
		return self.utils.updateValues()

	def timedRestart(self):
		tz = pytz.timezone('Europe/London')
		time = datetime.datetime.now(tz = tz)

		if (time.hour - self.utils.startTime.hour) % 3 == 0:
			if (time.minute == 10):
				print("Scheduled restart commencing...")
				self.restartCMC()

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
		# self.initDriver()
		self.driver.get(CMC_WEBSITE)

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