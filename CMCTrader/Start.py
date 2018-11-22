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
		self.plan_name = json.loads(user_info)['user_program']
		self.username = json.loads(user_info)['account_username']
		self.password = json.loads(user_info)['account_password']
		self.account_name = json.loads(user_info)['account_name']
		self.account_id = json.loads(user_info)['account_id']
		print(self.username, self.password, self.account_name, self.account_id)

		self.initDriver()

		self.isTrading = False
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
		options = webdriver.ChromeOptions()
		options.add_argument('--window-size='+ str(window_size[0]) + ',' + str(window_size[1]))

		self.driver = webdriver.Chrome(self.getChromeDriverPath(), chrome_options=options)
		self.driver.get(CMC_WEBSITE)
		self.driver.implicitly_wait(10)
		
	def initMainProgram(self):
		try:
			self.login()

			self.tickets = {}
			self.threads = []
			
			self.setup()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb, firstInit = True)

	def reinitMainProgram(self):
		self.isTrading = False
		try:
			self.login()
			self.tickets = {}
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

		self.driver.find_element_by_css_selector("input[name='username']").send_keys(str(self.username))

		self.driver.find_element_by_css_selector("input[type='password']").send_keys(str(self.password))

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

		self.plan = None

		try:
			import importlib.util
			spec = importlib.util.spec_from_file_location("CMCTrader.Plan", self.PATH)
			self.plan = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(self.plan)
		except FileNotFoundError as e:
			print(e)
			print("Path not found!")
			input("Press enter to continue...")
			sys.exit()

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

		self.utils = Utilities(self.driver, self.plan, self.plan_name, self.tickets, self.tAUDUSD)

		print("\nTrading plan is LIVE...\n-----------------------\n")
		try:
			self.plan.init(self.utils)
		except AttributeError as e:
			pass

		# self.utils.updateValues()

		self.seconds_elem = self.driver.execute_script(
			'return document.querySelector(\'[class="current-time"]\').querySelector(\'[class="s"]\');'
		)

		self.isDowntime = True
		self.functionCalls()
		
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

		if (not hasattr(self, 'utils')):
			self.utils = Utilities(self.driver, self.plan, self.plan_name, self.tickets, self.tAUDUSD)
		else:
			self.utils.setTickets(self.tickets)
			self.utils.setAUDUSDTicket(self.tAUDUSD)
			self.utils.reinit()

		self.seconds_elem = self.driver.execute_script(
			'return document.querySelector(\'[class="current-time"]\').querySelector(\'[class="s"]\');'
		)


		# task = self.recoverData
		# recoveryThread = threading.Thread(target = task)
		# recoveryThread.start()
		# recoveryThread.join()

		self.recoverData()
		self.functionCalls()

	def recoverData(self):
		try:
			missingTimestamps = self.utils.recoverMissingValues()

			try:
				if (len(missingTimestamps) > 0):
					self.plan.failsafe(missingTimestamps)
			except AttributeError as e:
				pass

		except StaleElementReferenceException as e:
			self.handleLostConnection()
		except Exception as e:
			tb = traceback.format_exc()
			self.handleError(e, tb)

	def functionCalls(self):
		self.isTrading = True
		# self.utils.isStopped = True
		
		self.utils.setTradeTimes()

		while (True):
			if (not self.utils.isStopped):
				try:
					self.checkIfInApp()
					try:
						if (self.utils.isTradeTime() or len(self.utils.positions) > 0):
							for pair in self.plan.VARIABLES['TICKETS']:
								if (self.utils.isCurrentTimestamp(pair)):
									self.plan.onLoop()
					except AttributeError as e:
						pass

					seconds = int(self.seconds_elem.text)
					second_is_zero = False
					if (seconds == 0 and not second_is_zero):
						second_is_zero = True
						
						self.utils.updatePositions()
						isUpdated = self.utils.updateValues()
						
						if (isUpdated):
							missingTimestamps = self.utils.recoverMissingValues()
							if (len(missingTimestamps) > 0):
								try:
									self.plan.failsafe(missingTimestamps)
								except AttributeError as e:
									pass
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
									

					elif (seconds != 0):
						second_is_zero = False

				except StaleElementReferenceException as e:
					print("ERROR: No internet connection!")
					print("Refreshing page...")
					self.handleLostConnection()
					# tb = traceback.format_exc()
					# self.handleError(e, tb)
				except Exception as e:
					tb = traceback.format_exc()
					self.handleError(e, tb)
			else:
				if (self.utils.manualChartReading):
					self.manualChartReading()

	def manualChartReading(self):
		pair = input("Enter pair: ")
		while (pair not in self.tickets.keys()):
			print("Pair not found!")
			pair = input("Enter pair: ")
			
		print("")

		ohlc = pickle.load(open("ohlc1811", "rb"))
		indicators = pickle.load(open("indicators1811", "rb"))

		# startDate = input("Start Date: ")
		# startTime = input("Start Time: ")
		# endDate = input("End Date: ")
		# endTime = input("End Time: ")
		# self.utils.backtestByTime(pair, startDate.strip(), startTime.strip(), endDate.strip(), endTime.strip())

		# ohlc = self.utils.ohlc[pair].copy()
		self.utils.ohlc[pair] = {}
		# indicators = {"overlays" : [], "studies" : []}
		for i in range(len(self.utils.indicators['overlays'])):
			# indicators['overlays'].append(self.utils.indicators['overlays'][i].history[pair].copy()) 
			self.utils.indicators['overlays'][i].history[pair] = {}
		for j in range(len(self.utils.indicators['studies'])):
			# indicators['studies'].append(self.utils.indicators['studies'][j].history[pair].copy())
			self.utils.indicators['studies'][j].history[pair] = {}
		
		# pickle.dump(ohlc, open("ohlc1811", "wb"))
		# pickle.dump(indicators, open("indicators1811", "wb"))
		
		sortedTimestamps = [i[0] for i in sorted(ohlc.items(), key=lambda kv: kv[0], reverse=False)]
		self.insertValuesByTimestamp(pair, sortedTimestamps[0], ohlc, indicators)

		timestamp = sortedTimestamps[i]
		time = self.utils.convertTimestampToTime(timestamp)

		tz = pytz.timezone('Australia/Melbourne')
		time = tz.localize(time)
		tz = pytz.timezone('Europe/London')
		londonTime = time.astimezone(tz)

		self.utils.setTradeTimes(currentTime = londonTime)

		skipTo = 0
		for i in range(1, len(ohlc)):
			timestamp = sortedTimestamps[i]
			time = self.utils.convertTimestampToTime(timestamp)
			print("Bar:", str(time.hour)+":"+str(time.minute)+":"+str(time.second))
			self.insertValuesByTimestamp(pair, timestamp, ohlc, indicators)
			
			tz = pytz.timezone('Australia/Melbourne')
			time = tz.localize(time)
			tz = pytz.timezone('Europe/London')
			londonTime = time.astimezone(tz)

			if (self.utils.isTradeTime(currentTime = londonTime)):
				# try:
				self.plan.backtest()
				# except AttributeError as e:
				# 	pass
			else:
				try:
					self.plan.onDownTime()
				except AttributeError as e:
					pass

			if (skipTo > i):
				continue
			else:
				skipTo = 0

			cmd = input("\nPress enter for next, or enter command: ")
			while not cmd == '':
				if cmd == 'show all':
					print("OHLC:", str(self.utils.ohlc[pair])+"\n")
					self.printIndicators(pair)
				elif cmd == 'show current':
					print("OHLC:", str(list(self.utils.ohlc[pair].values())[0])+"\n")
					self.printCurrent(pair)
				elif cmd == 'ohlc':
					print("OHLC:", str(self.utils.ohlc[pair])+"\n")
				elif cmd == 'indicators':
					self.printIndicators(pair)
				elif cmd.startswith('show indicator'):
					try:
						self.printIndicatorByIndex(int(cmd.split(' ')[2]), pair)
					except:
						print("Could not complete command.")
				elif cmd.startswith('show timestamp'):
					self.getValuesByTime(cmd.split(' ')[2:4], pair)
				elif cmd.startswith('skip'):
					try:
						skipTo = int(cmd.split(' ')[1])
						break
					except:
						print("Could not complete command.")
				else:
					print("Could not recognise command.")

				cmd = input("\nPress enter for next, or enter command: ")
			print("\n")


		print("Done!")
		input("Press enter to exit...")
		sys.exit()

	def insertValuesByTimestamp(self, pair, timestamp, ohlc, indicators):
		self.utils.ohlc[pair][timestamp] = ohlc[timestamp]
		for i in range(len(indicators['overlays'])):
			try:
				self.utils.indicators['overlays'][i].history[pair][timestamp] = indicators['overlays'][i][timestamp]
			except:
				self.utils.indicators['overlays'][i].history[pair][timestamp] = indicators['overlays'][i][timestamp - 60]	
		for j in range(len(indicators['studies'])):
			try:
				self.utils.indicators['studies'][j].history[pair][timestamp] = indicators['studies'][j][timestamp]
			except:
				self.utils.indicators['studies'][j].history[pair][timestamp] = indicators['studies'][j][timestamp - 60]

	def printIndicators(self, pair):
		for overlay in self.utils.indicators['overlays']:
			print(str(overlay.type)+":\n", str(overlay.history[pair])+"\n")
		for study in self.utils.indicators['studies']:
			print(str(study.type)+":\n", str(study.history[pair])+"\n")

	def printCurrent(self, pair):
		for overlay in self.utils.indicators['overlays']:
			print(str(overlay.type)+":\n", str(overlay.getCurrent(pair))+"\n")
		for study in self.utils.indicators['studies']:
			print(str(study.type)+":\n", str(study.getCurrent(pair))+"\n")

	def printIndicatorByIndex(self, index, pair):
		if (index < len(self.utils.indicators['overlays'])):
			indicator = self.utils.indicators['overlays'][index]
			print(str(indicator.type)+":\n", str(indicator.history[pair])+"\n")
			return
		elif (index < len(self.utils.indicators['overlays']) + len(self.utils.indicators['studies'])):
			indicator = self.utils.indicators['studies'][index - len(self.utils.indicators['overlays'])]
			print(str(indicator.type)+":\n", str(indicator.history[pair])+"\n")
			return
		print("Could not find indicator at index", index)

	def getValuesByTime(self, raw, pair):
		try:
			time = raw[0]
			hour = int(time.split(':')[0])
			minute = int(time.split(':')[1])
			date = raw[1]
			day = int(date.split('/')[0])
			month = int(date.split('/')[1])
			timestamp = self.utils.convertTimeToTimestamp(day, month, hour, minute)
		except:
			print("Could not complete command.")
			return
		try:
			print("OHLC:", str(self.utils.ohlc[pair][timestamp])+"\n")
			for overlay in self.utils.indicators['overlays']:
				print(str(overlay.type)+":\n", str(overlay.history[pair][timestamp])+"\n")
			for study in self.utils.indicators['studies']:
				print(str(study.type)+":\n", str(study.history[pair][timestamp])+"\n")
		except:
			print("Could not find saved data at that time.")
			return

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

# class end

# main = Main()